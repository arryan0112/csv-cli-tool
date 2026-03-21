# CSV CLI Agent

A conversational CLI tool that lets you query CSV files in plain English using LLM-powered tool calling.

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Built with Groq](https://img.shields.io/badge/Built%20with-Groq-orange.svg)

## Features

- Natural language queries over CSV data
- Tool calling pipeline with filter, aggregate, and sample operations
- Session memory with resume support
- Indian price formatting
- Case-insensitive search
- LRU file caching
- Built with Groq + Llama 3.3 70B

## Quick Start

```bash
pip install -e .
cp .env.example .env  # (add GROQ_API_KEY)
agent
# /load data/products.csv
# ask a question in plain English
```

## Commands

- `/load <path>` — Load a CSV file into memory
- `/schema` — Show column names and data types
- `/sessions` — List all conversation sessions
- `/resume <id>` — Resume a previous session
- `/export <id>` — Export session to JSON
- `/clear` — Clear current session
- `/exit` — Exit the agent

## Example Queries

- "What products are available in Bangalore?" → Lists all products in that city
- "Show me items under ₹50,000" → Filters by price
- "What's the average price of laptops?" → Computes mean
- "Which cities do you have data for?" → Lists unique city values
- "Is iPhone 15 in stock?" → Checks availability
- "Summarize all products" → Shows sample rows

## Tech Stack

Python, Groq, Llama 3.3 70B, Pandas, Pydantic, Rich, SQLite

## Project Structure

```
src/
├── __init__.py
├── main.py
├── agent/
│   ├── __init__.py
│   ├── core.py          # agent loop, tool execution
│   ├── prompts.py       # system prompt building
│   ├── tools.py         # tool definitions
│   └── runner.py        # CLI entry point
├── cli/
│   ├── __init__.py
│   ├── commands.py      # command handlers
│   ├── renderer.py      # output formatting
│   └── repl.py          # read-eval-print loop
├── config/
│   ├── __init__.py
│   ├── settings.py      # pydantic settings
│   └── .env.example
├── indexer/
│   └── __init__.py
├── memory/
│   ├── __init__.py
│   └── session_store.py # SQLite session storage
└── tools/
    ├── __init__.py
    └── csv_tool.py      # CSV operations
```

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

## OpenRouter

Alternatively supports OpenRouter as the LLM provider. Get a free key at [openrouter.ai](https://openrouter.ai). Add `OPENROUTER_API_KEY=your_key` to `.env`. Optionally set `OPENROUTER_MODEL=your_preferred_model`. Falls back to Groq automatically if OpenRouter key is not set.

## Contributing

- Fork the repo
- Create a feature branch
- New tools can be added in `src/agent/tools.py` and `src/tools/csv_tool.py`
- Submit a pull request