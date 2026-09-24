from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .decorator import Agent


def _make_handler(agent: Agent) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status_code: int, body: dict) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802 - required by http.server
            if self.path == "/health":
                self._send_json(200, {"status": "ok", "agent": agent.name})
            else:
                self._send_json(
                    404, {"error": {"type": "not_found", "message": f"No route for GET {self.path}"}}
                )

        def do_POST(self) -> None:  # noqa: N802 - required by http.server
            if self.path != "/run":
                self._send_json(
                    404, {"error": {"type": "not_found", "message": f"No route for POST {self.path}"}}
                )
                return

            length = int(self.headers.get("Content-Length", 0) or 0)
            raw_body = self.rfile.read(length) if length else b""

            try:
                payload = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                self._send_json(
                    400,
                    {"error": {"type": "invalid_json", "message": "Request body was not valid JSON"}},
                )
                return

            status_code, body = agent.handle_request(payload)
            self._send_json(status_code, body)

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - required by http.server
            pass  # suppress the default per-request stderr logging

    return Handler


def serve(agent: Agent, *, host: str = "127.0.0.1", port: int = 8001) -> None:
    """Run `agent` as a local dev server: POST /run + GET /health."""
    handler_cls = _make_handler(agent)
    httpd = HTTPServer((host, port), handler_cls)
    print(f"levragent dev server for '{agent.name}' listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
