"""Thin wrappers around operating-system integration."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from omni_download_manager.core.errors import AppError

logger = logging.getLogger(__name__)


def open_path(path: Path) -> None:
    """Open a file or folder with the default application."""
    if not path.exists():
        raise AppError("That file or folder no longer exists.", detail=f"Missing path: {path}")
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        logger.error("Could not open %s: %s", path, exc)
        raise AppError("The file couldn't be opened.", detail=repr(exc)) from exc


def resource_dir() -> Path:
    """Folder holding bundled assets, both in development and in a frozen build."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "omni_download_manager" / "resources"
    return Path(__file__).resolve().parent.parent / "resources"
