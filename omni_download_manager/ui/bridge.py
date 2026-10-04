"""Carries manager events (emitted on worker threads) safely onto the Qt GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from omni_download_manager.core.events import DownloadEvent, EventKind
from omni_download_manager.services.download_manager import DownloadManager


class ManagerBridge(QObject):
    """Qt delivers signals queued to receivers living in the GUI thread, so slots
    connected to these signals always run there."""

    item_added = Signal(object)
    item_updated = Signal(object)
    item_removed = Signal(str)

    def __init__(self, manager: DownloadManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._unsubscribe = manager.subscribe(self._on_event)

    def _on_event(self, event: DownloadEvent) -> None:
        if event.kind is EventKind.ADDED:
            self.item_added.emit(event.item)
        elif event.kind is EventKind.UPDATED:
            self.item_updated.emit(event.item)
        else:
            self.item_removed.emit(event.item.id)

    def close(self) -> None:
        self._unsubscribe()
