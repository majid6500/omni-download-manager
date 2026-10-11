import io
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from omni_download_manager.browser_integration.ipc import BrowserIpcServer, send_to_running_app
from omni_download_manager.browser_integration.native_messaging import (
    handle_message,
    run_native_host,
)
from omni_download_manager.browser_integration.protocol import (
    MAX_MESSAGE_BYTES,
    decode_frame,
    encode_frame,
    validate_message,
)
from omni_download_manager.config.paths import AppPaths


class BrowserProtocolTests(unittest.TestCase):
    def test_download_message_is_validated_and_referer_is_reduced_to_its_origin(self) -> None:
        result = validate_message(
            {
                "action": "download",
                "url": "https://example.com/files/report.zip?token=abc",
                "filename": "../../CON.txt",
                "referer": "https://example.com/page?private=1",
            }
        )
        self.assertEqual(result["url"], "https://example.com/files/report.zip?token=abc")
        self.assertEqual(result["filename"], "_.._CON.txt")
        self.assertEqual(result["referer"], "https://example.com/")

    def test_rejects_unsupported_actions_schemes_and_malformed_fields(self) -> None:
        for message in (
            {"action": "execute", "url": "https://example.com"},
            {"action": "download", "url": "file:///private.txt"},
            {"action": "download", "url": "https://user:secret@example.com/private"},
            {"action": "download", "url": "https://example.com", "filename": 42},
        ):
            with self.subTest(message=message), self.assertRaises(ValueError):
                validate_message(message)

    def test_json_frame_roundtrip_and_oversize_guard(self) -> None:
        message = {"action": "download", "url": "https://example.com/a.zip"}
        self.assertEqual(decode_frame(encode_frame(message)), message)
        with self.assertRaises(ValueError):
            encode_frame({"value": "x" * MAX_MESSAGE_BYTES})

    def test_native_host_reads_and_writes_native_messaging_frames(self) -> None:
        incoming = encode_frame({"action": "status"})
        source = io.BytesIO(incoming)
        destination = io.BytesIO()
        with tempfile.TemporaryDirectory() as root:
            result = run_native_host(AppPaths(Path(root)), source, destination)
        self.assertEqual(result, 0)
        response = decode_frame(destination.getvalue())
        self.assertTrue(response["ok"])
        self.assertTrue(response["native_host"])
        self.assertFalse(response["application_running"])

    def test_native_host_launches_desktop_and_retries_ipc_without_command_line_url(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            paths = AppPaths(Path(root))
            message = {"action": "download", "url": "https://example.com/private?token=secret"}
            with (
                patch("omni_download_manager.browser_integration.native_messaging.Path.is_file",
                      return_value=True),
                patch("omni_download_manager.browser_integration.native_messaging.subprocess.Popen") as popen,
                patch(
                    "omni_download_manager.browser_integration.native_messaging.send_to_running_app",
                    side_effect=[None, {"ok": True, "message": "accepted"}],
                ),
                patch("omni_download_manager.browser_integration.native_messaging.time.sleep"),
            ):
                response = handle_message(paths, message)

        self.assertTrue(response["ok"])
        launch_args = popen.call_args.args[0]
        self.assertIn("--browser-request-listener", launch_args)
        self.assertNotIn(message["url"], launch_args)


class BrowserIpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_request_is_delivered_to_running_application(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            paths = AppPaths(Path(root))
            received = []
            server = BrowserIpcServer(paths, received.append)
            result = []

            def send() -> None:
                result.append(
                    send_to_running_app(
                        paths,
                        {"action": "download", "url": "https://example.com/file.zip"},
                    )
                )

            worker = threading.Thread(target=send)
            worker.start()
            deadline = time.monotonic() + 3
            while worker.is_alive() and time.monotonic() < deadline:
                self._app.processEvents()
                time.sleep(0.005)
            worker.join(timeout=1)
            server.close()

            self.assertFalse(worker.is_alive())
            self.assertTrue(result, "IPC client did not return a response")
            self.assertIsNotNone(result[0], "IPC server did not return a response")
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["url"], "https://example.com/file.zip")
            self.assertTrue(result[0]["ok"])


if __name__ == "__main__":
    unittest.main()
