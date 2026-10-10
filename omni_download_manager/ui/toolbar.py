"""The fixed toolbar above the download list.

Actions live here instead of on every card: the toolbar shows what the current
selection allows and stays visible all the time. Enable/disable rules come from
:func:`omni_download_manager.ui.actions.toolbar_specs`, so the buttons can never
offer something the controller would reject.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from omni_download_manager.constants import APP_NAME
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.ui.actions import ActionSpec, ItemAction, toolbar_specs
from omni_download_manager.ui.icons import logo_icon, make_icon
from omni_download_manager.ui.theme import ThemeManager
from omni_download_manager.ui.widgets import make_label

TOOLBAR_ICON_SIZE = 28
TOOLBAR_BUTTON_SIZE = 46
TOOLBAR_ICON_COLOR = "#00d9ff"
REMOVE_ICON_COLOR = "#fc037f"
ADD_ICON_COLOR = "#25cf0e"
ADD_SHORTCUT = "Ctrl+N"


class ToolButton(QPushButton):
    """Icon-only toolbar button that re-tints its icon for state and theme."""

    def __init__(self, theme: ThemeManager, spec: ActionSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._spec = spec
        self._tint: str | None = None
        self.setProperty("variant", "tool")
        if spec.action is ItemAction.REMOVE:
            self.setProperty("variant", "tool-plain")
        self.setToolTip(spec.tooltip)
        self.setAccessibleName(spec.label)
        self.setFixedSize(TOOLBAR_BUTTON_SIZE, TOOLBAR_BUTTON_SIZE)
        self.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        theme.changed.connect(self.update)

    @property
    def action(self) -> ItemAction:
        return self._spec.action

    def _color(self) -> str:
        palette = self._theme.palette
        if self._spec.action is ItemAction.REMOVE:
            return REMOVE_ICON_COLOR
        if not self.isEnabled():
            return palette.text_faint
        if self.property("variant") == "tool-primary":
            return palette.accent_text
        return TOOLBAR_ICON_COLOR

    def paintEvent(self, event) -> None:  # noqa: N802
        color = self._color()
        if color != self._tint:  # only rebuild when the tint actually changes
            self._tint = color
            self.setIcon(make_icon(self._spec.icon, color, TOOLBAR_ICON_SIZE))
        super().paintEvent(event)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        super().setEnabled(enabled)
        self._tint = None  # repaint with the disabled colour


class Toolbar(QFrame):
    """Fixed action bar: Add Download, selection actions and open shortcuts."""

    addRequested = Signal()
    settingsRequested = Signal()
    actionRequested = Signal(str, str)  # (ItemAction value, download id)
    bulkActionRequested = Signal(str, object)  # (ItemAction value, list of ids)

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Toolbar")
        self._theme = theme
        self._items: list[DownloadItem] = []

        self._add = QPushButton()
        self._add.setProperty("variant", "tool-plain")
        self._add.setIcon(make_icon("add-02", ADD_ICON_COLOR, TOOLBAR_ICON_SIZE))
        self._add.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        self._add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add.setAccessibleName("Add download")
        self._add.setToolTip(f"Add a download ({ADD_SHORTCUT})")
        self._add.setShortcut(ADD_SHORTCUT)
        self._add.setFixedSize(TOOLBAR_BUTTON_SIZE, TOOLBAR_BUTTON_SIZE)
        self._add.clicked.connect(self.addRequested)
        theme.changed.connect(self._update_add_icon)

        self._buttons: dict[ItemAction, ToolButton] = {}
        specs = toolbar_specs([])
        for spec in specs:
            button = ToolButton(theme, spec)
            button.setEnabled(spec.enabled)
            button.clicked.connect(lambda _=False, a=spec.action: self._on_action(a))
            self._buttons[spec.action] = button

        self._settings = QPushButton()
        self._settings.setProperty("variant", "tool")
        self._settings.setIcon(make_icon("settings-02", TOOLBAR_ICON_COLOR, TOOLBAR_ICON_SIZE))
        self._settings.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        self._settings.setFixedSize(TOOLBAR_BUTTON_SIZE, TOOLBAR_BUTTON_SIZE)
        self._settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings.setAccessibleName("Settings")
        self._settings.setToolTip("Settings")
        self._settings.clicked.connect(self.settingsRequested)
        theme.changed.connect(self._update_settings_icon)

        self._brand = QWidget()
        self._brand.setAccessibleName(APP_NAME)
        brand_layout = QHBoxLayout(self._brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(8)
        brand_layout.addWidget(make_label(APP_NAME, name="PageTitle"))
        logo = QLabel()
        logo.setPixmap(logo_icon().pixmap(QSize(28, 28)))
        logo.setFixedSize(28, 28)
        logo.setAccessibleName(f"{APP_NAME} logo")
        brand_layout.addWidget(logo)

        self._count = make_label(role="muted", name="SelectionCount")
        self._count.setMinimumWidth(0)  # an idle toolbar must not force the window wide
        self._count.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

        row = QHBoxLayout()
        row.setContentsMargins(20, 14, 20, 14)
        row.setSpacing(6)
        row.addWidget(self._add)
        for action in (
            ItemAction.RESUME, ItemAction.PAUSE, ItemAction.RETRY, ItemAction.CANCEL,
            ItemAction.REMOVE, ItemAction.OPEN_FOLDER, ItemAction.OPEN_FILE,
        ):
            row.addWidget(self._buttons[action])
        row.addWidget(self._settings)
        row.addWidget(self._count)
        row.addStretch(1)
        row.addWidget(self._brand)
        self.setLayout(row)

    # ------------------------------------------------------------------ state

    def set_selection(self, items: list[DownloadItem]) -> None:
        """Refresh every button from the downloads currently selected in the list."""
        self._items = list(items)
        for spec in toolbar_specs(self._items):
            self._buttons[spec.action].setEnabled(spec.enabled)
        self._count.setText(f"{len(self._items)} selected" if self._items else "")

    # ------------------------------------------------------------------ input

    def _on_action(self, action: ItemAction) -> None:
        if not self._items:
            return
        if len(self._items) == 1:
            item = self._items[0]
            if action is ItemAction.RESUME and item.status in (
                DownloadStatus.PENDING,
                DownloadStatus.QUEUED,
            ):
                action = ItemAction.START
            self.actionRequested.emit(action.value, item.id)
            return
        self.bulkActionRequested.emit(action.value, [item.id for item in self._items])

    def _update_add_icon(self) -> None:
        self._add.setIcon(make_icon("add-02", ADD_ICON_COLOR, TOOLBAR_ICON_SIZE))

    def _update_settings_icon(self) -> None:
        self._settings.setIcon(make_icon("settings-02", TOOLBAR_ICON_COLOR, TOOLBAR_ICON_SIZE))
