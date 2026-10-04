"""Custom painting of one download card.

Cards are painted rather than built from child widgets: it keeps scrolling smooth with
long histories and gives full control over the visual design. Text content comes from
``presentation`` and the available buttons from ``actions`` so this file only handles
geometry and drawing.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from omni_download_manager.core.filetypes import FileCategory, badge_label, categorize
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.ui.actions import ActionSpec, ItemAction, row_buttons
from omni_download_manager.ui.icons import icon_pixmap
from omni_download_manager.ui.models import ITEM_ROLE
from omni_download_manager.ui.presentation import (
    Tone,
    describe,
    is_indeterminate,
    percent_text,
    shows_progress_bar,
)
from omni_download_manager.ui.theme import Palette, ThemeManager

ROW_HEIGHT = 92
CARD_MARGIN_V = 4
CARD_MARGIN_RIGHT = 12
PADDING = 16
BADGE_SIZE = 44
BUTTON_SIZE = 32
BUTTON_GAP = 4
MAX_BUTTONS = 3
BAR_HEIGHT = 6
PERCENT_WIDTH = 46

S = DownloadStatus

CATEGORY_COLORS = {
    FileCategory.ARCHIVE: "#F5B544",
    FileCategory.VIDEO: "#B084FF",
    FileCategory.AUDIO: "#FF7AB6",
    FileCategory.IMAGE: "#3DD68C",
    FileCategory.DOCUMENT: "#5B8CFF",
    FileCategory.PROGRAM: "#FF8A5B",
    FileCategory.OTHER: "#9BA4B5",
}


def tone_color(palette: Palette, tone: Tone) -> QColor:
    return QColor(
        {
            Tone.ACCENT: palette.accent,
            Tone.SUCCESS: palette.success,
            Tone.WARNING: palette.warning,
            Tone.DANGER: palette.danger,
            Tone.MUTED: palette.text_muted,
        }[tone]
    )


class DownloadItemDelegate(QStyledItemDelegate):
    def __init__(self, theme: ThemeManager, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.hovered: tuple[str, ItemAction] | None = None
        self.pressed: tuple[str, ItemAction] | None = None

    # ------------------------------------------------------------- geometry

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), ROW_HEIGHT)

    @staticmethod
    def card_rect(row_rect: QRect) -> QRectF:
        return QRectF(row_rect).adjusted(0, CARD_MARGIN_V, -CARD_MARGIN_RIGHT, -CARD_MARGIN_V)

    def button_rects(self, row_rect: QRect, item: DownloadItem) -> list[tuple[ActionSpec, QRectF]]:
        card = self.card_rect(row_rect)
        specs = row_buttons(item)
        y = card.center().y() - BUTTON_SIZE / 2
        right = card.right() - 14
        result = []
        for position, spec in enumerate(specs):
            remaining = len(specs) - position
            x = right - remaining * BUTTON_SIZE - (remaining - 1) * BUTTON_GAP
            result.append((spec, QRectF(x, y, BUTTON_SIZE, BUTTON_SIZE)))
        return result

    def action_at(self, row_rect: QRect, item: DownloadItem, pos: QPointF) -> ActionSpec | None:
        for spec, rect in self.button_rects(row_rect, item):
            if rect.contains(pos):
                return spec
        return None

    # --------------------------------------------------------------- paint

    def paint(self, painter: QPainter, option, index) -> None:
        item: DownloadItem | None = index.data(ITEM_ROLE)
        if item is None:
            return
        palette = self._theme.palette
        card = self.card_rect(option.rect)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        text = describe(item)

        painter.save()
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )

        painter.setPen(QPen(QColor(palette.accent if selected else palette.border), 1))
        painter.setBrush(QColor(palette.surface_hover if hovered else palette.surface))
        painter.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)

        self._paint_badge(painter, card, item, palette)

        text_left = card.left() + PADDING + BADGE_SIZE + 14
        buttons_width = MAX_BUTTONS * BUTTON_SIZE + (MAX_BUTTONS - 1) * BUTTON_GAP
        text_right = card.right() - 14 - buttons_width - 16
        text_width = max(40.0, text_right - text_left)

        self._paint_title(painter, option.font, item, text_left, card.top() + 11, text_width, palette)
        self._paint_status_line(painter, option.font, text, text_left, card.top() + 34, text_width, palette)

        bottom = QRectF(text_left, card.top() + 56, text_width, 16)
        if shows_progress_bar(item):
            self._paint_progress(painter, option.font, item, bottom, palette)
        elif text.footer:
            self._paint_footer(painter, option.font, text.footer, text.footer_tone, bottom, palette)

        for spec, rect in self.button_rects(option.rect, item):
            self._paint_button(painter, item, spec, rect, palette)
        painter.restore()

    def _paint_badge(self, painter, card: QRectF, item: DownloadItem, palette: Palette) -> None:
        color = QColor(CATEGORY_COLORS[categorize(item.filename)])
        rect = QRectF(card.left() + PADDING, card.center().y() - BADGE_SIZE / 2, BADGE_SIZE, BADGE_SIZE)
        tint = QColor(color)
        tint.setAlpha(40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(tint)
        painter.drawRoundedRect(rect, 11, 11)

        font = QFont(painter.font())
        font.setPointSizeF(8.5)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(color)
        label = badge_label(item.filename)
        metrics = QFontMetrics(font)
        painter.drawText(
            QPointF(
                rect.center().x() - metrics.horizontalAdvance(label) / 2,
                rect.center().y() + (metrics.ascent() - metrics.descent()) / 2,
            ),
            label,
        )

    def _paint_title(self, painter, base_font: QFont, item, x, y, width, palette) -> None:
        font = QFont(base_font)
        font.setPointSizeF(base_font.pointSizeF() + 0.5)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(palette.text))
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(item.filename, Qt.TextElideMode.ElideMiddle, int(width))
        painter.drawText(QPointF(x, y + metrics.ascent() + 2), elided)

    def _paint_status_line(self, painter, base_font: QFont, text, x, y, width, palette) -> None:
        font = QFont(base_font)
        font.setPointSizeF(max(8.0, base_font.pointSizeF() - 0.5))
        metrics = QFontMetrics(font)
        baseline = y + metrics.ascent() + 1

        label_font = QFont(font)
        label_font.setWeight(QFont.Weight.DemiBold)
        label_metrics = QFontMetrics(label_font)
        painter.setFont(label_font)
        painter.setPen(tone_color(palette, text.tone))
        painter.drawText(QPointF(x, baseline), text.status)

        if text.detail:
            offset = label_metrics.horizontalAdvance(text.status) + 10
            painter.setFont(font)
            painter.setPen(QColor(palette.text_muted))
            detail = metrics.elidedText(text.detail, Qt.TextElideMode.ElideRight, int(max(0, width - offset)))
            painter.drawText(QPointF(x + offset, baseline), detail)

    def _paint_footer(self, painter, base_font: QFont, footer, tone, rect: QRectF, palette) -> None:
        font = QFont(base_font)
        font.setPointSizeF(max(8.0, base_font.pointSizeF() - 0.5))
        painter.setFont(font)
        color = QColor(palette.danger if tone is Tone.DANGER else palette.text_faint)
        painter.setPen(color)
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(footer, Qt.TextElideMode.ElideMiddle, int(rect.width()))
        painter.drawText(QPointF(rect.left(), rect.center().y() + (metrics.ascent() - metrics.descent()) / 2), elided)

    def _paint_progress(self, painter, base_font: QFont, item: DownloadItem, rect: QRectF, palette) -> None:
        track = QRectF(rect.left(), rect.center().y() - BAR_HEIGHT / 2, rect.width() - PERCENT_WIDTH, BAR_HEIGHT)
        fill_color = {
            S.PAUSED: QColor(palette.warning),
            S.PENDING: QColor(palette.text_faint),
        }.get(item.status, QColor(palette.accent))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette.track))
        painter.drawRoundedRect(track, BAR_HEIGHT / 2, BAR_HEIGHT / 2)
        painter.setBrush(fill_color)

        if is_indeterminate(item):
            clip = QPainterPath()
            clip.addRoundedRect(track, BAR_HEIGHT / 2, BAR_HEIGHT / 2)
            painter.save()
            painter.setClipPath(clip)
            segment = track.width() * 0.35
            phase = (time.monotonic() * 0.9) % 1.0
            x = track.left() - segment + phase * (track.width() + segment)
            painter.drawRoundedRect(QRectF(x, track.top(), segment, BAR_HEIGHT), BAR_HEIGHT / 2, BAR_HEIGHT / 2)
            painter.restore()
            return

        progress = item.progress or 0.0
        if progress > 0:
            width = max(BAR_HEIGHT, track.width() * progress)
            painter.drawRoundedRect(QRectF(track.left(), track.top(), width, BAR_HEIGHT), BAR_HEIGHT / 2, BAR_HEIGHT / 2)

        font = QFont(base_font)
        font.setPointSizeF(max(8.0, base_font.pointSizeF() - 0.5))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(palette.text_muted))
        metrics = QFontMetrics(font)
        label = percent_text(item)
        painter.drawText(
            QPointF(rect.right() - metrics.horizontalAdvance(label), rect.center().y() + (metrics.ascent() - metrics.descent()) / 2),
            label,
        )

    def _paint_button(self, painter, item: DownloadItem, spec: ActionSpec, rect: QRectF, palette: Palette) -> None:
        key = (item.id, spec.action)
        is_hover = self.hovered == key and spec.enabled
        is_pressed = self.pressed == key and spec.enabled
        if is_hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(palette.border if is_pressed else palette.surface_raised))
            painter.drawRoundedRect(rect, 8, 8)

        if not spec.enabled:
            color = palette.text_faint
        elif is_hover and spec.danger:
            color = palette.danger
        elif is_hover:
            color = palette.text
        else:
            color = palette.text_muted
        dpr = painter.device().devicePixelRatioF()
        pixmap = icon_pixmap(spec.icon, color, 18, dpr)
        painter.drawPixmap(QPointF(rect.center().x() - 9, rect.center().y() - 9), pixmap)
