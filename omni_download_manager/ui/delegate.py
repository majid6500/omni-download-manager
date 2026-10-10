"""Custom painting of one download card.

Cards are painted rather than built from child widgets: it keeps scrolling smooth with
long histories and gives full control over the visual design. Text content comes from
``presentation`` so this file only handles geometry and drawing. Actions live in the
fixed toolbar, not on the card.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from omni_download_manager.core.filetypes import FileCategory, badge_label, categorize
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.ui.models import ITEM_ROLE
from omni_download_manager.ui.presentation import (
    CardText,
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
CARD_RADIUS = 8
PADDING = 16
BADGE_SIZE = 44
BAR_HEIGHT = 8
PERCENT_WIDTH = 46
PILL_HEIGHT = 20
PILL_RADIUS = 6

# Vertical anchors inside the card.
TITLE_TOP = 11
DETAIL_TOP = 34
BOTTOM_TOP = 56

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

    # ------------------------------------------------------------- geometry

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), ROW_HEIGHT)

    @staticmethod
    def card_rect(row_rect: QRect) -> QRectF:
        return QRectF(row_rect).adjusted(0, CARD_MARGIN_V, -CARD_MARGIN_RIGHT, -CARD_MARGIN_V)

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

        self._paint_card(painter, card, selected, hovered, palette)
        self._paint_badge(painter, card, item, palette)

        text_left = card.left() + PADDING + BADGE_SIZE + 14
        text_right = card.right() - PADDING
        pill, pill_width = self._pill_rect(option.font, text, text_right, card.top())
        # Title stops short of the status pill so long names never run underneath it.
        text_width = max(40.0, text_right - pill_width - 12 - text_left)
        if pill is None:
            text_width = max(40.0, text_right - text_left)

        self._paint_title(painter, option.font, item, text_left, card.top() + TITLE_TOP, text_width, palette)
        if pill is not None:
            self._paint_pill(painter, option.font, text, pill, palette)
        if text.detail:
            self._paint_detail(
                painter, option.font, text.detail, text_left, card.top() + DETAIL_TOP,
                text_right - text_left, palette,
            )

        bottom = QRectF(text_left, card.top() + BOTTOM_TOP, text_right - text_left, 16)
        if shows_progress_bar(item):
            self._paint_progress(painter, option.font, item, bottom, palette)
        elif text.footer:
            self._paint_footer(painter, option.font, text.footer, text.footer_tone, bottom, palette)
        painter.restore()

    def _paint_card(self, painter, card: QRectF, selected: bool, hovered: bool, palette: Palette) -> None:
        background = QColor(palette.surface_hover if hovered else palette.surface)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(card, CARD_RADIUS, CARD_RADIUS)
        if selected:
            overlay = QColor(palette.accent)
            overlay.setAlpha(20)
            painter.setBrush(overlay)
            painter.drawRoundedRect(card, CARD_RADIUS, CARD_RADIUS)
        painter.setPen(QPen(QColor(palette.accent if selected else palette.border), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), CARD_RADIUS, CARD_RADIUS)

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

    # ---------------------------------------------------------------- status

    @staticmethod
    def _pill_font(base_font: QFont) -> QFont:
        font = QFont(base_font)
        font.setPointSizeF(max(8.0, base_font.pointSizeF() - 0.5))
        font.setWeight(QFont.Weight.DemiBold)
        return font

    def _pill_rect(
        self, base_font: QFont, text: CardText, right: float, card_top: float
    ) -> tuple[QRectF | None, float]:
        """Right-aligned status pill for the title row; ``None`` when there is no status."""
        if not text.status:
            return None, 0.0
        metrics = QFontMetrics(self._pill_font(base_font))
        width = float(metrics.horizontalAdvance(text.status) + 16)
        return QRectF(right - width, card_top + 8, width, PILL_HEIGHT), width

    def _paint_pill(self, painter, base_font: QFont, text: CardText, rect: QRectF, palette: Palette) -> None:
        color = tone_color(palette, text.tone)
        fill = QColor(color)
        fill.setAlpha(32)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, PILL_RADIUS, PILL_RADIUS)

        font = self._pill_font(base_font)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(
            QRectF(rect.left(), rect.top(), rect.width(), rect.height()),
            Qt.AlignmentFlag.AlignCenter,
            text.status,
        )

    def _paint_detail(self, painter, base_font: QFont, detail, x, y, width, palette) -> None:
        font = QFont(base_font)
        font.setPointSizeF(max(8.0, base_font.pointSizeF() - 0.5))
        painter.setFont(font)
        painter.setPen(QColor(palette.text_muted))
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(detail, Qt.TextElideMode.ElideRight, int(width))
        painter.drawText(QPointF(x, y + metrics.ascent() + 1), elided)

    def _paint_footer(self, painter, base_font: QFont, footer, tone, rect: QRectF, palette) -> None:
        font = QFont(base_font)
        font.setPointSizeF(max(8.0, base_font.pointSizeF() - 0.5))
        painter.setFont(font)
        color = QColor(palette.danger if tone is Tone.DANGER else palette.text_faint)
        painter.setPen(color)
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(footer, Qt.TextElideMode.ElideMiddle, int(rect.width()))
        painter.drawText(
            QPointF(rect.left(), rect.center().y() + (metrics.ascent() - metrics.descent()) / 2),
            elided,
        )

    # -------------------------------------------------------------- progress

    def _paint_progress(self, painter, base_font: QFont, item: DownloadItem, rect: QRectF, palette: Palette) -> None:
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
            self._paint_percent(painter, base_font, item, rect, palette)
            return

        fills = item.segment_fill
        if fills and len(fills) >= 2:
            self._paint_segmented_bar(
                painter,
                track,
                fills,
                fill_color,
                palette,
                retries=item.segment_retries,
                stalled=item.segment_stalled,
            )
        else:
            progress = item.progress or 0.0
            if progress > 0:
                width = max(BAR_HEIGHT, track.width() * progress)
                painter.drawRoundedRect(
                    QRectF(track.left(), track.top(), width, BAR_HEIGHT), BAR_HEIGHT / 2, BAR_HEIGHT / 2
                )
        self._paint_percent(painter, base_font, item, rect, palette)

    def _paint_percent(self, painter, base_font: QFont, item: DownloadItem, rect: QRectF, palette: Palette) -> None:
        font = QFont(base_font)
        font.setPointSizeF(max(8.0, base_font.pointSizeF() - 0.5))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(palette.text_muted))
        metrics = QFontMetrics(font)
        label = percent_text(item)
        painter.drawText(
            QPointF(
                rect.right() - metrics.horizontalAdvance(label),
                rect.center().y() + (metrics.ascent() - metrics.descent()) / 2,
            ),
            label,
        )

    def _paint_segmented_bar(
        self,
        painter: QPainter,
        track: QRectF,
        fills: tuple[float, ...],
        fill_color: QColor,
        palette: Palette,
        retries: tuple[int, ...] | None = None,
        stalled: tuple[bool, ...] | None = None,
    ) -> None:
        """Paint a segmented progress bar where each slot represents one download segment.

        The visual indicates per-segment fill fraction and optional status hints:
        - stalled segments are drawn in the danger color
        - segments with retry attempts are drawn in the warning color and show a small retry count
        """
        count = len(fills)
        gap = 1.0
        total_gap = gap * (count - 1)
        slot = max(1.0, (track.width() - total_gap) / count)
        x = track.left()
        for index, fill in enumerate(fills):
            slot_rect = QRectF(x, track.top(), slot, BAR_HEIGHT)
            # Reset the pen every slot: the retry badge below changes it.
            painter.setPen(Qt.PenStyle.NoPen)
            # Background for the slot
            painter.setBrush(QColor(palette.surface_raised))
            painter.drawRoundedRect(slot_rect, 2, 2)

            if fill > 0:
                inner_w = max(1.0, slot * min(1.0, fill))
                # Choose color according to status hints: stalled > retry > normal
                seg_color = fill_color
                if stalled and index < len(stalled) and stalled[index]:
                    seg_color = QColor(palette.danger)
                elif retries and index < len(retries) and retries[index] > 0:
                    seg_color = QColor(palette.warning)
                painter.setBrush(seg_color)
                painter.drawRoundedRect(
                    QRectF(slot_rect.left(), slot_rect.top(), inner_w, BAR_HEIGHT), 2, 2
                )

                # If there are retry attempts, draw a small count overlay if there's space
                retry_count = (retries[index] if (retries and index < len(retries)) else 0)
                if retry_count:
                    # Small badge at the right of the segment slot
                    badge_w = min(18.0, slot * 0.35)
                    badge_h = max(10.0, BAR_HEIGHT - 2)
                    bx = slot_rect.right() - badge_w - 2
                    by = slot_rect.top() + (BAR_HEIGHT - badge_h) / 2
                    badge_rect = QRectF(bx, by, badge_w, badge_h)
                    painter.setBrush(QColor(palette.surface_raised))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(badge_rect, 2, 2)
                    # small number
                    font = QFont(painter.font())
                    font.setPointSizeF(max(6.0, painter.font().pointSizeF() - 2))
                    painter.setFont(font)
                    painter.setPen(QColor(palette.warning))
                    metrics = QFontMetrics(font)
                    label = str(retry_count)
                    painter.drawText(
                        QPointF(badge_rect.center().x() - metrics.horizontalAdvance(label) / 2,
                                badge_rect.center().y() + (metrics.ascent() - metrics.descent()) / 2),
                        label,
                    )
            x += slot + gap
