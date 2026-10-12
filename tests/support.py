"""A small local HTTP server and helpers shared by the tests."""

from __future__ import annotations

import random
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

PAYLOAD = random.Random(1234).randbytes(1_500_000)
SLOW_PAYLOAD = random.Random(99).randbytes(2_000_000)
# Big enough to be split into segments, small enough for a fast test, and served
# slowly so the sibling segments are still writing when one of them fails.
FAILING_SEGMENT_PAYLOAD = SLOW_PAYLOAD[:1_200_000]
ETAG = '"payload-v1"'


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    request_counts: dict[str, int] = {}

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, *args) -> None:  # keep test output clean
        pass

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        self.request_counts[path] = self.request_counts.get(path, 0) + 1
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
        elif path == "/movie/direct":
            self._send_bytes(
                PAYLOAD,
                content_type="video/mp4",
                extra={
                    "Content-Disposition": (
                        'attachment; filename="Spider-Man-Brand-New-Day-2026-4k-DUB_1080.mp4"'
                    )
                },
            )
        elif path == "/movie/extended":
            self._send_bytes(
                PAYLOAD,
                content_type="video/mp4",
                extra={
                    "Content-Disposition": (
                        "attachment; filename*=UTF-8''Caf%C3%A9-vid%C3%A9o.mp4"
                    )
                },
            )
        elif path == "/movie/redirect":
            self.send_response(302)
            self.send_header("Location", "/misleading/4")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/misleading/4":
            self.send_response(302)
            self.send_header("Location", "/media/final")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/movie/redirect-url":
            self.send_response(302)
            self.send_header("Location", "/misleading-url/4")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/misleading-url/4":
            self.send_response(302)
            self.send_header("Location", "/media/final-name")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/media/final":
            self._send_bytes(
                PAYLOAD,
                content_type="video/mp4",
                extra={
                    "Content-Disposition": (
                        'attachment; filename="Spider-Man-Brand-New-Day-2026-4k-DUB_1080.mp4"'
                    )
                },
            )
        elif path == "/media/final-name":
            self._send_bytes(PAYLOAD, content_type="video/mp4")
        elif path == "/movie/by-url":
            self._send_bytes(PAYLOAD, content_type="video/mp4")
        elif path == "/movie/4":
            self._send_bytes(PAYLOAD, content_type="video/mp4")
        elif path == "/metadata/malformed.mp4":
            self._send_bytes(
                PAYLOAD,
                content_type="video/mp4",
                extra={"Content-Disposition": 'attachment; filename="'},
            )
        elif path == "/metadata/url-name.mp4":
            self._send_bytes(
                PAYLOAD,
                content_type="video/mp4",
                extra={"Content-Disposition": 'attachment; filename="server-name.mp4"'},
            )
        elif path == "/noname/":
            self._send_bytes(PAYLOAD[:100], extra={"Content-Type": "application/zip"})
        elif path == "/no-type.bin":
            self._send_bytes(PAYLOAD[:5000], content_type=None)
        elif path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/file.bin")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/unsafe-redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1/private")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path.startswith("/redirect-count/"):
            remaining = int(path.rsplit("/", 1)[1])
            self.send_response(302)
            destination = (
                f"/redirect-count/{remaining - 1}" if remaining else "/html-meta"
            )
            self.send_header("Location", destination)
            self.send_header("Connection", "close")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/html-meta":
            self._send_html('<meta http-equiv="refresh" content="0; url=/file.bin">')
        elif path == "/html-meta-no-type":
            self._send_html(
                '<meta http-equiv="refresh" content="0; url=/file.bin">',
                content_type="application/octet-stream",
            )
        elif path == "/html-loop":
            self._send_html('<meta http-equiv="refresh" content="0; url=/html-loop">')
        elif path == "/html-js":
            self._send_html(
                "<script>fetch('/resolve.json').then(r => r.json())"
                ".then(x => location.assign(x.url))</script>"
            )
        elif path == "/html-js-nav":
            self._send_html(
                "<script>setTimeout(() => location.assign('/file.bin'), 25)</script>"
            )
        elif path == "/html-error":
            self._send_html("<!doctype html><html><body>Access denied</body></html>")
        elif path == "/expired":
            self._send_status(410)
        elif path == "/missing":
            self._send_status(404)
        elif path == "/boom":
            self._send_status(503)
        elif path == "/chunked.bin":
            self._send_chunked(PAYLOAD[:200_000])
        elif path == "/short.bin":
            self._send_truncated()
        elif path == "/forbidden-segment.bin":
            # The range covering the second quarter of the file is refused, which
            # makes exactly one multi-part segment give up and force a fallback.
            self._send_bytes(
                FAILING_SEGMENT_PAYLOAD,
                piece=16384,
                delay=0.01,
                fail_range=(
                    len(FAILING_SEGMENT_PAYLOAD) // 4,
                    len(FAILING_SEGMENT_PAYLOAD) // 2,
                ),
            )
        else:
            self._send_status(404)

    def _send_status(self, code: int) -> None:
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_html(
        self, content: str, content_type: str | None = "text/html; charset=utf-8"
    ) -> None:
        body = content.encode("utf-8")
        self.send_response(200)
        if content_type is not None:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        content_type: str | None = "application/octet-stream",
        fail_range: tuple[int, int] | None = None,
    ) -> None:
        start, status = 0, 200
        end = len(data) - 1
        range_header = self.headers.get("Range")
        if_range = self.headers.get("If-Range")
        if ranges and range_header and (if_range is None or if_range == etag):
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else end
                if fail_range is not None and fail_range[0] <= start < fail_range[1]:
                    # A range the server always refuses: not retryable for the client.
                    self._send_status(403)
                    return
                if start >= len(data):
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(data)}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206

        body = data[start : end + 1]
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        response_content_type = (extra or {}).get("Content-Type", content_type)
        if response_content_type is not None:
            self.send_header("Content-Type", response_content_type)
        if ranges:
            self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
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

    def request_count(self, path: str) -> int:
        return _Handler.request_counts.get(path, 0)


def wait_for(predicate: Callable[[], bool], timeout: float = 10.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()
