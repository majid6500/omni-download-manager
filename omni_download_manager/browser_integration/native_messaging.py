"""Chrome/Edge Native Messaging host entry point."""

from __future__ import annotations

import logging
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import BinaryIO

from omni_download_manager.browser_integration.ipc import send_to_running_app
from omni_download_manager.browser_integration.protocol import (
    MAX_MESSAGE_BYTES,
    decode_json,
    encode_json,
    validate_message,
)
from omni_download_manager.config.paths import AppPaths
from omni_download_manager.core.errors import AppError

logger = logging.getLogger(__name__)
APP_EXE_NAME = "Omni Download Manager.exe"


def run_native_host(paths: AppPaths, stdin: BinaryIO | None = None, stdout: BinaryIO | None = None) -> int:
    source = stdin or sys.stdin.buffer
    destination = stdout or sys.stdout.buffer
    while True:
        header = _read_exact(source, 4)
        if not header:
            return 0
        if len(header) != 4:
            logger.warning("Native Messaging input ended during frame header")
            return 1
        size = struct.unpack("<I", header)[0]
        if size > MAX_MESSAGE_BYTES:
            _write_response(destination, {"ok": False, "error": "Browser message is too large."})
            return 1
        payload = _read_exact(source, size)
        if len(payload) != size:
            _write_response(destination, {"ok": False, "error": "Browser message was incomplete."})
            return 1
        try:
            message = validate_message(decode_json(payload))
            response = handle_message(paths, message)
        except (AppError, ValueError) as exc:
            logger.info("Rejected Native Messaging request: %s", exc)
            response = {
                "ok": False,
                "error": exc.user_message if isinstance(exc, AppError) else str(exc),
            }
        except Exception:
            logger.exception("Unexpected Native Messaging host error")
            response = {
                "ok": False,
                "error": "The desktop download request could not be handled.",
            }
        _write_response(destination, response)


def handle_message(paths: AppPaths, message: dict[str, str]) -> dict[str, object]:
    if message["action"] == "status":
        running = send_to_running_app(paths, {"action": "status"}) is not None
        return {"ok": True, "native_host": True, "application_running": running}

    response = send_to_running_app(paths, message)
    if response is not None:
        return response

    executable = Path(sys.executable).resolve()
    app_executable = executable.with_name(APP_EXE_NAME)
    if not app_executable.is_file():
        raise RuntimeError("The Omni Download Manager application could not be found.")
    creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    try:
        subprocess.Popen(
            [str(app_executable), "--browser-request-listener"],
            cwd=str(app_executable.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creation_flags,
        )
    except OSError as exc:
        logger.exception("Could not start the desktop application")
        raise RuntimeError("Could not start Omni Download Manager.") from exc
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        response = send_to_running_app(paths, message)
        if response is not None:
            return response
        time.sleep(0.2)
    raise RuntimeError("Omni Download Manager did not become ready to receive the download.")


def _read_exact(stream: BinaryIO, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = stream.read(length - len(chunks))
        if not chunk:
            break
        chunks.extend(chunk)
    return bytes(chunks)


def _write_response(stream: BinaryIO, response: dict[str, object]) -> None:
    payload = encode_json(response)
    stream.write(struct.pack("<I", len(payload)))
    stream.write(payload)
    stream.flush()
