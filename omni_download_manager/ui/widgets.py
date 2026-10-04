"""Small reusable widgets."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QWidget

from omni_download_manager.ui.theme import ThemeManager

TRACK_WIDTH = 40
TRACK_HEIGHT = 22
KNOB = 16


class Toggle(QCheckBox):
    """An animated on/off switch, drawn with the active theme's colours."""

    def __init__(self, theme: ThemeManager, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._theme = theme
        self._offset = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._on_toggled)
        theme.changed.connect(self.update)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _on_toggled(self, checked: bool) -> None:
        target = 1.0 if checked else 0.0
        if not self.isVisible():
            self._set_offset(target)
            return
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(target)
        self._animation.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 (Qt naming)
        super().setChecked(checked)
        self._set_offset(1.0 if checked else 0.0)

    def sizeHint(self) -> QSize:  # noqa: N802
        text_width = self.fontMetrics().horizontalAdvance(self.text()) + 10 if self.text() else 0
        return QSize(TRACK_WIDTH + text_width, max(TRACK_HEIGHT, self.fontMetrics().height()) + 4)

    def hitButton(self, pos) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:  # noqa: N802
        palette = self._theme.palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = (self.height() - TRACK_HEIGHT) / 2

        off, on = QColor(palette.border_strong), QColor(palette.accent)
        mix = self._offset
        track = QColor(
            int(off.red() + (on.red() - off.red()) * mix),
            int(off.green() + (on.green() - off.green()) * mix),
            int(off.blue() + (on.blue() - off.blue()) * mix),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, top, TRACK_WIDTH, TRACK_HEIGHT), TRACK_HEIGHT / 2, TRACK_HEIGHT / 2)

        margin = (TRACK_HEIGHT - KNOB) / 2
        knob_x = margin + self._offset * (TRACK_WIDTH - KNOB - 2 * margin)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(knob_x, top + margin, KNOB, KNOB))

        if self.text():
            painter.setPen(QColor(palette.text))
            baseline = self.height() / 2 + (self.fontMetrics().ascent() - self.fontMetrics().descent()) / 2
            painter.drawText(TRACK_WIDTH + 10, int(baseline), self.text())


def make_label(text: str = "", *, role: str | None = None, name: str | None = None, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


def make_divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.Shape.NoFrame)
    return line
