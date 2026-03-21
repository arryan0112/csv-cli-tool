import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from src.config.settings import settings


def get_connection() -> sqlite3.Connection:
    """
    Opens a connection to the SQLite database.
    Creates the db/ folder if it doesn't exist yet.
    """
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row   # lets us access columns by name: row["id"]
    return conn


def init_db():
    """
    Creates all tables if they don't exist.
    Safe to call every time the app starts — won't overwrite existing data.

    4 tables:
      sessions     — one row per conversation session
      turns        — one row per user/assistant exchange inside a session
      tool_calls   — one row per tool the agent used inside a turn
      loaded_files — one row per CSV file loaded in a session
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS turns (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,      -- 'user' or 'assistant'
            content     TEXT NOT NULL,
            turn_number INTEGER NOT NULL,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS tool_calls (
            id          TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            turn_number INTEGER NOT NULL,
            tool_name   TEXT NOT NULL,
            args        TEXT NOT NULL,      -- stored as JSON string
            result      TEXT NOT NULL,      -- stored as JSON string
            created_at  TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );

        CREATE TABLE IF NOT EXISTS loaded_files (
            id              TEXT PRIMARY KEY,
            session_id      TEXT NOT NULL,
            file_path       TEXT NOT NULL,
            original_name   TEXT NOT NULL,
            columns         TEXT NOT NULL,  -- comma separated column names
            row_count       INTEGER NOT NULL,
            loaded_at       TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
    """)

    conn.commit()
    conn.close()


def create_session(name: str = None) -> str:
    """
    Creates a new session row and returns its ID.
    If no name given, auto-generates one like 'session-2025-03-21-14-30'
    """
    session_id = str(uuid.uuid4())
    if not name:
        name = f"session-{datetime.now().strftime('%Y-%m-%d-%H-%M')}"

    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (id, name, created_at) VALUES (?, ?, ?)",
        (session_id, name, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    return session_id


def save_turn(session_id: str, role: str, content: str, turn_number: int):
    """
    Saves one message (user or assistant) to the turns table.
    role must be either 'user' or 'assistant'.
    """
    conn = get_connection()
    conn.execute(
        """INSERT INTO turns (id, session_id, role, content, turn_number, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), session_id, role, content, turn_number,
         datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def save_tool_call(session_id: str, turn_number: int,
                   tool_name: str, args: str, result: str):
    """
    Saves one tool call (name + args + result) to the tool_calls table.
    args and result are JSON strings.
    """
    conn = get_connection()
    conn.execute(
        """INSERT INTO tool_calls
           (id, session_id, turn_number, tool_name, args, result, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), session_id, turn_number, tool_name, args, result,
         datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def save_loaded_file(session_id: str, file_path: str,
                     original_name: str, columns: list[str], row_count: int):
    """
    Records that a CSV file was loaded in this session.
    columns is stored as a comma-separated string.
    """
    conn = get_connection()
    conn.execute(
        """INSERT INTO loaded_files
           (id, session_id, file_path, original_name, columns, row_count, loaded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), session_id, file_path, original_name,
         ",".join(columns), row_count, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_history(session_id: str) -> list[dict]:
    """
    Returns all turns for a session in order, as a list of dicts.
    This is what gets passed to the LLM as conversation history.

    Returns:  [{"role": "user", "content": "..."}, ...]
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT role, content FROM turns
           WHERE session_id = ?
           ORDER BY turn_number ASC""",
        (session_id,)
    ).fetchall()
    conn.close()

    return [{"role": row["role"], "content": row["content"]} for row in rows]


def get_loaded_files(session_id: str) -> list[dict]:
    """
    Returns all files loaded in this session.
    Used by the prompt builder to tell the LLM what data is available.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT file_path, original_name, columns, row_count
           FROM loaded_files
           WHERE session_id = ?
           ORDER BY loaded_at ASC""",
        (session_id,)
    ).fetchall()
    conn.close()

    return [
        {
            "file_path": row["file_path"],
            "original_name": row["original_name"],
            "columns": row["columns"].split(","),
            "row_count": row["row_count"],
        }
        for row in rows
    ]


def list_sessions() -> list[dict]:
    """
    Returns all sessions ordered by newest first.
    Used by the /sessions command.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, created_at FROM sessions ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return [
        {"id": row["id"], "name": row["name"], "created_at": row["created_at"]}
        for row in rows
    ]


def get_session(session_id: str) -> dict | None:
    """
    Returns a single session by ID, or None if not found.
    Used by /resume to check the session exists before loading it.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT id, name, created_at FROM sessions WHERE id = ?",
        (session_id,)
    ).fetchone()
    conn.close()

    if not row:
        return None
    return {"id": row["id"], "name": row["name"], "created_at": row["created_at"]}