"""Integration tests for LoopStore."""

import time
from datetime import datetime, timezone, timedelta

from corefocus.store import LoopStore
from corefocus.utils import slugify


class TestCreate:
    def test_creates_loop_with_id_and_dir(self, store: LoopStore):
        loop = store.create("My test problem")
        assert loop["id"] == "my-test-problem"
        assert loop["title"] == "My test problem"
        assert store.loop_dir("my-test-problem").is_dir()

    def test_persists_to_json(self, store: LoopStore):
        store.create("Persisted loop")
        loops = store.load_loops()
        assert len(loops) == 1
        assert loops[0]["title"] == "Persisted loop"

    def test_duplicate_id_gets_date_prefix(self, store: LoopStore):
        first = store.create("Duplicate name")
        second = store.create("Duplicate name")
        assert first["id"] == "duplicate-name"
        assert second["id"] != "duplicate-name"
        assert second["id"].endswith("-duplicate-name")

    def test_kind_is_set(self, store: LoopStore):
        loop = store.create("Blocked on X", kind="blocker")
        assert loop["kind"] == "blocker"

    def test_kind_omitted_when_none(self, store: LoopStore):
        loop = store.create("Regular loop")
        assert "kind" not in loop

    def test_timestamps_are_iso(self, store: LoopStore):
        loop = store.create("Timestamped")
        dt = datetime.fromisoformat(loop["opened_at"])
        assert dt.tzinfo is not None


class TestNotes:
    def test_add_and_read(self, store: LoopStore):
        store.create("Note test")
        store.add_note("note-test", "First note")
        store.add_note("note-test", "Second note")
        lines = store.read_notes("note-test")
        assert len(lines) == 2
        assert "First note" in lines[0]
        assert "Second note" in lines[1]

    def test_add_note_updates_progress(self, store: LoopStore):
        store.create("Progress test")
        loop_before, _ = store.find("progress-test")
        t1 = loop_before["last_progress"]
        time.sleep(0.01)
        store.add_note("progress-test", "bump")
        loop_after, _ = store.find("progress-test")
        assert loop_after["last_progress"] > t1

    def test_add_note_to_missing_loop_raises(self, store: LoopStore):
        import pytest
        with pytest.raises(KeyError):
            store.add_note("nonexistent", "hello")

    def test_read_latest_note(self, store: LoopStore):
        store.create("Latest test")
        store.add_note("latest-test", "old note")
        store.add_note("latest-test", "new note")
        ts, msg = store.read_latest_note("latest-test")
        assert msg == "new note"
        assert ts is not None

    def test_read_latest_note_empty(self, store: LoopStore):
        store.create("Empty notes")
        ts, msg = store.read_latest_note("empty-notes")
        assert ts is None
        assert msg is None

    def test_source_tag_in_note(self, store: LoopStore):
        store.create("Source test")
        store.add_note("source-test", "tagged", source="viswa")
        lines = store.read_notes("source-test")
        assert "[viswa]" in lines[0]

    def test_no_source_tag_when_none(self, store: LoopStore):
        store.create("No source test")
        store.add_note("no-source-test", "untagged", source=None)
        lines = store.read_notes("no-source-test")
        assert "[]" not in lines[0]
        assert " — untagged" in lines[0]


class TestTodos:
    def test_add_todo(self, store: LoopStore):
        store.create("Todo test")
        idx = store.add_todo("todo-test", "Step one")
        assert idx == 1
        loop, _ = store.find("todo-test")
        assert len(loop["todos"]) == 1
        assert loop["todos"][0]["text"] == "Step one"
        assert loop["todos"][0]["done"] is False

    def test_done_todo(self, store: LoopStore):
        store.create("Done test")
        store.add_todo("done-test", "Finish this")
        todo = store.set_todo_done("done-test", 1)
        assert todo["done"] is True

    def test_undo_todo(self, store: LoopStore):
        store.create("Undo test")
        store.add_todo("undo-test", "Revert this")
        store.set_todo_done("undo-test", 1)
        todo = store.set_todo_done("undo-test", 1, done=False)
        assert todo["done"] is False

    def test_remove_todo(self, store: LoopStore):
        store.create("Remove test")
        store.add_todo("remove-test", "A")
        store.add_todo("remove-test", "B")
        removed = store.remove_todo("remove-test", 1)
        assert removed["text"] == "A"
        loop, _ = store.find("remove-test")
        assert len(loop["todos"]) == 1
        assert loop["todos"][0]["text"] == "B"

    def test_invalid_index_raises(self, store: LoopStore):
        import pytest
        store.create("Index test")
        store.add_todo("index-test", "Only one")
        with pytest.raises(IndexError):
            store.set_todo_done("index-test", 5)
        with pytest.raises(IndexError):
            store.remove_todo("index-test", 0)

    def test_todo_on_missing_loop_raises(self, store: LoopStore):
        import pytest
        with pytest.raises(KeyError):
            store.add_todo("ghost", "nope")


class TestClose:
    def test_close_moves_to_archive(self, store: LoopStore):
        store.create("Close me")
        store.close("close-me", no_verify=True)
        assert store.load_loops() == []
        archive = store.load_archive()
        assert len(archive) == 1
        assert archive[0]["close_reason"] == "done"
        assert "closed_at" in archive[0]

    def test_close_moves_directory(self, store: LoopStore):
        store.create("Move dir")
        assert store.loop_dir("move-dir").is_dir()
        store.close("move-dir", no_verify=True)
        assert not store.loop_dir("move-dir").exists()
        assert (store.archive_dir / "move-dir").is_dir()

    def test_close_creates_verification(self, store: LoopStore):
        store.create("Verify me")
        verify_id = store.close("verify-me")
        assert verify_id is not None
        assert verify_id.startswith("verify-")
        loops = store.load_loops()
        assert any(l["id"] == verify_id for l in loops)
        verify_loop = next(l for l in loops if l["id"] == verify_id)
        assert verify_loop["kind"] == "verification"

    def test_close_no_verify_flag(self, store: LoopStore):
        store.create("No verify")
        verify_id = store.close("no-verify", no_verify=True)
        assert verify_id is None
        assert store.load_loops() == []

    def test_close_blocker_no_verification(self, store: LoopStore):
        store.create("Blocked thing", kind="blocker")
        verify_id = store.close("blocked-thing")
        assert verify_id is None

    def test_close_verification_no_nested_verification(self, store: LoopStore):
        store.create("Verify something", kind="verification")
        verify_id = store.close("verify-something")
        assert verify_id is None

    def test_close_missing_loop_raises(self, store: LoopStore):
        import pytest
        with pytest.raises(KeyError):
            store.close("phantom")

    def test_close_with_notes_moves_files(self, store: LoopStore):
        store.create("Has notes")
        store.add_note("has-notes", "important note")
        store.close("has-notes", no_verify=True)
        archive_notes = store.archive_dir / "has-notes" / "notes.md"
        assert archive_notes.exists()
        assert "important note" in archive_notes.read_text()


class TestExpiry:
    def test_fresh_loop_not_expired(self, store: LoopStore):
        store.create("Fresh")
        expired = store.expire_stale()
        assert expired == []
        assert len(store.load_loops()) == 1

    def test_stale_loop_expires(self, store: LoopStore):
        store.create("Stale")
        # Backdate last_progress
        loops = store.load_loops()
        loops[0]["last_progress"] = (
            datetime.now(timezone.utc) - timedelta(days=3)
        ).isoformat()
        store.save_loops(loops)

        expired = store.expire_stale()
        assert len(expired) == 1
        assert expired[0]["close_reason"] == "expired"
        assert store.load_loops() == []
        assert len(store.load_archive()) == 1

    def test_blocker_has_longer_expiry(self, store: LoopStore):
        store.create("Patient blocker", kind="blocker")
        loops = store.load_loops()
        # 3 days old — should NOT expire (blocker gets 7 days)
        loops[0]["last_progress"] = (
            datetime.now(timezone.utc) - timedelta(days=3)
        ).isoformat()
        store.save_loops(loops)

        expired = store.expire_stale()
        assert expired == []

    def test_stale_blocker_expires(self, store: LoopStore):
        store.create("Old blocker", kind="blocker")
        loops = store.load_loops()
        loops[0]["last_progress"] = (
            datetime.now(timezone.utc) - timedelta(days=8)
        ).isoformat()
        store.save_loops(loops)

        expired = store.expire_stale()
        assert len(expired) == 1


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slugify("Fix: the bug (urgent!)") == "fix-the-bug-urgent"

    def test_strips_leading_trailing(self):
        assert slugify("  --hello--  ") == "hello"
