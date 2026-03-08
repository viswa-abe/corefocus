"""HTTP server for the web viewer."""

import http.server
import json

from corefocus.store import LoopStore
from corefocus.utils import format_timestamp, now_iso


def create_handler(store: LoopStore):
    """Create a request handler class bound to the given store."""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(store.base), **kwargs)

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
