"""Optional Windows-only polish. Every function is a safe no-op elsewhere."""

from __future__ import annotations

import logging
import sys

from omni_download_manager.constants import APP_USER_MODEL_ID

logger = logging.getLogger(__name__)


def set_app_user_model_id() -> None:
    """Lets the taskbar group and icon the app as itself rather than as python.exe."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        logger.debug("Could not set AppUserModelID", exc_info=True)


def _colorref(color: str) -> int:
    """Convert a #RRGGBB color to the COLORREF layout expected by DWM."""
    rgb = int(color.removeprefix("#"), 16)
    return ((rgb & 0xFF) << 16) | (rgb & 0xFF00) | ((rgb >> 16) & 0xFF)


def apply_title_bar_theme(hwnd: int, dark: bool, *, background: str, text: str, border: str) -> None:
    """Match the native title bar to the app palette where Windows supports it."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        dwmapi = ctypes.windll.dwmapi
        handle = wintypes.HWND(hwnd)
        dark_value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new / old id)
            result = dwmapi.DwmSetWindowAttribute(
                handle, attribute, ctypes.byref(dark_value), ctypes.sizeof(dark_value)
            )
            if result == 0:
                break

        # Custom caption colors are supported on Windows 11 22H2 and newer.
        for attribute, color in ((35, background), (36, text), (34, border)):
            value = ctypes.c_uint(_colorref(color))
            result = dwmapi.DwmSetWindowAttribute(
                handle, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result != 0:
                logger.debug("DWM title bar color attribute %d is unavailable", attribute)
    except Exception:
        logger.debug("Could not set title bar appearance", exc_info=True)
