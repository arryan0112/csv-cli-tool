"""
The REPL (Read-Eval-Print Loop) — the interactive heart of the CLI.

This is what runs when you type `python -m src.main`.
It loops forever doing three things:
  1. Read  — wait for the user to type something
  2. Eval  — if it starts with / send to commands, else send to agent
  3. Print — show the response

It stops when the user types /exit or presses Ctrl+C.
"""

import sys
from src.config.settings import settings
from src.memory.session_store import init_db, create_session, get_session
from src.agent.core import run_agent
from src.cli.commands import handle_command
from src.cli.renderer import (
    print_welcome,
    print_response,
    print_error,
    print_info,
    print_sessions,
    ThinkingSpinner,
    console,
)
from src.agent.modes import get_mode


def start_repl(resume_id: str = None):
    """
    Starts the interactive REPL loop.

    resume_id: optional session ID to resume instead of creating a new one.
    """

    # Boot the database — creates tables if they don't exist
    init_db()

    # Decide which session to use
    if resume_id:
        session = get_session(resume_id)
        if not session:
            print_error(f"Session not found: {resume_id}")
            sys.exit(1)
        session_id = session["id"]
        print_welcome()
        print_info(f"Resumed session: {session['name']}")
        print_info(f"ID: {session_id[:8]}...")
    else:
        session_id = create_session()
        print_welcome()
        print_info(f"New session started: {session_id[:8]}...")
        # Show quick tips for first-time users
        console.print("[bold cyan]Quick tips:[/bold cyan]")
        console.print("  • Start with [bold]/load data/products.csv[/bold] to load a CSV file")
        console.print("  • Ask questions in natural language, e.g., 'Show me Electronics products'")
        console.print("  • Use [bold]/help[/bold] to see all commands")
        console.print("  • Press [bold]Ctrl+C[/bold] to cancel, [bold]Ctrl+D[/bold] to exit")
        console.print()

    console.print()

    # --- Main loop ---
    while True:
        try:
            # Read — show prompt and wait for input
            # Using input() directly gives us a clean prompt line
            current_mode = get_mode()
            prompt = f"[{current_mode}] " if current_mode else ""
            user_input = input(f"{prompt}you > ").strip()

        except KeyboardInterrupt:
            # User pressed Ctrl+C
            console.print()
            print_info("Use /exit to quit.")
            continue

        except EOFError:
            # User pressed Ctrl+D — treat as exit
            console.print()
            break

        # Skip empty input
        if not user_input:
            continue

        # --- Eval ---
        if user_input.startswith("/"):
            # Slash command — route to commands handler
            try:
                status, session_id = handle_command(user_input, session_id)
            except Exception as e:
                print_error(f"Command failed: {str(e)}")
                status = "ok"  # Continue REPL
                
            if status == "exit":
                print_info("Goodbye.")
                break

            # If user resumed a session, update session_id and continue
            # Add subtle separator for clean output
            console.print()
            continue

        else:
            # Natural language — send to agent
            try:
                with ThinkingSpinner("Thinking..."):
                    response = run_agent(session_id, user_input)

                print_response(response)
                # Add subtle separator after agent response
                console.print()

            except KeyboardInterrupt:
                # User pressed Ctrl+C while agent was thinking
                console.print()
                print_info("Cancelled.")
                console.print()
                continue

            except Exception as e:
                print_error(f"Agent error: {str(e)}")
                console.print()
                continue
