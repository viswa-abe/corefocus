"""CLI command implementations."""

import os
import subprocess
import sys

from corefocus.store import LoopStore
from corefocus.utils import time_ago

# ANSI colors
RED = "\033[91m"
YELLOW = "\033[93m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def cmd_new(store: LoopStore, title: str, quick: bool = False, kind: str | None = None):
    store.expire_stale()
    loop = store.create(title, kind=kind)
    print(loop["id"])

    if not quick and not kind:
        desc_path = store.description_path(loop["id"])
        desc_path.write_text(f"# {title}\n\n")
        editor = os.environ.get("EDITOR", "vim")
        subprocess.run([editor, str(desc_path)])


def cmd_note(store: LoopStore, loop_id: str, message: str | None = None):
    if message is None:
        lines = store.read_notes(loop_id)
        if not lines:
            # Verify the loop exists before saying "no notes"
            loop, _ = store.find(loop_id)
            if not loop:
                print(f"Loop '{loop_id}' not found")
                sys.exit(1)
            print("No notes yet")
            return
        for line in reversed(lines):
            print(line)
        return

    try:
        store.add_note(loop_id, message)
    except KeyError:
        print(f"Loop '{loop_id}' not found")
        sys.exit(1)
    print(f"Noted: {message}")


def cmd_todo(store: LoopStore, loop_id: str, action: str, *args: str):
    loop, _ = store.find(loop_id)
    if not loop:
        print(f"Loop '{loop_id}' not found")
        sys.exit(1)

    if action == "add":
        text = " ".join(args)
        idx = store.add_todo(loop_id, text)
        print(f"[{idx}] {text}")
    elif action == "done":
        try:
            todo = store.set_todo_done(loop_id, int(args[0]))
            print(f"Done: {todo['text']}")
        except (IndexError, ValueError) as e:
            print(str(e))
            sys.exit(1)
    elif action == "undo":
        try:
            todo = store.set_todo_done(loop_id, int(args[0]), done=False)
            print(f"Undone: {todo['text']}")
        except (IndexError, ValueError) as e:
            print(str(e))
            sys.exit(1)
    elif action == "rm":
        try:
            removed = store.remove_todo(loop_id, int(args[0]))
            print(f"Removed: {removed['text']}")
        except (IndexError, ValueError) as e:
            print(str(e))
            sys.exit(1)
    elif action == "list":
        todos = loop.get("todos", [])
        if not todos:
            print("No todos")
            return
        for i, t in enumerate(todos, 1):
            mark = "x" if t["done"] else " "
            print(f"  [{mark}] {i}. {t['text']}")
    else:
        print(f"Unknown todo action: {action}")
        print("Usage: cf todo <id> add|done|rm|list ...")
        sys.exit(1)


def cmd_close(store: LoopStore, loop_id: str, no_verify: bool = False):
    loop, _ = store.find(loop_id)
    if not loop:
        print(f"Loop '{loop_id}' not found")
        sys.exit(1)

    title = loop["title"]
    try:
        verify_id = store.close(loop_id, no_verify=no_verify)
    except KeyError:
        print(f"Loop '{loop_id}' not found")
        sys.exit(1)
    print(f"Closed: {title}")
    if verify_id:
        print(f"Created verification: {verify_id}")


def cmd_show(store: LoopStore, loop_id: str):
    store.expire_stale()
    loop, _ = store.find(loop_id)
    if not loop:
        print(f"Loop '{loop_id}' not found")
        sys.exit(1)

    kind_labels = {
        "blocker": f" {RED}[BLOCKER]{RESET}",
        "verification": f" {YELLOW}[VERIFY]{RESET}",
    }
    kind_label = kind_labels.get(loop.get("kind", ""), "")
    print(f"{BOLD}{loop['title']}{RESET}{kind_label}")
    print(f"{DIM}ID: {loop['id']}{RESET}")
    print(f"{DIM}Opened: {time_ago(loop['opened_at'])}  ·  Last progress: {time_ago(loop['last_progress'])}{RESET}")

    todos = loop.get("todos", [])
    if todos:
        done = sum(1 for t in todos if t["done"])
        print(f"\nTodos ({done}/{len(todos)}):")
        for i, t in enumerate(todos, 1):
            mark = "x" if t["done"] else " "
            print(f"  [{mark}] {i}. {t['text']}")

    lines = store.read_notes(loop_id)
    if lines:
        recent = lines[-5:]
        print(f"\nNotes ({len(lines)} total):")
        for line in reversed(recent):
            print(f"  {line}")

    desc_path = store.description_path(loop_id)
    if desc_path.exists() and desc_path.read_text().strip():
        print(f"\n{DIM}Description: {desc_path}{RESET}")


def cmd_list(store: LoopStore):
    store.expire_stale()
    loops = store.load_loops()
    if not loops:
        print("No open loops")
        return

    blockers = [l for l in loops if l.get("kind") == "blocker"]
    verifications = [l for l in loops if l.get("kind") == "verification"]
    regular = [l for l in loops if not l.get("kind")]

    if blockers:
        for b in blockers:
            age = time_ago(b["last_progress"])
            _, note = store.read_latest_note(b["id"])
            print(f"{RED}⊘ {b['title']}  ({age}){RESET}")
            if note:
                preview = note[:80] + ("..." if len(note) > 80 else "")
                print(f"  {DIM}{preview}{RESET}")
        print()

    if verifications:
        for v in verifications:
            age = time_ago(v["last_progress"])
            _, note = store.read_latest_note(v["id"])
            print(f"{YELLOW}◇ {v['title']}  ({age}){RESET}")
            if note:
                preview = note[:80] + ("..." if len(note) > 80 else "")
                print(f"  {DIM}{preview}{RESET}")
        print()

    for loop in regular:
        age = time_ago(loop["last_progress"])
        todos = loop.get("todos", [])
        done_count = sum(1 for t in todos if t["done"])
        todo_suffix = f"  [{done_count}/{len(todos)}]" if todos else ""
        print(f"○ {loop['title']}  ({age}){todo_suffix}")
        _, note = store.read_latest_note(loop["id"])
        if note:
            preview = note[:80] + ("..." if len(note) > 80 else "")
            print(f"  {DIM}{preview}{RESET}")
        print()


def cmd_archive(store: LoopStore):
    archive = store.load_archive()
    if not archive:
        print("Archive is empty")
        return

    for item in sorted(archive, key=lambda l: l.get("closed_at", ""), reverse=True)[:20]:
        reason = item.get("close_reason", "unknown")
        print(f"{'✓' if reason == 'done' else '✗'} {item['title']}  ({reason}, {item.get('closed_at', '?')[:10]})")
