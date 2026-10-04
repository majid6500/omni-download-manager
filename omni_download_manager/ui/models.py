"""Qt model/proxy over the download snapshots published by the manager."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Slot,
)

from omni_download_manager.core.filetypes import FileCategory, categorize
from omni_download_manager.core.models import DownloadItem, DownloadStatus

S = DownloadStatus
ITEM_ROLE = Qt.ItemDataRole.UserRole + 1


class ViewFilter(str, Enum):
    ALL = "all"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def title(self) -> str:
        return {
            ViewFilter.ALL: "All downloads",
            ViewFilter.ACTIVE: "In progress",
            ViewFilter.COMPLETED: "Completed",
            ViewFilter.FAILED: "Failed",
        }[self]

    def matches(self, item: DownloadItem) -> bool:
        if self is ViewFilter.ALL:
            return True
        if self is ViewFilter.ACTIVE:
            return item.status in (S.PENDING, S.QUEUED, S.CONNECTING, S.DOWNLOADING, S.PAUSED)
        if self is ViewFilter.COMPLETED:
            return item.status is S.COMPLETED
        return item.status is S.FAILED


class DownloadSort(str, Enum):
    NEWEST = "newest"
    OLDEST = "oldest"
    NAME = "name"
    LARGEST = "largest"

    @property
    def title(self) -> str:
        return {
            DownloadSort.NEWEST: "Newest first",
            DownloadSort.OLDEST: "Oldest first",
            DownloadSort.NAME: "Name (A–Z)",
            DownloadSort.LARGEST: "Largest first",
        }[self]


class DownloadListModel(QAbstractListModel):
    """Newest first. Holds snapshots; the manager remains the source of truth."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[DownloadItem] = []
        self._rows: dict[str, int] = {}

    def _reindex(self) -> None:
        self._rows = {item.id: row for row, item in enumerate(self._items)}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role == ITEM_ROLE:
            return item
        if role == Qt.ItemDataRole.DisplayRole:
            return item.filename
        return None

    def items(self) -> list[DownloadItem]:
        return list(self._items)

    def item_by_id(self, item_id: str) -> DownloadItem | None:
        row = self._rows.get(item_id)
        return self._items[row] if row is not None else None

    def set_items(self, items: list[DownloadItem]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self._reindex()
        self.endResetModel()

    @Slot(object)
    def add_item(self, item: DownloadItem) -> None:
        if item.id in self._rows:
            return
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._items.insert(0, item)
        self._reindex()
        self.endInsertRows()

    @Slot(object)
    def update_item(self, item: DownloadItem) -> None:
        row = self._rows.get(item.id)
        if row is None:  # already removed; a late update must not resurrect it
            return
        self._items[row] = item
        index = self.index(row)
        self.dataChanged.emit(index, index)

    @Slot(str)
    def remove_item(self, item_id: str) -> None:
        row = self._rows.get(item_id)
        if row is None:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._items[row]
        self._reindex()
        self.endRemoveRows()


class DownloadFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._filter = ViewFilter.ALL
        self._category: FileCategory | None = None
        self._query = ""
        self._sort_mode = DownloadSort.NEWEST
        self.setDynamicSortFilter(True)
        self.sort(0, Qt.SortOrder.DescendingOrder)

    @property
    def view_filter(self) -> ViewFilter:
        return self._filter

    @property
    def search_query(self) -> str:
        return self._query

    @property
    def category_filter(self) -> FileCategory | None:
        return self._category

    def set_view_filter(self, view_filter: ViewFilter) -> None:
        self._filter = view_filter
        self.invalidateRowsFilter()

    def set_search_query(self, query: str) -> None:
        self._query = query.strip().casefold()
        self.invalidateRowsFilter()

    def set_category_filter(self, category: FileCategory | None) -> None:
        self._category = category
        self.invalidateRowsFilter()

    def set_sort_mode(self, sort_mode: DownloadSort) -> None:
        self._sort_mode = sort_mode
        order = (
            Qt.SortOrder.AscendingOrder
            if sort_mode in (DownloadSort.OLDEST, DownloadSort.NAME)
            else Qt.SortOrder.DescendingOrder
        )
        self.sort(0, order)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        index = self.sourceModel().index(source_row, 0, source_parent)
        item = index.data(ITEM_ROLE)
        if item is None or not self._filter.matches(item):
            return False
        if self._category is not None and categorize(item.filename) is not self._category:
            return False
        return not self._query or self._query in item.filename.casefold() or self._query in item.url.casefold()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:  # noqa: N802
        left_item = left.data(ITEM_ROLE)
        right_item = right.data(ITEM_ROLE)
        if self._sort_mode is DownloadSort.NAME:
            return left_item.filename.casefold() < right_item.filename.casefold()
        if self._sort_mode is DownloadSort.LARGEST:
            left_size = left_item.total_bytes
            right_size = right_item.total_bytes
            return (left_size is not None, left_size or -1) < (right_size is not None, right_size or -1)
        return left_item.created_at < right_item.created_at
