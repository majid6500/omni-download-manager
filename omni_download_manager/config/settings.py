"""User-configurable settings.

Adding a setting means adding one field to :class:`Settings` (and, if it needs range
checks, one entry in ``_VALIDATORS``). Unknown or malformed values in the file on disk
fall back to the field's default, so older or hand-edited files never crash the app.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Callable

from omni_download_manager.core.errors import StorageError, storage_error_from_os

logger = logging.getLogger(__name__)

THEMES = ("dark", "light")


def default_download_dir() -> str:
    return str(Path.home() / "Downloads")


@dataclass(frozen=True)
class Settings:
    download_dir: str = field(default_factory=default_download_dir)
    start_immediately: bool = True
    confirm_destructive_actions: bool = True
    theme: str = "dark"
    connect_timeout: float = 15.0
    read_timeout: float = 30.0
    use_system_proxy: bool = True
    max_download_speed_mib: float = 0.0
    completion_notifications_enabled: bool = True
    window_geometry: str = ""


_VALIDATORS: dict[str, Callable[[Any], bool]] = {
    "theme": lambda value: value in THEMES,
    "connect_timeout": lambda value: 1 <= value <= 300,
    "read_timeout": lambda value: 1 <= value <= 300,
    "max_download_speed_mib": lambda value: 0 <= value <= 1000,
    "download_dir": lambda value: bool(value.strip()),
}


def _check(name: str, default: Any, value: Any) -> tuple[bool, Any]:
    """Validate ``value`` against the type of ``default`` and any range rule."""
    if isinstance(default, bool):
        ok = isinstance(value, bool)
    elif isinstance(default, float):
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        if ok:
            value = float(value)
    else:
        ok = isinstance(value, type(default))
    if ok and name in _VALIDATORS:
        ok = bool(_VALIDATORS[name](value))
    return ok, value


def _coerce(name: str, default: Any, value: Any) -> Any:
    ok, checked = _check(name, default, value)
    return checked if ok else default


def settings_from_dict(data: dict[str, Any]) -> Settings:
    defaults = Settings()
    values = {
        f.name: _coerce(f.name, getattr(defaults, f.name), data[f.name])
        for f in fields(Settings)
        if f.name in data
    }
    return replace(defaults, **values)


class SettingsStore:
    """Loads, validates, saves and broadcasts changes to :class:`Settings`."""

    def __init__(self, path: Path, settings: Settings | None = None) -> None:
        self._path = path
        self._settings = settings or Settings()
        self._lock = threading.Lock()
        self._listeners: list[Callable[[Settings], None]] = []

    @classmethod
    def load(cls, path: Path) -> "SettingsStore":
        if not path.exists():
            return cls(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("settings root must be an object")
        except (OSError, ValueError) as exc:
            logger.warning("Could not read settings (%s). Using defaults.", exc)
            _quarantine(path)
            return cls(path)
        return cls(path, settings_from_dict(raw))

    def get(self) -> Settings:
        with self._lock:
            return self._settings

    def subscribe(self, listener: Callable[[Settings], None]) -> None:
        self._listeners.append(listener)

    def update(self, **changes: Any) -> Settings:
        """Apply ``changes``, persist them and notify listeners.

        Invalid values are rejected with ``ValueError`` before anything changes.
        """
        valid_names = {f.name for f in fields(Settings)}
        unknown = set(changes) - valid_names
        if unknown:
            raise ValueError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
        with self._lock:
            current = self._settings
            checked: dict[str, Any] = {}
            for name, value in changes.items():
                ok, coerced = _check(name, getattr(current, name), value)
                if not ok:
                    raise ValueError(f"Invalid value for setting '{name}': {value!r}")
                checked[name] = coerced
            self._settings = replace(current, **checked)
            updated = self._settings
        self._save(updated)
        for listener in list(self._listeners):
            try:
                listener(updated)
            except Exception:
                logger.exception("Settings listener failed")
        return updated

    def _save(self, settings: Settings) -> None:
        temp = self._path.with_suffix(".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
            os.replace(temp, self._path)
        except OSError as exc:
            logger.error("Could not save settings: %s", exc)
            raise StorageError(
                "Your settings couldn't be saved. " + storage_error_from_os(exc).user_message,
                detail=repr(exc),
            ) from exc


def _quarantine(path: Path) -> None:
    try:
        os.replace(path, path.with_suffix(".corrupt"))
    except OSError:
        logger.debug("Could not move aside unreadable settings file", exc_info=True)
