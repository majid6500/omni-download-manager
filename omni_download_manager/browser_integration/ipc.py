"""Single-user local IPC for forwarding browser requests to the running app."""

from __future__ import annotations

import hashlib
import logging
import struct
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QIODeviceBase
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from omni_download_manager.browser_integration.protocol import (
    MAX_MESSAGE_BYTES,
    decode_json,
    encode_frame,
    validate_message,
)
from omni_download_manager.config.paths import AppPaths
from omni_download_manager.constants import APP_SHORT_NAME
from omni_download_manager.core.errors import AppError

logger = logging.getLogger(__name__)
_SOCKET_TIMEOUT_MS = 2500


def server_name(paths: AppPaths) -> str:
    identity = hashlib.sha256(str(paths.data_dir.resolve()).casefold().encode("utf-8")).hexdigest()[:20]
    return f"{APP_SHORT_NAME.lower()}-{identity}"


def send_to_running_app(paths: AppPaths, message: dict[str, str]) -> dict[str, object] | None:
    socket = QLocalSocket()
    socket.connectToServer(server_name(paths), QIODeviceBase.OpenModeFlag.ReadWrite)
    if not socket.waitForConnected(_SOCKET_TIMEOUT_MS):
        return None
    try:
        if socket.write(encode_frame(message)) < 0:
            return None
        socket.flush()
        time.sleep(0.05)
        if not socket.waitForReadyRead(_SOCKET_TIMEOUT_MS):
            return None
        data = bytearray(socket.readAll().data())
        while len(data) < 4:
            if not socket.waitForReadyRead(_SOCKET_TIMEOUT_MS):
                return None
            data.extend(socket.readAll().data())
        expected = struct.unpack("<I", data[:4])[0]
        if expected > MAX_MESSAGE_BYTES:
            raise ValueError("The desktop application returned an oversized response.")
        while len(data) < expected + 4:
            if not socket.waitForReadyRead(_SOCKET_TIMEOUT_MS):
                return None
            data.extend(socket.readAll().data())
        response = decode_json(bytes(data[4 : expected + 4]))
        return response if isinstance(response, dict) else None
    finally:
        socket.disconnectFromServer()


class BrowserIpcServer(QObject):
    def __init__(
        self,
        paths: AppPaths,
        on_download: Callable[[dict[str, str]], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_download = on_download
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept_connections)
        if not self._server.listen(server_name(paths)):
            raise RuntimeError(f"Could not listen for browser requests: {self._server.errorString()}")
        self._buffers: dict[object, bytearray] = {}

    def close(self) -> None:
        self._server.close()
        for socket in tuple(self._buffers):
            socket.abort()
        self._buffers.clear()

    def _accept_connections(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            self._buffers[socket] = bytearray()
            socket.readyRead.connect(lambda client=socket: self._read_message(client))
            socket.disconnected.connect(lambda client=socket: self._forget(client))
            if socket.bytesAvailable():
                self._read_message(socket)

    def _read_message(self, socket: object) -> None:
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        if len(buffer) + socket.bytesAvailable() > MAX_MESSAGE_BYTES + 4:
            self._reply(socket, {"ok": False, "error": "Browser message is too large."})
            return
        buffer.extend(socket.readAll().data())
        if len(buffer) < 4:
            return
        length = struct.unpack("<I", buffer[:4])[0]
        if length > MAX_MESSAGE_BYTES:
            self._reply(socket, {"ok": False, "error": "Browser message is too large."})
            return
        if len(buffer) < length + 4:
            return
        try:
            message = validate_message(decode_json(bytes(buffer[4 : length + 4])))
            if message["action"] == "status":
                result: dict[str, object] = {"ok": True, "application": "running"}
            else:
                self._on_download(message)
                result = {"ok": True, "message": "Download added to the queue."}
        except (ValueError, AppError) as exc:
            logger.info("Rejected browser integration message: %s", exc)
            result = {"ok": False, "error": exc.user_message if isinstance(exc, AppError) else str(exc)}
        except Exception:
            logger.exception("Unexpected error handling browser integration message")
            result = {"ok": False, "error": "The download request could not be added."}
        self._reply(socket, result)

    def _reply(self, socket: object, response: dict[str, object]) -> None:
        try:
            socket.write(encode_frame(response))
            socket.flush()
            socket.disconnectFromServer()
        except (OSError, ValueError):
            logger.exception("Could not reply to browser integration client")
            socket.abort()

    def _forget(self, socket: object) -> None:
        self._buffers.pop(socket, None)
