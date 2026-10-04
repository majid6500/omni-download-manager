import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from omni_download_manager.config.paths import AppPaths
from omni_download_manager.config.settings import SettingsStore
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.ui.main_window import MainWindow
from omni_download_manager.ui.theme import ThemeManager
from omni_download_manager.ui.notifications import CompletionNotifier


class CompletionNotifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_non_windows_platform_does_not_create_tray_icon(self) -> None:
        with patch("omni_download_manager.ui.notifications.sys.platform", "linux"), \
                patch("omni_download_manager.ui.notifications.QSystemTrayIcon") as tray:
            notifier = CompletionNotifier(QIcon(), enabled=True)
            notifier.notify_completed("file.zip")
            notifier.close()
        tray.assert_not_called()

    def test_enabled_notifier_shows_completion_message_and_can_be_disabled(self) -> None:
        tray = Mock()
        tray_type = Mock()
        tray_type.isSystemTrayAvailable.return_value = True
        tray_type.return_value = tray
        tray_type.MessageIcon.Information = object()
        with patch("omni_download_manager.ui.notifications.sys.platform", "win32"), \
                patch("omni_download_manager.ui.notifications.QSystemTrayIcon", tray_type):
            notifier = CompletionNotifier(QIcon(), enabled=True)
            notifier.notify_completed("video.mp4")
            notifier.set_enabled(False)

        tray.show.assert_called_once()
        tray.showMessage.assert_called_once()
        self.assertIn("video.mp4", tray.showMessage.call_args.args[1])
        tray.hide.assert_called_once()

    def test_window_notifies_once_when_download_transitions_to_completed(self) -> None:
        item = DownloadItem(
            url="https://example.com/video",
            directory="C:/Downloads",
            filename="video.mp4",
            status=DownloadStatus.DOWNLOADING,
        )
        completed = DownloadItem(
            url=item.url,
            directory=item.directory,
            filename=item.filename,
            id=item.id,
            status=DownloadStatus.COMPLETED,
        )
        manager = Mock()
        manager.list_items.return_value = [item]
        manager.subscribe.return_value = lambda: None
        manager.active_count.return_value = 0
        notifier = Mock()

        with tempfile.TemporaryDirectory() as tmp:
            paths = AppPaths(Path(tmp))
            settings = SettingsStore.load(paths.settings_file)
            with patch("omni_download_manager.ui.notifications.sys.platform", "linux"), \
                    patch("omni_download_manager.ui.main_window.CompletionNotifier", return_value=notifier):
                window = MainWindow(manager, settings, ThemeManager(), paths)
                window._on_item_updated(completed)
                window._on_item_updated(completed)
            notifier.notify_completed.assert_called_once_with("video.mp4")
            window._bridge.close()
            window.close()


if __name__ == "__main__":
    unittest.main()
