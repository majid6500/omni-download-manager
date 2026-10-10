"""The main page: fixed toolbar, header controls, download list and empty state."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
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
from omni_download_manager.ui.toolbar import Toolbar
from omni_download_manager.ui.widgets import make_label
from omni_download_manager.utils.formatting import format_speed

_EMPTY_TEXT = {
    ViewFilter.ALL: ("No downloads yet", "Paste a link to start your first download."),
    ViewFilter.ACTIVE: ("Nothing in progress", "Active and paused downloads show up here."),
    ViewFilter.COMPLETED: ("No completed downloads", "Finished downloads will be listed here."),
    ViewFilter.FAILED: ("No failed downloads", "Everything is working as expected."),
}


def make_icon_label(icon_name: str) -> QLabel:
    """A small icon-only label used as a visual prefix for a header control."""
    label = QLabel()
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    label.setProperty("iconName", icon_name)
    return label


class DownloadsPage(QWidget):
    addRequested = Signal()
    settingsRequested = Signal()
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
        self._title.setMinimumWidth(0)  # lets the header shrink instead of clipping
        self._title.setWordWrap(True)  # wraps rather than pushing the controls out
        self._subtitle = make_label(role="muted")
        # The subtitle is metadata: it may clip in a very narrow window rather
        # than force the whole header (and the window minimum) to grow.
        self._subtitle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        # The fixed action bar: always visible, driven by the current selection.
        self._toolbar = Toolbar(theme)
        self._toolbar.addRequested.connect(self.addRequested)
        self._toolbar.settingsRequested.connect(self.settingsRequested)
        self._toolbar.actionRequested.connect(self.actionRequested)
        self._toolbar.bulkActionRequested.connect(self.bulkActionRequested)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search filename or URL")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(240)
        self._search.setMinimumWidth(150)  # shrink before the sort controls clip
        self._search.setAccessibleName("Search downloads")
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
        self._category.setFixedWidth(150)
        self._category.setMinimumWidth(125)

        self._sort = QComboBox()
        for mode in DownloadSort:
            self._sort.addItem(mode.title, mode)
        self._sort.currentIndexChanged.connect(
            lambda: self._proxy.set_sort_mode(self._sort.currentData())
        )
        self._sort.setFixedWidth(150)
        self._sort.setMinimumWidth(125)

        self._category_icon = make_icon_label("filter")
        self._sort_icon = make_icon_label("sort")

        self._view = DownloadListView(theme)
        self._view.setModel(self._proxy)
        self._view.actionRequested.connect(self.actionRequested)
        self._view.customContextMenuRequested.connect(self._on_context_menu)
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._proxy.modelReset.connect(self._on_selection_changed)
        self._proxy.rowsInserted.connect(self._on_selection_changed)
        self._proxy.rowsRemoved.connect(self._on_selection_changed)

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
        header.setSpacing(8)
        header.addLayout(titles, 1)
        header.addWidget(self._search)
        header.addWidget(self._category_icon)
        header.addWidget(self._category)
        header.addWidget(self._sort_icon)
        header.addWidget(self._sort)

        content = QVBoxLayout()
        content.setSpacing(16)
        content.addLayout(header)
        content.addLayout(self._stack, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 18, 24, 10)
        body_layout.addLayout(content)
        layout.addWidget(body, 1)

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

    # ------------------------------------------------------------- selection

    def _selected_items(self) -> list[DownloadItem]:
        return [
            item
            for index in self._view.selectionModel().selectedRows()
            if (item := self._view.item_at(index)) is not None
        ]

    def _on_selection_changed(self, *_args) -> None:
        self._toolbar.set_selection(self._selected_items())

    def _on_context_menu(self, pos: QPoint) -> None:
        index = self._view.indexAt(pos)
        item = self._view.item_at(index)
        if item is not None:
            self._view.setCurrentIndex(index)
            self.contextMenuRequested.emit(item.id, self._view.viewport().mapToGlobal(pos))

    def _refresh_icons(self) -> None:
        palette = self._theme.palette
        self._empty_button.setIcon(make_icon("plus", palette.accent_text, 18))
        self._empty_icon.setPixmap(icon_pixmap("inbox", palette.text_faint, 56, self.devicePixelRatioF()))
        dpr = self.devicePixelRatioF()
        for label in (self._category_icon, self._sort_icon):
            label.setPixmap(icon_pixmap(label.property("iconName"), palette.accent, 16, dpr))

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
        # Status can change without the selection changing, so the toolbar follows
        # every refresh: it must always match what a click would actually do.
        self._on_selection_changed()
