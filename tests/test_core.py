import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from omni_download_manager.config.paths import resolve_app_paths
from omni_download_manager.config.settings import Settings, SettingsStore
from omni_download_manager.core.errors import InvalidOperationError, StorageError
from omni_download_manager.core.filetypes import FileCategory, badge_label, categorize
from omni_download_manager.core.models import ALLOWED_TRANSITIONS, DownloadItem, DownloadStatus, StopReason
from omni_download_manager.engine.base import DownloadControl
from omni_download_manager.engine.filenames import (
    derive_filename,
    filename_from_content_disposition,
    reserve_partial,
    sanitize_filename,
)
from omni_download_manager.engine.speed import DownloadSpeedLimiter, SpeedMeter
from omni_download_manager.storage.repository import MIGRATIONS, SqliteDownloadRepository, open_repository
from omni_download_manager.utils.formatting import format_eta, format_percent, format_size, format_speed

S = DownloadStatus


class StateMachineTests(unittest.TestCase):
    def item(self, status=S.PENDING) -> DownloadItem:
        return DownloadItem(url="http://x/a.zip", directory="/tmp", filename="a.zip", status=status)

    def test_every_status_has_transition_rules(self) -> None:
        self.assertEqual(set(ALLOWED_TRANSITIONS), set(S))

    def test_valid_and_invalid_transitions(self) -> None:
        item = self.item()
        item.transition_to(S.CONNECTING)
        item.transition_to(S.DOWNLOADING)
        item.transition_to(S.COMPLETED)
        with self.assertRaises(InvalidOperationError):
            item.transition_to(S.DOWNLOADING)
        with self.assertRaises(InvalidOperationError):
            self.item(S.PAUSED).transition_to(S.COMPLETED)

    def test_progress_and_eta(self) -> None:
        item = self.item(S.DOWNLOADING)
        self.assertIsNone(item.progress)
        item.total_bytes, item.downloaded_bytes, item.speed_bps = 1000, 250, 50
        self.assertEqual(item.progress, 0.25)
        self.assertEqual(item.eta_seconds, 15)
        item.downloaded_bytes = 5000
        self.assertEqual(item.progress, 1.0)
        self.assertEqual(self.item(S.PAUSED).eta_seconds, None)

    def test_paths(self) -> None:
        item = self.item()
        self.assertEqual(item.partial_path.name, "a.zip.part")


class FilenameTests(unittest.TestCase):
    def test_sanitize(self) -> None:
        self.assertEqual(sanitize_filename('a<b>:c"/d\\e|f?g*.txt'), "a_b__c__d_e_f_g_.txt")
        self.assertEqual(sanitize_filename("  . "), "download")
        self.assertEqual(sanitize_filename("CON.txt"), "_CON.txt")
        self.assertEqual(sanitize_filename("report. "), "report")
        long = sanitize_filename("x" * 400 + ".pdf")
        self.assertTrue(long.endswith(".pdf") and len(long) <= 180)

    def test_content_disposition(self) -> None:
        f = filename_from_content_disposition
        self.assertEqual(f('attachment; filename="a b.zip"'), "a b.zip")
        self.assertEqual(f("attachment; filename=plain.zip"), "plain.zip")
        self.assertEqual(f("attachment; filename*=UTF-8''na%C3%AFve.txt"), "naïve.txt")
        self.assertEqual(f('attachment; filename="../../evil.sh"'), "evil.sh")
        self.assertIsNone(f("inline"))
        self.assertIsNone(f(None))

    def test_derive_filename_fallbacks(self) -> None:
        self.assertEqual(derive_filename("http://h/dir/f%20x.zip?q=1", {}), "f x.zip")
        self.assertEqual(derive_filename("http://h/", {"Content-Type": "application/pdf"}), "download.pdf")
        self.assertEqual(derive_filename("http://h/", {}), "download")

    def test_reserve_partial_picks_free_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.tar.gz").write_bytes(b"x")
            name1, part1 = reserve_partial(d, "a.tar.gz")
            name2, _ = reserve_partial(d, "a.tar.gz")
            self.assertEqual((name1, name2), ("a (1).tar.gz", "a (2).tar.gz"))
            self.assertTrue(part1.exists())


class SpeedMeterTests(unittest.TestCase):
    def test_speed_over_window(self) -> None:
        now = [0.0]
        meter = SpeedMeter(window_seconds=4, clock=lambda: now[0])
        now[0] = 1.0
        self.assertAlmostEqual(meter.update(1000), 1000)
        now[0] = 2.0
        self.assertAlmostEqual(meter.update(3000), 1500)
        now[0] = 10.0
        meter.update(3000)
        now[0] = 11.0
        self.assertAlmostEqual(meter.update(4000), 1000, delta=1)  # only the last second counts after a stall

    def test_global_speed_limiter_shares_the_configured_rate(self) -> None:
        limiter = DownloadSpeedLimiter(1024)
        control = DownloadControl()
        started = time.monotonic()
        self.assertFalse(limiter.wait_for(512, control))
        self.assertFalse(limiter.wait_for(512, control))
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 0.9)
        self.assertLess(elapsed, 2.0)

    def test_unlimited_speed_limiter_does_not_wait(self) -> None:
        limiter = DownloadSpeedLimiter()
        started = time.monotonic()
        self.assertFalse(limiter.wait_for(1024, DownloadControl()))
        self.assertLess(time.monotonic() - started, 0.1)

    def test_speed_limiter_wait_is_interruptible(self) -> None:
        limiter = DownloadSpeedLimiter(1)
        control = DownloadControl()
        stopper = threading.Timer(0.05, control.request_stop, args=(StopReason.PAUSE,))
        stopper.start()
        started = time.monotonic()
        self.assertTrue(limiter.wait_for(1024, control))
        stopper.join()
        self.assertLess(time.monotonic() - started, 0.5)


class FormattingTests(unittest.TestCase):
    def test_formats(self) -> None:
        self.assertEqual(format_size(None), "Unknown size")
        self.assertEqual(format_size(1023), "1023 B")
        self.assertEqual(format_size(1536), "1.5 KB")
        self.assertEqual(format_size(250 * 1024**2), "250 MB")
        self.assertEqual(format_speed(1024 * 1024), "1.0 MB/s")
        self.assertEqual(format_eta(45), "45s")
        self.assertEqual(format_eta(125), "2m 05s")
        self.assertEqual(format_eta(7500), "2h 05m")
        self.assertEqual(format_percent(0.456), "45%")
        self.assertEqual(format_percent(None), "")

    def test_filetypes(self) -> None:
        self.assertIs(categorize("a.ZIP"), FileCategory.ARCHIVE)
        self.assertIs(categorize("movie.mkv"), FileCategory.VIDEO)
        self.assertIs(categorize("noext"), FileCategory.OTHER)
        self.assertEqual(badge_label("a.zip"), "ZIP")
        self.assertEqual(badge_label("noext"), "FILE")
        self.assertEqual(badge_label("a.verylong"), "FILE")


class SettingsTests(unittest.TestCase):
    def test_roundtrip_and_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            store = SettingsStore.load(path)
            seen = []
            store.subscribe(seen.append)
            store.update(
                theme="light",
                read_timeout=45,
                start_immediately=False,
                use_system_proxy=False,
                max_download_speed_mib=2.5,
                completion_notifications_enabled=False,
            )
            self.assertEqual(len(seen), 1)
            again = SettingsStore.load(path).get()
            self.assertEqual(
                (again.theme, again.read_timeout, again.start_immediately,
                 again.use_system_proxy, again.max_download_speed_mib,
                 again.completion_notifications_enabled),
                ("light", 45.0, False, False, 2.5, False),
            )

    def test_invalid_values_rejected_and_bad_files_tolerated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            store = SettingsStore.load(path)
            with self.assertRaises(ValueError):
                store.update(theme="neon")
            with self.assertRaises(ValueError):
                store.update(connect_timeout=0)
            with self.assertRaises(ValueError):
                store.update(max_download_speed_mib=-0.1)
            with self.assertRaises(ValueError):
                store.update(max_download_speed_mib=1000.1)
            with self.assertRaises(ValueError):
                store.update(completion_notifications_enabled="yes")
            with self.assertRaises(ValueError):
                store.update(use_system_proxy="yes")
            with self.assertRaises(ValueError):
                store.update(nonexistent=1)
            self.assertEqual(store.get().theme, "dark")

            path.write_text("{ not json", encoding="utf-8")
            self.assertEqual(SettingsStore.load(path).get(), Settings(download_dir=store.get().download_dir))
            self.assertTrue(path.with_suffix(".corrupt").exists())

            path.write_text(json.dumps({"theme": 5, "read_timeout": "x", "future_key": 1,
                                        "start_immediately": False}), encoding="utf-8")
            loaded = SettingsStore.load(path).get()
            self.assertEqual((loaded.theme, loaded.read_timeout, loaded.start_immediately),
                             ("dark", 30.0, False))

    def test_unwritable_location_raises_storage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "file"
            blocker.write_text("x")
            store = SettingsStore(blocker / "settings.json")
            with self.assertRaises(StorageError):
                store.update(theme="light")


class PathsTests(unittest.TestCase):
    def test_override(self) -> None:
        paths = resolve_app_paths(Path("/tmp/x"))
        self.assertEqual(paths.database_file, Path("/tmp/x/downloads.db"))
        self.assertEqual(paths.log_dir, Path("/tmp/x/logs"))

    def test_legacy_default_data_directory_is_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "Fetchly"
            legacy.mkdir()
            (legacy / "settings.json").write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, {"APPDATA": tmp}, clear=True), \
                    patch("omni_download_manager.config.paths.sys.platform", "win32"):
                paths = resolve_app_paths()
            self.assertEqual(paths.data_dir, root / "Omni Download Manager")
            self.assertFalse(legacy.exists())
            self.assertTrue(paths.settings_file.exists())

    def test_existing_new_data_directory_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "Fetchly"
            legacy.mkdir()
            (legacy / "legacy.txt").write_text("keep", encoding="utf-8")
            current = root / "Omni Download Manager"
            current.mkdir()
            with patch.dict(os.environ, {"APPDATA": tmp}, clear=True), \
                    patch("omni_download_manager.config.paths.sys.platform", "win32"):
                paths = resolve_app_paths()
            self.assertEqual(paths.data_dir, current)
            self.assertTrue((legacy / "legacy.txt").exists())

    def test_legacy_data_directory_environment_variable_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"FETCHLY_DATA_DIR": tmp}, clear=True):
                paths = resolve_app_paths()
            self.assertEqual(paths.data_dir, Path(tmp))


class RepositoryTests(unittest.TestCase):
    def test_migrates_existing_database_to_store_schedules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.db"
            connection = sqlite3.connect(path)
            connection.executescript(MIGRATIONS[0])
            connection.execute("PRAGMA user_version = 1")
            connection.close()

            repo = SqliteDownloadRepository(path)
            try:
                self.assertEqual(
                    repo._connection.execute("PRAGMA user_version").fetchone()[0],
                    len(MIGRATIONS),
                )
                self.assertEqual(repo.load_all(), [])
            finally:
                repo.close()

    def test_roundtrip_update_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteDownloadRepository(Path(tmp) / "d.db")
            scheduled_at = time.time() + 300
            item = DownloadItem(url="http://x/a", directory="/d", filename="a", total_bytes=10,
                                resumable=True, etag='"e"', filename_resolved=True,
                                scheduled_at=scheduled_at)
            repo.save(item)
            item.status, item.downloaded_bytes, item.error_message = S.FAILED, 4, "boom"
            repo.save(item)
            [loaded] = repo.load_all()
            self.assertEqual((loaded.status, loaded.downloaded_bytes, loaded.error_message,
                              loaded.resumable, loaded.etag, loaded.scheduled_at),
                             (S.FAILED, 4, "boom", True, '"e"', scheduled_at))
            self.assertEqual(loaded.speed_bps, 0)
            repo.delete(item.id)
            self.assertEqual(repo.load_all(), [])
            repo.close()

    def test_corrupt_database_is_moved_aside(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.db"
            path.write_bytes(b"this is definitely not sqlite" * 50)
            repo = open_repository(path)
            self.assertEqual(repo.load_all(), [])
            repo.close()
            self.assertTrue(list(Path(tmp).glob("d.db.corrupt-*")))

    def test_unknown_status_rows_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteDownloadRepository(Path(tmp) / "d.db")
            repo.save(DownloadItem(url="u", directory="d", filename="f"))
            repo._connection.execute("UPDATE downloads SET status='from_the_future'")
            repo._connection.commit()
            self.assertEqual(repo.load_all(), [])
            repo.close()


if __name__ == "__main__":
    unittest.main()
