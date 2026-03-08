"""LoopStore — all data operations for loops and archive."""

import json
import re
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

from corefocus.utils import slugify, now_iso, format_timestamp

EXPIRY_LOOP = 2       # days
EXPIRY_BLOCKER = 7    # days
EXPIRY_VERIFY = 7     # days


def expiry_days(kind: str | None) -> int:
    if kind == "blocker":
        return EXPIRY_BLOCKER
    if kind == "verification":
        return EXPIRY_VERIFY
    return EXPIRY_LOOP


class LoopStore:
    """Manages loop persistence — JSON metadata + markdown files."""

    def __init__(self, base: Path | None = None):
        self.base = base or Path.home() / ".corefocus"
        self.loops_file = self.base / "loops.json"
        self.archive_file = self.base / "archive.json"
        self.loops_dir = self.base / "loops"
        self.archive_dir = self.base / "archive"

    def ensure_dirs(self):
        """Create base directories if they don't exist."""
        self.loops_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    # ── JSON persistence ──

    def load_loops(self) -> list[dict]:
        if not self.loops_file.exists():
            return []
        return json.loads(self.loops_file.read_text())

    def save_loops(self, loops: list[dict]):
        self.loops_file.write_text(json.dumps(loops, indent=2, default=str) + "\n")

    def load_archive(self) -> list[dict]:
        if not self.archive_file.exists():
            return []
        return json.loads(self.archive_file.read_text())

    def save_archive(self, archive: list[dict]):
        self.archive_file.write_text(json.dumps(archive, indent=2, default=str) + "\n")

    # ── Loop lookup ──

    def find(self, loop_id: str) -> tuple[dict | None, list[dict]]:
        """Find a loop by ID. Returns (loop, all_loops) or (None, all_loops)."""
        loops = self.load_loops()
        loop = next((l for l in loops if l["id"] == loop_id), None)
        return loop, loops

    # ── Path helpers ──

    def description_path(self, loop_id: str) -> Path:
        return self.loops_dir / loop_id / "description.md"

    def notes_path(self, loop_id: str) -> Path:
        return self.loops_dir / loop_id / "notes.md"

    def loop_dir(self, loop_id: str) -> Path:
        return self.loops_dir / loop_id

    # ── Core operations ──

    def create(self, title: str, kind: str | None = None) -> dict:
        """Create a new loop. Returns the loop dict."""
        loops = self.load_loops()
        loop_id = slugify(title)

        existing_ids = {l["id"] for l in loops}
        if loop_id in existing_ids:
            prefix = datetime.now().strftime("%m%d")
            loop_id = f"{prefix}-{loop_id}"

        loop = {
            "id": loop_id,
            "title": title,
            "opened_at": now_iso(),
            "last_progress": now_iso(),
        }
        if kind:
            loop["kind"] = kind

        loop_dir = self.loops_dir / loop_id
        loop_dir.mkdir(parents=True, exist_ok=True)

        loops.append(loop)
        self.save_loops(loops)
        return loop

    def add_note(self, loop_id: str, message: str, source: str = "claude") -> str:
        """Append a timestamped note. Returns the formatted timestamp."""
        loop, loops = self.find(loop_id)
        if not loop:
            raise KeyError(f"Loop '{loop_id}' not found")

        notes_path = self.notes_path(loop_id)
        notes_path.parent.mkdir(parents=True, exist_ok=True)

        ts = format_timestamp()
        source_tag = f" [{source}]" if source else ""
        entry = f"- **{ts}**{source_tag} — {message}\n"
        with open(notes_path, "a") as f:
            f.write(entry)

        loop["last_progress"] = now_iso()
        self.save_loops(loops)
        return ts

    def read_notes(self, loop_id: str) -> list[str]:
        """Read all note lines for a loop. Returns lines (oldest first)."""
        notes_path = self.notes_path(loop_id)
        if not notes_path.exists():
            return []
        return [l for l in notes_path.read_text().strip().splitlines() if l.strip()]

    def read_latest_note(self, loop_id: str) -> tuple[str | None, str | None]:
        """Read the latest note. Returns (timestamp, message) or (None, None)."""
        lines = self.read_notes(loop_id)
        if not lines:
            return None, None
        last = lines[-1]
        match = re.match(r'^- \*\*(.+?)\*\*(?:\s*\[.*?\])?\s*—\s*(.+)$', last)
        if match:
            return match.group(1), match.group(2)
        return None, last.lstrip("- ")

    def add_todo(self, loop_id: str, text: str) -> int:
        """Add a todo item. Returns the 1-based index."""
        loop, loops = self.find(loop_id)
        if not loop:
            raise KeyError(f"Loop '{loop_id}' not found")
        if "todos" not in loop:
            loop["todos"] = []
        loop["todos"].append({"text": text, "done": False})
        loop["last_progress"] = now_iso()
        self.save_loops(loops)
        return len(loop["todos"])

    def set_todo_done(self, loop_id: str, index: int, done: bool = True):
        """Mark a todo done/undone by 1-based index."""
        loop, loops = self.find(loop_id)
        if not loop:
            raise KeyError(f"Loop '{loop_id}' not found")
        todos = loop.get("todos", [])
        idx = index - 1
        if idx < 0 or idx >= len(todos):
            raise IndexError(f"Invalid index {index} (1-{len(todos)})")
        todos[idx]["done"] = done
        if done:
            loop["last_progress"] = now_iso()
        self.save_loops(loops)
        return todos[idx]

    def remove_todo(self, loop_id: str, index: int) -> dict:
        """Remove a todo by 1-based index. Returns the removed item."""
        loop, loops = self.find(loop_id)
        if not loop:
            raise KeyError(f"Loop '{loop_id}' not found")
        todos = loop.get("todos", [])
        idx = index - 1
        if idx < 0 or idx >= len(todos):
            raise IndexError(f"Invalid index {index} (1-{len(todos)})")
        removed = todos.pop(idx)
        self.save_loops(loops)
        return removed

    def close(self, loop_id: str, no_verify: bool = False) -> str | None:
        """Close a loop, move to archive. Returns verify_id if created, else None."""
        loop, loops = self.find(loop_id)
        if not loop:
            raise KeyError(f"Loop '{loop_id}' not found")

        remaining = [l for l in loops if l["id"] != loop_id]

        loop["closed_at"] = now_iso()
        loop["close_reason"] = "done"

        # Move loop dir to archive
        src = self.loops_dir / loop["id"]
        dst = self.archive_dir / loop["id"]
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                shutil.rmtree(dst)
            src.rename(dst)

        archive = self.load_archive()
        archive.append(loop)
        self.save_archive(archive)
        self.save_loops(remaining)

        # Auto-create verification loop
        verify_id = None
        if not no_verify and loop.get("kind") not in ("blocker", "verification"):
            verify_title = f"Verify: {loop['title']}"
            verify_id = slugify(verify_title)
            existing_ids = {l["id"] for l in remaining}
            if verify_id in existing_ids:
                prefix = datetime.now().strftime("%m%d")
                verify_id = f"{prefix}-{verify_id}"
            verify_loop = {
                "id": verify_id,
                "title": verify_title,
                "kind": "verification",
                "opened_at": now_iso(),
                "last_progress": now_iso(),
            }
            verify_dir = self.loops_dir / verify_id
            verify_dir.mkdir(parents=True, exist_ok=True)
            remaining.append(verify_loop)
            self.save_loops(remaining)

        return verify_id

    def expire_stale(self) -> list[dict]:
        """Archive loops past their expiry. Returns list of expired loops."""
        loops = self.load_loops()
        archive = self.load_archive()
        now = datetime.now(timezone.utc)

        expired = []
        remaining = []
        for loop in loops:
            last = datetime.fromisoformat(loop["last_progress"])
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            cutoff = now - timedelta(days=expiry_days(loop.get("kind")))
            if last < cutoff:
                loop["closed_at"] = now_iso()
                loop["close_reason"] = "expired"
                src = self.loops_dir / loop["id"]
                dst = self.archive_dir / loop["id"]
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if dst.exists():
                        shutil.rmtree(dst)
                    src.rename(dst)
                expired.append(loop)
            else:
                remaining.append(loop)

        if expired:
            archive.extend(expired)
            self.save_loops(remaining)
            self.save_archive(archive)

        return expired
