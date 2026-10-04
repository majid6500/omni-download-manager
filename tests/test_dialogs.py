import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QApplication, QCheckBox

from omni_download_manager.config.paths import AppPaths
from omni_download_manager.config.settings import SettingsStore
from omni_download_manager.core.filetypes import FileCategory
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.ui.dialogs import (
    AddDownloadDialog,
    ConfirmDialog,
    ThemedDialog,
    show_error,
    show_information,
)
from omni_download_manager.ui.downloads_page import DownloadsPage
from omni_download_manager.ui.icons import logo_icon
from omni_download_manager.ui.models import ITEM_ROLE, DownloadListModel
from omni_download_manager.ui.settings_page import SettingsPage
from omni_download_manager.ui.theme import ThemeManager, build_stylesheet


class AddDownloadDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_scheduling_disables_immediate_start_and_enables_date_picker(self) -> None:
        dialog = AddDownloadDialog(ThemeManager(), str(Path.cwd()), True, lambda _: None)
        self.assertTrue(dialog._start.isChecked())
        self.assertFalse(dialog._schedule_time.isEnabled())

        dialog._schedule_enabled.setChecked(True)

        self.assertFalse(dialog._start.isEnabled())
        self.assertTrue(dialog._schedule_time.isEnabled())
        dialog.close()

    def test_dialog_title_bar_uses_theme_without_changing_title_bar_border(self) -> None:
        theme = ThemeManager("dark")
        dialog = AddDownloadDialog(theme, str(Path.cwd()), True, lambda _: None)
        with patch("omni_download_manager.ui.dialogs.apply_title_bar_theme") as apply:
            dialog._on_theme_changed()
        args = apply.call_args
        self.assertTrue(args.args[1])
        self.assertEqual(args.kwargs["background"], theme.palette.bg)
        self.assertEqual(args.kwargs["text"], theme.palette.text)
        self.assertEqual(args.kwargs["border"], theme.palette.border)
        dialog.close()

    def test_confirmation_dialog_uses_the_shared_theme_title_bar(self) -> None:
        theme = ThemeManager("light")
        dialog = ConfirmDialog(theme, "Remove item?", "Confirm removal.", "Remove")
        with patch("omni_download_manager.ui.dialogs.apply_title_bar_theme") as apply:
            dialog._on_theme_changed()
        args = apply.call_args
        self.assertFalse(args.args[1])
        self.assertEqual(args.kwargs["background"], theme.palette.bg)
        self.assertEqual(args.kwargs["text"], theme.palette.text)
        self.assertEqual(args.kwargs["border"], theme.palette.border)
        dialog.close()

    def test_error_and_information_dialogs_use_the_shared_themed_dialog(self) -> None:
        theme = ThemeManager()
        with patch.object(ThemedDialog, "exec", return_value=0) as execute:
            show_error(theme, None, "Error", "Something went wrong.")
            show_information(theme, None, "Information", "Already running.")
        self.assertEqual(execute.call_count, 2)

    def test_theme_uses_requested_pink_accent_but_keeps_title_bar_border_color(self) -> None:
        for theme_name in ("dark", "light"):
            palette = ThemeManager(theme_name).palette
            stylesheet = build_stylesheet(palette)
            self.assertEqual(palette.accent, "#fc037f")
            self.assertIn("border: 1px solid #fc037f", stylesheet)
            self.assertNotEqual(palette.border, "#fc037f")

    def test_application_logo_icon_loads_from_png_resource(self) -> None:
        icon = logo_icon()
        self.assertFalse(icon.isNull())
        self.assertFalse(icon.pixmap(128, 128).isNull())

    def test_submit_passes_local_schedule_time_and_does_not_start_immediately(self) -> None:
        submitted = []
        dialog = AddDownloadDialog(
            ThemeManager(), str(Path.cwd()), True, submitted.append
        )
        dialog._url.setText("https://example.com/file.bin")
        when = QDateTime.currentDateTime().addSecs(120)
        dialog._schedule_time.setDateTime(when)
        dialog._schedule_enabled.setChecked(True)

        dialog._on_add()

        self.assertEqual(len(submitted), 1)
        self.assertFalse(submitted[0].start)
        self.assertAlmostEqual(submitted[0].scheduled_at, when.toSecsSinceEpoch(), delta=1)
        dialog.close()

    def test_downloads_page_filters_by_category_without_moving_files(self) -> None:
        video = DownloadItem(
            url="https://example.com/video",
            directory="C:/Downloads",
            filename="clip.mp4",
            status=DownloadStatus.COMPLETED,
        )
        audio = DownloadItem(
            url="https://example.com/audio",
            directory="C:/Downloads",
            filename="song.mp3",
            status=DownloadStatus.COMPLETED,
        )
        model = DownloadListModel()
        model.set_items([video, audio])
        page = DownloadsPage(model, ThemeManager())

        page._category.setCurrentIndex(page._category.findData(FileCategory.VIDEO.value))

        self.assertEqual(page._proxy.rowCount(), 1)
        self.assertEqual(page._proxy.index(0, 0).data(ITEM_ROLE).filename, "clip.mp4")
        self.assertEqual([item.directory for item in model.items()], ["C:/Downloads", "C:/Downloads"])
        page.close()

    def test_system_proxy_setting_is_saved_from_settings_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = AppPaths(Path(tmp))
            store = SettingsStore.load(Path(tmp) / "settings.json")
            page = SettingsPage(store, ThemeManager(), paths)
            toggle = page.findChild(QCheckBox, "SystemProxyToggle")

            self.assertIsNotNone(toggle)
            assert toggle is not None
            self.assertTrue(toggle.isChecked())
            toggle.setChecked(False)

            self.assertFalse(store.get().use_system_proxy)
            page.close()

    def test_settings_background_updates_when_switching_to_light_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = ThemeManager("dark")
            theme.apply()
            paths = AppPaths(Path(tmp))
            page = SettingsPage(
                SettingsStore.load(Path(tmp) / "settings.json"),
                theme,
                paths,
            )
            page.resize(900, 720)
            page.show()
            self._app.processEvents()

            theme.set_theme("light")
            self._app.processEvents()

            image = page.grab().toImage()
            self.assertEqual(image.pixelColor(5, 5).name(), theme.palette.bg.lower())
            page.close()


if __name__ == "__main__":
    unittest.main()
