"""Bottom navigation for the download views."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

from omni_download_manager.ui.icons import icon_pixmap
from omni_download_manager.ui.models import ViewFilter
from omni_download_manager.ui.theme import ThemeManager

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
        self.setFixedHeight(54)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        theme.changed.connect(self.update)

    def set_count(self, count: int | None) -> None:
        self._count = count
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(180, 54)

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
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0, 1, 0, -1), 9, 9)

        color = palette.accent if checked else (palette.text if hover else palette.text_muted)
        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold if checked else QFont.Weight.Medium)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        baseline = self.height() / 2 + (metrics.ascent() - metrics.descent()) / 2
        icon_size = 18
        gap = 8
        label_width = metrics.horizontalAdvance(self.text())
        content_width = icon_size + gap + label_width
        content_left = max(12, (self.width() - content_width) / 2)
        painter.drawPixmap(
            QPointF(content_left, (self.height() - icon_size) / 2),
            icon_pixmap(self._icon, color, icon_size, self.devicePixelRatioF()),
        )
        painter.setPen(QColor(palette.text if checked else color))
        painter.drawText(QPointF(content_left + icon_size + gap, baseline), self.text())

        if self._count:
            # A small pill so the count reads as metadata, not as part of the label.
            small = QFont(font)
            small.setPointSizeF(max(8.0, font.pointSizeF() - 1))
            painter.setFont(small)
            small_metrics = QFontMetrics(small)
            label = str(self._count)
            pill_width = small_metrics.horizontalAdvance(label) + 14
            pill_height = 20
            pill = QRectF(
                self.width() - 16 - pill_width,
                (self.height() - pill_height) / 2,
                pill_width,
                pill_height,
            )
            pill_bg = QColor(palette.accent if checked else palette.surface_raised)
            if checked:
                pill_bg.setAlpha(70)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pill_bg)
            painter.drawRoundedRect(pill, pill_height / 2, pill_height / 2)
            painter.setPen(QColor(palette.text if checked else palette.text_faint))
            painter.drawText(
                pill,
                Qt.AlignmentFlag.AlignCenter,
                label,
            )


class BottomNavigation(QWidget):
    selected = Signal(str)

    def __init__(self, theme: ThemeManager, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomNavigation")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self._buttons: dict[str, NavButton] = {}

        def add(key: str, icon: str, title: str) -> NavButton:
            button = NavButton(theme, icon, title)
            group.addButton(button)
            button.clicked.connect(lambda _=False, k=key: self.selected.emit(k))
            self._buttons[key] = button
            return button

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(8)
        for view in ViewFilter:
            button = add(
                view.value,
                _VIEW_ICONS[view],
                view.title if view is not ViewFilter.ALL else "All downloads",
            )
            layout.addWidget(button, 1)

        self._buttons[ViewFilter.ALL.value].setChecked(True)

    def set_counts(self, counts: dict[ViewFilter, int]) -> None:
        for view, count in counts.items():
            self._buttons[view.value].set_count(count)

    def select(self, key: str) -> None:
        """Select a view from code, keeping the highlighted button in sync.

        ``selected.emit(...)`` alone only runs the slot; the checked state of the
        buttons changes on ``clicked``, so the highlight would go out of sync.
        """
        button = self._buttons.get(key)
        if button is not None:
            button.setChecked(True)
        self.selected.emit(key)
