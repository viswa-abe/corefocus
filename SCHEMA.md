# Open Loops — Schema

## loops.json

Array of loop objects:

```json
{
  "id": "slugified-title",
  "title": "Human readable problem description",
  "kind": null | "blocker" | "verification",
  "todos": [{"text": "step description", "done": false}],
  "opened_at": "ISO 8601 UTC",
  "last_progress": "ISO 8601 UTC"
}
```

## File structure

```
~/.corefocus/
  loops.json                       # active loops
  archive.json                     # closed/expired loops
  loops/<id>/description.md        # problem description (markdown)
  loops/<id>/notes.md              # timestamped notes (append-only)
  archive/<id>/                    # archived loop files
```

## CLI commands

```
cf                          List all open loops (latest note as preview)
cf new "problem"            Create loop + open $EDITOR for description
cf new "problem" -q         Create loop without editor (Claude uses this)
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
cf serve                    Start web viewer on :3333
```

## Expiry

- Open loops: 2 days without progress
- Blockers: 7 days
- Verifications: 7 days

## Philosophy

- A loop is a PROBLEM, not a task or solution
- Ephemeral by design — if it matters, recreate it
- Notes are the primary interface (fast capture, timestamped)
- Description is the thorough problem writeup (edited in browser or $EDITOR)
- Todos are flat checkboxes for atomic steps
- No nesting — everything is flat
- Blockers and verifications are independent from loops
- Claude creates loops with -q flag and writes description.md directly
