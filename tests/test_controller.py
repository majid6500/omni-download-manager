import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.ui.actions import ItemAction
from omni_download_manager.ui.controller import ItemActionController
from omni_download_manager.ui.downloads_page import DownloadsPage
from omni_download_manager.ui.models import DownloadListModel
from omni_download_manager.ui.theme import ThemeManager
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication


class ItemActionControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_open_folder_uses_selected_download_directory(self) -> None:
        directory = Path("D:/Users/example/Downloads/Music")
        item = DownloadItem(
            url="https://example.com/song.mp3",
            directory=str(directory),
            filename="song.mp3",
            status=DownloadStatus.COMPLETED,
        )
        manager = Mock()
        manager.get_item.return_value = item
        controller = ItemActionController(manager, Mock(), Mock(), Mock())

        with patch("omni_download_manager.ui.controller.open_path") as open_path:
            controller._perform(ItemAction.OPEN_FOLDER, item.id)

        open_path.assert_called_once_with(directory)

    def test_bulk_pause_skips_downloads_that_cannot_resume(self) -> None:
        running = DownloadItem(
            url="https://example.com/a",
            directory="/downloads",
            filename="a",
            status=DownloadStatus.DOWNLOADING,
            resumable=True,
        )
        non_resumable = DownloadItem(
            url="https://example.com/b",
            directory="/downloads",
            filename="b",
            status=DownloadStatus.DOWNLOADING,
            resumable=False,
        )
        manager = Mock()
        manager.get_item.side_effect = {running.id: running, non_resumable.id: non_resumable}.get
        settings = Mock()
        settings.get.return_value = SimpleNamespace(confirm_destructive_actions=True)
        controller = ItemActionController(manager, settings, Mock(), Mock())

        controller.perform_bulk("pause", [running.id, non_resumable.id])

        manager.pause.assert_called_once_with(running.id)

    def test_bulk_remove_can_delete_only_selected_completed_files(self) -> None:
        completed = DownloadItem(
            url="https://example.com/a",
            directory="/downloads",
            filename="a",
            status=DownloadStatus.COMPLETED,
        )
        failed = DownloadItem(
            url="https://example.com/b",
            directory="/downloads",
            filename="b",
            status=DownloadStatus.FAILED,
        )
        manager = Mock()
        manager.get_item.side_effect = {completed.id: completed, failed.id: failed}.get
        dialog = Mock()
        dialog.exec.return_value = True
        dialog.option_checked = True
        controller = ItemActionController(manager, Mock(), Mock(), Mock())

        with patch("omni_download_manager.ui.controller.ConfirmDialog", return_value=dialog):
            controller.perform_bulk("remove", [completed.id, failed.id])

        manager.remove.assert_any_call(completed.id, delete_file=True)
        manager.remove.assert_any_call(failed.id, delete_file=False)
        self.assertEqual(manager.remove.call_count, 2)

    def test_downloads_page_emits_bulk_action_for_multiselection(self) -> None:
        model = DownloadListModel()
        items = [
            DownloadItem(
                url=f"https://example.com/{name}",
                directory="/downloads",
                filename=name,
                status=DownloadStatus.PENDING,
            )
            for name in ("a", "b")
        ]
        model.set_items(items)
        page = DownloadsPage(model, ThemeManager())
        page._view.selectionModel().select(
            page._proxy.index(0, 0), QItemSelectionModel.SelectionFlag.Select
        )
        page._view.selectionModel().select(
            page._proxy.index(1, 0), QItemSelectionModel.SelectionFlag.Select
        )
        observed = []
        page.bulkActionRequested.connect(lambda action, ids: observed.append((action, ids)))

        page._bulk_cancel.click()

        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][0], "cancel")
        self.assertCountEqual(observed[0][1], [item.id for item in items])
        page.close()

    def test_clicking_selected_card_again_clears_selection_and_bulk_toolbar(self) -> None:
        model = DownloadListModel()
        model.set_items([
            DownloadItem(
                url=f"https://example.com/{name}",
                directory="/downloads",
                filename=name,
                status=DownloadStatus.PENDING,
            )
            for name in ("a", "b")
        ])
        page = DownloadsPage(model, ThemeManager())
        page._view.resize(600, 500)
        page.show()
        self._app.processEvents()
        card_index = page._proxy.index(0, 0)
        card_rect = page._view.visualRect(card_index)
        click_point = QPoint(card_rect.left() + 80, card_rect.center().y())
        hit_index, hit_item, hit_action = page._view._hit(click_point)
        self.assertEqual(hit_index, card_index)
        self.assertIsNotNone(hit_item)
        self.assertIsNone(hit_action)

        QTest.mouseClick(page._view.viewport(), Qt.MouseButton.LeftButton, pos=click_point)
        self.assertEqual(len(page._view.selectionModel().selectedRows()), 1)
        self.assertTrue(page._bulk_remove.isVisible())

        QTest.qWait(QApplication.doubleClickInterval() + 50)
        self.assertTrue(page._view.selectionModel().isSelected(card_index))
        QTest.mouseClick(page._view.viewport(), Qt.MouseButton.LeftButton, pos=click_point)

        self.assertEqual(len(page._view.selectionModel().selectedRows()), 0)
        self.assertFalse(page._bulk_remove.isVisible())
        self.assertEqual(page._selection_count.text(), "")
        page.close()

    def test_clicking_another_card_adds_and_deselects_independently(self) -> None:
        model = DownloadListModel()
        model.set_items([
            DownloadItem(
                url=f"https://example.com/{name}",
                directory="/downloads",
                filename=name,
                status=DownloadStatus.PENDING,
            )
            for name in ("a", "b")
        ])
        page = DownloadsPage(model, ThemeManager())
        page._view.resize(600, 500)
        page.show()
        self._app.processEvents()

        first = page._proxy.index(0, 0)
        second = page._proxy.index(1, 0)
        for index in (first, second):
            rect = page._view.visualRect(index)
            QTest.mouseClick(
                page._view.viewport(),
                Qt.MouseButton.LeftButton,
                pos=QPoint(rect.left() + 80, rect.center().y()),
            )
            QTest.qWait(QApplication.doubleClickInterval() + 50)

        self.assertEqual(len(page._view.selectionModel().selectedRows()), 2)
        self.assertTrue(page._bulk_remove.isVisible())

        first_rect = page._view.visualRect(first)
        QTest.mouseClick(
            page._view.viewport(),
            Qt.MouseButton.LeftButton,
            pos=QPoint(first_rect.left() + 80, first_rect.center().y()),
        )
        QTest.qWait(QApplication.doubleClickInterval() + 50)

        self.assertEqual(len(page._view.selectionModel().selectedRows()), 1)
        self.assertTrue(page._bulk_remove.isVisible())
        remaining = page._view.selectionModel().selectedRows()[0]
        remaining_item = page._view.item_at(remaining)
        self.assertIsNotNone(remaining_item)
        self.assertNotEqual(remaining_item.id, page._view.item_at(first).id)
        page.close()


if __name__ == "__main__":
    unittest.main()
