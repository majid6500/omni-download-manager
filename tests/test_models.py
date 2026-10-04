import unittest

from PySide6.QtWidgets import QApplication

from omni_download_manager.core.filetypes import FileCategory
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.ui.models import (
    ITEM_ROLE,
    DownloadFilterProxy,
    DownloadListModel,
    DownloadSort,
    ViewFilter,
)


class DownloadFilterProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.model = DownloadListModel()
        self.model.set_items([
            DownloadItem(
                url="https://media.example/video",
                directory="/downloads",
                filename="z-video.mp4",
                status=DownloadStatus.COMPLETED,
                total_bytes=2_000,
                created_at=3,
            ),
            DownloadItem(
                url="https://music.example/song",
                directory="/downloads",
                filename="a-song.mp3",
                status=DownloadStatus.FAILED,
                total_bytes=1_000,
                created_at=2,
            ),
            DownloadItem(
                url="https://archive.example/data",
                directory="/downloads",
                filename="m-data.zip",
                status=DownloadStatus.PENDING,
                total_bytes=None,
                created_at=1,
            ),
        ])
        self.proxy = DownloadFilterProxy()
        self.proxy.setSourceModel(self.model)

    def visible_items(self) -> list[DownloadItem]:
        return [
            self.proxy.index(row, 0).data(ITEM_ROLE)
            for row in range(self.proxy.rowCount())
        ]

    def test_search_matches_filename_and_url_case_insensitively(self) -> None:
        self.proxy.set_search_query("Z-VIDEO")
        self.assertEqual([item.filename for item in self.visible_items()], ["z-video.mp4"])
        self.proxy.set_search_query("MUSIC.EXAMPLE")
        self.assertEqual([item.filename for item in self.visible_items()], ["a-song.mp3"])

    def test_search_composes_with_status_filter(self) -> None:
        self.proxy.set_view_filter(ViewFilter.COMPLETED)
        self.proxy.set_search_query("example")
        self.assertEqual([item.filename for item in self.visible_items()], ["z-video.mp4"])

    def test_category_filter_composes_with_search_and_status(self) -> None:
        self.proxy.set_category_filter(FileCategory.AUDIO)
        self.assertEqual([item.filename for item in self.visible_items()], ["a-song.mp3"])

        self.proxy.set_search_query("music.example")
        self.assertEqual([item.filename for item in self.visible_items()], ["a-song.mp3"])

        self.proxy.set_view_filter(ViewFilter.COMPLETED)
        self.assertEqual(self.visible_items(), [])

    def test_other_category_includes_unrecognized_extensions(self) -> None:
        self.proxy.set_category_filter(FileCategory.OTHER)
        self.assertEqual(self.visible_items(), [])
        self.model.add_item(DownloadItem(
            url="https://example.com/file.unknown",
            directory="/downloads",
            filename="file.unknown",
            status=DownloadStatus.PENDING,
        ))
        self.assertEqual([item.filename for item in self.visible_items()], ["file.unknown"])

    def test_sort_modes_order_downloads(self) -> None:
        self.proxy.set_sort_mode(DownloadSort.NEWEST)
        self.assertEqual(
            [item.filename for item in self.visible_items()],
            ["z-video.mp4", "a-song.mp3", "m-data.zip"],
        )
        self.proxy.set_sort_mode(DownloadSort.NAME)
        self.assertEqual(
            [item.filename for item in self.visible_items()],
            ["a-song.mp3", "m-data.zip", "z-video.mp4"],
        )
        self.proxy.set_sort_mode(DownloadSort.LARGEST)
        self.assertEqual(
            [item.filename for item in self.visible_items()],
            ["z-video.mp4", "a-song.mp3", "m-data.zip"],
        )


if __name__ == "__main__":
    unittest.main()
