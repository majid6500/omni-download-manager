"""HTTP multi-part download engine with automatic fallback to single-connection."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import closing
from dataclasses import dataclass, replace
from typing import Callable

import requests

from omni_download_manager.constants import (
    DEFAULT_MULTIPART_CONNECTIONS,
    MAX_SEGMENT_RETRIES,
    RETRY_BACKOFF_BASE_SECONDS,
    VERSION,
)
from omni_download_manager.core.errors import AppError, NetworkError, storage_error_from_os
from omni_download_manager.core.models import StopReason
from omni_download_manager.engine.base import (
    DownloadControl,
    DownloadJob,
    DownloadObserver,
    DownloadOutcome,
    OutcomeKind,
    ProgressSnapshot,
    TransferMetadata,
)
from omni_download_manager.engine.filenames import derive_filename, finalize_partial, reserve_partial
from omni_download_manager.engine.http_downloader import (
    HttpDownloader,
    _CONTENT_RANGE,
    _RANGE_UNSATISFIED,
    _int_or_none,
    _next_chunk,
    _remove_quietly,
    translate_request_error,
)
from omni_download_manager.engine.segments import (
    MultiPartResumeState,
    SegmentProgress,
    has_segment_files,
    merge_segments_to_partial,
    plan_segments,
    remove_segment_files,
    resume_state_from_specs,
    segment_downloaded_bytes,
    segment_file_path,
    segment_fill_from_state,
    total_downloaded_from_state,
)
from omni_download_manager.engine.speed import DownloadSpeedLimiter, SpeedMeter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ProbeResult:
    url: str
    filename: str
    total_bytes: int
    etag: str | None
    last_modified: str | None


class MultiPartHttpDownloader:
    """Range-based segmented downloads; one item uses a small pool of segment workers."""

    def __init__(
        self,
        *,
        chunk_size: int = 128 * 1024,
        progress_interval: float = 0.2,
        user_agent: str | None = None,
        speed_limiter: DownloadSpeedLimiter | None = None,
        connection_count: int = DEFAULT_MULTIPART_CONNECTIONS,
        single: HttpDownloader | None = None,
    ) -> None:
        self._chunk_size = chunk_size
        self._progress_interval = progress_interval
        self._user_agent = user_agent or f"ODM/{VERSION}"
        self._speed_limiter = speed_limiter or DownloadSpeedLimiter()
        self._connection_count = connection_count
        self._single = single or HttpDownloader(
            chunk_size=chunk_size,
            progress_interval=progress_interval,
            user_agent=user_agent,
            speed_limiter=self._speed_limiter,
        )

    def download(
        self, job: DownloadJob, control: DownloadControl, observer: DownloadObserver
    ) -> DownloadOutcome:
        try:
            job.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise storage_error_from_os(exc) from exc

        if control.stop_requested:
            return self._single._stopped(control, None, 0, None)

        resume = job.multipart_resume
        if resume is not None and len(resume.segments) >= 2:
            return self._run_multipart(job, control, observer, resume)

        if job.transfer_mode == "single":
            return self._single.download(job, control, observer)

        if job.filename_resolved and has_segment_files(job.directory, job.filename):
            decoded = job.multipart_resume
            if decoded is not None:
                return self._run_multipart(job, control, observer, decoded)

        probe = self._probe(job)
        if probe is None:
            logger.info("Multi-part probe failed for %s; using single connection", job.url)
            return self._single.download(job, control, observer)

        specs = plan_segments(probe.total_bytes, self._connection_count)
        if not specs:
            logger.info(
                "File too small for multi-part (%d bytes); using single connection",
                probe.total_bytes,
            )
            return self._single.download(_job_with_probe(job, probe), control, observer)

        filename = job.filename if job.filename_resolved else probe.filename
        if not job.filename_resolved:
            _, _ = reserve_partial(job.directory, filename)
        state = resume_state_from_specs(job.directory, filename, probe.total_bytes, specs)
        job = replace(
            _job_with_probe(job, probe),
            filename=filename,
            filename_resolved=True,
            multipart_resume=state,
        )
        logger.info(
            "Multi-part capability detected for %s: %d segments, %d bytes total",
            job.url,
            len(specs),
            probe.total_bytes,
        )
        return self._run_multipart(job, control, observer, state)

    # ------------------------------------------------------------------ probe

    def _probe(self, job: DownloadJob) -> _ProbeResult | None:
        with requests.Session() as session:
            session.headers.update({"User-Agent": self._user_agent, "Accept": "*/*"})
            proxies = None if job.use_system_proxy else {"http": "", "https": ""}
            head = None
            try:
                head = session.head(
                    job.url,
                    allow_redirects=True,
                    timeout=(job.connect_timeout, job.read_timeout),
                    proxies=proxies,
                )
                if head.status_code >= 400:
                    head = None
            except requests.RequestException:
                head = None

            url = head.url if head is not None else job.url
            total = _int_or_none(head.headers.get("Content-Length")) if head is not None else None
            etag = head.headers.get("ETag") if head is not None else None
            last_modified = head.headers.get("Last-Modified") if head is not None else None

            try:
                response = session.get(
                    url,
                    headers={"Range": "bytes=0-0"},
                    stream=True,
                    timeout=(job.connect_timeout, job.read_timeout),
                    proxies=proxies,
                )
            except requests.RequestException as exc:
                raise translate_request_error(exc) from exc

            with closing(response):
                if response.status_code != 206:
                    logger.debug(
                        "Range probe for %s returned %s (expected 206)",
                        url,
                        response.status_code,
                    )
                    return None
                range_headers = response.headers
                match = _CONTENT_RANGE.match(range_headers.get("Content-Range", ""))
                if not match or match.group(3) == "*":
                    return None
                declared_total = int(match.group(3))
                if total is not None and declared_total != total:
                    logger.debug(
                        "Range probe total mismatch for %s: head=%d content-range=%d",
                        url,
                        total,
                        declared_total,
                    )
                    return None
                if int(match.group(1)) != 0 or int(match.group(2)) != 0:
                    return None
                probe_length = _int_or_none(range_headers.get("Content-Length"))
                if probe_length is not None and probe_length != 1:
                    return None
                if total is None:
                    total = declared_total
                if total <= 0:
                    return None
                if etag is None:
                    etag = range_headers.get("ETag")
                if last_modified is None:
                    last_modified = range_headers.get("Last-Modified")

            if total is None or total <= 0:
                return None

            filename = (
                job.filename
                if job.filename_resolved
                else derive_filename(url, dict(range_headers))
            )
            return _ProbeResult(url, filename, total, etag, last_modified)

    # ------------------------------------------------------------------ run

    def _run_multipart(
        self,
        job: DownloadJob,
        control: DownloadControl,
        observer: DownloadObserver,
        state: MultiPartResumeState,
    ) -> DownloadOutcome:
        specs = plan_segments(state.total_bytes, self._connection_count)
        valid_state = len(specs) == len(state.segments) and all(
            (saved.index, saved.start, saved.end) == (spec.index, spec.start, spec.end)
            for saved, spec in zip(state.segments, specs)
        )
        if not valid_state or len(specs) < 2:
            logger.warning("Invalid multi-part resume state for %s; restarting as single", job.url)
            self._abort_multipart(job)
            fallback_job = replace(job, transfer_mode="single", multipart_resume=None)
            return self._single.download(fallback_job, control, observer)

        actual_segments: list[SegmentProgress] = []
        for spec in specs:
            path = segment_file_path(job.directory, job.filename, spec.index)
            actual = segment_downloaded_bytes(path)
            if actual > spec.length:
                logger.warning(
                    "Discarding oversized segment %d for %s (%d > %d bytes)",
                    spec.index,
                    job.filename,
                    actual,
                    spec.length,
                )
                self._abort_multipart(job)
                fallback_job = replace(job, transfer_mode="single", multipart_resume=None)
                return self._single.download(fallback_job, control, observer)
            actual_segments.append(
                SegmentProgress(spec.index, spec.start, spec.end, actual)
            )
        state = MultiPartResumeState(state.total_bytes, tuple(actual_segments))

        observer.metadata_received(
            TransferMetadata(
                filename=job.filename,
                total_bytes=state.total_bytes,
                resumable=True,
                etag=job.etag,
                last_modified=job.last_modified,
                resumed_from=total_downloaded_from_state(state),
                transfer_mode="multipart",
                multipart_state=state,
            )
        )

        progress_lock = threading.Lock()
        state_holder: list[MultiPartResumeState] = [state]
        # Per-segment UI hints: retry count and stalled flag.
        retries: list[int] = [0] * len(state.segments)
        stalled: list[bool] = [False] * len(state.segments)
        meter = SpeedMeter(initial_bytes=total_downloaded_from_state(state))
        last_report = time.monotonic()
        # Set when the multi-part run has to stop without a user pause/cancel (a
        # sibling segment failed, or the transfer is aborting): every segment worker
        # exits at the next check so no file is written while it is being cleaned up.
        stop_event = threading.Event()
        fallback_index: int | None = None

        def report_progress(force: bool = False) -> None:
            nonlocal last_report
            with progress_lock:
                current = state_holder[0]
                downloaded = total_downloaded_from_state(current)
                fill = segment_fill_from_state(current)
                retries_snapshot = tuple(retries) if retries else None
                stalled_snapshot = tuple(stalled) if stalled else None
            now = time.monotonic()
            if force or now - last_report >= self._progress_interval:
                last_report = now
                observer.progress(
                    ProgressSnapshot(
                        downloaded,
                        state.total_bytes,
                        meter.update(downloaded),
                        segment_fill=fill,
                        multipart_state=current,
                        segment_retries=retries_snapshot,
                        segment_stalled=stalled_snapshot,
                    )
                )

        def update_segment(index: int, downloaded: int) -> None:
            with progress_lock:
                current = state_holder[0]
                segments = list(current.segments)
                pos = next(i for i, s in enumerate(segments) if s.index == index)
                segment = segments[pos]
                segments[pos] = SegmentProgress(
                    segment.index, segment.start, segment.end, downloaded
                )
                state_holder[0] = MultiPartResumeState(current.total_bytes, tuple(segments))

        def on_status(index: int, attempt: int, is_stalled: bool) -> None:
            """Callback from segment workers to report retry attempts and stalled/backoff state.

            attempt is the attempt number (0-based); is_stalled is True during backoff delays.
            """
            with progress_lock:
                if 0 <= index < len(retries):
                    retries[index] = attempt
                    stalled[index] = is_stalled
            # Push an immediate update so the UI reflects the status change.
            report_progress(force=True)

        report_progress(force=True)

        # One requests.Session per segment worker: requests documents Session as not
        # thread-safe, so a shared one races on its connection pool.
        proxies = None if job.use_system_proxy else {"http": "", "https": ""}

        with ThreadPoolExecutor(max_workers=len(state.segments)) as pool:
            futures: dict[Future[bool], int] = {}
            for segment in state.segments:
                if segment.complete:
                    continue
                futures[
                    pool.submit(
                        self._download_segment,
                        job,
                        state.total_bytes,
                        segment,
                        control,
                        stop_event,
                        update_segment,
                        on_status,
                        proxies,
                    )
                ] = segment.index

            while futures:
                if control.stop_requested:
                    stop_event.set()
                    _cancel_pending(futures)
                    break
                done, _ = wait(futures.keys(), timeout=0.2, return_when=FIRST_COMPLETED)
                for future in done:
                    index = futures.pop(future)
                    try:
                        ok = future.result()
                    except AppError:
                        stop_event.set()
                        _cancel_pending(futures)
                        raise
                    except Exception as exc:
                        stop_event.set()
                        _cancel_pending(futures)
                        logger.exception("Segment %d failed unexpectedly", index)
                        raise NetworkError(
                            "A segment failed unexpectedly.", detail=repr(exc), retryable=True
                        ) from exc
                    if not ok:
                        logger.warning(
                            "Segment %d failed for %s; falling back to single connection",
                            index,
                            job.url,
                        )
                        fallback_index = index
                        # Stop the sibling segments and leave this block before touching
                        # any file: the pool's exit waits until every worker has returned
                        # and closed its segment file. Deleting here would race with
                        # writers and, on Windows, fail on the open handle and leave
                        # orphaned *.part.seg* files behind.
                        stop_event.set()
                        _cancel_pending(futures)
                        break
                if fallback_index is not None:
                    break
                report_progress()
        # From here on no segment worker is running, so the segment files are closed
        # and safe to delete or read.

        if control.stop_requested:
            with progress_lock:
                final_state = state_holder[0]
                retries_snapshot = tuple(retries) if retries else None
                stalled_snapshot = tuple(stalled) if stalled else None
            downloaded = total_downloaded_from_state(final_state)
            observer.progress(
                ProgressSnapshot(
                    downloaded,
                    state.total_bytes,
                    0.0,
                    segment_fill=segment_fill_from_state(final_state),
                    multipart_state=final_state,
                    segment_retries=retries_snapshot,
                    segment_stalled=stalled_snapshot,
                )
            )
            observer.metadata_received(
                TransferMetadata(
                    filename=job.filename,
                    total_bytes=state.total_bytes,
                    resumable=True,
                    etag=job.etag,
                    last_modified=job.last_modified,
                    resumed_from=downloaded,
                    transfer_mode="multipart",
                    multipart_state=final_state,
                )
            )
            if control.reason is StopReason.CANCEL:
                self._abort_multipart(job)
                return DownloadOutcome(OutcomeKind.CANCELLED, None, 0, state.total_bytes)
            return DownloadOutcome(OutcomeKind.PAUSED, None, downloaded, state.total_bytes)

        if fallback_index is not None:
            # A segment gave up for good. Every worker has stopped and closed its
            # file, so the partial segments can be discarded before the single
            # connection restarts the transfer.
            self._abort_multipart(job)
            fallback_job = replace(job, transfer_mode="single", multipart_resume=None)
            return self._single.download(fallback_job, control, observer)

        with progress_lock:
            final_state = state_holder[0]
        if not all(s.complete for s in final_state.segments):
            self._abort_multipart(job)
            fallback_job = replace(job, transfer_mode="single", multipart_resume=None)
            return self._single.download(fallback_job, control, observer)

        if any(
            segment_downloaded_bytes(segment_file_path(job.directory, job.filename, s.index))
            != s.length
            for s in final_state.segments
        ):
            logger.warning("A completed segment has an invalid size for %s", job.filename)
            self._abort_multipart(job)
            fallback_job = replace(job, transfer_mode="single", multipart_resume=None)
            return self._single.download(fallback_job, control, observer)

        logger.info("Merging %d segments for %s", len(final_state.segments), job.filename)
        try:
            part_path = merge_segments_to_partial(job.directory, job.filename, final_state)
        except OSError as exc:
            raise storage_error_from_os(exc) from exc
        if segment_downloaded_bytes(part_path) != state.total_bytes:
            logger.warning("Merged file has an invalid size for %s", job.filename)
            self._abort_multipart(job)
            fallback_job = replace(job, transfer_mode="single", multipart_resume=None)
            return self._single.download(fallback_job, control, observer)
        remove_segment_files(job.directory, job.filename)
        final_path = finalize_partial(part_path)
        total = state.total_bytes
        observer.progress(
            ProgressSnapshot(
                total,
                total,
                0.0,
                segment_fill=None,
                multipart_state=None,
                segment_retries=None,
                segment_stalled=None,
            )
        )
        logger.info("Multi-part download completed: %s", final_path)
        return DownloadOutcome(OutcomeKind.COMPLETED, final_path, total, total)

    def _download_segment(
        self,
        job: DownloadJob,
        total_bytes: int,
        segment: SegmentProgress,
        control: DownloadControl,
        stop_event: threading.Event,
        on_progress: Callable[[int, int], None],
        on_status: Callable[[int, int, bool], None],
        proxies: dict[str, str] | None,
    ) -> bool:
        """Download one byte range on its own connection.

        ``stop_event`` is set by the caller when the whole multi-part run is being
        aborted (a sibling segment failed, or the transfer is stopping); the worker
        then returns at the next check so the caller can wait for every file to be
        closed before cleaning up.
        """
        # A session per segment keeps connection state off shared, non-thread-safe
        # objects while preserving the exact headers used before.
        with requests.Session() as session:
            session.headers.update(
                {
                    "User-Agent": self._user_agent,
                    "Accept": "*/*",
                    "Accept-Encoding": "identity",
                }
            )
            return self._transfer_segment(
                session, job, total_bytes, segment, control, stop_event,
                on_progress, on_status, proxies,
            )

    def _transfer_segment(
        self,
        session: requests.Session,
        job: DownloadJob,
        total_bytes: int,
        segment: SegmentProgress,
        control: DownloadControl,
        stop_event: threading.Event,
        on_progress: Callable[[int, int], None],
        on_status: Callable[[int, int, bool], None],
        proxies: dict[str, str] | None,
    ) -> bool:
        seg_path = segment_file_path(job.directory, job.filename, segment.index)
        local = segment_downloaded_bytes(seg_path)
        if local > segment.length:
            local = segment.length

        for attempt in range(MAX_SEGMENT_RETRIES):
            # Report current attempt (0-based) and that we're active (not stalled/backing off).
            try:
                on_status(segment.index, attempt, False)
            except Exception:
                # Do not let UI reporting break the download logic.
                pass

            if control.stop_requested or stop_event.is_set():
                return True
            if local >= segment.length:
                on_progress(segment.index, segment.length)
                logger.debug("Segment %d completed (%d bytes)", segment.index, segment.length)
                try:
                    on_status(segment.index, attempt, False)
                except Exception:
                    pass
                return True

            byte_start = segment.start + local
            headers = {"Range": f"bytes={byte_start}-{segment.end}"}
            validator = job.etag if job.etag and not job.etag.startswith("W/") else job.last_modified
            if validator:
                headers["If-Range"] = validator

            try:
                response = session.get(
                    job.url,
                    headers=headers,
                    stream=True,
                    timeout=(job.connect_timeout, job.read_timeout),
                    proxies=proxies,
                )
            except requests.RequestException as exc:
                err = translate_request_error(exc)
                # If we're going to back off, mark the segment as stalled while waiting.
                if attempt + 1 >= MAX_SEGMENT_RETRIES or not getattr(err, "retryable", False):
                    logger.warning("Segment %d network failure: %s", segment.index, err)
                    return False
                delay = RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.info("Retrying segment %d in %.1f s", segment.index, delay)
                try:
                    on_status(segment.index, attempt + 1, True)
                except Exception:
                    pass
                if _wait_during_backoff(control, stop_event, delay):
                    return True
                # Clear stalled flag before next attempt; update will happen at loop top.
                try:
                    on_status(segment.index, attempt + 1, False)
                except Exception:
                    pass
                continue

            with closing(response):
                status = response.status_code
                if status == 416:
                    match = _RANGE_UNSATISFIED.match(response.headers.get("Content-Range", ""))
                    if match and int(match.group(1)) == byte_start:
                        on_progress(segment.index, segment.length)
                        return True
                    return False
                if status == 200:
                    logger.info("Segment %d: server returned 200 instead of 206", segment.index)
                    return False
                if status != 206:
                    if 500 <= status < 600 or status in (408, 429):
                        if attempt + 1 >= MAX_SEGMENT_RETRIES:
                            return False
                        delay = RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt)
                        try:
                            on_status(segment.index, attempt + 1, True)
                        except Exception:
                            pass
                        if _wait_during_backoff(control, stop_event, delay):
                            return True
                        try:
                            on_status(segment.index, attempt + 1, False)
                        except Exception:
                            pass
                        continue
                    return False

                match = _CONTENT_RANGE.match(response.headers.get("Content-Range", ""))
                if (
                    not match
                    or int(match.group(1)) != byte_start
                    or int(match.group(2)) != segment.end
                ):
                    return False
                if match.group(3) != "*" and int(match.group(3)) != total_bytes:
                    return False
                content_length = _int_or_none(response.headers.get("Content-Length"))
                if content_length is not None and content_length != segment.end - byte_start + 1:
                    return False

                try:
                    handle = open(seg_path, "ab" if local else "wb")
                except OSError as exc:
                    raise storage_error_from_os(exc) from exc

                iterator = response.iter_content(self._chunk_size)
                with handle:
                    while local < segment.length:
                        if control.stop_requested or stop_event.is_set():
                            on_progress(segment.index, local)
                            return True
                        chunk = _next_chunk(iterator)
                        if chunk is None:
                            break
                        if self._speed_limiter.wait_for(len(chunk), control):
                            on_progress(segment.index, local)
                            return True
                        chunk = chunk[: segment.length - local]
                        try:
                            handle.write(chunk)
                        except OSError as exc:
                            raise storage_error_from_os(exc) from exc
                        local += len(chunk)
                        on_progress(segment.index, local)

                if local < segment.length:
                    if attempt + 1 >= MAX_SEGMENT_RETRIES:
                        return False
                    delay = RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt)
                    logger.info(
                        "Segment %d incomplete (%d/%d); retry in %.1f s",
                        segment.index,
                        local,
                        segment.length,
                        delay,
                    )
                    try:
                        on_status(segment.index, attempt + 1, True)
                    except Exception:
                        pass
                    if _wait_during_backoff(control, stop_event, delay):
                        return True
                    try:
                        on_status(segment.index, attempt + 1, False)
                    except Exception:
                        pass
                    continue
                logger.debug("Segment %d completed", segment.index)
                try:
                    on_status(segment.index, attempt, False)
                except Exception:
                    pass
                return True

        return False

    def _abort_multipart(self, job: DownloadJob) -> None:
        remove_segment_files(job.directory, job.filename)
        part_path = job.directory / (job.filename + ".part")
        _remove_quietly(part_path)


def _cancel_pending(futures: dict[Future[bool], int]) -> None:
    """Drop queued segment work; workers already running stop at their next check.

    Waiting for those workers to actually finish is the pool block's job: leaving it
    blocks until every segment thread has returned and closed its file.
    """
    for future in futures:
        future.cancel()
    futures.clear()


def _wait_during_backoff(
    control: DownloadControl, stop_event: threading.Event, delay: float
) -> bool:
    """Sleep through a segment retry backoff.

    Returns True when the transfer should stop, either because the user paused or
    cancelled (``control``) or because the multi-part run was aborted (``stop_event``).
    The wait is sliced so an abort raised by a sibling segment is noticed at once
    instead of after the whole backoff.
    """
    deadline = time.monotonic() + delay
    while True:
        if control.stop_requested or stop_event.is_set():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        if stop_event.wait(min(remaining, 0.1)):
            return True


def _job_with_probe(job: DownloadJob, probe: _ProbeResult) -> DownloadJob:
    return replace(
        job,
        url=probe.url,
        filename=probe.filename if not job.filename_resolved else job.filename,
        etag=probe.etag or job.etag,
        last_modified=probe.last_modified or job.last_modified,
    )
