"""The scrolling list of download cards, with hover/click handling for card buttons."""

from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QPoint,
    QPointF,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QAbstractItemView, QFrame, QListView, QToolTip

from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.ui.actions import ActionSpec, ItemAction
from omni_download_manager.ui.delegate import DownloadItemDelegate
from omni_download_manager.ui.models import ITEM_ROLE
from omni_download_manager.ui.theme import ThemeManager


class DownloadListView(QListView):
    actionRequested = Signal(str, str)  # (ItemAction value, download id)

    def __init__(self, theme: ThemeManager, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DownloadList")
        self._delegate = DownloadItemDelegate(theme, self)
        self.setItemDelegate(self._delegate)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.verticalScrollBar().setSingleStep(24)
        theme.changed.connect(self.viewport().update)
        self._selection_click_handled = False

        # Drives the indeterminate progress animation only while it is needed.
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(40)
        self._animation_timer.timeout.connect(self.viewport().update)

    def set_animated(self, animated: bool) -> None:
        if animated and not self._animation_timer.isActive():
            self._animation_timer.start()
        elif not animated and self._animation_timer.isActive():
            self._animation_timer.stop()

    def item_at(self, index: QModelIndex) -> DownloadItem | None:
        return index.data(ITEM_ROLE) if index.isValid() else None

    def _hit(self, pos: QPoint) -> tuple[QModelIndex, DownloadItem | None, ActionSpec | None]:
        index = self.indexAt(pos)
        item = self.item_at(index)
        if item is None:
            return index, None, None
        spec = self._delegate.action_at(self.visualRect(index), item, QPointF(pos))
        return index, item, spec

    # ------------------------------------------------------------------ mouse

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        _, item, spec = self._hit(event.position().toPoint())
        hovered = (item.id, spec.action) if item and spec else None
        if hovered != self._delegate.hovered:
            self._delegate.hovered = hovered
            self.viewport().update()
        over_button = spec is not None and spec.enabled
        self.viewport().setCursor(
            Qt.CursorShape.PointingHandCursor if over_button else Qt.CursorShape.ArrowCursor
        )
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Never carry a swallowed release into the next click.
        self._selection_click_handled = False
        index, item, spec = self._hit(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and item and spec and spec.enabled:
            self.setCurrentIndex(index)
            self._delegate.pressed = (item.id, spec.action)
            self.viewport().update()
            event.accept()
            return
        if (
            event.button() == Qt.MouseButton.LeftButton
            and item is not None
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            # A plain click selects the row (and only that row); Ctrl/Shift clicks
            # fall through to the base class, which toggles/extends the selection.
            self._selection_click_handled = True
            selection = self.selectionModel()
            selection.select(
                index,
                QItemSelectionModel.SelectionFlag.ClearAndSelect,
            )
            selection.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            event.accept()
            return
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not index.isValid()
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            self._selection_click_handled = True
            self.clearSelection()
            self.selectionModel().setCurrentIndex(
                QModelIndex(), QItemSelectionModel.SelectionFlag.NoUpdate
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._selection_click_handled:
            self._selection_click_handled = False
            event.accept()
            return
        pressed = self._delegate.pressed
        if pressed is not None:
            self._delegate.pressed = None
            self.viewport().update()
            _, item, spec = self._hit(event.position().toPoint())
            if item and spec and (item.id, spec.action) == pressed:
                self.actionRequested.emit(spec.action.value, item.id)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        _, item, spec = self._hit(event.position().toPoint())
        # Opening only makes sense once the file exists; on a running download the
        # gesture would be a silent no-op.
        if item and not spec and item.status is DownloadStatus.COMPLETED:
            self.actionRequested.emit(ItemAction.OPEN_FILE.value, item.id)
            return
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._delegate.hovered = None
        self._delegate.pressed = None
        self.viewport().update()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        item = self.item_at(self.currentIndex())
        if item is not None and event.key() == Qt.Key.Key_Delete:
            self.actionRequested.emit(ItemAction.REMOVE.value, item.id)
            return
        if item is not None and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if item.status is DownloadStatus.COMPLETED:
                self.actionRequested.emit(ItemAction.OPEN_FILE.value, item.id)
            return
        super().keyPressEvent(event)

    def viewportEvent(self, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.ToolTip:
            _, item, spec = self._hit(event.pos())
            if spec is not None:
                QToolTip.showText(event.globalPos(), spec.tooltip, self)
            elif item is not None:
                QToolTip.showText(event.globalPos(), str(item.file_path), self)
            else:
                QToolTip.hideText()
            return True
        return super().viewportEvent(event)
