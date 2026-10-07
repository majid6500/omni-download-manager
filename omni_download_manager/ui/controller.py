"""Turns user actions on a download card into manager calls and dialogs."""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QObject, QPoint
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMenu, QWidget

from omni_download_manager.config.settings import SettingsStore
from omni_download_manager.core.errors import AppError
from omni_download_manager.core.models import DownloadStatus
from omni_download_manager.services.download_manager import DownloadManager
from omni_download_manager.ui.actions import ItemAction, menu_actions
from omni_download_manager.ui.dialogs import ConfirmDialog, show_error
from omni_download_manager.ui.icons import make_icon
from omni_download_manager.ui.theme import ThemeManager
from omni_download_manager.utils.system import open_path

logger = logging.getLogger(__name__)


class ItemActionController(QObject):
    def __init__(
        self,
        manager: DownloadManager,
        settings: SettingsStore,
        theme: ThemeManager,
        window_provider: Callable[[], QWidget],
    ) -> None:
        super().__init__()
        self._manager = manager
        self._settings = settings
        self._theme = theme
        self._window = window_provider

    def report(self, exc: AppError, title: str = "Something went wrong") -> None:
        show_error(self._theme, self._window(), title, exc.user_message)

    def perform(self, action_value: str, item_id: str) -> None:
        try:
            self._perform(ItemAction(action_value), item_id)
        except AppError as exc:
            logger.warning("Action %s failed: %s", action_value, exc)
            self.report(exc)
        except Exception:
            logger.exception("Unexpected error performing %s", action_value)
            show_error(self._theme, self._window(), "Something went wrong",
                       "An unexpected error occurred. Details were written to the log.")

    def perform_bulk(self, action_value: str, item_ids: list[str]) -> None:
        action = ItemAction(action_value)
        items = []
        for item_id in dict.fromkeys(item_ids):
            try:
                items.append(self._manager.get_item(item_id))
            except AppError as exc:
                self.report(exc)
                return

        if action is ItemAction.PAUSE:
            targets = [
                item for item in items
                if (item.is_active or item.status is DownloadStatus.QUEUED)
                and item.resumable is not False
            ]
            operation = self._manager.pause
        elif action is ItemAction.RESUME:
            startable = {
                DownloadStatus.PENDING,
                DownloadStatus.PAUSED,
                DownloadStatus.FAILED,
                DownloadStatus.CANCELLED,
            }
            targets = [item for item in items if item.status in startable]
            operation = self._manager.start
        elif action is ItemAction.CANCEL:
            targets = [
                item for item in items
                if item.status not in (DownloadStatus.COMPLETED, DownloadStatus.CANCELLED)
            ]
            operation = self._manager.cancel
            if targets and self._settings.get().confirm_destructive_actions:
                dialog = ConfirmDialog(
                    self._theme,
                    "Cancel downloads?",
                    f"{len(targets)} download(s) will be cancelled and partial data deleted.",
                    "Cancel downloads",
                    danger=True,
                    parent=self._window(),
                )
                if not dialog.exec():
                    return
        elif action is ItemAction.REMOVE:
            targets = items
            completed_count = sum(item.status is DownloadStatus.COMPLETED for item in targets)
            dialog = ConfirmDialog(
                self._theme,
                "Remove downloads?",
                f"{len(targets)} download(s) will be removed from the list.",
                "Remove downloads",
                danger=True,
                option_text=(
                    f"Also delete {completed_count} completed file(s) from disk"
                    if completed_count else None
                ),
                parent=self._window(),
            )
            if not dialog.exec():
                return
            delete_completed = dialog.option_checked
            for item in targets:
                try:
                    self._manager.remove(
                        item.id,
                        delete_file=delete_completed and item.status is DownloadStatus.COMPLETED,
                    )
                except AppError as exc:
                    logger.warning("Bulk remove failed for %s: %s", item.id, exc)
            return
        else:
            raise ValueError(f"Unsupported bulk action: {action_value}")

        for item in targets:
            try:
                operation(item.id)
            except AppError as exc:
                logger.warning("Bulk action %s failed for %s: %s", action.value, item.id, exc)

    def _perform(self, action: ItemAction, item_id: str) -> None:
        manager = self._manager
        if action in (ItemAction.START, ItemAction.RESUME, ItemAction.RETRY):
            manager.start(item_id)
        elif action is ItemAction.PAUSE:
            manager.pause(item_id)
        elif action is ItemAction.CANCEL:
            self._cancel(item_id)
        elif action is ItemAction.REMOVE:
            self._remove(item_id)
        elif action is ItemAction.OPEN_FILE:
            item = manager.get_item(item_id)
            if item.status is DownloadStatus.COMPLETED:
                open_path(item.file_path)
        elif action is ItemAction.OPEN_FOLDER:
            item = manager.get_item(item_id)
            open_path(item.file_path.parent)
        elif action is ItemAction.COPY_URL:
            QGuiApplication.clipboard().setText(manager.get_item(item_id).url)

    def _confirm_needed(self) -> bool:
        return self._settings.get().confirm_destructive_actions

    def _cancel(self, item_id: str) -> None:
        item = self._manager.get_item(item_id)
        if item.downloaded_bytes > 0 and self._confirm_needed():
            dialog = ConfirmDialog(
                self._theme, "Cancel download?",
                "The part that was already downloaded will be deleted.",
                "Cancel download", danger=True, parent=self._window(),
            )
            if not dialog.exec():
                return
        self._manager.cancel(item_id)

    def _remove(self, item_id: str) -> None:
        item = self._manager.get_item(item_id)
        completed = item.status is DownloadStatus.COMPLETED
        delete_file = False
        if self._confirm_needed() or completed:
            dialog = ConfirmDialog(
                self._theme, "Remove from list?",
                f"“{item.filename}” will be removed from the list."
                + ("" if completed else " Unfinished data will be deleted."),
                "Remove", danger=True,
                option_text="Also delete the file from disk" if completed else None,
                parent=self._window(),
            )
            if not dialog.exec():
                return
            delete_file = dialog.option_checked
        self._manager.remove(item_id, delete_file=delete_file)

    def show_menu(self, item_id: str, global_pos: QPoint) -> None:
        try:
            item = self._manager.get_item(item_id)
        except AppError:
            return
        palette = self._theme.palette
        menu = QMenu(self._window())
        for entry in menu_actions(item):
            if entry is None:
                menu.addSeparator()
                continue
            color = palette.danger if entry.danger else palette.text_muted
            action = menu.addAction(make_icon(entry.icon, color, 16), entry.label)
            action.setEnabled(entry.enabled)
            action.triggered.connect(
                lambda _checked=False, a=entry.action.value: self.perform(a, item_id)
            )
        menu.exec(global_pos)
