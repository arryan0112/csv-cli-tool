# CSV CLI Agent

A conversational CLI tool that lets you query CSV files in plain English using LLM-powered tool calling.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Built with Groq](https://img.shields.io/badge/Built%20with-Groq-orange.svg)

## Features

### Core Features
- **Natural language queries** - Ask questions in plain English over CSV data
- **Tool calling pipeline** - Filter, aggregate, sample, join operations
- **Session memory** - Resume past conversations
- **Indian price formatting** - Auto-formats prices in Indian number system

### Data Analysis Features
- **Bar & Pie Charts** - Visualize data with `create_chart` tool
- **Column Statistics** - Min/max/mean/median/unique counts
- **Outlier Detection** - IQR-based statistical outlier finding
- **Value Distribution** - Histograms for numeric, frequency for categorical
- **SQL-like Queries** - GROUP BY, ORDER BY, LIMIT, WHERE support

### Advanced Features
- **Semantic Search** - AI-powered similarity search using embeddings + ChromaDB
- **Offline Index** - Build search index for fast natural language queries
- **Data Quality Reports** - Null counts, duplicates, type analysis
- **Export Results** - Save filtered data to CSV

### Robustness
- **Retry Logic** - 3x API retry with exponential backoff
- **LRU Caching** - Efficient memory management for large files
- **Case-insensitive Search** - Flexible text matching

## Quick Start

```bash
pip install -e .
cp .env.example .env  # (add GROQ_API_KEY)
agent
# /load data/products.csv
# ask a question in plain English
```

## Commands

| Command | Description |
|---------|-------------|
| `/load <path>` | Load a CSV file into memory |
| `/schema` | Show column names and data types |
| `/index <path>` | Build semantic search index |
| `/sessions` | List all conversation sessions |
| `/resume <id>` | Resume a previous session |
| `/export <path>` | Export last result to CSV |
| `/next` / `/prev` | Paginate through results |
| `/mode [name]` | Switch domain mode or show current mode |
| `/clear` | Clear the terminal screen |
| `/help` | Show all commands |
| `/exit` | Exit the agent |

## Example Queries

### Basic Queries
- "What products are available in Bangalore?" → Filters by city
- "Show me items under ₹50,000" → Filters by price
- "What's the average price of laptops?" → Aggregates data
- "Which cities do you have data for?" → Lists unique values

### Advanced Queries
- "Is iPhone 15 in stock?" → Checks availability
- "Show prices by category as a bar chart" → Creates visualization
- "Find products similar to affordable phones" → Semantic search
- "Find outliers in the price column" → Statistical analysis
- "Show the distribution of categories" → Value frequency
- "Run a query: SELECT category, SUM(price) FROM table GROUP BY category" → SQL

## Tech Stack

Python, Groq, Llama 3.3 70B, Pandas, Pydantic, Rich, ChromaDB, Sentence-Transformers, SQLite

## Project Structure

```
src/
├── __init__.py
├── main.py
├── agent/
│   ├── core.py          # agent loop, tool execution
│   ├── prompts.py       # system prompt building
│   ├── tools.py         # tool definitions
│   └── runner.py        # CLI entry point
├── cli/
│   ├── commands.py      # command handlers
│   ├── renderer.py      # output formatting
│   └── repl.py          # read-eval-print loop
├── config/
│   ├── settings.py      # pydantic settings
│   └── .env.example
├── indexer/
│   └── __init__.py      # semantic search with ChromaDB
├── memory/
│   ├── __init__.py
│   └── session_store.py # SQLite session storage
└── tools/
    ├── __init__.py
    └── csv_tool.py      # CSV operations
```

## Available Tools

The agent has access to these tools:

| Tool | Description |
|------|-------------|
| `load_csv` | Load CSV into memory |
| `filter_rows` | Filter by column conditions |
| `aggregate` | Sum/mean/min/max/count/median |
| `create_chart` | Bar or pie chart visualization |
| `semantic_search` | AI-powered similarity search |
| `get_column_stats` | Column statistics (min/max/mean/unique) |
| `detect_outliers` | Find statistical outliers |
| `get_distribution` | Value distribution/histogram |
| `run_sql_query` | SQL-like queries with GROUP BY |
| `join_csvs` | Join two CSV files |
| `get_sample` | Get first N rows |
| `get_schema` | Show column names/types |
| `calculate_rate` | Calculate rate/percentage by group |

## Installation

1. **Requirements**: Python 3.10+, a Groq API key (free at [console.groq.com](https://console.groq.com))
2. Clone the repo
3. Create and activate a virtual environment
4. `pip install -e .`
5. Create `.env` file with `GROQ_API_KEY=your_key`
6. Run `agent`
7. Load any CSV file with `/load path/to/file.csv`
8. Start asking questions in plain English

## Bring Your Own Data

Works with any CSV file, not just products. Supports text, numeric, and boolean columns. Just `/load` your file and start querying.

Example: `/load sales.csv` then "what is the total revenue?"

## Semantic Search

Build a search index to enable AI-powered similarity search:

```bash
/load data/products.csv
/index data/products.csv
# Now ask: "Find affordable laptops"
```

The semantic search uses sentence-transformers embeddings and ChromaDB for vector storage.

## OpenRouter

Alternatively supports OpenRouter as the LLM provider. Get a free key at [openrouter.ai](https://openrouter.ai). Add `OPENROUTER_API_KEY=your_key` to `.env`. Optionally set `OPENROUTER_MODEL=your_preferred_model`. Falls back to Groq automatically if OpenRouter key is not set.

## Multi-Domain AI Data Copilot

The CLI now supports domain-specific analytics modes that provide specialized insights for different business domains.

### Available Modes

| Mode | Description | Sample Data |
|------|-------------|-------------|
| `call_analytics` | Analyze call logs for performance, failures, and regional trends | `data/calls.csv` |
| `product_analytics` | Analyze user behavior, retention patterns, and funnel drop-offs | `data/events.csv` |
| `log_debugging` | Analyze logs to identify root causes, error patterns, and anomalies | `data/logs.csv` |
| `claims_analysis` | Analyze insurance claims for fraud detection and risk assessment | `data/claims.csv` |
| `system_metrics` | Analyze system performance, detect anomalies, and find correlations | `data/metrics.csv` |

### Using Modes

```bash
# Switch to a domain mode
/mode call_analytics

# Load sample data for that domain
/load data/calls.csv

# Ask domain-specific questions
show failed calls
show success rate by city
find outliers in call_duration
```

### Mode Features

- **Domain-specific prompts** - Each mode has a specialized system prompt that biases toward relevant insights
- **Schema guidance** - Expected columns are documented for each mode
- **Automatic insights** - After every analysis, the agent provides 1-2 actionable insights
- **Rate calculations** - Built-in tools for calculating success/failure rates by category
- **Anomaly detection** - Context-aware outlier detection with plain English explanations

### Switching Modes

```bash
/mode                 # Show current mode
/mode help            # List all available modes
/mode <mode_name>    # Switch to a specific mode
```

## Contributing

- Fork the repo
- Create a feature branch
- New tools can be added in `src/agent/tools.py` and `src/tools/csv_tool.py`
- New modes can be added in `src/agent/modes.py`
- Submit a pull request
