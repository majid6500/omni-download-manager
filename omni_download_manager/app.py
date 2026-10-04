"""Application bootstrap: builds the object graph and starts the Qt event loop."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from omni_download_manager.config.paths import resolve_app_paths
from omni_download_manager.config.settings import SettingsStore
from omni_download_manager.constants import APP_NAME, VERSION
from omni_download_manager.engine.http_downloader import HttpDownloader
from omni_download_manager.services.download_manager import DownloadManager
from omni_download_manager.storage.repository import open_repository
from omni_download_manager.ui.icons import logo_icon
from omni_download_manager.ui.dialogs import show_information
from omni_download_manager.ui.main_window import MainWindow
from omni_download_manager.ui.theme import ThemeManager
from omni_download_manager.ui.windows_effects import set_app_user_model_id
from omni_download_manager.utils.logging_setup import install_exception_hooks, setup_logging

logger = logging.getLogger("omni_download_manager.app")


def main(argv: list[str] | None = None) -> int:
    paths = resolve_app_paths()
    paths.ensure()
    setup_logging(paths.log_dir)
    install_exception_hooks()
    logger.info("Starting %s %s (data dir: %s)", APP_NAME, VERSION, paths.data_dir)

    set_app_user_model_id()
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(logo_icon())
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter", "Helvetica Neue", "Arial"])
    font.setPointSizeF(10.0)
    app.setFont(font)

    settings = SettingsStore.load(paths.settings_file)
    theme = ThemeManager(settings.get().theme)
    theme.apply()

    lock = QLockFile(str(paths.lock_file))
    # QLockFile detects locks left behind by a crashed process, so no manual cleanup is needed.
    if not lock.tryLock(100):
        show_information(theme, None, APP_NAME, f"{APP_NAME} is already running.")
        return 0

    downloader = HttpDownloader()
    downloader.set_speed_limit_mib(settings.get().max_download_speed_mib)
    settings.subscribe(
        lambda current: downloader.set_speed_limit_mib(current.max_download_speed_mib)
    )
    manager = DownloadManager(open_repository(paths.database_file), downloader, settings.get)
    manager.load()
    app.aboutToQuit.connect(manager.shutdown)

    window = MainWindow(manager, settings, theme, paths)
    window.show()
    code = app.exec()
    logger.info("Exiting with code %d", code)
    lock.unlock()
    return code
