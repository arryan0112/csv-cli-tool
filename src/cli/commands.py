"""
This file handles all slash commands — things that start with /

When the user types something starting with / in the REPL,
it comes here instead of going to the agent.

Each function returns a string status:
  "ok"       — command ran successfully, continue the REPL
  "exit"     — user wants to quit, REPL should stop
  "resume"   — user resumed a session, REPL should update its session_id
"""

import os
import json
import difflib
import pandas as pd
from pathlib import Path

from src.config.settings import settings
from src.memory.session_store import (
    get_loaded_files,
    list_sessions,
    get_session,
    save_loaded_file,
)
from src.tools.csv_tool import load_csv, get_data_quality
from src.indexer import build_index, list_indexes
from src.cli.renderer import (
    print_error,
    print_success,
    print_info,
    print_help,
    print_sessions,
    print_loaded_files,
    print_table,
    console,
)

# Available commands for suggestion
COMMANDS = [
    "/help", "/load", "/schema", "/sessions", "/resume",
    "/export", "/clear", "/exit", "/quit", "/next", "/prev", "/index"
]

# We store the last result here so /export can access it
_last_result: list[dict] | None = None

# Pagination state
_pagination_state: dict = {
    "data": [],
    "current_offset": 0,
    "page_size": 20,
    "total_rows": 0,
    "file_path": None,
}


def _suggest_command(cmd: str) -> str | None:
    """Suggest a similar command using fuzzy matching."""
    matches = difflib.get_close_matches(cmd, COMMANDS, n=1, cutoff=0.6)
    return matches[0] if matches else None


def handle_command(command: str, session_id: str) -> tuple[str, str]:
    """
    Main router — takes a raw command string like "/load data/products.csv"
    and routes it to the right handler.

    Returns a tuple: (status, session_id)
      status is "ok", "exit", or "resume"
      session_id may change if user resumes a different session
    """
    try:
        parts = command.strip().split()
        if not parts:
            print_error("Empty command. Type /help for available commands.")
            return "ok", session_id
        
        cmd = parts[0].lower()
        args = parts[1:]

        # Validate command exists
        if cmd not in COMMANDS:
            suggestion = _suggest_command(cmd)
            if suggestion:
                print_error(f"Unknown command: {cmd}. Did you mean '{suggestion}'?")
            else:
                print_error(f"Unknown command: {cmd}. Type /help to see available commands.")
            return "ok", session_id

        if cmd == "/help":
            return _cmd_help(), session_id

        elif cmd == "/load":
            return _cmd_load(args, session_id), session_id

        elif cmd == "/schema":
            return _cmd_schema(session_id), session_id

        elif cmd == "/sessions":
            return _cmd_sessions(), session_id

        elif cmd == "/resume":
            new_session_id = _cmd_resume(args, session_id)
            if new_session_id != session_id:
                return "resume", new_session_id
            return "ok", session_id

        elif cmd == "/export":
            return _cmd_export(args), session_id

        elif cmd == "/clear":
            return _cmd_clear(), session_id

        elif cmd == "/next":
            return _cmd_next(), session_id

        elif cmd == "/prev":
            return _cmd_prev(), session_id

        elif cmd == "/index":
            return _cmd_index(args), session_id

        elif cmd == "/exit" or cmd == "/quit":
            return "exit", session_id

        else:
            print_error(f"Unknown command: {cmd}. Type /help to see available commands.")
            return "ok", session_id
            
    except Exception as e:
        print_error(f"Command failed unexpectedly: {str(e)}")
        return "ok", session_id


# ---------------------------------------------------------------------------
# Individual command handlers
# ---------------------------------------------------------------------------

def _cmd_help() -> str:
    print_help()
    return "ok"


def _cmd_load(args: list[str], session_id: str) -> str:
    """
    /load <path>

    Loads a CSV file into memory and saves it to the session store
    so the agent knows about it in future turns.
    """
    if not args:
        print_error("Please provide a file path. Usage: /load <file.csv>")
        print_info("Example: /load data/products.csv")
        return "ok"

    file_path = args[0]

    # Validate file extension
    if not file_path.lower().endswith('.csv'):
        print_error(f"File must be a CSV. Got: {file_path}")
        print_info("Usage: /load <file.csv>")
        return "ok"

    # Check file existence
    if not Path(file_path).exists():
        print_error(f"File not found: {file_path}")
        print_info("Check the path and try again. Use relative paths like 'data/products.csv'")
        return "ok"

    # Actually load the CSV
    try:
        result = load_csv(file_path)
    except Exception as e:
        print_error(f"Failed to load CSV: {str(e)}")
        return "ok"

    if "error" in result:
        print_error(result["error"])
        return "ok"

    # Save to session store so the prompt builder picks it up
    try:
        save_loaded_file(
            session_id=session_id,
            file_path=file_path,
            original_name=Path(file_path).name,
            columns=result["columns"],
            row_count=result["rows"],
        )
    except Exception as e:
        print_error(f"Failed to save file to session: {str(e)}")
        return "ok"

    print_success(f"Loaded {result['file']} — {result['rows']} rows, {len(result['columns'])} columns")
    print_info(f"Columns: {', '.join(result['columns'])}")

    # Show a preview table
    if result.get("preview"):
        print_table(result["preview"], title="Preview (first 3 rows)")

    # Show data quality report
    try:
        quality = get_data_quality(file_path)
        if "error" not in quality:
            print_info("Data Quality Report:")
            if quality.get("null_counts"):
                nulls = ", ".join(f"{k}: {v} nulls" for k, v in quality["null_counts"].items())
                print_info(f"  • Null values: {nulls}")
            if quality.get("duplicate_rows", 0) > 0:
                print_info(f"  • Duplicate rows: {quality['duplicate_rows']}")
            if not quality.get("null_counts") and not quality.get("duplicate_rows"):
                print_info("  • No data quality issues found")
    except Exception:
        pass  # Silently skip if quality check fails

    return "ok"


def _cmd_schema(session_id: str) -> str:
    """
    /schema

    Shows all files loaded in this session with their columns.
    """
    files = get_loaded_files(session_id)
    print_loaded_files(files)
    return "ok"


def _cmd_sessions() -> str:
    """
    /sessions

    Lists all past sessions so the user can pick one to resume.
    """
    sessions = list_sessions()
    print_sessions(sessions)
    return "ok"


def _cmd_resume(args: list[str], current_session_id: str) -> str:
    """
    /resume <session_id>

    Switches to a past session. The user only needs to type
    the first few characters of the session ID.
    """
    if not args:
        print_error("Please provide a session ID. Usage: /resume <session_id>")
        print_info("Use /sessions to see available sessions")
        return current_session_id

    partial_id = args[0].lower()
    
    try:
        all_sessions = list_sessions()
    except Exception as e:
        print_error(f"Failed to list sessions: {str(e)}")
        return current_session_id

    match = None
    for s in all_sessions:
        if s["id"].startswith(partial_id):
            match = s
            break

    if not match:
        print_error(f"No session found starting with '{partial_id}'")
        print_info("Use /sessions to see all session IDs")
        return current_session_id

    print_success(f"Resumed session: {match['name']}")
    print_info(f"ID: {match['id'][:8]}... | Created: {match['created_at'][:16]}")
    return match["id"]


def _cmd_export(args: list[str]) -> str:
    """
    /export <path>

    Exports the last query result to a CSV file.
    """
    global _last_result

    if not _last_result:
        print_error("No result to export yet. Run a query first.")
        print_info("Ask the agent a question that returns data, then use /export")
        return "ok"

    if not args:
        print_error("Please provide a file path. Usage: /export <file.csv>")
        print_info("Example: /export results.csv")
        return "ok"

    output_path = args[0]

    # Validate file extension
    if not output_path.lower().endswith('.csv'):
        print_error(f"Output must be a CSV file. Got: {output_path}")
        print_info("Usage: /export <file.csv>")
        return "ok"

    try:
        df = pd.DataFrame(_last_result)
        df.to_csv(output_path, index=False)
        print_success(f"Exported {len(_last_result)} rows to {output_path}")
    except Exception as e:
        print_error(f"Export failed: {str(e)}")
        print_info("Check file permissions and path")

    return "ok"


def _cmd_clear() -> str:
    """
    /clear

    Clears the terminal screen.
    """
    try:
        os.system("clear" if os.name != "nt" else "cls")
    except Exception as e:
        print_error(f"Failed to clear screen: {str(e)}")
    return "ok"


def set_last_result(data: list[dict], total_rows: int = 0, file_path: str = None):
    """
    Called by the REPL after every agent response that contains table data.
    Stores the data so /export can access it.
    Also updates pagination state.
    """
    global _last_result, _pagination_state
    _last_result = data
    if data and total_rows > len(data):
        _pagination_state = {
            "data": data,
            "current_offset": 0,
            "page_size": 20,
            "total_rows": total_rows,
            "file_path": file_path,
        }
    elif not data:
        _pagination_state = {
            "data": [],
            "current_offset": 0,
            "page_size": 20,
            "total_rows": 0,
            "file_path": None,
        }


def _cmd_next() -> str:
    """
    /next - Show next page of results
    """
    global _pagination_state
    
    if not _pagination_state["data"]:
        print_info("No previous query results to navigate. Run a query first.")
        return "ok"
    
    total = _pagination_state["total_rows"]
    current = _pagination_state["current_offset"]
    page_size = _pagination_state["page_size"]
    
    if current + page_size >= total:
        print_info(f"Already at the last page. Showing rows {current + 1}-{total} of {total}.")
        return "ok"
    
    new_offset = current + page_size
    _pagination_state["current_offset"] = new_offset
    
    start = new_offset + 1
    end = min(new_offset + page_size, total)
    print_info(f"Showing rows {start}-{end} of {total}. Use /prev to go back.")
    
    return "ok"


def _cmd_prev() -> str:
    """
    /prev - Show previous page of results
    """
    global _pagination_state
    
    if not _pagination_state["data"]:
        print_info("No previous query results to navigate. Run a query first.")
        return "ok"
    
    current = _pagination_state["current_offset"]
    page_size = _pagination_state["page_size"]
    
    if current == 0:
        print_info("Already at the first page.")
        return "ok"
    
    new_offset = max(0, current - page_size)
    _pagination_state["current_offset"] = new_offset
    
    start = new_offset + 1
    end = min(new_offset + page_size, _pagination_state["total_rows"])
    print_info(f"Showing rows {start}-{end} of {_pagination_state['total_rows']}. Use /next for more.")
    
    return "ok"


def _cmd_index(args: list[str]) -> str:
    """
    /index <path> [text_columns]
    
    Builds a semantic search index from a CSV file.
    """
    if not args:
        print_error("Please provide a file path. Usage: /index <file.csv>")
        print_info("Example: /index data/products.csv")
        return "ok"
    
    file_path = args[0]
    
    if not file_path.lower().endswith('.csv'):
        print_error(f"File must be a CSV. Got: {file_path}")
        return "ok"
    
    if not Path(file_path).exists():
        print_error(f"File not found: {file_path}")
        return "ok"
    
    text_columns = args[1:] if len(args) > 1 else None
    
    print_info("Building semantic search index... (this may take a moment)")
    
    try:
        result = build_index(file_path, text_columns if text_columns else None)
    except Exception as e:
        print_error(f"Index build failed: {str(e)}")
        return "ok"
    
    if "error" in result:
        print_error(result["error"])
        return "ok"
    
    print_success(f"Index built: {result['documents_indexed']} documents indexed")
    print_info(f"Collection: {result['collection_name']}")
    print_info(f"Columns used: {', '.join(result['columns_used'])}")
    print_info("You can now search semantically, e.g., 'Find affordable laptops'")
    
    return "ok"