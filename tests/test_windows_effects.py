import unittest
from unittest.mock import patch

from omni_download_manager.ui.windows_effects import _colorref, apply_title_bar_theme


class WindowsEffectsTests(unittest.TestCase):
    def test_colorref_conversion(self) -> None:
        self.assertEqual(_colorref("#123456"), 0x563412)
        self.assertEqual(_colorref("#FFFFFF"), 0xFFFFFF)

    def test_title_bar_theme_is_noop_outside_windows(self) -> None:
        with patch("omni_download_manager.ui.windows_effects.sys.platform", "linux"):
            apply_title_bar_theme(
                1,
                True,
                background="#000000",
                text="#FFFFFF",
                border="#333333",
            )


if __name__ == "__main__":
    unittest.main()
