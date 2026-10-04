"""Native Windows notifications for completed downloads."""

from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon

from omni_download_manager.constants import APP_NAME

logger = logging.getLogger(__name__)


class CompletionNotifier:
    def __init__(self, icon: QIcon, enabled: bool) -> None:
        self._icon = icon
        self._tray: QSystemTrayIcon | None = None
        self.set_enabled(enabled)

    def set_enabled(self, enabled: bool) -> None:
        if sys.platform != "win32":
            return
        if not enabled:
            if self._tray is not None:
                self._tray.hide()
                self._tray.deleteLater()
                self._tray = None
            return
        if self._tray is not None:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("Windows notifications are enabled but the system tray is unavailable")
            return
        self._tray = QSystemTrayIcon(self._icon)
        self._tray.setToolTip(APP_NAME)
        self._tray.show()

    def notify_completed(self, filename: str) -> None:
        if self._tray is None:
            return
        self._tray.showMessage(
            APP_NAME,
            f"{filename} has finished downloading.",
            QSystemTrayIcon.MessageIcon.Information,
            10_000,
        )

    def close(self) -> None:
        if self._tray is not None:
            self._tray.hide()
            self._tray.deleteLater()
            self._tray = None
