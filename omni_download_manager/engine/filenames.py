"""File naming: derive, sanitise and reserve names for downloads."""

from __future__ import annotations

import mimetypes
import os
import re
import threading
from email.message import Message
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote, urlsplit

from omni_download_manager.constants import PARTIAL_SUFFIX
from omni_download_manager.core.errors import StorageError, storage_error_from_os

FALLBACK_NAME = "download"
MAX_NAME_LENGTH = 180
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}

# Reservations must be atomic across concurrently starting downloads.
_NAME_LOCK = threading.Lock()


def sanitize_filename(name: str, fallback: str = FALLBACK_NAME) -> str:
    """Make ``name`` safe as a single Windows/POSIX path component."""
    cleaned = _INVALID_CHARS.sub("_", name).strip().strip(".")
    cleaned = cleaned.rstrip(" .")
    if not cleaned:
        return fallback
    if cleaned.split(".")[0].upper() in _RESERVED_NAMES:
        cleaned = "_" + cleaned
    if len(cleaned) > MAX_NAME_LENGTH:
        stem, ext = _split_extension(cleaned)
        cleaned = stem[: MAX_NAME_LENGTH - len(ext)] + ext
    return cleaned


def filename_from_url(url: str) -> str | None:
    segment = unquote(urlsplit(url).path).rstrip("/").rsplit("/", 1)[-1]
    segment = sanitize_filename(segment, fallback="") if segment else ""
    return segment or None


def filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None
    # Servers often send raw UTF-8 that the HTTP layer decoded as latin-1.
    try:
        value = value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    message = Message()
    message["content-disposition"] = value
    name = message.get_filename()
    if not name:
        return None
    return sanitize_filename(os.path.basename(name.replace("\\", "/")), fallback="") or None


def derive_filename(final_url: str, headers: Mapping[str, str]) -> str:
    """Name from Content-Disposition, else the URL path, else a generic name + extension."""
    name = filename_from_content_disposition(headers.get("Content-Disposition"))
    if name:
        return name
    name = filename_from_url(final_url)
    if name:
        return name
    content_type = (headers.get("Content-Type") or "").split(";")[0].strip()
    extension = mimetypes.guess_extension(content_type) if content_type else None
    return FALLBACK_NAME + (extension or "")


def partial_path_for(directory: Path, filename: str) -> Path:
    return directory / (filename + PARTIAL_SUFFIX)


def reserve_partial(directory: Path, filename: str) -> tuple[str, Path]:
    """Atomically claim a free name and create its (empty) ``.part`` file.

    Existing files are never overwritten: ``report.pdf`` becomes ``report (1).pdf``.
    Returns the chosen file name and the path of the partial file.
    """
    stem, extension = _split_extension(filename)
    with _NAME_LOCK:
        for attempt in range(10_000):
            candidate = filename if attempt == 0 else f"{stem} ({attempt}){extension}"
            final_path = directory / candidate
            part_path = partial_path_for(directory, candidate)
            if final_path.exists() or part_path.exists():
                continue
            try:
                with open(part_path, "xb"):
                    pass
            except FileExistsError:
                continue
            except OSError as exc:
                raise storage_error_from_os(exc) from exc
            return candidate, part_path
    raise StorageError("Could not find a free file name in the destination folder.")


def finalize_partial(part_path: Path) -> Path:
    """Rename ``name.part`` to ``name`` without overwriting an existing file."""
    final_name = part_path.name[: -len(PARTIAL_SUFFIX)]
    stem, extension = _split_extension(final_name)
    directory = part_path.parent
    with _NAME_LOCK:
        for attempt in range(10_000):
            candidate = final_name if attempt == 0 else f"{stem} ({attempt}){extension}"
            target = directory / candidate
            if target.exists():
                continue
            try:
                os.replace(part_path, target)
            except OSError as exc:
                raise storage_error_from_os(exc) from exc
            return target
    raise StorageError("Could not find a free file name in the destination folder.")


def _split_extension(name: str) -> tuple[str, str]:
    stem, extension = os.path.splitext(name)
    if stem.lower().endswith(".tar"):
        stem, extension = stem[:-4], ".tar" + extension
    return stem, extension
