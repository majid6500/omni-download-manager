"""The main page: header, download list and empty state."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from omni_download_manager.core.filetypes import FileCategory
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.ui.icons import icon_pixmap, make_icon
from omni_download_manager.ui.list_view import DownloadListView
from omni_download_manager.ui.models import (
    DownloadFilterProxy,
    DownloadListModel,
    DownloadSort,
    ITEM_ROLE,
    ViewFilter,
)
from omni_download_manager.ui.presentation import is_indeterminate
from omni_download_manager.ui.theme import ThemeManager
from omni_download_manager.ui.widgets import make_label
from omni_download_manager.utils.formatting import format_speed

_EMPTY_TEXT = {
    ViewFilter.ALL: ("No downloads yet", "Paste a link to start your first download."),
    ViewFilter.ACTIVE: ("Nothing in progress", "Active and paused downloads show up here."),
    ViewFilter.COMPLETED: ("No completed downloads", "Finished downloads will be listed here."),
    ViewFilter.FAILED: ("No failed downloads", "Everything is working as expected."),
}


class DownloadsPage(QWidget):
    addRequested = Signal()
    actionRequested = Signal(str, str)
    bulkActionRequested = Signal(str, object)
    contextMenuRequested = Signal(str, QPoint)

    def __init__(self, model: DownloadListModel, theme: ThemeManager, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._model = model
        self._proxy = DownloadFilterProxy(self)
        self._proxy.setSourceModel(model)

        self._title = make_label(ViewFilter.ALL.title, name="PageTitle")
        self._subtitle = make_label(role="muted")
        self._add_button = QPushButton("  Add download")
        self._add_button.setProperty("variant", "primary")
        self._add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_button.setMinimumHeight(40)
        self._add_button.setShortcut("Ctrl+N")
        self._add_button.clicked.connect(self.addRequested)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search filename or URL")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(240)
        self._search.textChanged.connect(self._on_search_changed)
        self._category = QComboBox()
        self._category.addItem("All file types", None)
        for category in FileCategory:
            self._category.addItem(category.title, category.value)
        self._category.setAccessibleName("Filter by file type")
        self._category.setToolTip("Filter downloads by file type")
        self._category.currentIndexChanged.connect(
            lambda: self._on_category_changed(self._category.currentData())
        )
        self._category.setFixedWidth(140)
        self._sort = QComboBox()
        for mode in DownloadSort:
            self._sort.addItem(mode.title, mode)
        self._sort.currentIndexChanged.connect(
            lambda: self._proxy.set_sort_mode(self._sort.currentData())
        )
        self._sort.setFixedWidth(150)

        self._selection_count = make_label(role="muted")
        self._bulk_pause = QPushButton("Pause")
        self._bulk_resume = QPushButton("Resume")
        self._bulk_cancel = QPushButton("Cancel")
        self._bulk_remove = QPushButton("Remove")
        for button in (self._bulk_pause, self._bulk_resume, self._bulk_cancel, self._bulk_remove):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setVisible(False)
        self._bulk_pause.clicked.connect(lambda: self._run_bulk_action("pause"))
        self._bulk_resume.clicked.connect(lambda: self._run_bulk_action("resume"))
        self._bulk_cancel.clicked.connect(lambda: self._run_bulk_action("cancel"))
        self._bulk_remove.clicked.connect(lambda: self._run_bulk_action("remove"))

        self._view = DownloadListView(theme)
        self._view.setModel(self._proxy)
        self._view.actionRequested.connect(self.actionRequested)
        self._view.customContextMenuRequested.connect(self._on_context_menu)
        self._view.selectionModel().selectionChanged.connect(self._update_bulk_actions)
        self._proxy.modelReset.connect(self._update_bulk_actions)
        self._proxy.rowsInserted.connect(self._update_bulk_actions)
        self._proxy.rowsRemoved.connect(self._update_bulk_actions)

        self._empty_icon = QLabel()
        self._empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_title = make_label(name="SectionTitle")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_text = make_label(role="muted")
        self._empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_button = QPushButton("  Add download")
        self._empty_button.setProperty("variant", "primary")
        self._empty_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._empty_button.clicked.connect(self.addRequested)

        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(8)
        empty_layout.addWidget(self._empty_icon)
        empty_layout.addSpacing(6)
        empty_layout.addWidget(self._empty_title)
        empty_layout.addWidget(self._empty_text)
        empty_layout.addSpacing(14)
        empty_layout.addWidget(self._empty_button, 0, Qt.AlignmentFlag.AlignCenter)

        self._stack = QStackedLayout()
        self._stack.addWidget(self._view)
        self._stack.addWidget(empty)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self._title)
        titles.addWidget(self._subtitle)
        header = QHBoxLayout()
        header.addLayout(titles, 1)
        header.addWidget(self._search, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(self._category, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(self._sort, 0, Qt.AlignmentFlag.AlignTop)
        header.addWidget(self._add_button, 0, Qt.AlignmentFlag.AlignTop)
        bulk = QHBoxLayout()
        bulk.setSpacing(8)
        bulk.addWidget(self._selection_count)
        bulk.addWidget(self._bulk_pause)
        bulk.addWidget(self._bulk_resume)
        bulk.addWidget(self._bulk_cancel)
        bulk.addWidget(self._bulk_remove)
        bulk.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 20, 12)
        layout.setSpacing(18)
        layout.addLayout(header)
        layout.addLayout(bulk)
        layout.addLayout(self._stack, 1)

        for signal in (model.dataChanged, model.rowsInserted, model.rowsRemoved, model.modelReset):
            signal.connect(self.refresh)
        theme.changed.connect(self._refresh_icons)
        self._refresh_icons()
        self.refresh()

    @property
    def view_filter(self) -> ViewFilter:
        return self._proxy.view_filter

    def set_filter(self, view_filter: ViewFilter) -> None:
        self._proxy.set_view_filter(view_filter)
        self._title.setText(view_filter.title)
        self.refresh()

    def _on_search_changed(self, query: str) -> None:
        self._proxy.set_search_query(query)
        self.refresh()

    def _on_category_changed(self, category_value: str | None) -> None:
        category = FileCategory(category_value) if category_value is not None else None
        self._proxy.set_category_filter(category)
        self.refresh()

    def _selected_item_ids(self) -> list[str]:
        return [
            item.id
            for index in self._view.selectionModel().selectedRows()
            if (item := self._view.item_at(index)) is not None
        ]

    def _run_bulk_action(self, action: str) -> None:
        item_ids = self._selected_item_ids()
        if item_ids:
            self.bulkActionRequested.emit(action, item_ids)

    def _update_bulk_actions(self, *_args) -> None:
        item_ids = self._selected_item_ids()
        selected = bool(item_ids)
        self._selection_count.setText(f"{len(item_ids)} selected" if selected else "")
        selected_items = [self._view.item_at(index) for index in self._view.selectionModel().selectedRows()]
        selected_items = [item for item in selected_items if item is not None]
        can_pause = any(item.is_active and item.resumable is not False for item in selected_items)
        can_resume = any(item.status in {
            DownloadStatus.PENDING, DownloadStatus.PAUSED, DownloadStatus.FAILED, DownloadStatus.CANCELLED
        } for item in selected_items)
        can_cancel = any(item.status not in (DownloadStatus.COMPLETED, DownloadStatus.CANCELLED)
                         for item in selected_items)
        self._bulk_pause.setVisible(selected)
        self._bulk_resume.setVisible(selected)
        self._bulk_cancel.setVisible(selected)
        self._bulk_remove.setVisible(selected)
        self._bulk_pause.setEnabled(can_pause)
        self._bulk_resume.setEnabled(can_resume)
        self._bulk_cancel.setEnabled(can_cancel)
        self._bulk_remove.setEnabled(selected)

    def _on_context_menu(self, pos: QPoint) -> None:
        index = self._view.indexAt(pos)
        item = self._view.item_at(index)
        if item is not None:
            self._view.setCurrentIndex(index)
            self.contextMenuRequested.emit(item.id, self._view.viewport().mapToGlobal(pos))

    def _refresh_icons(self) -> None:
        palette = self._theme.palette
        self._add_button.setIcon(make_icon("plus", palette.accent_text, 18))
        self._empty_button.setIcon(make_icon("plus", palette.accent_text, 18))
        self._empty_icon.setPixmap(icon_pixmap("inbox", palette.text_faint, 56, self.devicePixelRatioF()))

    def refresh(self, *_args) -> None:
        items: list[DownloadItem] = [
            self._proxy.index(row, 0).data(ITEM_ROLE)
            for row in range(self._proxy.rowCount())
        ]
        active = [i for i in items if i.status is DownloadStatus.DOWNLOADING]
        speed = sum(i.speed_bps for i in active)

        if not items:
            if self._proxy.search_query or self._proxy.category_filter is not None:
                title, text = (
                    "No matching downloads",
                    "Try different search terms or choose another file type.",
                )
            else:
                title, text = _EMPTY_TEXT[self.view_filter]
            self._empty_title.setText(title)
            self._empty_text.setText(text)
            self._empty_button.setVisible(
                self.view_filter is ViewFilter.ALL
                and not self._proxy.search_query
                and self._proxy.category_filter is None
            )
            self._stack.setCurrentIndex(1)
            self._subtitle.setText(
                "No matches"
                if self._proxy.search_query or self._proxy.category_filter is not None
                else "Nothing here yet"
            )
        else:
            self._stack.setCurrentIndex(0)
            parts = [f"{len(items)} download" + ("" if len(items) == 1 else "s")]
            if active:
                parts.append(f"{len(active)} active")
                if speed > 0:
                    parts.append(f"↓ {format_speed(speed)}")
            self._subtitle.setText("  ·  ".join(parts))
        self._view.set_animated(any(is_indeterminate(i) for i in items))
        self._update_bulk_actions()
