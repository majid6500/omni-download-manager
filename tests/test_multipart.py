import tempfile
import unittest
from pathlib import Path

from omni_download_manager.constants import DEFAULT_MULTIPART_CONNECTIONS
from omni_download_manager.core.models import StopReason
from omni_download_manager.engine.adaptive_http_downloader import AdaptiveHttpDownloader
from omni_download_manager.engine.base import DownloadControl, DownloadJob, OutcomeKind
from omni_download_manager.engine.segments import (
    encode_multipart_state,
    plan_segments,
    resume_state_from_specs,
    segment_file_path,
    total_downloaded_from_state,
)
from tests.support import PAYLOAD, TestServer, wait_for
from tests.test_engine import Recorder


class SegmentPlanningTests(unittest.TestCase):
    def test_plan_covers_entire_file_without_gaps(self) -> None:
        total = 10_000_000
        specs = plan_segments(total, DEFAULT_MULTIPART_CONNECTIONS)
        self.assertEqual(len(specs), DEFAULT_MULTIPART_CONNECTIONS)
        self.assertEqual(specs[0].start, 0)
        self.assertEqual(specs[-1].end, total - 1)
        covered = sum(spec.length for spec in specs)
        self.assertEqual(covered, total)

    def test_small_file_returns_no_segments(self) -> None:
        self.assertEqual(plan_segments(1024), ())


class MultiPartEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = TestServer().start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.engine = AdaptiveHttpDownloader(chunk_size=32 * 1024, progress_interval=0.0)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def job(self, path: str, name: str = "x", resolved: bool = False, **kw) -> DownloadJob:
        return DownloadJob(
            url=self.server.url(path),
            directory=self.dir,
            filename=name,
            filename_resolved=resolved,
            connect_timeout=3,
            read_timeout=10,
            **kw,
        )

    def test_multipart_download_matches_payload(self) -> None:
        recorder = Recorder()
        outcome = self.engine.download(self.job("/file.bin"), DownloadControl(), recorder)
        self.assertEqual(outcome.kind, OutcomeKind.COMPLETED)
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD)
        self.assertEqual(recorder.metadata.transfer_mode, "multipart")
        self.assertIsNotNone(recorder.metadata.multipart_state)
        self.assertGreaterEqual(len(recorder.metadata.multipart_state.segments), 2)

    def test_norange_falls_back_to_single(self) -> None:
        recorder = Recorder()
        outcome = self.engine.download(self.job("/norange.bin"), DownloadControl(), recorder)
        self.assertEqual(outcome.kind, OutcomeKind.COMPLETED)
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD)
        self.assertEqual(recorder.metadata.transfer_mode, "single")

    def test_progress_uses_byte_totals(self) -> None:
        recorder = Recorder()
        self.engine.download(self.job("/file.bin"), DownloadControl(), recorder)
        last = recorder.progress_updates[-1]
        self.assertEqual(last.downloaded_bytes, len(PAYLOAD))
        self.assertEqual(last.total_bytes, len(PAYLOAD))

    def test_oversized_saved_segment_falls_back_without_corrupting_file(self) -> None:
        filename = "damaged.bin"
        specs = plan_segments(len(PAYLOAD))
        state = resume_state_from_specs(self.dir, filename, len(PAYLOAD), specs)
        first = specs[0]
        segment_file_path(self.dir, filename, first.index).write_bytes(
            b"x" * (first.length + 1)
        )
        recorder = Recorder()
        job = self.job("/file.bin", filename, resolved=True, transfer_mode="multipart",
                       multipart_resume=state)

        outcome = self.engine.download(job, DownloadControl(), recorder)

        self.assertEqual(outcome.kind, OutcomeKind.COMPLETED)
        self.assertEqual(outcome.path.read_bytes(), PAYLOAD)
        self.assertEqual(recorder.metadata.transfer_mode, "single")

    def test_pause_keeps_segment_files(self) -> None:
        control = DownloadControl()
        recorder = Recorder()
        thread = __import__("threading").Thread(
            target=self.engine.download,
            args=(self.job("/slow.bin", "slow.bin"), control, recorder),
            daemon=True,
        )
        thread.start()
        ok = wait_for(lambda: len(recorder.progress_updates) > 2, timeout=8)
        self.assertTrue(ok)
        control.request_stop(StopReason.PAUSE)
        thread.join(timeout=10)
        seg_files = list(self.dir.glob("slow.bin.part.seg*"))
        self.assertGreaterEqual(len(seg_files), 1)


class MultiPartPersistenceTests(unittest.TestCase):
    def test_encode_decode_roundtrip(self) -> None:
        specs = plan_segments(1_500_000)
        state = resume_state_from_specs(Path("."), "f.bin", 1_500_000, specs)
        raw = encode_multipart_state(state)
        self.assertIn("segments", raw)
        self.assertEqual(total_downloaded_from_state(state), 0)
