from src.memory.session_store import init_db, create_session
from src.agent.core import run_agent

def main():
    init_db()
    session_id = create_session()
    print(f"Session: {session_id[:8]}...")
    print()

    print("Q: what can you help me with?")
    response = run_agent(session_id, "what can you help me with?")
    print(f"A: {response}")
    print()

    print("Q: load data/products.csv and show me the schema")
    response = run_agent(session_id, "load data/products.csv and show me the schema")
    print(f"A: {response}")

if __name__ == "__main__":
    main()



from src.cli.renderer import (
    print_welcome,
    print_response,
    print_error,
    print_success,
    print_table,
    print_sessions,
    print_help,
    ThinkingSpinner,
)
from src.memory.session_store import init_db, create_session
from src.agent.core import run_agent

def main():
    init_db()

    print_welcome()
    print_help()
    print_success("CSV file loaded: products.csv")
    print_error("File not found: missing.csv")

    # Test table rendering
    sample_data = [
        {"name": "MacBook Pro", "price": 150000, "city": "Bangalore"},
        {"name": "iPhone 15",   "price": 79000,  "city": "Bangalore"},
        {"name": "iPad Pro",    "price": 90000,  "city": "Bangalore"},
    ]
    print_table(sample_data, title="Bangalore products")

    # Test spinner + real agent call
    session_id = create_session()
    with ThinkingSpinner():
        response = run_agent(session_id, "what can you help me with?")
    print_response(response)

if __name__ == "__main__":
    main()    

from src.memory.session_store import init_db, create_session
from src.cli.commands import handle_command
from src.cli.renderer import print_welcome

def main():
    init_db()
    session_id = create_session()
    print_welcome()

    # Simulate slash commands
    tests = [
        "/help",
        "/load data/products.csv",
        "/schema",
        "/sessions",
        "/load missing.csv",         # should show error
        "/unknowncommand",           # should show unknown command error
    ]

    for cmd in tests:
        print(f"\n[running: {cmd}]")
        status, session_id = handle_command(cmd, session_id)
        print(f"[status: {status}]")

if __name__ == "__main__":
    main()


"""
Entrypoint for the CLI agent.

Run with:
  python -m src.main              — start a new session
  python -m src.main --resume <id> — resume a past session
"""

import sys
from src.cli.repl import start_repl


def main():
    # Check for --resume flag
    resume_id = None
    if "--resume" in sys.argv:
        idx = sys.argv.index("--resume")
        if idx + 1 < len(sys.argv):
            resume_id = sys.argv[idx + 1]
        else:
            print("Usage: python -m src.main --resume <session-id>")
            sys.exit(1)

    start_repl(resume_id=resume_id)


if __name__ == "__main__":
    main()