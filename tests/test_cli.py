"""Integration tests for the CLI entry point."""

import pytest
from pathlib import Path

from corefocus.cli import main
from corefocus.store import LoopStore


@pytest.fixture
def store(tmp_path: Path) -> LoopStore:
    s = LoopStore(base=tmp_path)
    s.ensure_dirs()
    return s


class TestCLINew:
    def test_new_quick(self, store: LoopStore, capsys):
        main(["new", "Test problem", "-q"], store=store)
        out = capsys.readouterr().out.strip()
        assert out == "test-problem"
        assert len(store.load_loops()) == 1

    def test_new_blocker(self, store: LoopStore, capsys):
        main(["block", "Waiting on API keys"], store=store)
        out = capsys.readouterr().out.strip()
        assert out == "waiting-on-api-keys"
        loop, _ = store.find("waiting-on-api-keys")
        assert loop["kind"] == "blocker"


class TestCLINote:
    def test_add_note(self, store: LoopStore, capsys):
        store.create("Note CLI test")
        main(["note", "note-cli-test", "Hello from CLI"], store=store)
        out = capsys.readouterr().out.strip()
        assert "Noted: Hello from CLI" in out

    def test_read_notes(self, store: LoopStore, capsys):
        store.create("Read CLI test")
        store.add_note("read-cli-test", "First")
        store.add_note("read-cli-test", "Second")
        main(["note", "read-cli-test"], store=store)
        out = capsys.readouterr().out
        # Latest first
        lines = [l for l in out.strip().splitlines() if l.strip()]
        assert "Second" in lines[0]
        assert "First" in lines[1]

    def test_note_missing_loop(self, store: LoopStore):
        with pytest.raises(SystemExit):
            main(["note", "ghost", "msg"], store=store)


class TestCLITodo:
    def test_add_todo(self, store: LoopStore, capsys):
        store.create("Todo CLI")
        main(["todo", "todo-cli", "add", "Step one"], store=store)
        out = capsys.readouterr().out.strip()
        assert "[1] Step one" in out

    def test_done_todo(self, store: LoopStore, capsys):
        store.create("Done CLI")
        store.add_todo("done-cli", "Finish")
        main(["todo", "done-cli", "done", "1"], store=store)
        out = capsys.readouterr().out.strip()
        assert "Done: Finish" in out

    def test_list_todos(self, store: LoopStore, capsys):
        store.create("List CLI")
        store.add_todo("list-cli", "A")
        store.add_todo("list-cli", "B")
        store.set_todo_done("list-cli", 1)
        main(["todo", "list-cli", "list"], store=store)
        out = capsys.readouterr().out
        assert "[x] 1. A" in out
        assert "[ ] 2. B" in out


class TestCLIClose:
    def test_close_with_verify(self, store: LoopStore, capsys):
        store.create("Close CLI")
        main(["close", "close-cli"], store=store)
        out = capsys.readouterr().out
        assert "Closed: Close CLI" in out
        assert "verification" in out

    def test_close_no_verify(self, store: LoopStore, capsys):
        store.create("Close NV")
        main(["close", "close-nv", "--no-verify"], store=store)
        out = capsys.readouterr().out
        assert "Closed: Close NV" in out
        assert "verification" not in out


class TestCLIList:
    def test_empty_list(self, store: LoopStore, capsys):
        main([], store=store)
        out = capsys.readouterr().out.strip()
        assert "No open loops" in out

    def test_list_with_loops(self, store: LoopStore, capsys):
        store.create("Regular problem")
        store.create("Blocked thing", kind="blocker")
        store.create("Check this", kind="verification")
        main([], store=store)
        out = capsys.readouterr().out
        assert "Regular problem" in out
        assert "Blocked thing" in out
        assert "Check this" in out


class TestCLIShow:
    def test_show_loop(self, store: LoopStore, capsys):
        store.create("Show test")
        store.add_note("show-test", "A note")
        store.add_todo("show-test", "A step")
        main(["show", "show-test"], store=store)
        out = capsys.readouterr().out
        assert "Show test" in out
        assert "A note" in out
        assert "A step" in out

    def test_bare_id_shows(self, store: LoopStore, capsys):
        """Bare ID (without 'show' command) should show the loop."""
        store.create("Bare ID test")
        main(["bare-id-test"], store=store)
        out = capsys.readouterr().out
        assert "Bare ID test" in out


class TestCLIArchive:
    def test_empty_archive(self, store: LoopStore, capsys):
        main(["archive"], store=store)
        out = capsys.readouterr().out.strip()
        assert "Archive is empty" in out

    def test_archive_shows_closed(self, store: LoopStore, capsys):
        store.create("Archive me")
        store.close("archive-me", no_verify=True)
        main(["archive"], store=store)
        out = capsys.readouterr().out
        assert "Archive me" in out
        assert "done" in out


class TestCLIHelp:
    def test_help(self, store: LoopStore, capsys):
        main(["--help"], store=store)
        out = capsys.readouterr().out
        assert "open loop tracker" in out
