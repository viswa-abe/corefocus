"""HTTP server for the web viewer."""

import http.server
import json
import time
from pathlib import Path

from corefocus.store import LoopStore
from corefocus.utils import format_timestamp, now_iso

STATUS_DIR = Path.home() / ".claude" / "status"


def create_handler(store: LoopStore):
    """Create a request handler class bound to the given store."""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(store.base), **kwargs)

        def do_GET(self):
            if self.path.startswith('/api/status'):
                self._handle_status()
            else:
                super().do_GET()

        def do_POST(self):
            if self.path == '/api/note':
                self._handle_note()
            elif self.path == '/api/close':
                self._handle_close()
            else:
                self.send_response(405)
                self.end_headers()

        def _handle_note(self):
            body = self._read_json()
            loop_id = body.get('id', '')
            message = body.get('message', '').strip()
            if not loop_id or not message:
                self._respond(400, {"error": "id and message required"})
                return
            try:
                ts = store.add_note(loop_id, message, source=None)
                self._respond(200, {"ok": True, "ts": ts})
            except KeyError:
                self._respond(404, {"error": "loop not found"})

        def _handle_status(self):
            """Return all active Claude session statuses."""
            sessions = []
            now = time.time()
            if STATUS_DIR.exists():
                for f in STATUS_DIR.glob("*.json"):
                    try:
                        data = json.loads(f.read_text())
                        age = now - data.get("ts", 0)
                        if age > 1800:  # skip stale >30min
                            continue
                        data["age_seconds"] = int(age)
                        sessions.append(data)
                    except Exception:
                        pass
            sessions.sort(key=lambda s: s.get("ts", 0), reverse=True)
            self._respond(200, sessions)

        def _handle_close(self):
            body = self._read_json()
            loop_id = body.get('id', '')
            if not loop_id:
                self._respond(400, {"error": "id required"})
                return
            want_verify = body.get('verify', False)
            try:
                verify_id = store.close(loop_id, no_verify=not want_verify)
                self._respond(200, {"ok": True, "verify_id": verify_id})
            except KeyError:
                self._respond(404, {"error": "loop not found"})

        def _read_json(self) -> dict:
            length = int(self.headers.get('Content-Length', 0))
            return json.loads(self.rfile.read(length))

        def _respond(self, code: int, data: dict):
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def log_message(self, format, *args):
            pass  # suppress request logs

    return Handler


def serve(store: LoopStore, port: int = 3333):
    """Start the web viewer server."""
    handler = create_handler(store)
    server = http.server.HTTPServer(("127.0.0.1", port), handler)
    print(f"Serving at http://localhost:{port}")
    server.serve_forever()
