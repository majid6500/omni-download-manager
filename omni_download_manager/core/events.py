"""Events published by the download manager to any interested listener."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from omni_download_manager.core.models import DownloadItem


class EventKind(str, Enum):
    ADDED = "added"
    UPDATED = "updated"
    REMOVED = "removed"


@dataclass(frozen=True)
class DownloadEvent:
    """``item`` is an immutable-by-convention snapshot, safe to hand to other threads."""

    kind: EventKind
    item: DownloadItem
