"""The download manager: the application's single entry point for download operations.

Responsibilities
----------------
* owns the authoritative :class:`DownloadItem` objects and enforces the state machine;
* starts each transfer on a worker thread and translates the engine's callbacks and
  outcome into state changes;
* persists changes (progress is persisted at a throttled rate);
* publishes :class:`DownloadEvent` snapshots to subscribers (the UI, later e.g.
  notifications).

It deliberately knows nothing about Qt. Concurrency policy lives in one place,
``_start_queued``: it fills available worker slots in FIFO order.
"""

from __future__ import annotations

import dataclasses
import logging
import math
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from omni_download_manager.config.settings import Settings
from omni_download_manager.core.errors import (
    AppError,
    HttpStatusError,
    InvalidOperationError,
    NetworkError,
    PersistenceError,
    StorageError,
    storage_error_from_os,
)
from omni_download_manager.core.events import DownloadEvent, EventKind
from omni_download_manager.core.models import ACTIVE_STATUSES, DownloadItem, DownloadStatus, StopReason
from omni_download_manager.constants import MAX_CONCURRENT_DOWNLOADS
from omni_download_manager.constants import MAX_AUTOMATIC_RETRIES, RETRY_BACKOFF_BASE_SECONDS
from omni_download_manager.engine.base import (
    DownloadControl,
    DownloadJob,
    DownloadOutcome,
    Downloader,
    OutcomeKind,
    ProgressSnapshot,
    TransferMetadata,
)
from omni_download_manager.engine.filenames import filename_from_url, sanitize_filename
from omni_download_manager.engine.segments import (
    decode_multipart_state,
    encode_multipart_state,
    list_segment_files,
    remove_segment_files,
    segment_downloaded_bytes,
    segment_fill_from_state,
    total_downloaded_from_state,
)
from omni_download_manager.storage.repository import DownloadRepository
from omni_download_manager.utils.urls import validate_url

logger = logging.getLogger(__name__)
SCHEDULE_CHECK_INTERVAL_SECONDS = 0.5

Listener = Callable[[DownloadEvent], None]
UNEXPECTED_ERROR_MESSAGE = "Something unexpected went wrong. Details were written to the log."
_STARTABLE = frozenset(
    {
        DownloadStatus.PENDING,
        DownloadStatus.QUEUED,
        DownloadStatus.PAUSED,
        DownloadStatus.FAILED,
        DownloadStatus.CANCELLED,
    }
)


@dataclass
class _Worker:
    control: DownloadControl
    thread: threading.Thread


class DownloadManager:
    def __init__(
        self,
        repository: DownloadRepository,
        downloader: Downloader,
        settings_provider: Callable[[], Settings],
        *,
        persist_interval: float = 2.0,
    ) -> None:
        self._repository = repository
        self._downloader = downloader
        self._settings_provider = settings_provider
        self._persist_interval = persist_interval

        self._lock = threading.RLock()
        # Per-thread nesting depth of _locked(); only the outermost block publishes.
        self._local = threading.local()
        self._pending: list[DownloadEvent] = []
        self._items: dict[str, DownloadItem] = {}
        self._workers: dict[str, _Worker] = {}
        self._listeners: list[Listener] = []
        self._last_persisted: dict[str, float] = {}
        self._shutting_down = False
        self._shutdown_ready_to_close = False
        self._repository_closed = False
        self._scheduler_stop = threading.Event()
        self._scheduler_thread = threading.Thread(
            target=self._run_scheduler,
            name="download-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()

    # ------------------------------------------------------------ subscription

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        with self._locked():
            self._listeners.append(listener)

        def unsubscribe() -> None:
            with self._locked():
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return unsubscribe

    @contextmanager
    def _locked(self):
        """Context manager: hold the manager lock, then publish what it produced.

        Every state change that must notify subscribers runs inside this block.
        Listeners are only called after the lock has been released (see
        :meth:`_dispatch_events`), so a slow listener can never block another
        thread's state change and a listener that calls back into the manager
        cannot deadlock against it. Nesting is supported: only the outermost block
        publishes, which keeps the events in recording order.
        """
        depth = getattr(self._local, "depth", 0)
        try:
            with self._lock:
                self._local.depth = depth + 1
                try:
                    yield
                finally:
                    self._local.depth = depth
        finally:
            if getattr(self._local, "depth", 0) == 0:
                self._dispatch_events()

    def _record_event(self, kind: EventKind, item: DownloadItem) -> None:
        """Snapshot an event for later publication. The caller must hold the lock."""
        self._pending.append(DownloadEvent(kind, dataclasses.replace(item)))

    def _dispatch_events(self) -> None:
        """Publish recorded events to the listeners without holding any lock."""
        while True:
            with self._lock:
                if not self._pending:
                    return
                events, self._pending = self._pending, []
                listeners = list(self._listeners)
            for event in events:
                for listener in listeners:
                    try:
                        listener(event)
                    except Exception:
                        logger.exception("Download event listener failed")

    # ----------------------------------------------------------------- queries

    def list_items(self) -> list[DownloadItem]:
        """Snapshots of all downloads, newest first."""
        with self._locked():
            items = sorted(self._items.values(), key=lambda i: i.created_at, reverse=True)
            return [dataclasses.replace(i) for i in items]

    def get_item(self, item_id: str) -> DownloadItem:
        with self._locked():
            return dataclasses.replace(self._require(item_id))

    def active_count(self) -> int:
        with self._locked():
            return len(self._workers)

    # -------------------------------------------------------------- life cycle

    def load(self) -> None:
        """Load saved downloads. Transfers interrupted by a crash or exit become paused."""
        with self._locked():
            for item in self._repository.load_all():
                if item.status in ACTIVE_STATUSES:
                    item.transition_to(DownloadStatus.PAUSED)
                elif item.status is DownloadStatus.QUEUED:
                    item.transition_to(DownloadStatus.PENDING)
                if item.status in (DownloadStatus.PAUSED, DownloadStatus.FAILED):
                    item.downloaded_bytes = _restored_downloaded_bytes(item)
                item.speed_bps = 0.0
                item.segment_fill = None
                item.stop_reason = None
                item.retry_attempt = 0
                self._items[item.id] = item
        logger.info("Loaded %d download(s)", len(self._items))

    def shutdown(self, timeout: float = 8.0) -> None:
        """Request pauses, wait briefly, and close storage after workers have stopped."""
        with self._locked():
            if self._repository_closed:
                return
            self._shutting_down = True
            self._scheduler_stop.set()
            workers = dict(self._workers)
            for worker in workers.values():
                worker.control.request_stop(StopReason.PAUSE)
        deadline = time.monotonic() + timeout
        self._scheduler_thread.join(max(0.0, deadline - time.monotonic()))
        for worker in workers.values():
            worker.thread.join(max(0.0, deadline - time.monotonic()))

        with self._locked():
            for item_id, worker in self._workers.items():
                if worker.thread.is_alive():
                    logger.warning("Worker for %s did not stop in time", item_id)
            for item in self._items.values():
                self._persist(item)
            self._shutdown_ready_to_close = True
        self._close_repository_if_idle()

    # ---------------------------------------------------------------- commands

    def add(
        self,
        url: str,
        directory: str | Path,
        filename: str | None = None,
        *,
        start: bool | None = None,
        scheduled_at: float | None = None,
    ) -> DownloadItem:
        clean_url = validate_url(url)
        if start is None:
            start = scheduled_at is None
        if scheduled_at is not None:
            if not math.isfinite(scheduled_at) or scheduled_at <= time.time():
                raise InvalidOperationError("Choose a start time in the future.")
            if start:
                raise InvalidOperationError(
                    "A scheduled download can't also be set to start immediately."
                )
        if not str(directory).strip():
            raise StorageError("Choose a folder to save the file in.")
        target = Path(directory).expanduser()
        _check_directory(target)

        custom_name = sanitize_filename(filename) if filename and filename.strip() else None
        item = DownloadItem(
            url=clean_url,
            directory=str(target),
            filename=custom_name or filename_from_url(clean_url) or "download",
            filename_resolved=custom_name is not None,
            scheduled_at=scheduled_at,
        )
        with self._locked():
            self._items[item.id] = item
            self._persist(item)
            self._record_event(EventKind.ADDED, item)
        logger.info("Added download %s: %s", item.id, clean_url)

        if start:
            self.start(item.id)
        return self.get_item(item.id)

    def start(self, item_id: str) -> None:
        """Start, resume or retry a download (the same operation from the engine's view)."""
        with self._locked():
            item = self._require(item_id)
            if item_id in self._workers:
                logger.debug("Start ignored for %s: already running", item_id)
                return
            if item.status not in _STARTABLE:
                raise InvalidOperationError(
                    f"This download is {item.status.value} and can't be started.",
                    detail=f"start() from {item.status.value}",
                )
            item.scheduled_at = None
            self._start_item(item)

    def restart(self, item_id: str) -> None:
        """Discard a failed or cancelled transfer and start it again from byte zero."""
        with self._locked():
            item = self._require(item_id)
            if item_id in self._workers:
                logger.debug("Restart ignored for %s: already running", item_id)
                return
            if item.status not in (DownloadStatus.FAILED, DownloadStatus.CANCELLED):
                raise InvalidOperationError(
                    f"This download is {item.status.value} and can't be restarted.",
                    detail=f"restart() from {item.status.value}",
                )
            if item.status is DownloadStatus.FAILED:
                item.transition_to(DownloadStatus.CANCELLED)
            _clear_transfer_artifacts(item)
            item.downloaded_bytes = 0
            item.transfer_mode = None
            item.multipart_segments_json = None
            item.segment_fill = None
            item.segment_retries = None
            item.segment_stalled = None
            item.error_message = None
            item.scheduled_at = None
            self._start_item(item)

    def _start_item(self, item: DownloadItem) -> None:
        item.error_message = None
        item.speed_bps = 0.0
        item.stop_reason = None
        item.retry_attempt = 0
        if len(self._workers) >= MAX_CONCURRENT_DOWNLOADS:
            item.transition_to(DownloadStatus.QUEUED)
        else:
            item.transition_to(DownloadStatus.CONNECTING)
            self._launch(item)
        self._persist(item)
        self._record_event(EventKind.UPDATED, item)

    def pause(self, item_id: str) -> None:
        with self._locked():
            item = self._require(item_id)
            if item.status is DownloadStatus.QUEUED:
                # Not running yet: leave the queue without discarding what the item
                # already downloaded (cancelling it would delete that data).
                item.transition_to(DownloadStatus.PENDING)
                self._persist(item)
                self._record_event(EventKind.UPDATED, item)
                return
            worker = self._workers.get(item_id)
            if worker is None or not item.is_active:
                raise InvalidOperationError("Only a running download can be paused.")
            if item.resumable is False:
                raise InvalidOperationError(
                    "This server doesn't support resuming, so the download can't be paused. "
                    "You can cancel it instead."
                )
            worker.control.request_stop(StopReason.PAUSE)
            if item.stop_reason is not StopReason.CANCEL:
                item.stop_reason = StopReason.PAUSE
            self._record_event(EventKind.UPDATED, item)

    def cancel(self, item_id: str) -> None:
        """Stop the download and discard what was downloaded so far."""
        with self._locked():
            item = self._require(item_id)
            worker = self._workers.get(item_id)
            if worker is not None:
                worker.control.request_stop(StopReason.CANCEL)
                item.stop_reason = StopReason.CANCEL
                self._record_event(EventKind.UPDATED, item)
                return
            if item.status in (DownloadStatus.COMPLETED, DownloadStatus.CANCELLED):
                raise InvalidOperationError("This download can't be cancelled.")
            item.transition_to(DownloadStatus.CANCELLED)
            item.scheduled_at = None
            _clear_transfer_artifacts(item)
            item.downloaded_bytes = 0
            item.transfer_mode = None
            item.multipart_segments_json = None
            item.segment_fill = None
            item.error_message = None
            self._persist(item)
            self._record_event(EventKind.UPDATED, item)

    def remove(self, item_id: str, *, delete_file: bool = False) -> None:
        """Remove from the list. Unfinished data is always discarded.

        ``delete_file`` additionally deletes the finished file from disk.
        """
        with self._locked():
            item = self._require(item_id)
            worker = self._workers.get(item_id)
            if worker is not None:
                # The worker deletes its own partial file when it sees the cancel request.
                worker.control.request_stop(StopReason.CANCEL)
            elif item.status is not DownloadStatus.COMPLETED:
                _clear_transfer_artifacts(item)
            elif delete_file:
                _delete_quietly(item.file_path)

            del self._items[item_id]
            self._last_persisted.pop(item_id, None)
            try:
                self._repository.delete(item_id)
            except PersistenceError:
                logger.exception("Could not delete download %s from the database", item_id)
            self._record_event(EventKind.REMOVED, item)
        logger.info("Removed download %s", item_id)

    # ----------------------------------------------------------------- workers

    def _run_scheduler(self) -> None:
        while not self._scheduler_stop.wait(SCHEDULE_CHECK_INTERVAL_SECONDS):
            self._start_due_scheduled()

    def _start_due_scheduled(self) -> None:
        now = time.time()
        with self._locked():
            if self._shutting_down:
                return
            due_items = sorted(
                (
                    item for item in self._items.values()
                    if item.status is DownloadStatus.PENDING
                    and item.scheduled_at is not None
                    and item.scheduled_at <= now
                ),
                key=lambda item: (item.scheduled_at, item.created_at),
            )
            for item in due_items:
                item.scheduled_at = None
                self._start_item(item)

    def _launch(self, item: DownloadItem) -> None:
        """Launch one worker; callers enforce the concurrency limit under _lock."""
        settings = self._settings_provider()
        job = DownloadJob(
            url=item.url,
            directory=Path(item.directory),
            filename=item.filename,
            filename_resolved=item.filename_resolved,
            etag=item.etag,
            last_modified=item.last_modified,
            connect_timeout=settings.connect_timeout,
            read_timeout=settings.read_timeout,
            use_system_proxy=settings.use_system_proxy,
            transfer_mode=item.transfer_mode,
            multipart_resume=decode_multipart_state(item.multipart_segments_json),
        )
        control = DownloadControl()
        thread = threading.Thread(
            target=self._run_worker,
            args=(item.id, job, control),
            name=f"download-{item.id[:6]}",
            daemon=True,
        )
        self._workers[item.id] = _Worker(control, thread)
        thread.start()

    def _run_worker(self, item_id: str, job: DownloadJob, control: DownloadControl) -> None:
        outcome: DownloadOutcome | None = None
        failure: str | None = None
        observer = _Observer(self, item_id)
        for attempt in range(MAX_AUTOMATIC_RETRIES + 1):
            try:
                outcome = self._downloader.download(job, control, observer)
                break
            except AppError as exc:
                if not _is_retryable(exc) or attempt >= MAX_AUTOMATIC_RETRIES:
                    logger.warning("Download %s failed: %s", item_id, exc)
                    failure = exc.user_message
                    break
                retry_number = attempt + 1
                delay = RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.info(
                    "Retrying download %s (%d/%d) in %.1f seconds",
                    item_id, retry_number, MAX_AUTOMATIC_RETRIES, delay,
                )
                self._on_retry(item_id, retry_number, exc.user_message, delay)
                if control.wait_for_stop(delay):
                    outcome = self._stopped_during_backoff(item_id, job, control)
                    break
                job = self._refresh_job(item_id, job)
            except Exception:
                logger.exception("Unexpected error in download %s", item_id)
                failure = UNEXPECTED_ERROR_MESSAGE
                break
        try:
            self._finish(item_id, control, outcome, failure)
        except Exception:
            logger.exception("Could not record the result of download %s", item_id)
            # Whatever went wrong, the slot must be released and the queue kept
            # moving, and the item must never be left looking like it still runs.
            with self._locked():
                self._workers.pop(item_id, None)
                item = self._items.get(item_id)
                if item is not None and item.status in ACTIVE_STATUSES:
                    item.transition_to(DownloadStatus.PAUSED)
                    self._persist(item)
                    self._record_event(EventKind.UPDATED, item)
                try:
                    self._start_queued()
                except Exception:
                    logger.exception("Could not continue the queue for %s", item_id)
        finally:
            self._close_repository_if_idle()

    def _finish(
        self,
        item_id: str,
        control: DownloadControl,
        outcome: DownloadOutcome | None,
        failure: str | None,
    ) -> None:
        with self._locked():
            self._workers.pop(item_id, None)
            item = self._items.get(item_id)
            if item is None:  # removed while running
                self._start_queued()
                return
            item.speed_bps = 0.0
            item.stop_reason = None

            if failure is not None and control.reason is StopReason.CANCEL:
                outcome, failure = DownloadOutcome(OutcomeKind.CANCELLED, None, 0, None), None
                _delete_quietly(item.partial_path)
            elif failure is not None and control.reason is StopReason.PAUSE:
                outcome, failure = DownloadOutcome(OutcomeKind.PAUSED, None, 0, None), None

            if failure is not None:
                item.error_message = failure
                item.transition_to(DownloadStatus.FAILED)
                item.downloaded_bytes = _restored_downloaded_bytes(item)
            elif outcome is not None and outcome.kind is OutcomeKind.COMPLETED:
                item.transition_to(DownloadStatus.COMPLETED)
                if outcome.path is not None:
                    item.filename = outcome.path.name
                item.downloaded_bytes = outcome.downloaded_bytes
                item.total_bytes = outcome.downloaded_bytes
                item.completed_at = time.time()
                item.error_message = None
                item.transfer_mode = None
                item.multipart_segments_json = None
                item.segment_fill = None
                logger.info("Download %s completed: %s", item_id, item.file_path)
            elif outcome is not None and outcome.kind is OutcomeKind.CANCELLED:
                item.transition_to(DownloadStatus.CANCELLED)
                item.downloaded_bytes = 0
                logger.info("Download %s cancelled", item_id)
            else:
                item.transition_to(DownloadStatus.PAUSED)
                item.downloaded_bytes = _restored_downloaded_bytes(item)
                logger.info("Download %s paused at %d bytes", item_id, item.downloaded_bytes)

            self._persist(item)
            self._record_event(EventKind.UPDATED, item)
            self._start_queued()

    def _start_queued(self) -> None:
        """Fill free worker slots in FIFO order."""
        if self._shutting_down:
            return
        while len(self._workers) < MAX_CONCURRENT_DOWNLOADS:
            queued = [
                item for item in self._items.values()
                if item.status is DownloadStatus.QUEUED
            ]
            if not queued:
                return
            item = min(queued, key=lambda candidate: candidate.created_at)
            try:
                item.transition_to(DownloadStatus.CONNECTING)
                item.error_message = None
                item.speed_bps = 0.0
                item.stop_reason = None
                self._launch(item)
            except Exception:
                # Roll back instead of leaving a half-started item or blocking the
                # loop; the queue is retried on the next completion.
                logger.exception("Could not start queued download %s", item.id)
                self._workers.pop(item.id, None)
                if item.status is DownloadStatus.CONNECTING:
                    item.transition_to(DownloadStatus.QUEUED)
                break
            self._persist(item)
            self._record_event(EventKind.UPDATED, item)

    def _on_retry(self, item_id: str, attempt: int, message: str, delay: float) -> None:
        with self._locked():
            item = self._items.get(item_id)
            if item is None:
                return
            if item.status is DownloadStatus.DOWNLOADING:
                item.transition_to(DownloadStatus.CONNECTING)
            item.retry_attempt = attempt
            item.error_message = f"{message} Retrying in {delay:g} s."
            item.speed_bps = 0.0
            self._record_event(EventKind.UPDATED, item)

    def _stopped_during_backoff(
        self, item_id: str, job: DownloadJob, control: DownloadControl
    ) -> DownloadOutcome:
        with self._locked():
            item = self._items.get(item_id)
            item = dataclasses.replace(item) if item is not None else None
        partial_path = item.partial_path if item is not None else job.directory / f"{job.filename}.part"
        downloaded = _size_or_zero(partial_path)
        if control.reason is StopReason.CANCEL:
            _delete_quietly(partial_path)
            return DownloadOutcome(OutcomeKind.CANCELLED, None, 0, None)
        return DownloadOutcome(OutcomeKind.PAUSED, partial_path, downloaded, None)

    def _refresh_job(self, item_id: str, job: DownloadJob) -> DownloadJob:
        with self._locked():
            item = self._items.get(item_id)
            if item is None:
                return job
            return dataclasses.replace(
                job,
                filename=item.filename,
                filename_resolved=item.filename_resolved,
                etag=item.etag,
                last_modified=item.last_modified,
            )

    # Called from worker threads through _Observer.

    def _on_metadata(self, item_id: str, metadata: TransferMetadata) -> None:
        with self._locked():
            item = self._items.get(item_id)
            if item is None:
                return
            item.filename = metadata.filename
            item.filename_resolved = True
            item.total_bytes = metadata.total_bytes
            item.resumable = metadata.resumable
            item.etag = metadata.etag
            item.last_modified = metadata.last_modified
            item.downloaded_bytes = metadata.resumed_from
            item.transfer_mode = metadata.transfer_mode
            if metadata.multipart_state is not None:
                item.multipart_segments_json = encode_multipart_state(metadata.multipart_state)
                item.segment_fill = segment_fill_from_state(metadata.multipart_state)
            elif metadata.transfer_mode == "single":
                item.multipart_segments_json = None
                item.segment_fill = None
            if item.status is DownloadStatus.CONNECTING:
                item.transition_to(DownloadStatus.DOWNLOADING)
            item.retry_attempt = 0
            item.error_message = None
            self._persist(item)
            self._record_event(EventKind.UPDATED, item)

    def _on_progress(self, item_id: str, snapshot: ProgressSnapshot) -> None:
        with self._locked():
            item = self._items.get(item_id)
            if item is None or item.status is not DownloadStatus.DOWNLOADING:
                return
            item.downloaded_bytes = snapshot.downloaded_bytes
            if snapshot.total_bytes is not None:
                item.total_bytes = snapshot.total_bytes
            item.speed_bps = snapshot.speed_bps
            item.segment_fill = snapshot.segment_fill
            # Per-segment UI hints
            item.segment_retries = snapshot.segment_retries
            item.segment_stalled = snapshot.segment_stalled
            if snapshot.multipart_state is not None:
                item.multipart_segments_json = encode_multipart_state(snapshot.multipart_state)
            now = time.monotonic()
            if now - self._last_persisted.get(item_id, 0.0) >= self._persist_interval:
                self._persist(item)
            self._record_event(EventKind.UPDATED, item)

    # ----------------------------------------------------------------- helpers

    def _require(self, item_id: str) -> DownloadItem:
        item = self._items.get(item_id)
        if item is None:
            raise InvalidOperationError(
                "That download no longer exists.", detail=f"Unknown download id {item_id}"
            )
        return item

    def _persist(self, item: DownloadItem) -> None:
        self._last_persisted[item.id] = time.monotonic()
        try:
            self._repository.save(item)
        except PersistenceError:
            # Losing a progress write must not abort a running download.
            logger.exception("Could not save download %s", item.id)

    def _close_repository_if_idle(self) -> None:
        with self._locked():
            if (
                not self._shutdown_ready_to_close
                or self._workers
                or self._repository_closed
            ):
                return
            self._repository.close()
            self._repository_closed = True
            logger.info("Download manager shut down")


class _Observer:
    """Adapter handed to the engine; forwards its callbacks to the manager."""

    def __init__(self, manager: DownloadManager, item_id: str) -> None:
        self._manager = manager
        self._item_id = item_id

    def metadata_received(self, metadata: TransferMetadata) -> None:
        self._manager._on_metadata(self._item_id, metadata)

    def progress(self, snapshot: ProgressSnapshot) -> None:
        self._manager._on_progress(self._item_id, snapshot)


def _check_directory(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise storage_error_from_os(exc) from exc
    if not path.is_dir() or not os.access(path, os.W_OK):
        raise StorageError("Omni Download Manager can't save files to that folder. Choose another one.")


def _size_or_zero(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _restored_downloaded_bytes(item: DownloadItem) -> int:
    """Bytes already on disk for an item that is not running.

    For a multi-part transfer the persisted segment state is authoritative; when it
    is missing (old record, unreadable JSON) the segment files themselves are
    measured instead of reporting zero. Otherwise the ``.part`` file is used.
    """
    if item.transfer_mode == "multipart":
        state = decode_multipart_state(item.multipart_segments_json)
        if state is not None:
            return total_downloaded_from_state(state)
        if item.filename_resolved:
            segment_files = list_segment_files(Path(item.directory), item.filename)
            if segment_files:
                return sum(segment_downloaded_bytes(path) for path in segment_files)
    return _size_or_zero(item.partial_path)


def _clear_transfer_artifacts(item: DownloadItem) -> None:
    _delete_quietly(item.partial_path)
    if item.filename_resolved:
        remove_segment_files(Path(item.directory), item.filename)


def _delete_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete %s", path, exc_info=True)


def _is_retryable(exc: AppError) -> bool:
    if isinstance(exc, NetworkError):
        return exc.retryable
    if isinstance(exc, HttpStatusError):
        return exc.status_code in (408, 425, 429) or 500 <= exc.status_code < 600
    return False
