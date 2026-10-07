"""Main application window: composition and wiring only."""

from __future__ import annotations

import logging

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from omni_download_manager.config.paths import AppPaths
from omni_download_manager.config.settings import SettingsStore
from omni_download_manager.constants import APP_NAME, APP_SHORT_NAME, VERSION
from omni_download_manager.core.errors import AppError
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.services.download_manager import DownloadManager
from omni_download_manager.ui.bridge import ManagerBridge
from omni_download_manager.ui.controller import ItemActionController
from omni_download_manager.ui.dialogs import AddDownloadDialog, ConfirmDialog, NewDownload
from omni_download_manager.ui.downloads_page import DownloadsPage
from omni_download_manager.ui.icons import logo_icon
from omni_download_manager.ui.models import DownloadListModel, ViewFilter
from omni_download_manager.ui.notifications import CompletionNotifier
from omni_download_manager.ui.settings_page import SettingsPage
from omni_download_manager.ui.sidebar import SETTINGS_KEY, Sidebar
from omni_download_manager.ui.theme import ThemeManager
from omni_download_manager.ui.windows_effects import apply_title_bar_theme

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        manager: DownloadManager,
        settings: SettingsStore,
        theme: ThemeManager,
        paths: AppPaths,
    ) -> None:
        super().__init__()
        self._manager, self._settings, self._theme = manager, settings, theme
        self._notifier = CompletionNotifier(
            logo_icon(), settings.get().completion_notifications_enabled
        )
        settings.subscribe(
            lambda current: self._notifier.set_enabled(current.completion_notifications_enabled)
        )
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(logo_icon())
        self.setMinimumSize(920, 620)
        self.resize(1160, 740)
        self._restore_geometry()

        # Subscribe and connect before taking the snapshot: every event published
        # from now on reaches the model, and events that arrive before the snapshot
        # is read are covered by it (the handlers ignore unknown/duplicate ids).
        self._model = DownloadListModel(self)
        self._counts_signature: tuple | None = None
        self._bridge = ManagerBridge(manager, self)
        self._bridge.item_added.connect(self._model.add_item, Qt.ConnectionType.QueuedConnection)
        self._bridge.item_updated.connect(self._on_item_updated, Qt.ConnectionType.QueuedConnection)
        self._bridge.item_removed.connect(self._model.remove_item, Qt.ConnectionType.QueuedConnection)
        self._model.set_items(manager.list_items())

        self._controller = ItemActionController(manager, settings, theme, lambda: self)

        self._sidebar = Sidebar(theme, APP_SHORT_NAME, VERSION, logo_icon())
        self._downloads = DownloadsPage(self._model, theme)
        self._settings_page = SettingsPage(settings, theme, paths)
        self._pages = QStackedWidget()
        self._pages.addWidget(self._downloads)
        self._pages.addWidget(self._settings_page)

        root = QWidget()
        root.setObjectName("Root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._pages, 1)
        self.setCentralWidget(root)

        self._sidebar.selected.connect(self._on_nav)
        self._downloads.addRequested.connect(self.show_add_dialog)
        self._downloads.actionRequested.connect(self._controller.perform)
        self._downloads.bulkActionRequested.connect(self._controller.perform_bulk)
        self._downloads.contextMenuRequested.connect(self._controller.show_menu)
        for signal in (self._model.dataChanged, self._model.rowsInserted,
                       self._model.rowsRemoved, self._model.modelReset):
            signal.connect(self._update_counts)
        theme.changed.connect(self._on_theme_changed)
        self._update_counts()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._on_theme_changed()

    def _on_theme_changed(self) -> None:
        palette = self._theme.palette
        apply_title_bar_theme(
            int(self.winId()),
            palette.name == "dark",
            background=palette.bg,
            text=palette.text,
            border=palette.border,
        )

    def _on_item_updated(self, item: DownloadItem) -> None:
        previous = self._model.item_by_id(item.id)
        self._model.update_item(item)
        if (
            previous is not None
            and previous.status is not DownloadStatus.COMPLETED
            and item.status is DownloadStatus.COMPLETED
        ):
            self._notifier.notify_completed(item.filename)

    def _on_nav(self, key: str) -> None:
        if key == SETTINGS_KEY:
            self._pages.setCurrentWidget(self._settings_page)
            return
        self._downloads.set_filter(ViewFilter(key))
        self._pages.setCurrentWidget(self._downloads)

    def _update_counts(self, *_args) -> None:
        items = self._model.items()
        # Sidebar counts only change when a status changes, not on progress ticks.
        signature = tuple(item.status for item in items)
        if signature == self._counts_signature:
            return
        self._counts_signature = signature
        self._sidebar.set_counts({v: sum(1 for i in items if v.matches(i)) for v in ViewFilter})

    # ------------------------------------------------------------------ add

    def show_add_dialog(self) -> None:
        current = self._settings.get()
        dialog = AddDownloadDialog(
            self._theme, current.download_dir, current.start_immediately, self._add_download, self
        )
        dialog.exec()

    def _add_download(self, request: NewDownload) -> None:
        self._manager.add(
            request.url,
            request.directory,
            request.filename,
            start=request.start,
            scheduled_at=request.scheduled_at,
        )
        if self._downloads.view_filter is ViewFilter.COMPLETED or self._downloads.view_filter is ViewFilter.FAILED:
            self._sidebar.select(ViewFilter.ALL.value)

    # ---------------------------------------------------------------- close

    def _restore_geometry(self) -> None:
        encoded = self._settings.get().window_geometry
        if encoded:
            self.restoreGeometry(QByteArray.fromBase64(encoded.encode("ascii")))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        running = self._manager.active_count()
        if running:
            dialog = ConfirmDialog(
                self._theme, "Quit Omni Download Manager?",
                f"{running} download{'s are' if running != 1 else ' is'} in progress. "
                "They will be paused and can be resumed next time.",
                "Quit", parent=self,
            )
            if not dialog.exec():
                event.ignore()
                return
        try:
            geometry = bytes(self.saveGeometry().toBase64().data()).decode("ascii")
            self._settings.update(window_geometry=geometry)
        except (AppError, ValueError):
            logger.warning("Could not save window geometry", exc_info=True)
        self._bridge.close()
        self._notifier.close()
        event.accept()
