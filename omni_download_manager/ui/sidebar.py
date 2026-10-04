"""Left navigation: logo, download views, settings."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from omni_download_manager.ui.icons import icon_pixmap
from omni_download_manager.ui.models import ViewFilter
from omni_download_manager.ui.theme import ThemeManager
from omni_download_manager.ui.widgets import make_label

SETTINGS_KEY = "settings"
_VIEW_ICONS = {
    ViewFilter.ALL: "list",
    ViewFilter.ACTIVE: "activity",
    ViewFilter.COMPLETED: "check",
    ViewFilter.FAILED: "alert",
}


class NavButton(QAbstractButton):
    def __init__(self, theme: ThemeManager, icon: str, text: str, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._icon = icon
        self._count: int | None = None
        self.setText(text)
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        theme.changed.connect(self.update)

    def set_count(self, count: int | None) -> None:
        self._count = count
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(180, 40)

    def paintEvent(self, event) -> None:  # noqa: N802
        palette = self._theme.palette
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        checked, hover = self.isChecked(), self.underMouse()

        if checked or hover:
            background = QColor(palette.accent) if checked else QColor(palette.surface_hover)
            if checked:
                background.setAlpha(40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(QRectF(self.rect()), 10, 10)

        color = palette.accent if checked else (palette.text if hover else palette.text_muted)
        painter.drawPixmap(QPointF(14, (self.height() - 18) / 2), icon_pixmap(self._icon, color, 18, self.devicePixelRatioF()))

        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold if checked else QFont.Weight.Medium)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        baseline = self.height() / 2 + (metrics.ascent() - metrics.descent()) / 2
        painter.setPen(QColor(palette.text if checked else color))
        painter.drawText(QPointF(44, baseline), self.text())

        if self._count:
            small = QFont(font)
            small.setPointSizeF(max(8.0, font.pointSizeF() - 1))
            painter.setFont(small)
            painter.setPen(QColor(palette.text_faint))
            label = str(self._count)
            painter.drawText(QPointF(self.width() - 14 - QFontMetrics(small).horizontalAdvance(label), baseline), label)


class Sidebar(QWidget):
    selected = Signal(str)  # a ViewFilter value or SETTINGS_KEY

    def __init__(self, theme: ThemeManager, app_name: str, version: str, logo, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(232)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self._buttons: dict[str, NavButton] = {}

        def add(key: str, icon: str, title: str) -> NavButton:
            button = NavButton(theme, icon, title)
            group.addButton(button)
            button.clicked.connect(lambda _=False, k=key: self.selected.emit(k))
            self._buttons[key] = button
            return button

        logo_label = QLabel()
        logo_label.setPixmap(logo.pixmap(32, 32))
        brand = QHBoxLayout()
        brand.setSpacing(12)
        brand.addWidget(logo_label)
        brand.addWidget(make_label(app_name, name="AppName"))
        brand.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 22, 16, 16)
        layout.setSpacing(4)
        layout.addLayout(brand)
        layout.addSpacing(26)
        for view in ViewFilter:
            layout.addWidget(add(view.value, _VIEW_ICONS[view], view.title if view is not ViewFilter.ALL else "All downloads"))
        layout.addStretch(1)
        layout.addWidget(add(SETTINGS_KEY, "sliders", "Settings"))
        layout.addSpacing(8)
        layout.addWidget(make_label(f"Version {version}", role="faint"))

        self._buttons[ViewFilter.ALL.value].setChecked(True)

    def set_counts(self, counts: dict[ViewFilter, int]) -> None:
        for view, count in counts.items():
            self._buttons[view.value].set_count(count)
