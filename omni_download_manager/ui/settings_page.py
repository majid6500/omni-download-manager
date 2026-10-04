"""Settings page. Changes apply and are saved immediately."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QDoubleSpinBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from omni_download_manager.config.paths import AppPaths
from omni_download_manager.config.settings import SettingsStore
from omni_download_manager.core.errors import AppError
from omni_download_manager.ui.dialogs import show_error
from omni_download_manager.ui.theme import ThemeManager
from omni_download_manager.ui.widgets import Toggle, make_divider, make_label
from omni_download_manager.utils.system import open_path


class SettingsPage(QWidget):
    def __init__(self, store: SettingsStore, theme: ThemeManager, paths: AppPaths, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self._store, self._theme, self._paths = store, theme, paths
        current = store.get()

        self._folder = QLineEdit(current.download_dir)
        self._folder.setReadOnly(True)
        browse = self._button("Change…")
        browse.clicked.connect(self._choose_folder)
        folder_box = QHBoxLayout()
        folder_box.setSpacing(8)
        folder_box.addWidget(self._folder, 1)
        folder_box.addWidget(browse)
        folder_widget = QWidget()
        folder_widget.setLayout(folder_box)
        folder_widget.setMinimumWidth(340)
        folder_box.setContentsMargins(0, 0, 0, 0)

        start = Toggle(theme)
        start.setChecked(current.start_immediately)
        start.toggled.connect(lambda v: self._save(start_immediately=v))
        confirm = Toggle(theme)
        confirm.setChecked(current.confirm_destructive_actions)
        confirm.toggled.connect(lambda v: self._save(confirm_destructive_actions=v))
        notifications = Toggle(theme)
        notifications.setChecked(current.completion_notifications_enabled)
        notifications.toggled.connect(
            lambda v: self._save(completion_notifications_enabled=v)
        )

        self._theme_buttons: dict[str, QPushButton] = {}
        theme_box = QHBoxLayout()
        theme_box.setSpacing(8)
        for name, label in (("dark", "Dark"), ("light", "Light")):
            button = self._button(label, "segment")
            button.setCheckable(True)
            button.setChecked(current.theme == name)
            button.clicked.connect(lambda _=False, n=name: self._set_theme(n))
            self._theme_buttons[name] = button
            theme_box.addWidget(button)
        theme_widget = QWidget()
        theme_widget.setLayout(theme_box)
        theme_box.setContentsMargins(0, 0, 0, 0)

        connect = self._spin(current.connect_timeout, "connect_timeout")
        read = self._spin(current.read_timeout, "read_timeout")
        speed_limit = self._speed_spin(current.max_download_speed_mib)
        system_proxy = Toggle(theme)
        system_proxy.setChecked(current.use_system_proxy)
        system_proxy.setObjectName("SystemProxyToggle")
        system_proxy.toggled.connect(lambda v: self._save(use_system_proxy=v))

        open_data = self._button("Open data folder")
        open_data.clicked.connect(lambda: self._open(paths.data_dir))
        open_logs = self._button("Open logs folder")
        open_logs.clicked.connect(lambda: self._open(paths.log_dir))
        tools_box = QHBoxLayout()
        tools_box.setSpacing(8)
        tools_box.addWidget(open_data)
        tools_box.addWidget(open_logs)
        tools_widget = QWidget()
        tools_widget.setLayout(tools_box)
        tools_box.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        content.setObjectName("SettingsContent")
        column = QVBoxLayout(content)
        column.setContentsMargins(32, 28, 32, 28)
        column.setSpacing(18)
        column.addWidget(make_label("Settings", name="PageTitle"))
        column.addWidget(make_label("Changes are saved automatically.", role="muted"))
        column.addSpacing(6)
        column.addWidget(self._card("Downloads", [
            ("Default download folder", "Where new downloads are saved.", folder_widget),
            ("Start immediately", "Begin downloading as soon as a link is added.", start),
            ("Confirm before removing", "Ask before cancelling or removing a download.", confirm),
        ]))
        column.addWidget(self._card("Appearance", [("Theme", "Choose how Omni Download Manager looks.", theme_widget)]))
        column.addWidget(self._card("Notifications", [
            ("Download complete", "Show a native Windows notification when a download finishes.", notifications),
        ]))
        column.addWidget(self._card("Network", [
            ("Connection timeout", "How long to wait for a server to answer.", connect),
            ("Read timeout", "How long to wait for data before giving up.", read),
            ("Use system proxy", "Use the proxy configured by Windows or the environment.", system_proxy),
            ("Maximum total speed", "Shared by all downloads. Unlimited by default.", speed_limit),
        ]))
        column.addWidget(self._card("Storage", [
            ("Application data", str(paths.data_dir), tools_widget),
        ]))
        column.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    @staticmethod
    def _button(text: str, variant: str | None = None) -> QPushButton:
        button = QPushButton(text)
        if variant:
            button.setProperty("variant", variant)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _spin(self, value: float, key: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 300)
        spin.setSuffix(" s")
        spin.setValue(int(value))
        spin.setFixedWidth(100)
        spin.editingFinished.connect(lambda: self._save(**{key: float(spin.value())}))
        return spin

    def _speed_spin(self, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 1000)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setSpecialValueText("Unlimited")
        spin.setSuffix(" MiB/s")
        spin.setValue(value)
        spin.setFixedWidth(140)
        spin.editingFinished.connect(
            lambda: self._save(max_download_speed_mib=spin.value())
        )
        return spin

    def _card(self, title: str, rows: list[tuple[str, str, QWidget]]) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(make_label(title, name="SectionTitle"))
        for position, (name, description, control) in enumerate(rows):
            if position:
                layout.addWidget(make_divider())
            row = QHBoxLayout()
            row.setSpacing(24)
            texts = QVBoxLayout()
            texts.setSpacing(2)
            texts.addWidget(make_label(name))
            texts.addWidget(make_label(description, role="muted", wrap=True))
            row.addLayout(texts, 1)
            row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addLayout(row)
        return card

    def _save(self, **changes) -> None:
        try:
            self._store.update(**changes)
        except (AppError, ValueError) as exc:
            message = exc.user_message if isinstance(exc, AppError) else str(exc)
            show_error(self._theme, self.window(), "Settings", message)

    def _choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Default download folder", self._folder.text())
        if chosen:
            self._folder.setText(chosen)
            self._save(download_dir=chosen)

    def _set_theme(self, name: str) -> None:
        for key, button in self._theme_buttons.items():
            button.setChecked(key == name)
        self._theme.set_theme(name)
        self._save(theme=name)

    def _open(self, path: Path) -> None:
        try:
            path.mkdir(parents=True, exist_ok=True)
            open_path(path)
        except (AppError, OSError) as exc:
            message = exc.user_message if isinstance(exc, AppError) else str(exc)
            show_error(self._theme, self.window(), "Open folder", message)
