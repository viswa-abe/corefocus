#!/usr/bin/env python3
"""Hook: log user prompts and assistant responses to the active cf loop.

Reads CF_LOOP env var (set by clauded function, inherited by subagents).
Tags: [viswa] for user, [claude] for main assistant, [agent:type] for subagents.

SubagentStart: logs the task description sent to the agent.
SubagentStop: saves full output to agents/<agent_id>.md, logs a short link note.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path.home() / ".corefocus"
LOOPS_FILE = BASE / "loops.json"


def get_active_loop():
    return os.environ.get("CF_LOOP", "")


def append_note(loop_id, message, source=""):
    notes_path = BASE / "loops" / loop_id / "notes.md"
    if not notes_path.parent.exists():
        return
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tag = f" [{source}]" if source else ""
    # Ensure message is single-line (no markdown bleed)
    message = message.replace("\n", " ").strip()
    entry = f"- **{ts}**{tag} — {message}\n"
    with open(notes_path, "a") as f:
        f.write(entry)
    try:
        loops = json.loads(LOOPS_FILE.read_text())
        for loop in loops:
            if loop["id"] == loop_id:
                loop["last_progress"] = datetime.now(timezone.utc).isoformat()
                break
        LOOPS_FILE.write_text(json.dumps(loops, indent=2, default=str) + "\n")
    except Exception:
        pass


def save_agent_output(loop_id, agent_id, agent_type, text):
    """Save full agent output to a separate file, return the filename."""
    agents_dir = BASE / "loops" / loop_id / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    # Use agent_id for uniqueness, agent_type for readability
    safe_id = (agent_id or "unknown").replace("/", "-")[-12:]
    filename = f"{agent_type}-{safe_id}.md"
    filepath = agents_dir / filename
    filepath.write_text(f"# {agent_type} agent output\n\n{text}\n")
    return filename


def main():
    loop_id = get_active_loop()
    if not loop_id:
        print(json.dumps({}))
        return

    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception:
        print(json.dumps({}))
        return

    event = data.get("hook_event_name", "")
    agent_id = data.get("agent_id", "")
    agent_type = data.get("agent_type", "")

    if event == "UserPromptSubmit":
        prompt = data.get("prompt", "").strip()
        if not prompt or len(prompt) < 5:
            print(json.dumps({}))
            return
        if agent_id:
            source = f"agent:{agent_type}" if agent_type else "agent"
        else:
            source = "viswa"
        if len(prompt) > 300:
            sid = agent_id or data.get("session_id", "main")
            filename = save_agent_output(loop_id, sid, source.replace(":", "-") + "-prompt", prompt)
            first_line = prompt.split("\n")[0][:150]
            append_note(loop_id, f"{first_line} → [full message](agents/{filename})", source=source)
        else:
            append_note(loop_id, prompt, source=source)

    elif event == "Stop":
        text = data.get("last_assistant_message", "").strip()
        if not text or len(text) < 20:
            print(json.dumps({}))
            return
        if agent_id:
            # Inside subagent — skip, SubagentStop will handle it
            pass
        else:
            if len(text) > 300:
                filename = save_agent_output(loop_id, data.get("session_id", "main"), "claude", text)
                first_line = text.split("\n")[0][:150]
                append_note(loop_id, f"{first_line} → [full response](agents/{filename})", source="claude")
            else:
                append_note(loop_id, text, source="claude")

    elif event == "SubagentStart":
        # Don't log "Subagent started" — wait for SubagentStop with the result
        pass

    elif event == "SubagentStop":
        source = f"agent:{agent_type}" if agent_type else "agent"
        text = data.get("last_assistant_message", "").strip()
        if text and len(text) > 50:
            # Save full output to file
            filename = save_agent_output(loop_id, agent_id, agent_type, text)
            # Log a short summary with link to full output
            first_line = text.split("\n")[0][:150]
            append_note(loop_id, f"{first_line} → [full output](agents/{filename})", source=source)
        elif text:
            append_note(loop_id, text[:300], source=source)
        else:
            append_note(loop_id, f"{agent_type} agent finished (no output)", source=source)

    print(json.dumps({}))


if __name__ == "__main__":
    main()
