import pandas as pd
from pathlib import Path
import logging
import os
from collections import OrderedDict
import difflib

_dataframes: dict[str, pd.DataFrame] = OrderedDict()
MAX_CACHED_FILES = 3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def _get_df(file_path: str):
    return _dataframes.get(file_path)

def _add_to_cache(normalized_path: str, df: pd.DataFrame):
    """Add DataFrame to cache with LRU eviction."""
    _dataframes[normalized_path] = df
    if len(_dataframes) > MAX_CACHED_FILES:
        evicted_path, _ = _dataframes.popitem(last=False)
        logger.info(f"Evicted oldest file from cache: {evicted_path}")

def _load_dataframe(file_path: str) -> tuple[pd.DataFrame | None, str | None]:
    """Load CSV with encoding fallback, chunking, and malformed row handling. Returns (DataFrame, error)."""
    from src.config.settings import settings
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    path = Path(normalized_path)
    
    if not path.exists():
        return None, f"File not found: {file_path}"
    if path.suffix.lower() != ".csv":
        return None, f"File must be a CSV, got: {path.suffix}"
    
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > settings.max_csv_size_mb:
        return None, f"File too large ({file_size_mb:.2f}MB). Maximum allowed size is {settings.max_csv_size_mb}MB"
    
    encodings = ['utf-8', 'utf-8-sig', 'latin-1']
    df = None
    last_error = None
    
    for encoding in encodings:
        try:
            read_csv_kwargs = {
                "encoding": encoding,
                "on_bad_lines": "skip"  # Skip malformed rows
            }
            if file_size_mb > 1:
                read_csv_kwargs["chunksize"] = 10000
                chunks = []
                for chunk in pd.read_csv(normalized_path, **read_csv_kwargs):
                    chunks.append(chunk)
                df = pd.concat(chunks, ignore_index=True)
            else:
                df = pd.read_csv(normalized_path, **read_csv_kwargs)
            logger.debug(f"Successfully loaded with encoding: {encoding}")
            break
        except UnicodeDecodeError as e:
            last_error = e
            continue
        except Exception as e:
            last_error = e
            break
    
    if df is None:
        return None, f"Failed to read CSV with any encoding: {str(last_error)}"
    
    if len(df) == 0:
        return None, "CSV file is empty or all rows were malformed and skipped"
    
    return df, None

def _safe_cast(value: any, dtype):
    """Safely cast value to target dtype, handling NaN and None."""
    import pandas as pd
    # Handle missing/NaN values
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if value == "":
        return None
    try:
        dtype_str = str(dtype)
        if "int" in dtype_str:
            return int(value)
        elif "float" in dtype_str:
            return float(value)
        elif "bool" in dtype_str:
            # Convert string to boolean
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.lower()
                if lowered in ("true", "1", "yes", "y", "t"):
                    return True
                elif lowered in ("false", "0", "no", "n", "f"):
                    return False
            return bool(value)
        else:
            return str(value) if value is not None else None
    except (ValueError, TypeError):
        return value  # Return original on conversion failure

def _ensure_loaded(file_path: str):
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    if normalized_path in _dataframes:
        # Move to end to mark as recently used (LRU)
        _dataframes.move_to_end(normalized_path)
        logger.debug(f"File already loaded, moved to LRU end: {normalized_path}")
        return
    
    df, error = _load_dataframe(file_path)
    if df is not None:
        _add_to_cache(normalized_path, df)
    else:
        logger.debug(f"Failed to load file: {error}")

def load_csv(file_path: str) -> dict:
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    if df is None:
        return {"error": f"Failed to load file: {file_path}"}
    
    path = Path(normalized_path)
    return {
        "success": True,
        "file": path.name,
        "rows": len(df),
        "columns": list(df.columns),
        "preview": df.head(3).to_dict(orient="records"),
    }

def get_schema(file_path: str) -> dict:
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    if df is None:
        return {"error": f"File not found: {file_path}"}
    return {
        "file": Path(normalized_path).name,
        "columns": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "row_count": len(df),
    }

def filter_rows(file_path: str, column: str, operator: str, value: str) -> dict:
    """Filter rows with robust error handling and NaN support."""
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    if df is None:
        return {"error": f"File not found: {file_path}. Use /load to load a CSV file first."}
    if column not in df.columns:
        # Suggest similar column names
        suggestions = difflib.get_close_matches(column, df.columns, n=3, cutoff=0.6)
        suggestion_text = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        return {"error": f"Column '{column}' not found.{suggestion_text} Available columns: {', '.join(df.columns)}"}
    if operator not in {"=", "!=", ">", "<", ">=", "<=", "contains", "startswith"}:
        return {"error": f"Unknown operator '{operator}'. Supported: =, !=, >, <, >=, <=, contains, startswith"}
    
    try:
        col = df[column]
        col_dtype = col.dtype
        cast_value = _safe_cast(value, col_dtype)
        
        # Handle None/missing cast values
        if cast_value is None:
            if operator == "=":
                result = df[col.isna()]
            elif operator == "!=":
                result = df[col.notna()]
            else:
                return {"error": f"Cannot use operator '{operator}' with empty/missing values. Try /sample to see data format."}
        else:
            if operator == "=":
                # Case-insensitive for text fields
                if isinstance(cast_value, str):
                    result = df[col.astype(str).str.lower() == cast_value.lower()]
                else:
                    result = df[col == cast_value]
            elif operator == "!=":
                # Case-insensitive for text fields
                if isinstance(cast_value, str):
                    result = df[col.astype(str).str.lower() != cast_value.lower()]
                else:
                    result = df[col != cast_value]
            elif operator == ">":
                result = df[col > cast_value]
            elif operator == "<":
                result = df[col < cast_value]
            elif operator == ">=":
                result = df[col >= cast_value]
            elif operator == "<=":
                result = df[col <= cast_value]
            elif operator == "contains":
                result = df[col.fillna('').astype(str).str.contains(str(cast_value), case=False, na=False)]
            elif operator == "startswith":
                result = df[col.fillna('').astype(str).str.startswith(str(cast_value), case=False, na=False)]
        
        return {
            "rows_found": len(result),
            "total_rows": len(result),
            "data": result.head(20).to_dict(orient="records"),
            "note": f"Showing first 20 of {len(result)} rows. Use /next to see more." if len(result) > 20 else None,
            **({"message": "No matching rows found."} if len(result) == 0 else {}),
        }
    except TypeError as e:
        return {"error": f"Type error during filter: {str(e)}. Check column data type with /schema or try a different operator."}
    except Exception as e:
        return {"error": f"Filter operation failed: {str(e)}"}

def aggregate(file_path: str, column: str, operation: str) -> dict:
    """Aggregate column with robust handling of missing/invalid data."""
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    if df is None:
        return {"error": f"File not found: {file_path}. Use /load to load a CSV file first."}
    if column not in df.columns:
        # Suggest similar column names
        suggestions = difflib.get_close_matches(column, df.columns, n=3, cutoff=0.6)
        suggestion_text = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        return {"error": f"Column '{column}' not found.{suggestion_text} Available columns: {', '.join(df.columns)}"}
    if operation not in {"sum", "mean", "min", "max", "count", "median"}:
        return {"error": f"Unknown operation '{operation}'. Supported: sum, mean, min, max, count, median"}
    
    try:
        col = df[column]
        # Compute only the requested operation to avoid unnecessary errors
        if operation == "sum":
            result = col.sum(skipna=True)
        elif operation == "mean":
            result = col.mean(skipna=True)
        elif operation == "min":
            result = col.min(skipna=True)
        elif operation == "max":
            result = col.max(skipna=True)
        elif operation == "count":
            result = col.count()
        elif operation == "median":
            result = col.median(skipna=True)
        else:
            return {"error": f"Unknown operation '{operation}'. Supported: sum, mean, min, max, count, median"}
        
        if hasattr(result, "item"):
            result = result.item()
        elif hasattr(result, "tolist"):
            result = result.tolist()
        
        return {
            "file": Path(normalized_path).name,
            "column": column,
            "operation": operation,
            "result": result,
        }
    except TypeError as e:
        return {"error": f"Type error during aggregation: {str(e)}. Column '{column}' may contain non-numeric data. Use /sample to inspect values."}
    except Exception as e:
        return {"error": f"Aggregation failed: {str(e)}"}


def get_column_stats(file_path: str, column: str) -> dict:
    """Get detailed statistics for a column including unique count, min/max for text, etc."""
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    
    if df is None:
        return {"error": f"File not loaded: {file_path}. Use /load to load a CSV file first."}
    
    if column not in df.columns:
        suggestions = difflib.get_close_matches(column, df.columns, n=3, cutoff=0.6)
        suggestion_text = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        return {"error": f"Column '{column}' not found.{suggestion_text} Available columns: {', '.join(df.columns)}"}
    
    col = df[column]
    dtype = str(col.dtype)
    
    stats = {
        "column": column,
        "dtype": dtype,
        "total_rows": len(col),
        "null_count": int(col.isna().sum()),
        "unique_count": int(col.nunique()),
    }
    
    if dtype in ['int64', 'float64']:
        stats.update({
            "min": float(col.min()) if not pd.isna(col.min()) else None,
            "max": float(col.max()) if not pd.isna(col.max()) else None,
            "mean": float(col.mean()) if not pd.isna(col.mean()) else None,
            "median": float(col.median()) if not pd.isna(col.median()) else None,
            "std": float(col.std()) if not pd.isna(col.std()) else None,
        })
    else:
        stats["sample_values"] = list(col.dropna().unique()[:10])
    
    return stats


def export_filtered_data(file_path: str, output_path: str, column: str = None, operator: str = None, value: str = None) -> dict:
    """Export filtered data to a new CSV file."""
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    
    if df is None:
        return {"error": f"File not loaded: {file_path}"}
    
    try:
        if column and operator and value:
            filtered_df = _apply_filter(df, column, operator, value)
        else:
            filtered_df = df
        
        filtered_df.to_csv(output_path, index=False)
        return {
            "success": True,
            "rows_exported": len(filtered_df),
            "output_file": output_path,
        }
    except Exception as e:
        return {"error": f"Export failed: {str(e)}"}


def _apply_filter(df: pd.DataFrame, column: str, operator: str, value: str) -> pd.DataFrame:
    """Helper to apply filter to dataframe."""
    from src.tools.csv_tool import _safe_cast
    col = df[column]
    col_dtype = col.dtype
    cast_value = _safe_cast(value, col_dtype)
    
    if cast_value is None:
        if operator == "=":
            return df[col.isna()]
        elif operator == "!=":
            return df[col.notna()]
    else:
        if operator == "=":
            if isinstance(cast_value, str):
                return df[col.astype(str).str.lower() == cast_value.lower()]
            return df[col == cast_value]
        elif operator == "!=":
            if isinstance(cast_value, str):
                return df[col.astype(str).str.lower() != cast_value.lower()]
            return df[col != cast_value]
        elif operator == ">":
            return df[col > cast_value]
        elif operator == "<":
            return df[col < cast_value]
        elif operator == ">=":
            return df[col >= cast_value]
        elif operator == "<=":
            return df[col <= cast_value]
        elif operator == "contains":
            return df[col.fillna('').astype(str).str.contains(str(cast_value), case=False, na=False)]
    return df

def get_sample(file_path: str, n: int = 5) -> dict:
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    if df is None:
        return {"error": f"File not found: {file_path}"}
    return {
        "file": Path(normalized_path).name,
        "rows_shown": min(n, len(df)),
        "total_rows": len(df),
        "data": df.head(n).to_dict(orient="records"),
    }

def list_loaded_files() -> dict:
    if not _dataframes:
        return {"loaded_files": [], "message": "No files loaded yet."}
    return {
        "loaded_files": [
            {"path": path, "rows": len(df), "columns": list(df.columns)}
            for path, df in _dataframes.items()
        ]
    }


def get_data_quality(file_path: str) -> dict:
    """Analyze CSV data quality and return a report."""
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    
    if df is None:
        return {"error": f"File not loaded: {file_path}"}
    
    report = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "null_counts": {},
        "duplicate_rows": 0,
        "column_types": {},
        "issues": [],
    }
    
    for col in df.columns:
        null_count = df[col].isna().sum()
        if null_count > 0:
            report["null_counts"][col] = int(null_count)
            if null_count > len(df) * 0.5:
                report["issues"].append(f"Column '{col}' has {null_count} null values ({null_count/len(df)*100:.1f}%)")
        
        report["column_types"][col] = str(df[col].dtype)
    
    duplicate_rows = df.duplicated().sum()
    report["duplicate_rows"] = int(duplicate_rows)
    if duplicate_rows > 0:
        report["issues"].append(f"Found {duplicate_rows} duplicate rows")
    
    return report


def join_csvs(file_path1: str, file_path2: str, join_column: str, join_type: str = "inner") -> dict:
    """Join two CSV files on a common column."""
    normalized_path1 = os.path.abspath(os.path.realpath(file_path1))
    normalized_path2 = os.path.abspath(os.path.realpath(file_path2))
    
    _ensure_loaded(normalized_path1)
    _ensure_loaded(normalized_path2)
    
    df1 = _get_df(normalized_path1)
    df2 = _get_df(normalized_path2)
    
    if df1 is None:
        return {"error": f"First file not loaded: {file_path1}"}
    if df2 is None:
        return {"error": f"Second file not loaded: {file_path2}"}
    
    if join_column not in df1.columns:
        return {"error": f"Column '{join_column}' not found in first file. Available: {', '.join(df1.columns)}"}
    if join_column not in df2.columns:
        return {"error": f"Column '{join_column}' not found in second file. Available: {', '.join(df2.columns)}"}
    
    if join_type not in {"inner", "left", "right"}:
        return {"error": f"Invalid join_type '{join_type}'. Use: inner, left, or right"}
    
    try:
        how_map = {"inner": "inner", "left": "left", "right": "right"}
        result = pd.merge(df1, df2, on=join_column, how=how_map[join_type])
        
        return {
            "success": True,
            "rows": len(result),
            "columns": list(result.columns),
            "preview": result.head(10).to_dict(orient="records"),
        }
    except Exception as e:
        return {"error": f"Join failed: {str(e)}"}


def get_chart_data(file_path: str, label_column: str, value_column: str) -> dict:
    """
    Get aggregated data for charting. Groups by label_column and sums value_column.
    Returns list of dicts with label and value keys.
    """
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    
    if df is None:
        return {"error": f"File not loaded: {file_path}. Use /load to load a CSV file first."}
    
    if label_column not in df.columns:
        suggestions = difflib.get_close_matches(label_column, df.columns, n=3, cutoff=0.6)
        suggestion_text = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        return {"error": f"Column '{label_column}' not found.{suggestion_text} Available columns: {', '.join(df.columns)}"}
    
    if value_column not in df.columns:
        suggestions = difflib.get_close_matches(value_column, df.columns, n=3, cutoff=0.6)
        suggestion_text = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        return {"error": f"Column '{value_column}' not found.{suggestion_text} Available columns: {', '.join(df.columns)}"}
    
    try:
        grouped = df.groupby(label_column)[value_column].sum().reset_index()
        data = [
            {"label": row[label_column], "value": row[value_column]}
            for _, row in grouped.iterrows()
        ]
        data.sort(key=lambda x: x["value"], reverse=True)
        
        return {
            "success": True,
            "data": data,
            "label_column": label_column,
            "value_column": value_column,
        }
    except Exception as e:
        return {"error": f"Chart data preparation failed: {str(e)}"}


def get_correlation_matrix(file_path: str) -> dict:
    """Get correlation matrix for all numeric columns."""
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    
    if df is None:
        return {"error": f"File not loaded: {file_path}"}
    
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    if len(numeric_cols) < 2:
        return {"error": "Need at least 2 numeric columns for correlation. Found: " + ", ".join(numeric_cols)}
    
    corr_matrix = df[numeric_cols].corr()
    return {
        "success": True,
        "columns": numeric_cols,
        "correlation": corr_matrix.to_dict(),
    }


def detect_outliers(file_path: str, column: str) -> dict:
    """Detect outliers using IQR method."""
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    
    if df is None:
        return {"error": f"File not loaded: {file_path}"}
    
    if column not in df.columns:
        return {"error": f"Column '{column}' not found. Available: {', '.join(df.columns)}"}
    
    col = df[column]
    if col.dtype not in ['int64', 'float64']:
        return {"error": f"Column '{column}' is not numeric. Cannot detect outliers."}
    
    Q1 = col.quantile(0.25)
    Q3 = col.quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    
    outliers = df[(col < lower) | (col > upper)]
    
    return {
        "column": column,
        "method": "IQR",
        "Q1": float(Q1),
        "Q3": float(Q3),
        "IQR": float(IQR),
        "lower_bound": float(lower),
        "upper_bound": float(upper),
        "outlier_count": len(outliers),
        "outliers": outliers.head(10).to_dict(orient="records"),
    }


def get_distribution(file_path: str, column: str, bins: int = 10) -> dict:
    """Get value distribution for a column."""
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    
    if df is None:
        return {"error": f"File not loaded: {file_path}"}
    
    if column not in df.columns:
        return {"error": f"Column '{column}' not found."}
    
    col = df[column]
    dtype = str(col.dtype)
    
    if dtype in ['int64', 'float64']:
        hist, bin_edges = pd.cut(col.dropna(), bins=bins, retbins=True)
        counts = hist.value_counts().sort_index()
        return {
            "column": column,
            "type": "numeric",
            "bins": bins,
            "distribution": [{"range": f"{edge:.0f}-{bin_edges[i+1]:.0f}", "count": int(count)} 
                           for i, (edge, count) in enumerate(counts.items())],
        }
    else:
        value_counts = col.value_counts().head(20)
        return {
            "column": column,
            "type": "categorical",
            "distribution": [{"value": str(v), "count": int(c)} for v, c in value_counts.items()],
        }


def run_sql_query(file_path: str, query: str) -> dict:
    """
    Run a SQL-like query on a CSV file using pandas.
    Supports: SELECT, WHERE, GROUP BY, ORDER BY, LIMIT
    """
    import re
    
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    _ensure_loaded(normalized_path)
    df = _get_df(normalized_path)
    
    if df is None:
        return {"error": f"File not loaded: {file_path}. Use /load first."}
    
    try:
        query_lower = query.lower().strip()
        
        has_aggregate = any(x in query_lower for x in ["sum(", "avg(", "count(", "max(", "min("])
        
        if 'group by' in query_lower and has_aggregate:
            group_match = re.search(r'group\s+by\s+(\w+)', query_lower)
            if group_match:
                group_col = group_match.group(1)
                result_df = df.groupby(group_col).agg({
                    'price': 'sum' if 'sum(' in query_lower else 
                             'mean' if 'avg(' in query_lower else
                             'count' if 'count(' in query_lower else
                             'max' if 'max(' in query_lower else 'min',
                }).reset_index()
                result_df.columns = [group_col, 'value']
        elif 'group by' in query_lower:
            group_match = re.search(r'group\s+by\s+([\w,]+)', query_lower)
            if group_match:
                cols = [c.strip() for c in group_match.group(1).split(',')]
                result_df = df.groupby(cols).size().reset_index(name='count')
        else:
            result_df = df.copy()
        
        if 'where' in query_lower:
            where_match = re.search(r'where\s+(.+?)(?:\s+group|\s+order|\s+limit|$)', query_lower)
            if where_match:
                where_clause = where_match.group(1).strip()
                result_df = _parse_where_clause(result_df, where_clause)
        
        if 'order by' in query_lower:
            order_match = re.search(r'order\s+by\s+(\w+)(?:\s+(desc|asc))?', query_lower)
            if order_match:
                col = order_match.group(1)
                if col in result_df.columns:
                    asc = order_match.group(2) != 'desc'
                    result_df = result_df.sort_values(by=col, ascending=asc)
        
        if 'limit' in query_lower:
            limit_match = re.search(r'limit\s+(\d+)', query_lower)
            if limit_match:
                result_df = result_df.head(int(limit_match.group(1)))
        
        return {
            "success": True,
            "rows": len(result_df),
            "columns": list(result_df.columns),
            "data": result_df.head(50).to_dict(orient="records"),
        }
        
    except Exception as e:
        return {"error": f"Query failed: {str(e)}"}


def _parse_where_clause(df: pd.DataFrame, where_clause: str) -> pd.DataFrame:
    """Parse WHERE clause conditions."""
    import re
    
    conditions = re.split(r'\s+and\s+', where_clause, flags=re.IGNORECASE)
    
    for cond in conditions:
        cond = cond.strip()
        if '>=' in cond:
            col, val = cond.split('>=')
            df = df[df[col.strip()] >= _cast_value(val.strip())]
        elif '<=' in cond:
            col, val = cond.split('<=')
            df = df[df[col.strip()] <= _cast_value(val.strip())]
        elif '!=' in cond:
            col, val = cond.split('!=')
            df = df[df[col.strip()] != _cast_value(val.strip())]
        elif '=' in cond:
            col, val = cond.split('=')
            df = df[df[col.strip()] == _cast_value(val.strip())]
        elif '>' in cond:
            col, val = cond.split('>')
            df = df[df[col.strip()] > _cast_value(val.strip())]
        elif '<' in cond:
            col, val = cond.split('<')
            df = df[df[col.strip()] < _cast_value(val.strip())]
    
    return df


def _cast_value(val: str):
    """Cast string value to appropriate type."""
    val = val.strip().strip("'\"")
    if val.isdigit():
        return int(val)
    try:
        return float(val)
    except:
        return val