"""Where Omni Download Manager keeps its data."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from omni_download_manager.constants import APP_DATA_DIR_NAME, APP_NAME

logger = logging.getLogger(__name__)

DATA_DIR_ENV_VAR = "ODM_DATA_DIR"
LEGACY_DATA_DIR_ENV_VAR = "FETCHLY_DATA_DIR"
LEGACY_APP_NAME = "Fetchly"


@dataclass(frozen=True)
class AppPaths:
    data_dir: Path

    @property
    def settings_file(self) -> Path:
        return self.data_dir / "settings.json"

    @property
    def database_file(self) -> Path:
        return self.data_dir / "downloads.db"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def lock_file(self) -> Path:
        # Keep the lock basename so locks from the previous version survive directory migration.
        return self.data_dir / "fetchly.lock"

    def ensure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


def resolve_app_paths(override: Path | None = None) -> AppPaths:
    """Pick the data directory.

    Order: explicit argument, ``ODM_DATA_DIR``, the legacy ``FETCHLY_DATA_DIR``,
    then the platform's per-user application data location. The old default data
    directory is renamed in place on first launch to preserve settings and history.
    """
    if override is not None:
        return AppPaths(Path(override))
    for env_var in (DATA_DIR_ENV_VAR, LEGACY_DATA_DIR_ENV_VAR):
        env_value = os.environ.get(env_var)
        if env_value:
            return AppPaths(Path(env_value))
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        data_dir = base / APP_NAME
        legacy_dir = base / LEGACY_APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
        data_dir = base / APP_DATA_DIR_NAME
        legacy_dir = base / LEGACY_APP_NAME.lower()

    if not data_dir.exists() and legacy_dir.exists():
        logger.info("Migrating application data from %s to %s", legacy_dir, data_dir)
        legacy_dir.rename(data_dir)
    return AppPaths(data_dir)
