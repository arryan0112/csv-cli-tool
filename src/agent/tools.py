TOOLS = [
    {
        "name": "load_csv",
        "description": "Loads a CSV file into memory. Must be called before any other CSV operation.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to a CSV file (must end with .csv)",
                    "pattern": r"\.csv$",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "get_schema",
        "description": "Returns column names and data types of a loaded CSV file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an already loaded CSV file",
                    "pattern": r"\.csv$",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "filter_rows",
        "description": "Filters rows in a loaded CSV based on column conditions.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an already loaded CSV file",
                    "pattern": r"\.csv$",
                },
                "column": {
                    "type": "string",
                    "description": "Column name to filter on",
                    "minLength": 1,
                },
                "operator": {
                    "type": "string",
                    "description": "Comparison operator",
                    "enum": ["=", "!=", ">", "<", ">=", "<=", "contains", "startswith"],
                },
                "value": {
                    "type": "string",
                    "description": "Value to compare against",
                    "minLength": 1,
                },
            },
            "required": ["file_path", "column", "operator", "value"],
        },
    },
    {
        "name": "aggregate",
        "description": "Performs aggregation on a numeric column (sum, mean, min, max, count, median).",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an already loaded CSV file",
                    "pattern": r"\.csv$",
                },
                "column": {
                    "type": "string",
                    "description": "Numeric column to aggregate",
                    "minLength": 1,
                },
                "operation": {
                    "type": "string",
                    "description": "Aggregation operation",
                    "enum": ["sum", "mean", "min", "max", "count", "median"],
                },
            },
            "required": ["file_path", "column", "operation"],
        },
    },
    {
        "name": "get_sample",
        "description": "Returns the first N rows of a loaded CSV.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an already loaded CSV file",
                    "pattern": r"\.csv$",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of rows to return (1-100)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 5,
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "join_csvs",
        "description": "Joins two loaded CSV files on a common column (like SQL JOIN).",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path1": {
                    "type": "string",
                    "description": "Path to the first CSV file",
                    "pattern": r"\.csv$",
                },
                "file_path2": {
                    "type": "string",
                    "description": "Path to the second CSV file",
                    "pattern": r"\.csv$",
                },
                "join_column": {
                    "type": "string",
                    "description": "Column name to join on (must exist in both files)",
                    "minLength": 1,
                },
                "join_type": {
                    "type": "string",
                    "description": "Type of join operation",
                    "enum": ["inner", "left", "right"],
                    "default": "inner",
                },
            },
            "required": ["file_path1", "file_path2", "join_column"],
        },
    },
    {
        "name": "create_chart",
        "description": "Creates a bar chart or pie chart from CSV data. Automatically groups and sums values by category.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an already loaded CSV file",
                    "pattern": r"\.csv$",
                },
                "label_column": {
                    "type": "string",
                    "description": "Column name for chart labels (categories to group by)",
                    "minLength": 1,
                },
                "value_column": {
                    "type": "string",
                    "description": "Numeric column name to sum for chart values",
                    "minLength": 1,
                },
                "chart_type": {
                    "type": "string",
                    "description": "Type of chart to create",
                    "enum": ["bar", "pie"],
                },
                "title": {
                    "type": "string",
                    "description": "Optional title for the chart",
                },
            },
            "required": ["file_path", "label_column", "value_column", "chart_type"],
        },
    },
    {
        "name": "semantic_search",
        "description": "Search indexed CSV data using natural language. Finds semantically similar matches even without exact keyword matches. Use after index is built with /index command.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an indexed CSV file",
                    "pattern": r"\.csv$",
                },
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                    "minLength": 1,
                },
                "n": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 5,
                },
            },
            "required": ["file_path", "query"],
        },
    },
    {
        "name": "get_column_stats",
        "description": "Get detailed statistics for a column including unique count, min/max for numbers, sample values for text.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an already loaded CSV file",
                    "pattern": r"\.csv$",
                },
                "column": {
                    "type": "string",
                    "description": "Column name to get statistics for",
                    "minLength": 1,
                },
            },
            "required": ["file_path", "column"],
        },
    },
    {
        "name": "detect_outliers",
        "description": "Detect statistical outliers in a numeric column using the IQR method.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an already loaded CSV file",
                    "pattern": r"\.csv$",
                },
                "column": {
                    "type": "string",
                    "description": "Numeric column name to check for outliers",
                    "minLength": 1,
                },
            },
            "required": ["file_path", "column"],
        },
    },
    {
        "name": "get_distribution",
        "description": "Get value distribution for a column showing histogram for numeric or frequency count for categorical.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an already loaded CSV file",
                    "pattern": r"\.csv$",
                },
                "column": {
                    "type": "string",
                    "description": "Column name to analyze distribution",
                    "minLength": 1,
                },
                "bins": {
                    "type": "integer",
                    "description": "Number of bins for numeric columns",
                    "default": 10,
                },
            },
            "required": ["file_path", "column"],
        },
    },
    {
        "name": "run_sql_query",
        "description": "Run a SQL-like query on CSV data. Supports SELECT, WHERE, GROUP BY, ORDER BY, LIMIT. Example: SELECT category, SUM(price) FROM table GROUP BY category ORDER BY SUM(price) DESC LIMIT 5",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an already loaded CSV file",
                    "pattern": r"\.csv$",
                },
                "query": {
                    "type": "string",
                    "description": "SQL-like query string",
                    "minLength": 1,
                },
            },
            "required": ["file_path", "query"],
        },
    },
    {
        "name": "calculate_rate",
        "description": "Calculate rate/percentage of rows matching a condition, grouped by a column. Example: success rate by city → group_by='city', condition_column='success', condition_value='TRUE'",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to an already loaded CSV file",
                    "pattern": r"\.csv$",
                },
                "group_by_column": {
                    "type": "string",
                    "description": "Column to group by (e.g., city, region, service)",
                    "minLength": 1,
                },
                "condition_column": {
                    "type": "string",
                    "description": "Column to check condition on (e.g., success, fraud_flag, churn_flag)",
                    "minLength": 1,
                },
                "condition_value": {
                    "type": "string",
                    "description": "Value that marks success/true (e.g., 'TRUE', 'true', '1')",
                    "minLength": 1,
                },
            },
            "required": ["file_path", "group_by_column", "condition_column", "condition_value"],
        },
    },
]


def get_tools_for_groq() -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in TOOLS
    ]


def get_tool_names() -> list[str]:
    return [tool["name"] for tool in TOOLS]