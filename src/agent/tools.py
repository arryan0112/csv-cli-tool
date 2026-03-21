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