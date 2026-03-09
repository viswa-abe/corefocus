# CoreFocus

An open loop tracker for developers who use AI coding agents. Track problems — not tasks — with automatic expiry, so nothing lingers longer than it should.

Built to work with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), but the CLI and web UI work standalone.

## Philosophy

- **A loop is a problem**, not a task or solution. "API returns stale data" not "Add cache invalidation".
- **Ephemeral by design.** Loops expire after 2 days without progress. If it still matters, recreate it.
- **Notes are the primary interface.** Fast timestamped capture — the append-only log of what happened.
- **Flat, not nested.** No subtrees, no dependencies, no priority fields. Just problems and progress.

## Install

```bash
git clone https://github.com/viswa-abe/corefocus.git ~/.corefocus
```

Requires Python 3.11+. No dependencies beyond the standard library.

## CLI

```
cf                          List all open loops
cf new "problem"            Create loop + open $EDITOR for description
cf new "problem" -q         Create loop without editor
cf block "dependency"       Create blocker (expires 7d)
cf note <id> "message"      Append timestamped note
cf note <id>                Show all notes (latest first)
cf todo <id> add "step"     Add todo item
cf todo <id> done <n>       Mark todo done
cf todo <id> rm <n>         Remove todo
cf close <id>               Close loop (auto-creates verification)
cf close <id> --no-verify   Close without verification
cf show <id>                Show loop details
cf archive                  Browse archived loops
cf serve                    Start web viewer on :3333
```

Run via `python3 ~/.corefocus/cf <command>`.

Add an alias if you want:

```bash
alias cf='python3 ~/.corefocus/cf'
```

## Web Viewer

```bash
python3 ~/.corefocus/cf serve
# Open http://localhost:3333
```

A single-page app with a terminal-green aesthetic. View loops, read descriptions and notes, add notes, and close loops — all from the browser.

## Expiry

| Kind | Expires after |
|------|--------------|
| Open loop | 2 days without progress |
| Blocker | 7 days |
| Verification | 7 days |

Expired loops move to the archive automatically. Every `cf` command and `cf serve` page load checks for stale loops.

## Data

Everything lives in `~/.corefocus/`:

```
loops.json                       # active loops (array of objects)
archive.json                     # closed/expired loops
loops/<id>/description.md        # problem writeup (markdown)
loops/<id>/notes.md              # timestamped notes (append-only)
archive/<id>/                    # archived loop files
```

No database. No config file. Just JSON and markdown.

## Wiring Up with Claude Code

CoreFocus becomes powerful when your AI agent uses it to track its own work. Here's how to set that up with Claude Code.

### 1. Shell hook: inject the active loop

Create a shell function that sets `CF_LOOP` before launching Claude:

```bash
# In your .zshrc or .bashrc
clauded() {
  # Pick the loop you want to work on (from `cf` output or the web UI)
  export CF_LOOP="$1"
  shift
  claude "$@"
}
```

### 2. Claude Code hooks: inject loop context on session start

In your project's `.claude/settings.json` (or global `~/.claude/settings.json`), add a hook that reads `CF_LOOP` and prints the loop's context into the conversation:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "python3 ~/.corefocus/hooks/session_start.py"
      }
    ]
  }
}
```

Write a small script that reads `CF_LOOP`, calls `cf show`, and prints the result so Claude sees it as system context. Example:

```python
#!/usr/bin/env python3
import os, subprocess, sys

loop_id = os.environ.get("CF_LOOP")
if not loop_id:
    sys.exit(0)

result = subprocess.run(
    ["python3", os.path.expanduser("~/.corefocus/cf"), "show", loop_id],
    capture_output=True, text=True
)
if result.stdout.strip():
    print(f"THIS SESSION IS TIED TO LOOP: {loop_id}")
    print(f"CF_LOOP={loop_id}")
    print(result.stdout)
```

### 3. CLAUDE.md instructions: teach the agent to use `cf`

Add this to your project's `CLAUDE.md` or global `~/.claude/CLAUDE.md`:

```markdown
## Open Loops

Track open problems in `~/.corefocus/`.

### CLI reference:
- `python3 ~/.corefocus/cf new "problem" -q` — create loop
- `python3 ~/.corefocus/cf note <id> "message"` — log progress
- `python3 ~/.corefocus/cf todo <id> add "step"` — add todo
- `python3 ~/.corefocus/cf todo <id> done <n>` — check off todo
- `python3 ~/.corefocus/cf close <id>` — close loop

### Rules:
- Every task gets a loop. Log progress as you work.
- A loop is a PROBLEM, not a task or solution.
- Use `CF_LOOP` env var — never ask which loop.
```

### How it works end-to-end

1. You pick a loop from `cf` or the web UI at `localhost:3333`
2. You launch Claude with `clauded <loop-id>`
3. The SessionStart hook injects the loop's title, todos, and recent notes
4. Claude works on the problem, logging progress with `cf note` and checking off todos with `cf todo done`
5. When done, Claude closes the loop with `cf close`, which auto-creates a verification loop
6. Stale loops expire on their own — no cleanup needed

## Tests

```bash
cd ~/.corefocus && python3 -m pytest
```

58 integration tests covering the store, CLI, and server.

## License

MIT
