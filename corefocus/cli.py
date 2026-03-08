"""CLI argument parsing and dispatch."""

import sys

from corefocus.store import LoopStore
from corefocus import commands
from corefocus.server import serve


USAGE = """cf — open loop tracker

Usage:
  cf                          List all open loops
  cf new "problem"            Create loop + open editor for description
  cf new "problem" -q         Create loop without editor
  cf block "dependency"       Create blocker (expires 7d)
  cf note <id> "message"      Append timestamped note
  cf note <id>                Show all notes (latest first)
  cf todo <id> add "step"     Add todo item
  cf todo <id> done <n>       Mark todo done
  cf todo <id> rm <n>         Remove todo
  cf todo <id> list           List todos
  cf close <id>               Close loop (auto-creates verification)
  cf close <id> --no-verify   Close without verification
  cf show <id>                Show loop details
  cf archive                  Browse archived loops
  cf serve                    Start web viewer on :3333"""


def main(argv: list[str] | None = None, store: LoopStore | None = None):
    """Entry point. Accepts argv/store overrides for testing."""
    args = argv if argv is not None else sys.argv[1:]
    store = store or LoopStore()

    if not args:
        commands.cmd_list(store)
    elif args[0] == "block":
        if len(args) < 2:
            print("Usage: cf block \"description\"")
            sys.exit(1)
        commands.cmd_new(store, args[1], quick=True, kind="blocker")
    elif args[0] == "new":
        if len(args) < 2:
            print("Usage: cf new \"title\" [-q]")
            sys.exit(1)
        quick = "-q" in args or "--quick" in args
        commands.cmd_new(store, args[1], quick=quick)
    elif args[0] == "note":
        if len(args) < 2:
            print("Usage: cf note <id> [\"message\"]")
            sys.exit(1)
        message = " ".join(args[2:]) if len(args) > 2 else None
        commands.cmd_note(store, args[1], message)
    elif args[0] == "todo":
        if len(args) < 3:
            print("Usage: cf todo <id> add|done|rm|list ...")
            sys.exit(1)
        commands.cmd_todo(store, args[1], args[2], *args[3:])
    elif args[0] == "close":
        if len(args) < 2:
            print("Usage: cf close <id> [--no-verify]")
            sys.exit(1)
        no_verify = "--no-verify" in args
        commands.cmd_close(store, args[1], no_verify=no_verify)
    elif args[0] == "show":
        if len(args) < 2:
            print("Usage: cf show <id>")
            sys.exit(1)
        commands.cmd_show(store, args[1])
    elif args[0] == "archive":
        commands.cmd_archive(store)
    elif args[0] == "serve":
        serve(store)
    elif args[0] in ("-h", "--help", "help"):
        print(USAGE)
    else:
        # bare id → show
        commands.cmd_show(store, args[0])
