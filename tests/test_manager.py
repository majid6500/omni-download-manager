import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from omni_download_manager.config.settings import Settings
from omni_download_manager.constants import MAX_CONCURRENT_DOWNLOADS
from omni_download_manager.core.errors import (
    HttpStatusError,
    InvalidOperationError,
    InvalidUrlError,
    NetworkError,
    StorageError,
)
from omni_download_manager.core.events import EventKind
from omni_download_manager.core.models import DownloadItem, DownloadStatus
from omni_download_manager.engine.base import DownloadOutcome, OutcomeKind
from omni_download_manager.engine.http_downloader import HttpDownloader
from omni_download_manager.services.download_manager import DownloadManager
from omni_download_manager.storage.repository import SqliteDownloadRepository
from tests.support import PAYLOAD, SLOW_PAYLOAD, TestServer, wait_for

S = DownloadStatus


class ManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = TestServer().start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.dest = self.root / "downloads"
        self.db = self.root / "downloads.db"
        self.events = []
        self.manager = self.make_manager()
        self.manager.subscribe(self.events.append)

    def tearDown(self) -> None:
        self.manager.shutdown(timeout=3)
        self._tmp.cleanup()

    def make_manager(self, downloader=None) -> DownloadManager:
        settings = Settings(download_dir=str(self.dest), connect_timeout=3, read_timeout=5)
        engine = downloader or HttpDownloader(chunk_size=16 * 1024, progress_interval=0.05)
        return DownloadManager(
            SqliteDownloadRepository(self.db), engine, lambda: settings, persist_interval=0.1
        )

    def status(self, item_id: str) -> DownloadStatus:
        return self.manager.get_item(item_id).status

    def wait_status(self, item_id: str, wanted: DownloadStatus, timeout: float = 10) -> None:
        ok = wait_for(lambda: self.status(item_id) is wanted, timeout)
        self.assertTrue(ok, f"expected {wanted}, got {self.status(item_id)}")

    def test_download_completes_and_is_persisted(self) -> None:
        item = self.manager.add(self.server.url("/file.bin"), self.dest)
        self.wait_status(item.id, S.COMPLETED)
        done = self.manager.get_item(item.id)
        self.assertEqual(done.file_path.read_bytes(), PAYLOAD)
        self.assertEqual(done.progress, 1.0)
        self.assertEqual(done.total_bytes, len(PAYLOAD))
        self.assertIsNotNone(done.completed_at)
        self.assertEqual(self.manager.active_count(), 0)

        kinds = [e.kind for e in self.events if e.item.id == item.id]
        self.assertEqual(kinds[0], EventKind.ADDED)
        self.assertTrue(all(k is EventKind.UPDATED for k in kinds[1:]))

        statuses = [e.item.status for e in self.events]
        self.assertIn(S.CONNECTING, statuses)
        self.assertIn(S.DOWNLOADING, statuses)
        self.assertIs(statuses[-1], S.COMPLETED)

        reloaded = SqliteDownloadRepository(self.db)
        try:
            self.assertEqual([i.status for i in reloaded.load_all()], [S.COMPLETED])
        finally:
            reloaded.close()

    def test_progress_and_speed_are_reported_while_downloading(self) -> None:
        item = self.manager.add(self.server.url("/slow.bin"), self.dest)
        self.assertTrue(
            wait_for(lambda: self.manager.get_item(item.id).speed_bps > 0, 10),
            "speed was never reported",
        )
        live = self.manager.get_item(item.id)
        self.assertEqual(live.status, S.DOWNLOADING)
        self.assertGreater(live.downloaded_bytes, 0)
        self.assertEqual(live.total_bytes, len(SLOW_PAYLOAD))
        self.assertIsNotNone(live.eta_seconds)
        self.manager.cancel(item.id)
        self.wait_status(item.id, S.CANCELLED)

    def test_pause_and_resume(self) -> None:
        item = self.manager.add(self.server.url("/slow.bin"), self.dest)
        wait_for(lambda: self.manager.get_item(item.id).downloaded_bytes > 20_000)
        self.manager.pause(item.id)
        self.wait_status(item.id, S.PAUSED)
        paused = self.manager.get_item(item.id)
        self.assertTrue(paused.partial_path.exists())
        self.assertEqual(paused.downloaded_bytes, paused.partial_path.stat().st_size)
        self.assertEqual(paused.speed_bps, 0)

        self.manager.start(item.id)
        self.wait_status(item.id, S.COMPLETED)
        self.assertEqual(self.manager.get_item(item.id).file_path.read_bytes(), SLOW_PAYLOAD)
        self.assertFalse(list(self.dest.glob("*.part")))

    def test_pause_not_allowed_without_resume_support(self) -> None:
        item = self.manager.add(self.server.url("/norange.bin"), self.dest)
        wait_for(lambda: self.manager.get_item(item.id).resumable is not None or
                 self.status(item.id) is S.COMPLETED)
        if self.status(item.id) is S.DOWNLOADING:
            with self.assertRaises(InvalidOperationError):
                self.manager.pause(item.id)
        self.wait_status(item.id, S.COMPLETED)

    def test_cancel_discards_data_and_retry_restarts(self) -> None:
        item = self.manager.add(self.server.url("/slow.bin"), self.dest)
        wait_for(lambda: self.manager.get_item(item.id).downloaded_bytes > 0)
        self.manager.cancel(item.id)
        self.wait_status(item.id, S.CANCELLED)
        self.assertEqual(list(self.dest.iterdir()), [])
        self.assertEqual(self.manager.get_item(item.id).downloaded_bytes, 0)

        self.manager.start(item.id)
        self.wait_status(item.id, S.COMPLETED)
        self.assertEqual(self.manager.get_item(item.id).file_path.read_bytes(), SLOW_PAYLOAD)

    def test_http_error_marks_failed_with_message(self) -> None:
        item = self.manager.add(self.server.url("/missing"), self.dest)
        self.wait_status(item.id, S.FAILED)
        failed = self.manager.get_item(item.id)
        self.assertIn("not found", failed.error_message)
        self.assertEqual(self.manager.active_count(), 0)
        self.manager.start(item.id)  # retry is allowed
        self.wait_status(item.id, S.FAILED)

    def test_connection_failure_marks_failed(self) -> None:
        item = self.manager.add("http://127.0.0.1:1/file.zip", self.dest)
        self.wait_status(item.id, S.FAILED, timeout=25)
        self.assertIn("connect", self.manager.get_item(item.id).error_message.lower())

    def test_invalid_input_is_rejected_without_creating_items(self) -> None:
        for bad in ("", "not a url", "ftp://x.com/a", "http://"):
            with self.assertRaises(InvalidUrlError):
                self.manager.add(bad, self.dest)
        with self.assertRaises(StorageError):
            self.manager.add(self.server.url("/file.bin"), "")
        self.assertEqual(self.manager.list_items(), [])

    def test_add_without_starting(self) -> None:
        item = self.manager.add(self.server.url("/file.bin"), self.dest, start=False)
        self.assertEqual(item.status, S.PENDING)
        self.assertEqual(self.manager.active_count(), 0)
        self.manager.start(item.id)
        self.wait_status(item.id, S.COMPLETED)

    def test_scheduled_download_starts_at_due_time_and_persists_schedule(self) -> None:
        scheduled_at = time.time() + 2
        item = self.manager.add(
            self.server.url("/file.bin"),
            self.dest,
            scheduled_at=scheduled_at,
        )
        self.assertEqual(item.status, S.PENDING)
        self.assertEqual(item.scheduled_at, scheduled_at)

        reloaded = SqliteDownloadRepository(self.db)
        try:
            [saved] = reloaded.load_all()
            self.assertEqual(saved.scheduled_at, scheduled_at)
        finally:
            reloaded.close()

        self.manager.shutdown(timeout=3)
        self.manager = self.make_manager()
        self.manager.load()
        self.wait_status(item.id, S.COMPLETED, timeout=10)
        completed = self.manager.get_item(item.id)
        self.assertIsNone(completed.scheduled_at)
        self.assertEqual(completed.file_path.read_bytes(), PAYLOAD)

    def test_scheduled_download_can_be_started_immediately(self) -> None:
        item = self.manager.add(
            self.server.url("/file.bin"),
            self.dest,
            start=False,
            scheduled_at=time.time() + 60,
        )
        self.manager.start(item.id)
        self.wait_status(item.id, S.COMPLETED)
        self.assertIsNone(self.manager.get_item(item.id).scheduled_at)

    def test_invalid_schedule_is_rejected(self) -> None:
        with self.assertRaises(InvalidOperationError):
            self.manager.add(
                self.server.url("/file.bin"),
                self.dest,
                start=False,
                scheduled_at=time.time() - 1,
            )
        with self.assertRaises(InvalidOperationError):
            self.manager.add(
                self.server.url("/file.bin"),
                self.dest,
                start=True,
                scheduled_at=time.time() + 60,
            )
        self.assertEqual(self.manager.list_items(), [])

    def test_concurrency_limit_queues_downloads_and_starts_them_fifo(self) -> None:
        running = [
            self.manager.add(self.server.url("/slow.bin"), self.dest)
            for _ in range(MAX_CONCURRENT_DOWNLOADS)
        ]
        self.assertTrue(wait_for(
            lambda: all(self.manager.get_item(item.id).downloaded_bytes > 0 for item in running)
        ))
        self.assertEqual(self.manager.active_count(), MAX_CONCURRENT_DOWNLOADS)

        queued = self.manager.add(self.server.url("/file.bin"), self.dest)
        queued_next = self.manager.add(self.server.url("/attach"), self.dest)
        discarded = self.manager.add(self.server.url("/missing"), self.dest)
        self.assertEqual((queued.status, queued_next.status, discarded.status),
                         (S.QUEUED, S.QUEUED, S.QUEUED))
        self.manager.cancel(discarded.id)
        self.assertEqual(self.manager.get_item(discarded.id).status, S.CANCELLED)

        self.manager.cancel(running[0].id)
        self.wait_status(running[0].id, S.CANCELLED)
        self.wait_status(queued.id, S.COMPLETED)
        self.wait_status(queued_next.id, S.COMPLETED)
        self.assertLessEqual(self.manager.active_count(), MAX_CONCURRENT_DOWNLOADS)

    def test_transient_network_error_is_retried(self) -> None:
        class FailOnce:
            def __init__(self) -> None:
                self.attempts = 0
                self.http = HttpDownloader(chunk_size=16 * 1024, progress_interval=0.05)

            def download(self, job, control, observer):
                self.attempts += 1
                if self.attempts == 1:
                    raise NetworkError("Temporary connection failure", retryable=True)
                return self.http.download(job, control, observer)

        downloader = FailOnce()
        self.manager.shutdown()
        self.manager = self.make_manager(downloader)
        with patch(
            "omni_download_manager.services.download_manager.RETRY_BACKOFF_BASE_SECONDS", 0.001
        ):
            item = self.manager.add(self.server.url("/attach"), self.dest)
            self.wait_status(item.id, S.COMPLETED)
        self.assertEqual(downloader.attempts, 2)
        self.assertEqual(self.manager.get_item(item.id).file_path.read_bytes(), PAYLOAD[:5000])

    def test_permanent_http_error_is_not_retried(self) -> None:
        class AlwaysMissing:
            def __init__(self) -> None:
                self.attempts = 0

            def download(self, job, control, observer):
                self.attempts += 1
                raise HttpStatusError(404)

        downloader = AlwaysMissing()
        self.manager.shutdown()
        self.manager = self.make_manager(downloader)
        item = self.manager.add(self.server.url("/missing"), self.dest)
        self.wait_status(item.id, S.FAILED)
        self.assertEqual(downloader.attempts, 1)

    def test_retryable_http_error_gets_three_retries(self) -> None:
        class AlwaysUnavailable:
            def __init__(self) -> None:
                self.attempts = 0

            def download(self, job, control, observer):
                self.attempts += 1
                raise HttpStatusError(503)

        downloader = AlwaysUnavailable()
        self.manager.shutdown()
        self.manager = self.make_manager(downloader)
        with patch(
            "omni_download_manager.services.download_manager.RETRY_BACKOFF_BASE_SECONDS", 0.001
        ):
            item = self.manager.add(self.server.url("/boom"), self.dest)
            self.wait_status(item.id, S.FAILED)
        self.assertEqual(downloader.attempts, 4)

    def test_pause_interrupts_retry_backoff(self) -> None:
        class AlwaysOffline:
            def __init__(self) -> None:
                self.attempts = 0

            def download(self, job, control, observer):
                self.attempts += 1
                raise NetworkError("Temporary connection failure", retryable=True)

        downloader = AlwaysOffline()
        self.manager.shutdown()
        self.manager = self.make_manager(downloader)
        with patch(
            "omni_download_manager.services.download_manager.RETRY_BACKOFF_BASE_SECONDS", 1
        ):
            item = self.manager.add(self.server.url("/slow.bin"), self.dest)
            self.assertTrue(wait_for(lambda: self.manager.get_item(item.id).retry_attempt == 1))
            self.manager.pause(item.id)
            self.wait_status(item.id, S.PAUSED)
        self.assertEqual(downloader.attempts, 1)

    def test_custom_filename(self) -> None:
        item = self.manager.add(self.server.url("/file.bin"), self.dest, "my:file?.bin")
        self.wait_status(item.id, S.COMPLETED)
        self.assertEqual(self.manager.get_item(item.id).filename, "my_file_.bin")

    def test_remove_completed_keeps_or_deletes_file(self) -> None:
        a = self.manager.add(self.server.url("/file.bin"), self.dest)
        self.wait_status(a.id, S.COMPLETED)
        path_a = self.manager.get_item(a.id).file_path
        self.manager.remove(a.id)
        self.assertTrue(path_a.exists())
        self.assertEqual(self.manager.list_items(), [])

        b = self.manager.add(self.server.url("/file.bin"), self.dest)
        self.wait_status(b.id, S.COMPLETED)
        path_b = self.manager.get_item(b.id).file_path
        self.manager.remove(b.id, delete_file=True)
        self.assertFalse(path_b.exists())
        reloaded = SqliteDownloadRepository(self.db)
        try:
            self.assertEqual(reloaded.load_all(), [])
        finally:
            reloaded.close()
        self.assertEqual(self.events[-1].kind, EventKind.REMOVED)

    def test_remove_active_download_cleans_up(self) -> None:
        item = self.manager.add(self.server.url("/slow.bin"), self.dest)
        wait_for(lambda: self.manager.get_item(item.id).downloaded_bytes > 0)
        self.manager.remove(item.id)
        self.assertTrue(wait_for(lambda: self.manager.active_count() == 0 and not list(self.dest.iterdir())))
        self.assertEqual(self.manager.list_items(), [])

    def test_same_file_twice_gets_distinct_names(self) -> None:
        ids = [self.manager.add(self.server.url("/file.bin"), self.dest).id for _ in range(3)]
        for item_id in ids:
            self.wait_status(item_id, S.COMPLETED)
        names = {self.manager.get_item(i).filename for i in ids}
        self.assertEqual(names, {"file.bin", "file (1).bin", "file (2).bin"})

    def test_invalid_operations_raise(self) -> None:
        item = self.manager.add(self.server.url("/file.bin"), self.dest)
        self.wait_status(item.id, S.COMPLETED)
        for action in (self.manager.start, self.manager.pause, self.manager.cancel):
            with self.assertRaises(InvalidOperationError):
                action(item.id)
        with self.assertRaises(InvalidOperationError):
            self.manager.start("does-not-exist")

    def test_shutdown_pauses_running_downloads_and_next_session_resumes(self) -> None:
        item = self.manager.add(self.server.url("/slow.bin"), self.dest)
        wait_for(lambda: self.manager.get_item(item.id).downloaded_bytes > 20_000)
        self.manager.shutdown(timeout=5)

        manager2 = self.make_manager()
        manager2.load()
        try:
            restored = manager2.get_item(item.id)
            self.assertEqual(restored.status, S.PAUSED)
            self.assertGreater(restored.downloaded_bytes, 0)
            manager2.start(item.id)
            self.assertTrue(
                wait_for(lambda: manager2.get_item(item.id).status is S.COMPLETED, 10)
            )
            self.assertEqual(manager2.get_item(item.id).file_path.read_bytes(), SLOW_PAYLOAD)
        finally:
            manager2.shutdown(timeout=3)
        self.manager = self.make_manager()  # tearDown shuts it down

    def test_crash_recovery_marks_interrupted_downloads_paused(self) -> None:
        repo = SqliteDownloadRepository(self.db)
        stuck = DownloadItem(
            url=self.server.url("/file.bin"), directory=str(self.dest), filename="file.bin",
            status=S.DOWNLOADING, downloaded_bytes=123,
        )
        repo.save(stuck)
        repo.close()
        manager = self.make_manager()
        manager.load()
        try:
            item = manager.get_item(stuck.id)
            self.assertEqual(item.status, S.PAUSED)
            self.assertEqual(item.downloaded_bytes, 0)  # no .part on disk
        finally:
            manager.shutdown(timeout=1)


    def test_listeners_run_after_the_manager_lock_is_released(self) -> None:
        """A listener must be able to hand the lock to another thread."""

        def lock_from_other_thread() -> bool:
            acquired = self.manager._lock.acquire(timeout=2.0)
            if acquired:
                self.manager._lock.release()
            return acquired

        results: list[bool] = []

        def listener(event) -> None:
            probe = threading.Thread(target=lambda: results.append(lock_from_other_thread()))
            probe.start()
            probe.join(timeout=3)
            if not results:
                results.append(False)

        self.manager.subscribe(listener)
        self.manager.add(self.server.url("/file.bin"), self.dest, start=False)

        self.assertTrue(results, "the listener was never called")
        self.assertTrue(
            all(results), "a listener ran while the manager lock was still held"
        )

    def test_queue_keeps_moving_when_recording_a_result_fails(self) -> None:
        """A broken _finish must still free the slot and start queued downloads."""

        class Blocking:
            def __init__(self) -> None:
                self.released = threading.Event()

            def download(self, job, control, observer):
                self.released.wait(timeout=10)
                return DownloadOutcome(
                    OutcomeKind.COMPLETED, job.directory / job.filename, 0, 0
                )

        engine = Blocking()
        self.manager.shutdown(timeout=3)
        self.manager = self.make_manager(engine)
        try:
            ids = [
                self.manager.add(self.server.url("/file.bin"), self.dest, start=True).id
                for _ in range(MAX_CONCURRENT_DOWNLOADS + 1)
            ]
            queued_id = ids[-1]
            self.assertTrue(
                wait_for(lambda: self.status(queued_id) is S.QUEUED, 5),
                f"expected a queued download, got {self.status(queued_id)}",
            )
            self.assertEqual(self.manager.active_count(), MAX_CONCURRENT_DOWNLOADS)

            def broken_finish(*args, **kwargs):
                raise RuntimeError("recording the result failed")

            with patch.object(DownloadManager, "_finish", broken_finish):
                engine.released.set()
                self.assertTrue(
                    wait_for(lambda: self.status(queued_id) is not S.QUEUED, 10),
                    "the queued download never started",
                )
        finally:
            engine.released.set()


if __name__ == "__main__":
    unittest.main()
