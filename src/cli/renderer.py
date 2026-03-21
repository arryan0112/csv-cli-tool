"""
All terminal output goes through this file.
We use the `rich` library to make everything look clean and professional.

Instead of plain print() statements, we have:
- print_response()    — the agent's answer, in a nice panel
- print_error()       — errors in red
- print_success()     — success messages in green
- print_table()       — data in a formatted table
- print_sessions()    — list of past sessions
- print_welcome()     — startup banner
- print_thinking()    — spinner while agent is working
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.spinner import Spinner
from rich.live import Live
from rich import box
import time

# One shared console instance — all output goes through this
console = Console()


def print_welcome():
    """Prints the startup banner when the agent launches."""
    console.print()
    console.print(Panel.fit(
        "[bold]CLI Agent[/bold]\n"
        "[dim]CSV analysis + offline product search[/dim]\n\n"
        "[dim]Type a question or use /help for commands[/dim]",
        border_style="blue",
        padding=(1, 4),
    ))
    console.print()


def print_response(text: str):
    """
    Prints the agent's response in a clean panel.
    Supports markdown-style bold (**text**) and bullet points.
    """
    console.print()
    console.print(Panel(
        text,
        border_style="green",
        padding=(0, 2),
    ))
    console.print()


def print_error(message: str):
    """Prints an error message in red."""
    console.print()
    console.print(f"  [bold red]Error:[/bold red] {message}")
    console.print()


def print_success(message: str):
    """Prints a success message in green."""
    console.print(f"  [bold green]✓[/bold green] {message}")


def print_info(message: str):
    """Prints a neutral info message in dim text."""
    console.print(f"  [dim]{message}[/dim]")


def print_table(data: list[dict], title: str = None):
    """
    Prints a list of dicts as a formatted table.

    Example:
      data = [{"name": "MacBook", "price": 150000}, ...]
      print_table(data, title="Products")
    """
    if not data:
        print_info("No data to display.")
        return

    table = Table(
        title=title,
        box=box.ROUNDED,
        border_style="dim",
        header_style="bold blue",
        show_lines=False,
        padding=(0, 1),
    )

    # Add columns from the first row's keys
    for col in data[0].keys():
        table.add_column(str(col), overflow="fold")

    # Add rows
    for row in data:
        table.add_row(*[str(v) if v is not None else "-" for v in row.values()])

    console.print()
    console.print(table)
    console.print()


def print_sessions(sessions: list[dict]):
    """
    Prints a list of past sessions as a table.
    Used by the /sessions command.
    """
    if not sessions:
        print_info("No past sessions found.")
        return

    table = Table(
        title="Past sessions",
        box=box.ROUNDED,
        border_style="dim",
        header_style="bold blue",
        padding=(0, 1),
    )

    table.add_column("ID", style="dim", width=12)
    table.add_column("Name")
    table.add_column("Created", style="dim")

    for s in sessions:
        # Show only first 8 chars of the UUID
        short_id = s["id"][:8]
        table.add_row(short_id, s["name"], s["created_at"][:16])

    console.print()
    console.print(table)
    console.print()


def print_loaded_files(files: list[dict]):
    """
    Prints a summary of loaded CSV files.
    Used by the /schema command.
    """
    if not files:
        print_info("No files loaded. Use /load <path> to load a CSV.")
        return

    for f in files:
        console.print()
        console.print(Panel(
            f"[bold]{f['original_name']}[/bold]\n"
            f"[dim]Path:[/dim] {f['file_path']}\n"
            f"[dim]Rows:[/dim] {f['row_count']}\n"
            f"[dim]Columns:[/dim] {', '.join(f['columns'])}",
            border_style="blue",
            padding=(0, 2),
        ))

    console.print()


def print_help():
    """Prints the help message showing all available commands."""
    table = Table(
        title="Available commands",
        box=box.ROUNDED,
        border_style="dim",
        header_style="bold blue",
        padding=(0, 1),
        show_header=True,
    )

    table.add_column("Command", style="bold")
    table.add_column("Description")

    commands = [
        ("/load <path>",     "Load a CSV file, e.g. /load data/products.csv"),
        ("/schema",          "Show columns of all loaded files"),
        ("/sessions",        "List all past sessions"),
        ("/resume <id>",     "Resume a past session by its ID"),
        ("/index <path>",    "Build offline search index from a CSV"),
        ("/export <path>",   "Export last result to a CSV file"),
        ("/clear",           "Clear the terminal screen"),
        ("/help",            "Show this help message"),
        ("/exit",            "Exit the agent"),
    ]

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    console.print()
    console.print(table)
    console.print()


class ThinkingSpinner:
    """
    Shows an animated spinner while the agent is thinking.

    Usage:
        with ThinkingSpinner():
            response = run_agent(...)
    """

    def __init__(self, message: str = "Thinking..."):
        self.message = message
        self._live = None

    def __enter__(self):
        self._live = Live(
            Spinner("dots", text=f"[dim]{self.message}[/dim]"),
            console=console,
            refresh_per_second=10,
            transient=True,   # clears the spinner when done
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        self._live.__exit__(*args)