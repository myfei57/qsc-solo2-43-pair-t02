"""Socket server that exposes the console over HTTP."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from .handlers import Console
from .response import json_response


class _RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "linecontrol"

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("request body is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("request body must be a JSON object")
        return parsed

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        query = {key: values[0] for key, values in parse_qs(parsed.query).items() if values}
        try:
            body = self._read_body()
        except ValueError as exc:
            response = json_response(400, {"error": "bad_request", "message": str(exc)})
        else:
            response = self.server.console.dispatch(method, parsed.path, query, body)
        data = response.body.encode("utf-8")
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, console: Console) -> None:
        super().__init__(address, _RequestHandler)
        self.console = console

    @property
    def bound_port(self) -> int:
        return int(self.server_address[1])


def build_server(console: Console, host: str = "127.0.0.1", port: int = 8080) -> ConsoleServer:
    return ConsoleServer((host, port), console)
