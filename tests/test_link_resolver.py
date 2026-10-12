from __future__ import annotations

import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import patch

import requests

from omni_download_manager.core.errors import HttpStatusError, NetworkError
from omni_download_manager.core.models import StopReason
from omni_download_manager.engine.adaptive_http_downloader import AdaptiveHttpDownloader
from omni_download_manager.engine.base import DownloadControl, DownloadJob, OutcomeKind
from omni_download_manager.engine.http_downloader import HttpDownloader
from omni_download_manager.engine.base import ScopedCookie
from omni_download_manager.engine.http_downloader import apply_session_headers
from omni_download_manager.engine.link_resolver import SmartLinkResolver, _validate_resolved_url
from tests.support import PAYLOAD, TestServer
from tests.test_engine import Recorder


def _playwright_runtime_available() -> bool:
    if find_spec("playwright") is None:
        return False
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path).is_file()
    except (ImportError, OSError, PlaywrightError):
        return False


class SmartLinkResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = TestServer().start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def setUp(self) -> None:
        self.resolver = SmartLinkResolver()

    def resolve(self, path: str):
        return self.resolver.resolve(
            self.server.url(path),
            DownloadControl(),
            referer=None,
            connect_timeout=2,
            read_timeout=2,
            use_system_proxy=False,
        )

    def test_meta_refresh_resolves_to_a_validated_file_target(self) -> None:
        with patch("omni_download_manager.engine.link_resolver._validate_resolved_url"):
            target = self.resolve("/html-meta")
        self.assertEqual(target.url, self.server.url("/file.bin"))

    def test_html_is_detected_even_with_a_non_html_content_type(self) -> None:
        with patch("omni_download_manager.engine.link_resolver._validate_resolved_url"):
            target = self.resolve("/html-meta-no-type")
        self.assertEqual(target.url, self.server.url("/file.bin"))

    def test_standard_http_redirect_limit_is_preserved(self) -> None:
        with patch("omni_download_manager.engine.link_resolver._validate_resolved_url"):
            target = self.resolve("/redirect-count/10")
        self.assertEqual(target.url, self.server.url("/file.bin"))

    def test_javascript_page_reports_missing_optional_browser(self) -> None:
        with patch.dict(
            "sys.modules",
            {"playwright": None, "playwright.sync_api": None},
        ):
            with self.assertRaises(NetworkError) as context:
                self.resolve("/html-js")
        self.assertIn("may need JavaScript", context.exception.user_message)

    @unittest.skipUnless(
        _playwright_runtime_available(),
        "Optional Playwright Chromium runtime is not installed.",
    )
    def test_javascript_navigation_is_captured_before_file_transfer(self) -> None:
        with patch("omni_download_manager.engine.link_resolver._validate_resolved_url"):
            target = self.resolve("/html-js-nav")
        self.assertEqual(target.url, self.server.url("/file.bin"))

    def test_expired_temporary_url_is_reported_as_http_error(self) -> None:
        with self.assertRaises(HttpStatusError) as context:
            self.resolve("/expired")
        self.assertEqual(context.exception.status_code, 410)

    def test_redirect_to_loopback_is_blocked_before_following(self) -> None:
        with self.assertRaises(NetworkError) as context:
            self.resolve("/unsafe-redirect")
        self.assertIn("blocked a redirect", context.exception.user_message)

    def test_direct_private_resolved_target_is_blocked(self) -> None:
        with self.assertRaises(NetworkError) as context:
            _validate_resolved_url("http://127.0.0.1/private")
        self.assertIn("blocked a redirect", context.exception.user_message)

    def test_html_redirect_loop_stops_after_a_bounded_number_of_hops(self) -> None:
        start_count = self.server.request_count("/html-loop")
        with patch("omni_download_manager.engine.link_resolver._validate_resolved_url"):
            with self.assertRaises(NetworkError) as context:
                self.resolve("/html-loop")
        self.assertIn("too many intermediate redirects", context.exception.user_message)
        self.assertLessEqual(self.server.request_count("/html-loop") - start_count, 9)

    def test_resolution_cancellation_stops_before_network_access(self) -> None:
        control = DownloadControl()
        control.request_stop(StopReason.CANCEL)
        with self.assertRaisesRegex(NetworkError, "cancelled"):
            self.resolver.resolve(
                self.server.url("/html-meta"),
                control,
                referer=None,
                connect_timeout=2,
                read_timeout=2,
                use_system_proxy=False,
            )

    def test_timeout_is_reported_without_resolution_retry(self) -> None:
        session = requests.Session()
        session.get = unittest.mock.Mock(side_effect=requests.Timeout("timeout"))
        session.__enter__ = unittest.mock.Mock(return_value=session)
        session.__exit__ = unittest.mock.Mock(return_value=False)
        with patch("omni_download_manager.engine.link_resolver.requests.Session", return_value=session):
            with self.assertRaises(NetworkError) as context:
                self.resolve("/html-meta")
        self.assertIn("too long", context.exception.user_message)
        session.get.assert_called_once()

    def test_adaptive_engine_resolves_html_then_uses_existing_download_engine(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            job = DownloadJob(
                self.server.url("/html-meta"),
                directory,
                "download",
                connect_timeout=2,
                read_timeout=2,
            )
            engine = AdaptiveHttpDownloader(chunk_size=16 * 1024, progress_interval=0)
            with patch("omni_download_manager.engine.link_resolver._validate_resolved_url"):
                outcome = engine.download(job, DownloadControl(), Recorder())
            self.assertEqual(outcome.kind, OutcomeKind.COMPLETED)
            self.assertEqual(outcome.path.read_bytes(), PAYLOAD)

    def test_html_error_is_not_saved_by_the_existing_single_stream_engine(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            job = DownloadJob(
                self.server.url("/html-error"),
                directory,
                "error-page",
                connect_timeout=2,
                read_timeout=2,
            )
            with self.assertRaises(NetworkError):
                HttpDownloader().download(job, DownloadControl(), Recorder())
            self.assertEqual(list(directory.iterdir()), [])

    def test_file_without_content_type_remains_downloadable(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            job = DownloadJob(
                self.server.url("/no-type.bin"),
                Path(root),
                "file.bin",
                connect_timeout=2,
                read_timeout=2,
                transfer_mode="single",
            )
            outcome = HttpDownloader().download(job, DownloadControl(), Recorder())
            self.assertEqual(outcome.kind, OutcomeKind.COMPLETED)
            self.assertEqual(outcome.path.read_bytes(), PAYLOAD[:5000])

    def test_download_engine_blocks_redirect_to_an_unrelated_private_host(self) -> None:
        job = DownloadJob(
            self.server.url("/unsafe-redirect"),
            Path(tempfile.gettempdir()),
            "blocked.bin",
            connect_timeout=2,
            read_timeout=2,
            transfer_mode="single",
        )
        with self.assertRaises(NetworkError) as context:
            HttpDownloader().download(job, DownloadControl(), Recorder())
        self.assertIn("blocked a redirect", context.exception.user_message)

    def test_normal_non_html_target_is_left_for_existing_engine(self) -> None:
        target = self.resolve("/file.bin")
        self.assertEqual(target.url, self.server.url("/file.bin"))

    def test_browser_cookies_remain_scoped_to_their_origin(self) -> None:
        session = requests.Session()
        apply_session_headers(
            session,
            user_agent="ODM tests",
            cookies=(
                ScopedCookie("session", "secret", "example.com", "/private"),
            ),
        )
        same_origin = session.prepare_request(
            requests.Request("GET", "https://example.com/private/file.zip")
        )
        other_origin = session.prepare_request(
            requests.Request("GET", "https://other.example/private/file.zip")
        )
        self.assertIn("session=secret", same_origin.headers["Cookie"])
        self.assertNotIn("Cookie", other_origin.headers)


if __name__ == "__main__":
    unittest.main()
