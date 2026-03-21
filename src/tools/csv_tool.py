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
            "data": result.head(20).to_dict(orient="records"),
            "note": "Showing first 20 rows" if len(result) > 20 else None,
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
            # Defensive: should not happen due to validation
            return {"error": f"Unknown operation '{operation}'. Supported: sum, mean, min, max, count, median"}
        
        # Convert numpy types to native Python types
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