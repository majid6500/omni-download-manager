"""Modal dialogs: add download, confirmation and error."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDateTimeEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from omni_download_manager.core.errors import AppError
from omni_download_manager.ui.theme import ThemeManager
from omni_download_manager.ui.widgets import Toggle, make_label
from omni_download_manager.ui.windows_effects import apply_title_bar_theme
from omni_download_manager.utils.urls import validate_url


def _button(text: str, variant: str | None = None) -> QPushButton:
    button = QPushButton(text)
    if variant:
        button.setProperty("variant", variant)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class ThemedDialog(QDialog):
    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        theme.changed.connect(self._on_theme_changed)

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


@dataclass(frozen=True)
class NewDownload:
    url: str
    directory: str
    filename: str | None
    start: bool
    scheduled_at: float | None = None


class AddDownloadDialog(ThemedDialog):
    """Collects a new download. ``submit`` performs the real work and may raise
    ``AppError``; its message is shown inline and the dialog stays open."""

    def __init__(
        self,
        theme: ThemeManager,
        default_directory: str,
        start_immediately: bool,
        submit: Callable[[NewDownload], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(theme, parent)
        self._submit = submit
        self.setWindowTitle("Add download")
        self.setModal(True)
        self.setMinimumWidth(540)

        self._url = QLineEdit()
        self._url.setPlaceholderText("https://example.com/file.zip")
        self._url.setClearButtonEnabled(True)
        self._directory = QLineEdit(default_directory)
        self._filename = QLineEdit()
        self._filename.setPlaceholderText("Detected automatically")
        browse = _button("Browse…")
        browse.clicked.connect(self._browse)
        self._start = Toggle(theme, "Start downloading immediately")
        self._start.setChecked(start_immediately)
        self._schedule_enabled = Toggle(theme, "Schedule start")
        self._schedule_time = QDateTimeEdit(QDateTime.currentDateTime().addSecs(60))
        self._schedule_time.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._schedule_time.setCalendarPopup(True)
        self._schedule_time.setMinimumDateTime(QDateTime.currentDateTime().addSecs(60))
        self._schedule_time.setEnabled(False)
        self._schedule_enabled.toggled.connect(self._on_schedule_toggled)
        self._error = make_label(role="error", wrap=True)
        self._error.hide()

        cancel = _button("Cancel", "ghost")
        cancel.clicked.connect(self.reject)
        self._add = _button("Add download", "primary")
        self._add.setDefault(True)
        self._add.clicked.connect(self._on_add)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self._directory, 1)
        folder_row.addWidget(browse)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self._add)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(6)
        layout.addWidget(make_label("Add download", name="PageTitle"))
        layout.addSpacing(10)
        layout.addWidget(make_label("Link", role="muted"))
        layout.addWidget(self._url)
        layout.addSpacing(8)
        layout.addWidget(make_label("Save to", role="muted"))
        layout.addLayout(folder_row)
        layout.addSpacing(8)
        layout.addWidget(make_label("File name (optional)", role="muted"))
        layout.addWidget(self._filename)
        layout.addSpacing(12)
        layout.addWidget(self._start)
        layout.addWidget(self._schedule_enabled)
        layout.addWidget(self._schedule_time)
        layout.addWidget(self._error)
        layout.addSpacing(14)
        layout.addLayout(buttons)

        self._prefill_from_clipboard()
        self._url.setFocus()

    def _prefill_from_clipboard(self) -> None:
        text = (QGuiApplication.clipboard().text() or "").strip()
        try:
            self._url.setText(validate_url(text))
            self._url.selectAll()
        except AppError:
            pass

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose download folder", self._directory.text())
        if chosen:
            self._directory.setText(str(Path(chosen)))

    def _on_schedule_toggled(self, enabled: bool) -> None:
        self._schedule_time.setEnabled(enabled)
        self._start.setEnabled(not enabled)

    def _on_add(self) -> None:
        scheduled_at = (
            float(self._schedule_time.dateTime().toSecsSinceEpoch())
            if self._schedule_enabled.isChecked()
            else None
        )
        request = NewDownload(
            url=self._url.text(),
            directory=self._directory.text().strip(),
            filename=self._filename.text().strip() or None,
            start=self._start.isChecked() and scheduled_at is None,
            scheduled_at=scheduled_at,
        )
        try:
            self._submit(request)
        except AppError as exc:
            self._error.setText(exc.user_message)
            self._error.show()
            return
        self.accept()


class ConfirmDialog(ThemedDialog):
    def __init__(
        self,
        theme: ThemeManager,
        title: str,
        message: str,
        confirm_text: str,
        *,
        danger: bool = False,
        option_text: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(theme, parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)

        body = QLabel(message)
        body.setWordWrap(True)
        body.setProperty("role", "muted")
        self._option = Toggle(theme, option_text) if option_text else None

        cancel = _button("Cancel", "ghost")
        cancel.clicked.connect(self.reject)
        confirm = _button(confirm_text, "danger" if danger else "primary")
        confirm.clicked.connect(self.accept)
        confirm.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)
        layout.addWidget(make_label(title, name="SectionTitle"))
        layout.addWidget(body)
        if self._option is not None:
            layout.addSpacing(4)
            layout.addWidget(self._option)
        layout.addSpacing(10)
        layout.addLayout(buttons)

    @property
    def option_checked(self) -> bool:
        return self._option is not None and self._option.isChecked()


def show_error(theme: ThemeManager, parent: QWidget | None, title: str, message: str) -> None:
    _show_message(theme, parent, title, message, "OK", "error")


def show_information(theme: ThemeManager, parent: QWidget | None, title: str, message: str) -> None:
    _show_message(theme, parent, title, message, "OK", "muted")


def _show_message(
    theme: ThemeManager,
    parent: QWidget | None,
    title: str,
    message: str,
    button_text: str,
    message_role: str,
) -> None:
    dialog = ThemedDialog(theme, parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumWidth(400)
    body = QLabel(message)
    body.setWordWrap(True)
    body.setProperty("role", message_role)
    ok = _button(button_text, "primary")
    ok.clicked.connect(dialog.accept)
    ok.setDefault(True)
    row = QHBoxLayout()
    row.addStretch(1)
    row.addWidget(ok)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(10)
    layout.addWidget(make_label(title, name="SectionTitle"))
    layout.addWidget(body)
    layout.addSpacing(10)
    layout.addLayout(row)
    dialog.exec()
