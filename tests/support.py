"""A small local HTTP server and helpers shared by the tests."""

from __future__ import annotations

import random
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

PAYLOAD = random.Random(1234).randbytes(1_500_000)
SLOW_PAYLOAD = random.Random(99).randbytes(600_000)
ETAG = '"payload-v1"'


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # keep test output clean
        pass

    def do_GET(self) -> None:
        try:
            self._route()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # the client stopped reading (pause/cancel) - expected

    def _route(self) -> None:
        path = self.path.split("?")[0]
        if path == "/file.bin":
            self._send_bytes(PAYLOAD)
        elif path == "/slow.bin":
            self._send_bytes(SLOW_PAYLOAD, piece=8192, delay=0.02)
        elif path == "/norange.bin":
            self._send_bytes(PAYLOAD, ranges=False)
        elif path == "/changing.bin":
            self._send_bytes(PAYLOAD, etag='"payload-v2"')
        elif path == "/attach":
            self._send_bytes(
                PAYLOAD[:5000],
                extra={"Content-Disposition": 'attachment; filename="My Report.pdf"'},
            )
        elif path == "/attach-utf8":
            self._send_bytes(
                PAYLOAD[:5000],
                extra={"Content-Disposition": "attachment; filename*=UTF-8''caf%C3%A9.txt"},
            )
        elif path == "/noname/":
            self._send_bytes(PAYLOAD[:100], extra={"Content-Type": "application/zip"})
        elif path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/file.bin")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/missing":
            self._send_status(404)
        elif path == "/boom":
            self._send_status(503)
        elif path == "/chunked.bin":
            self._send_chunked(PAYLOAD[:200_000])
        elif path == "/short.bin":
            self._send_truncated()
        else:
            self._send_status(404)

    def _send_status(self, code: int) -> None:
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_truncated(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", "100000")
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(PAYLOAD[:40_000])
        self.wfile.flush()
        self.close_connection = True

    def _send_chunked(self, data: bytes) -> None:
        self.send_response(200)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for start in range(0, len(data), 10_000):
            piece = data[start : start + 10_000]
            self.wfile.write(f"{len(piece):x}\r\n".encode() + piece + b"\r\n")
        self.wfile.write(b"0\r\n\r\n")

    def _send_bytes(
        self,
        data: bytes,
        *,
        ranges: bool = True,
        etag: str = ETAG,
        piece: int = 65536,
        delay: float = 0.0,
        extra: dict[str, str] | None = None,
    ) -> None:
        start, status = 0, 200
        range_header = self.headers.get("Range")
        if_range = self.headers.get("If-Range")
        if ranges and range_header and (if_range is None or if_range == etag):
            match = re.match(r"bytes=(\d+)-", range_header)
            if match:
                start = int(match.group(1))
                if start >= len(data):
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(data)}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206

        body = data[start:]
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.send_header("Content-Type", (extra or {}).get("Content-Type", "application/octet-stream"))
        if ranges:
            self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        for key, value in (extra or {}).items():
            if key != "Content-Type":
                self.send_header(key, value)
        self.end_headers()
        for offset in range(0, len(body), piece):
            self.wfile.write(body[offset : offset + piece])
            if delay:
                time.sleep(delay)


class TestServer:
    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> "TestServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}{path}"


def wait_for(predicate: Callable[[], bool], timeout: float = 10.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()
