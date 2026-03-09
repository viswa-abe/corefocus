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

### 1. Shell function: `clauded`

Add this to your `.zshrc` or `.bashrc`. It enforces the habit of always working inside a loop:

```bash
# clauded <loop-id>           — start claude session tied to a loop
# clauded new                 — create a new unnamed loop, start session
# clauded new "problem title" — create a named loop, start session
# clauded (no args)           — fail (forces the habit)
clauded() {
  if [[ -z "$1" ]]; then
    echo "Usage: clauded <loop-id>  or  clauded new [\"title\"]"
    echo ""
    python3 ~/.corefocus/cf
    echo ""
    echo "Pick a loop or create one with: clauded new"
    return 1
  fi

  local loop_id="$1"

  if [[ "$1" == "new" ]]; then
    local title="${*:2}"
    if [[ -z "$title" ]]; then
      title="session $(date +"%m%d-%H%M")"
    fi
    loop_id=$(python3 ~/.corefocus/cf new "$title" -q)
    echo "Created loop: $loop_id"
  else
    # Verify loop exists
    if ! python3 -c "
import json; loops = json.loads(open('$HOME/.corefocus/loops.json').read())
if not any(l['id'] == '$loop_id' for l in loops): exit(1)
" 2>/dev/null; then
      echo "Loop '$loop_id' not found. Open loops:"
      echo ""
      python3 ~/.corefocus/cf
      return 1
    fi
  fi

  CF_LOOP="$loop_id" claude
}
```

Usage:

```bash
clauded api-returns-stale-data     # attach to existing loop
clauded new "uploads failing"      # create loop + start session
clauded new                        # auto-named loop (session 0309-1420)
clauded                            # shows open loops, reminds you to pick one
```

With no arguments, it lists your open loops and refuses to start — so you never accidentally work outside a loop.

### 2. Claude Code hooks

CoreFocus uses four Claude Code hooks to create a continuous feedback loop between you, the agent, and your loops. Add these to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.corefocus/hooks/loop_context.py",
            "timeout": 3000
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.corefocus/hooks/loop_note.py",
            "timeout": 3000
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.corefocus/hooks/loop_note.py",
            "timeout": 3000
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.corefocus/hooks/loop_note.py",
            "timeout": 3000
          }
        ]
      }
    ]
  }
}
```

**What each hook does:**

| Hook | Script | Purpose |
|------|--------|---------|
| `SessionStart` | `loop_context.py` | Injects the loop's title, description, todos, and recent notes into Claude's context via `additionalContext`. Also detects unnamed sessions and tells Claude to define the problem first. |
| `UserPromptSubmit` | `loop_note.py` | Logs your prompts to the loop's notes, tagged `[viswa]`. Long prompts (>300 chars) are saved to `agents/` as separate files with a link in the note. |
| `Stop` | `loop_note.py` | Logs Claude's final response to the loop's notes, tagged `[claude]`. Same long-message handling. |
| `SubagentStop` | `loop_note.py` | Logs subagent results, tagged `[agent:type]`. Full output saved to `agents/<type>-<id>.md`, short summary in notes. |

The result: every loop has a complete, timestamped transcript of what happened — your questions, Claude's answers, and subagent results — all in `loops/<id>/notes.md` with overflow in `loops/<id>/agents/`.

#### `hooks/loop_context.py` — SessionStart

Reads `CF_LOOP` env var, loads the loop from `loops.json`, and returns `additionalContext` with:
- The loop title and ID (unmissable banner)
- Description from `description.md` (if written)
- Todo checklist with done/undone state
- Last 5 notes for continuity across sessions
- Instructions telling Claude to log progress and never ask which loop

For unnamed sessions (`clauded new`), it tells Claude to understand the problem first, then rename the loop and write a description.

#### `hooks/loop_note.py` — UserPromptSubmit, Stop, SubagentStop

A single script that handles multiple hook events. It reads `hook_event_name` from stdin to determine what to log:

- **UserPromptSubmit**: logs the user's prompt, tagged `[viswa]`
- **Stop**: logs Claude's response, tagged `[claude]` (skips if inside a subagent — SubagentStop handles that)
- **SubagentStop**: saves full agent output to `agents/<type>-<id>.md`, logs a one-line summary with a link

All notes update `last_progress` on the loop, keeping it alive and preventing expiry.

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
3. **SessionStart** hook injects the loop's title, todos, and recent notes into context
4. **UserPromptSubmit** hook logs every prompt you send to the loop's notes
5. Claude works on the problem, logging progress with `cf note` and checking off todos
6. **Stop** hook logs Claude's responses back to the loop's notes
7. **SubagentStop** hook captures subagent results into `agents/` files
8. When done, Claude closes the loop with `cf close`, which auto-creates a verification loop
9. Stale loops expire on their own — no cleanup needed

The loop's `notes.md` becomes a complete session transcript — searchable, reviewable, and persistent across context window resets.

## Tests

```bash
cd ~/.corefocus && python3 -m pytest
```

58 integration tests covering the store, CLI, and server.

## License

MIT
