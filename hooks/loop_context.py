#!/usr/bin/env python3
"""SessionStart hook: inject active loop context into Claude's session.

Reads CF_LOOP env var. If set, reads the loop's title, description, todos,
and recent notes, then injects it as additionalContext so Claude knows
what it's working on.
"""

import json
import os
import sys
from pathlib import Path

BASE = Path.home() / ".corefocus"
LOOPS_FILE = BASE / "loops.json"


def main():
    loop_id = os.environ.get("CF_LOOP", "")
    if not loop_id:
        print(json.dumps({}))
        return

    try:
        loops = json.loads(LOOPS_FILE.read_text())
    except Exception:
        print(json.dumps({}))
        return

    loop = next((l for l in loops if l["id"] == loop_id), None)
    if not loop:
        print(json.dumps({}))
        return

    # Build context — make it unmissable
    parts = []
    parts.append("=" * 60)
    parts.append(f"THIS SESSION IS TIED TO LOOP: {loop['title']}")
    parts.append(f"CF_LOOP={loop_id}")
    if "session" in loop['title'].lower() or "unnamed" in loop['title'].lower():
        parts.append("This is a fresh session with no problem defined yet.")
        parts.append("Your first job: understand what Viswa wants to work on,")
        parts.append("then rename this loop and write a description.md for it.")
        parts.append(f"Rename: edit loops.json to update the title for id={loop_id}")
        parts.append(f"Describe: write to ~/.corefocus/loops/{loop_id}/description.md")
    else:
        parts.append("All notes you log go to this loop. Do not ask which loop.")
    parts.append("=" * 60)

    kind = loop.get("kind", "")
    if kind:
        parts.append(f"Kind: {kind}")

    # Description
    desc_path = BASE / "loops" / loop_id / "description.md"
    if desc_path.exists():
        desc = desc_path.read_text().strip()
        # Strip leading H1 (same as title)
        import re
        desc = re.sub(r'^# .+\n*', '', desc).strip()
        if desc:
            parts.append(f"\nDescription:\n{desc}")

    # Todos
    todos = loop.get("todos", [])
    if todos:
        parts.append("\nTodos:")
        for i, t in enumerate(todos, 1):
            mark = "x" if t["done"] else " "
            parts.append(f"  [{mark}] {i}. {t['text']}")

    # Recent notes (last 5)
    notes_path = BASE / "loops" / loop_id / "notes.md"
    if notes_path.exists():
        lines = [l for l in notes_path.read_text().strip().splitlines() if l.strip()]
        if lines:
            recent = lines[-5:]
            parts.append(f"\nRecent notes ({len(lines)} total):")
            for line in recent:
                parts.append(f"  {line}")

    parts.append(f"\nYou are working on this loop. Do NOT ask which loop — you already know.")
    parts.append(f"Log progress: `python3 ~/.corefocus/cf note {loop_id} \"message\"`")
    parts.append(f"Check off todos: `python3 ~/.corefocus/cf todo {loop_id} done <n>`")

    context = "\n".join(parts)

    # Both stdout (visible in transcript) and additionalContext (injected into model context)
    result = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context
        }
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
