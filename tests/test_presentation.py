import time
import unittest

from omni_download_manager.core.models import DownloadItem, DownloadStatus as S, StopReason
from omni_download_manager.ui.actions import ItemAction, menu_actions, row_buttons
from omni_download_manager.ui.presentation import Tone, describe, is_indeterminate, shows_progress_bar


def make(status, **kw) -> DownloadItem:
    return DownloadItem(url="http://x/a.zip", directory="/d", filename="a.zip", status=status, **kw)


class PresentationTests(unittest.TestCase):
    def test_downloading_text_contains_sizes_speed_and_eta(self) -> None:
        text = describe(make(S.DOWNLOADING, total_bytes=10_000_000, downloaded_bytes=2_000_000, speed_bps=1_000_000))
        self.assertEqual(text.status, "Downloading")
        self.assertIn("of", text.detail)
        self.assertIn("/s", text.detail)
        self.assertIn("left", text.detail)

    def test_failed_shows_error_in_footer(self) -> None:
        text = describe(make(S.FAILED, error_message="No connection"))
        self.assertEqual((text.tone, text.footer), (Tone.DANGER, "No connection"))

    def test_retrying_download_shows_attempt_and_error(self) -> None:
        text = describe(make(
            S.CONNECTING,
            retry_attempt=2,
            error_message="Connection lost. Retrying in 2 s.",
        ))
        self.assertEqual(text.status, "Retrying (2/3)…")
        self.assertEqual(text.detail, "Connection lost. Retrying in 2 s.")
        self.assertIs(text.tone, Tone.WARNING)

    def test_scheduled_download_shows_its_start_time(self) -> None:
        scheduled_at = time.time() + 3600
        text = describe(make(S.PENDING, scheduled_at=scheduled_at))
        self.assertEqual(text.status, "Scheduled")
        self.assertIn("Starts", text.detail)
        self.assertIs(text.tone, Tone.WARNING)

    def test_stopping_states_override_status(self) -> None:
        self.assertEqual(describe(make(S.DOWNLOADING, stop_reason=StopReason.PAUSE)).status, "Pausing…")
        self.assertEqual(describe(make(S.DOWNLOADING, stop_reason=StopReason.CANCEL)).status, "Cancelling…")

    def test_progress_bar_visibility_and_indeterminate(self) -> None:
        self.assertTrue(shows_progress_bar(make(S.PAUSED)))
        self.assertFalse(shows_progress_bar(make(S.COMPLETED)))
        self.assertTrue(is_indeterminate(make(S.CONNECTING)))
        self.assertTrue(is_indeterminate(make(S.DOWNLOADING)))
        self.assertFalse(is_indeterminate(make(S.DOWNLOADING, total_bytes=10)))

    def test_every_status_offers_sensible_actions(self) -> None:
        for status in S:
            buttons = row_buttons(make(status))
            self.assertTrue(1 <= len(buttons) <= 3, status)
            self.assertTrue(any(isinstance(e, type(None)) for e in menu_actions(make(status))))

    def test_scheduled_download_offers_start_now_action(self) -> None:
        scheduled = make(S.PENDING, scheduled_at=time.time() + 3600)
        self.assertEqual(row_buttons(scheduled)[0].label, "Start now")

    def test_pause_disabled_when_server_cannot_resume(self) -> None:
        pause = row_buttons(make(S.DOWNLOADING, resumable=False))[0]
        self.assertIs(pause.action, ItemAction.PAUSE)
        self.assertFalse(pause.enabled)
        self.assertTrue(row_buttons(make(S.DOWNLOADING, resumable=True))[0].enabled)


if __name__ == "__main__":
    unittest.main()
