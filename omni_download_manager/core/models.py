"""Download state model.

A :class:`DownloadItem` is the single source of truth for one download. Its life cycle
is an explicit state machine (``ALLOWED_TRANSITIONS``) so that queues, retries,
scheduling or notifications can later be built on well-defined transitions instead of
ad-hoc flags.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from omni_download_manager.constants import PARTIAL_SUFFIX
from omni_download_manager.core.errors import InvalidOperationError


class DownloadStatus(str, Enum):
    PENDING = "pending"          # added, not started yet
    QUEUED = "queued"            # waiting for a worker slot
    CONNECTING = "connecting"    # worker started, waiting for the server
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StopReason(str, Enum):
    """Why a running transfer is being asked to stop."""

    PAUSE = "pause"
    CANCEL = "cancel"


ACTIVE_STATUSES = frozenset({DownloadStatus.CONNECTING, DownloadStatus.DOWNLOADING})

_S = DownloadStatus
ALLOWED_TRANSITIONS: dict[DownloadStatus, frozenset[DownloadStatus]] = {
    _S.PENDING: frozenset({_S.QUEUED, _S.CONNECTING, _S.CANCELLED}),
    _S.QUEUED: frozenset({_S.PENDING, _S.CONNECTING, _S.CANCELLED}),
    _S.CONNECTING: frozenset({_S.DOWNLOADING, _S.PAUSED, _S.FAILED, _S.CANCELLED, _S.COMPLETED}),
    _S.DOWNLOADING: frozenset({_S.CONNECTING, _S.PAUSED, _S.FAILED, _S.CANCELLED, _S.COMPLETED}),
    _S.PAUSED: frozenset({_S.QUEUED, _S.CONNECTING, _S.CANCELLED}),
    _S.FAILED: frozenset({_S.QUEUED, _S.CONNECTING, _S.CANCELLED}),
    _S.CANCELLED: frozenset({_S.QUEUED, _S.CONNECTING}),
    _S.COMPLETED: frozenset(),
}


@dataclass
class DownloadItem:
    url: str
    directory: str
    filename: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: DownloadStatus = DownloadStatus.PENDING
    total_bytes: int | None = None
    downloaded_bytes: int = 0
    # False until the real file name is known from the server's response headers.
    filename_resolved: bool = False
    # None = not known yet, False = the server cannot resume transfers.
    resumable: bool | None = None
    etag: str | None = None
    last_modified: str | None = None
    error_message: str | None = None
    created_at: float = field(default_factory=time.time)
    scheduled_at: float | None = None
    completed_at: float | None = None

    # Transient values: never persisted.
    speed_bps: float = 0.0
    stop_reason: StopReason | None = None
    retry_attempt: int = 0

    def transition_to(self, new_status: DownloadStatus) -> None:
        if new_status == self.status:
            return
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidOperationError(
                f"This action isn't available for a download that is {self.status.value}.",
                detail=f"Invalid transition {self.status.value} -> {new_status.value}",
            )
        self.status = new_status

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def file_path(self) -> Path:
        return Path(self.directory) / self.filename

    @property
    def partial_path(self) -> Path:
        return Path(self.directory) / (self.filename + PARTIAL_SUFFIX)

    @property
    def progress(self) -> float | None:
        """Fraction between 0 and 1, or ``None`` when the total size is unknown."""
        if self.status is DownloadStatus.COMPLETED:
            return 1.0
        if not self.total_bytes:
            return None
        return max(0.0, min(1.0, self.downloaded_bytes / self.total_bytes))

    @property
    def eta_seconds(self) -> float | None:
        if self.status is not DownloadStatus.DOWNLOADING or self.speed_bps <= 0:
            return None
        if not self.total_bytes:
            return None
        return max(0.0, (self.total_bytes - self.downloaded_bytes) / self.speed_bps)
