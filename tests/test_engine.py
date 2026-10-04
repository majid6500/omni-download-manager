import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from omni_download_manager.constants import PARTIAL_SUFFIX
from omni_download_manager.core.errors import HttpStatusError, InvalidUrlError, NetworkError
from omni_download_manager.core.models import StopReason
from omni_download_manager.engine.base import DownloadControl, DownloadJob, OutcomeKind
from omni_download_manager.engine.http_downloader import HttpDownloader
from omni_download_manager.engine.speed import DownloadSpeedLimiter
from tests.support import ETAG, PAYLOAD, SLOW_PAYLOAD, TestServer, wait_for


class Recorder:
    def __init__(self) -> None:
        self.metadata = None
        self.progress_updates = []

    def metadata_received(self, metadata) -> None:
        self.metadata = metadata

    def progress(self, snapshot) -> None:
        self.progress_updates.append(snapshot)


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = TestServer().start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.engine = HttpDownloader(chunk_size=16 * 1024, progress_interval=0.0)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def job(self, path: str, name: str = "x", resolved: bool = False, **kw) -> DownloadJob:
        return DownloadJob(
            url=self.server.url(path),
            directory=self.dir,
            filename=name,
            filename_resolved=resolved,
            connect_timeout=3,
            read_timeout=5,
            **kw,
        )

    def run_job(self, job: DownloadJob, control: DownloadControl | None = None):
        recorder = Recorder()
        outcome = self.engine.download(job, control or DownloadControl(), recorder)
        return outcome, recorder

    def test_full_download(self) -> None:
        outcome, rec = self.run_job(self.job("/file.bin"))
        self.assertEqual(outcome.kind, OutcomeKind.COMPLETED)
        self.assertEqual(outcome.path, self.dir / "file.bin")
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD)
        self.assertFalse(list(self.dir.glob("*" + PARTIAL_SUFFIX)))
        self.assertEqual(rec.metadata.total_bytes, len(PAYLOAD))
        self.assertTrue(rec.metadata.resumable)
        self.assertEqual(rec.metadata.etag, ETAG)
        self.assertGreater(len(rec.progress_updates), 3)
        self.assertEqual(rec.progress_updates[-1].downloaded_bytes, len(PAYLOAD))

    def test_system_proxy_can_be_disabled_for_requests(self) -> None:
        session = Mock()
        session.get.return_value.status_code = 200
        session.get.return_value.headers = {}

        self.engine._open_response(session, self.job("/file.bin", use_system_proxy=False), 0)

        self.assertEqual(
            session.get.call_args.kwargs["proxies"],
            {"http": "", "https": ""},
        )

    def test_http_download_obeys_speed_limit(self) -> None:
        engine = HttpDownloader(
            chunk_size=128 * 1024,
            progress_interval=0,
            speed_limiter=DownloadSpeedLimiter(2 * 1024 * 1024),
        )
        started = time.monotonic()
        outcome = engine.download(self.job("/file.bin"), DownloadControl(), Recorder())
        elapsed = time.monotonic() - started
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD)
        self.assertGreaterEqual(elapsed, 0.65)

    def test_redirect_uses_final_name(self) -> None:
        outcome, _ = self.run_job(self.job("/redirect"))
        self.assertEqual(outcome.path.name, "file.bin")
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD)

    def test_content_disposition_name(self) -> None:
        outcome, rec = self.run_job(self.job("/attach"))
        self.assertEqual(outcome.path.name, "My Report.pdf")
        self.assertEqual(rec.metadata.filename, "My Report.pdf")

    def test_content_disposition_utf8_name(self) -> None:
        outcome, _ = self.run_job(self.job("/attach-utf8"))
        self.assertEqual(outcome.path.name, "café.txt")

    def test_name_from_last_url_segment(self) -> None:
        outcome, _ = self.run_job(self.job("/noname/"))
        self.assertEqual(outcome.path.name, "noname")

    def test_existing_file_is_never_overwritten(self) -> None:
        (self.dir / "file.bin").write_bytes(b"precious")
        outcome, _ = self.run_job(self.job("/file.bin"))
        self.assertEqual(outcome.path.name, "file (1).bin")
        self.assertEqual((self.dir / "file.bin").read_bytes(), b"precious")

    def test_chunked_response_without_length(self) -> None:
        outcome, rec = self.run_job(self.job("/chunked.bin"))
        self.assertEqual(outcome.kind, OutcomeKind.COMPLETED)
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD[:200_000])
        self.assertIsNone(rec.metadata.total_bytes)

    def test_resume_from_partial_file(self) -> None:
        (self.dir / ("file.bin" + PARTIAL_SUFFIX)).write_bytes(PAYLOAD[:500_000])
        outcome, rec = self.run_job(self.job("/file.bin", "file.bin", True, etag=ETAG))
        self.assertEqual(rec.metadata.resumed_from, 500_000)
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD)

    def test_changed_file_restarts_instead_of_corrupting(self) -> None:
        (self.dir / ("changing.bin" + PARTIAL_SUFFIX)).write_bytes(b"old content" * 100)
        outcome, rec = self.run_job(self.job("/changing.bin", "changing.bin", True, etag=ETAG))
        self.assertEqual(rec.metadata.resumed_from, 0)
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD)

    def test_server_without_range_support_restarts(self) -> None:
        (self.dir / ("norange.bin" + PARTIAL_SUFFIX)).write_bytes(b"junk" * 50)
        outcome, rec = self.run_job(self.job("/norange.bin", "norange.bin", True))
        self.assertFalse(rec.metadata.resumable)
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD)

    def test_partial_that_is_already_complete(self) -> None:
        (self.dir / ("file.bin" + PARTIAL_SUFFIX)).write_bytes(PAYLOAD)
        outcome, _ = self.run_job(self.job("/file.bin", "file.bin", True, etag=ETAG))
        self.assertEqual(outcome.kind, OutcomeKind.COMPLETED)
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD)

    def test_http_error_status(self) -> None:
        with self.assertRaises(HttpStatusError) as ctx:
            self.run_job(self.job("/missing"))
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("not found", ctx.exception.user_message)
        with self.assertRaises(HttpStatusError):
            self.run_job(self.job("/boom"))
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_connection_refused(self) -> None:
        job = DownloadJob("http://127.0.0.1:1/x", self.dir, "x", connect_timeout=2, read_timeout=2)
        with self.assertRaises(NetworkError):
            self.run_job(job)

    def test_invalid_scheme(self) -> None:
        job = DownloadJob("ftp://example.com/x", self.dir, "x")
        with self.assertRaises(InvalidUrlError):
            self.run_job(job)

    def test_truncated_response_keeps_partial_for_resume(self) -> None:
        with self.assertRaises(NetworkError):
            self.run_job(self.job("/short.bin"))
        parts = list(self.dir.glob("*" + PARTIAL_SUFFIX))
        self.assertEqual(len(parts), 1)
        # Only bytes that were fully received are kept, and they must be a valid prefix.
        size = parts[0].stat().st_size
        self.assertTrue(0 < size <= 40_000)
        self.assertEqual(parts[0].read_bytes(), PAYLOAD[:size])

    def test_pause_then_resume_produces_identical_file(self) -> None:
        control = DownloadControl()
        recorder = Recorder()

        def stop_when_started() -> None:
            wait_for(lambda: len(recorder.progress_updates) >= 5)
            control.request_stop(StopReason.PAUSE)

        threading.Thread(target=stop_when_started, daemon=True).start()
        outcome = self.engine.download(self.job("/slow.bin"), control, recorder)
        self.assertEqual(outcome.kind, OutcomeKind.PAUSED)
        part = outcome.path
        self.assertTrue(part.name.endswith(PARTIAL_SUFFIX))
        paused_size = part.stat().st_size
        self.assertGreater(paused_size, 0)
        self.assertLess(paused_size, len(SLOW_PAYLOAD))

        meta = recorder.metadata
        resume_job = self.job(
            "/slow.bin", meta.filename, True, etag=meta.etag, last_modified=meta.last_modified
        )
        outcome2, rec2 = self.run_job(resume_job)
        self.assertEqual(rec2.metadata.resumed_from, paused_size)
        self.assertEqual(outcome2.kind, OutcomeKind.COMPLETED)
        self.assertEqual(outcome2.path.read_bytes(), SLOW_PAYLOAD)

    def test_cancel_deletes_partial_data(self) -> None:
        control = DownloadControl()
        recorder = Recorder()

        def cancel_when_started() -> None:
            wait_for(lambda: len(recorder.progress_updates) >= 3)
            control.request_stop(StopReason.CANCEL)

        threading.Thread(target=cancel_when_started, daemon=True).start()
        outcome = self.engine.download(self.job("/slow.bin"), control, recorder)
        self.assertEqual(outcome.kind, OutcomeKind.CANCELLED)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_stop_requested_before_start_makes_no_request(self) -> None:
        control = DownloadControl()
        control.request_stop(StopReason.PAUSE)
        outcome, rec = self.run_job(self.job("/file.bin"), control)
        self.assertEqual(outcome.kind, OutcomeKind.PAUSED)
        self.assertIsNone(rec.metadata)

    def test_cancel_wins_over_pause(self) -> None:
        control = DownloadControl()
        control.request_stop(StopReason.CANCEL)
        control.request_stop(StopReason.PAUSE)
        self.assertIs(control.reason, StopReason.CANCEL)

    def test_concurrent_downloads_of_same_name_do_not_collide(self) -> None:
        results = []

        def go() -> None:
            outcome, _ = self.run_job(self.job("/file.bin"))
            results.append(outcome.path.name)

        threads = [threading.Thread(target=go) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(set(results)), 4)
        for path in self.dir.iterdir():
            self.assertEqual(path.read_bytes(), PAYLOAD)


if __name__ == "__main__":
    unittest.main()
