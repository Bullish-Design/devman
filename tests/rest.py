"""A fake Dagu REST server for unit tests (PLAN Stage 6)."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


def run(dag: str, status: str = "succeeded", run_id: str = "r1") -> dict:
    """A run in the shape Dagu 2.20.1 returns (measured)."""
    return {
        "dagRunId": run_id,
        "name": dag,
        "statusLabel": status,
        "startedAt": "2026-10-15T22:58:27-04:00",
        "finishedAt": "2026-10-15T22:58:28-04:00",
    }


@contextmanager
def serve(runs: list[dict]) -> Iterator[int]:
    """Answer `GET /api/v1/dag-runs?name=...` from `runs`. Yield the port."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            name = query.get("name", [None])[0]
            found = [r for r in runs if name in (None, r["name"])]
            body = json.dumps({"dagRuns": found}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
