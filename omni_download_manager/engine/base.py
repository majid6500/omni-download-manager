"""Contracts between the download manager and a download engine.

The manager only depends on these types, so another transport (FTP, torrents, a
multi-connection HTTP engine, ...) can be added by implementing :class:`Downloader`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from omni_download_manager.core.models import StopReason

if TYPE_CHECKING:
    from omni_download_manager.engine.segments import MultiPartResumeState


class DownloadControl:
    """Thread-safe handle used to ask a running transfer to stop.

    The engine polls it between chunks. A cancel request always wins over a pause.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reason: StopReason | None = None
        self._stop_event = threading.Event()

    def request_stop(self, reason: StopReason) -> None:
        with self._lock:
            if self._reason is StopReason.CANCEL:
                return
            self._reason = reason
            self._stop_event.set()

    @property
    def reason(self) -> StopReason | None:
        with self._lock:
            return self._reason

    @property
    def stop_requested(self) -> bool:
        return self.reason is not None

    def wait_for_stop(self, timeout: float) -> bool:
        """Wait during retry backoff; return early when pause or cancel is requested."""
        return self._stop_event.wait(timeout)


@dataclass(frozen=True)
class DownloadJob:
    """Everything the engine needs to run one transfer."""

    url: str
    directory: Path
    filename: str
    # When False the engine derives the name from the server's response.
    filename_resolved: bool = False
    etag: str | None = None
    last_modified: str | None = None
    connect_timeout: float = 15.0
    read_timeout: float = 30.0
    use_system_proxy: bool = True
    # ``single`` / ``multipart`` when resuming; ``None`` lets the engine probe on a fresh start.
    transfer_mode: str | None = None
    multipart_resume: MultiPartResumeState | None = None
    # Page the link came from, when the caller knows it. Never invented by the engine.
    referer: str | None = None
    # Cookies already established for this transfer (e.g. by the multi-part probe's
    # redirect chain). Sent as plain name/value pairs, only for this download.
    cookies: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class TransferMetadata:
    """Facts learned from the server's first response."""

    filename: str
    total_bytes: int | None
    resumable: bool
    etag: str | None
    last_modified: str | None
    resumed_from: int = 0
    transfer_mode: str = "single"
    multipart_state: MultiPartResumeState | None = None


@dataclass(frozen=True)
class ProgressSnapshot:
    downloaded_bytes: int
    total_bytes: int | None
    speed_bps: float
    segment_fill: tuple[float, ...] | None = None
    multipart_state: MultiPartResumeState | None = None
    # Per-segment UI hints: retry counts and whether the segment is currently stalled/backing off.
    segment_retries: tuple[int, ...] | None = None
    segment_stalled: tuple[bool, ...] | None = None


class OutcomeKind(str, Enum):
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DownloadOutcome:
    kind: OutcomeKind
    path: Path | None
    downloaded_bytes: int
    total_bytes: int | None


class DownloadObserver(Protocol):
    """Receives updates from the thread running the transfer."""

    def metadata_received(self, metadata: TransferMetadata) -> None: ...

    def progress(self, snapshot: ProgressSnapshot) -> None: ...


class Downloader(Protocol):
    def download(
        self, job: DownloadJob, control: DownloadControl, observer: DownloadObserver
    ) -> DownloadOutcome:
        """Run the transfer to completion, a requested stop, or raise ``AppError``."""
        ...
