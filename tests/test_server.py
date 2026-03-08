"""Integration tests for the HTTP server."""

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

from corefocus.store import LoopStore
from corefocus.server import create_handler
import http.server


@pytest.fixture
def store(tmp_path: Path) -> LoopStore:
    s = LoopStore(base=tmp_path)
    s.ensure_dirs()
    # Copy a minimal index.html so GET / doesn't 404
    (tmp_path / "index.html").write_text("<html></html>")
    return s


@pytest.fixture
def server(store: LoopStore):
    """Start a test HTTP server on an ephemeral port."""
    handler = create_handler(store)
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv, port
    srv.shutdown()


def _post(port: int, path: str, data: dict) -> tuple[int, dict]:
    conn = HTTPConnection("127.0.0.1", port)
    body = json.dumps(data).encode()
    conn.request("POST", path, body, {"Content-Type": "application/json"})
    resp = conn.getresponse()
    return resp.status, json.loads(resp.read())


class TestNoteEndpoint:
    def test_add_note(self, store: LoopStore, server):
        _, port = server
        store.create("HTTP note test")
        status, body = _post(port, "/api/note", {"id": "http-note-test", "message": "hello"})
        assert status == 200
        assert body["ok"] is True
        lines = store.read_notes("http-note-test")
        assert len(lines) == 1
        assert "hello" in lines[0]

    def test_note_missing_loop(self, store: LoopStore, server):
        _, port = server
        status, body = _post(port, "/api/note", {"id": "ghost", "message": "hi"})
        assert status == 404

    def test_note_missing_fields(self, store: LoopStore, server):
        _, port = server
        status, body = _post(port, "/api/note", {"id": ""})
        assert status == 400


class TestCloseEndpoint:
    def test_close_loop(self, store: LoopStore, server):
        _, port = server
        store.create("HTTP close test")
        status, body = _post(port, "/api/close", {"id": "http-close-test"})
        assert status == 200
        assert body["ok"] is True
        assert store.load_loops() == []
        assert len(store.load_archive()) == 1

    def test_close_with_verify(self, store: LoopStore, server):
        _, port = server
        store.create("HTTP verify test")
        status, body = _post(port, "/api/close", {"id": "http-verify-test", "verify": True})
        assert status == 200
        assert body["verify_id"] is not None
        loops = store.load_loops()
        assert any(l["kind"] == "verification" for l in loops)

    def test_close_missing_loop(self, store: LoopStore, server):
        _, port = server
        status, body = _post(port, "/api/close", {"id": "phantom"})
        assert status == 404

    def test_close_missing_id(self, store: LoopStore, server):
        _, port = server
        status, body = _post(port, "/api/close", {"id": ""})
        assert status == 400
