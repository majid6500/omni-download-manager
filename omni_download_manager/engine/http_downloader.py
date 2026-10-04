"""HTTP(S) download engine.

One call to :meth:`HttpDownloader.download` performs one complete transfer on the
calling thread. The manager runs it on a worker thread; the engine itself knows nothing
about threads, the UI or persistence.

Design notes
------------
* Data is streamed to ``<name>.part`` in fixed-size chunks and renamed once complete,
  so a half-written file is never mistaken for a finished one and memory use is
  constant regardless of file size.
* Resuming is based on the real size of the ``.part`` file and an HTTP ``Range``
  request (with ``If-Range`` when the server gave us a validator). If the server
  ignores or rejects the range, the transfer transparently restarts from zero.
* ``Accept-Encoding: identity`` is requested so byte counts match ``Content-Length``.
"""

from __future__ import annotations

import logging
import re
import time
from contextlib import closing
from pathlib import Path
from typing import Mapping

import requests
import urllib3

from omni_download_manager.constants import VERSION
from omni_download_manager.core.errors import (
    AppError,
    HttpStatusError,
    InvalidUrlError,
    NetworkError,
    storage_error_from_os,
)
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
from omni_download_manager.engine.filenames import (
    derive_filename,
    finalize_partial,
    partial_path_for,
    reserve_partial,
)
from omni_download_manager.engine.speed import DownloadSpeedLimiter, SpeedMeter

logger = logging.getLogger(__name__)

_CONTENT_RANGE = re.compile(r"^\s*bytes\s+(\d+)-(\d+)/(\d+|\*)\s*$", re.IGNORECASE)
_RANGE_UNSATISFIED = re.compile(r"^\s*bytes\s+\*/(\d+)\s*$", re.IGNORECASE)
_MAX_RANGE_ATTEMPTS = 3


class HttpDownloader:
    def __init__(
        self,
        *,
        chunk_size: int = 128 * 1024,
        progress_interval: float = 0.2,
        user_agent: str | None = None,
        speed_limiter: DownloadSpeedLimiter | None = None,
    ) -> None:
        self._chunk_size = chunk_size
        self._progress_interval = progress_interval
        self._user_agent = user_agent or f"ODM/{VERSION}"
        self._speed_limiter = speed_limiter or DownloadSpeedLimiter()

    def set_speed_limit_mib(self, value: float) -> None:
        """Set the shared cap in MiB/s; zero means unlimited."""
        self._speed_limiter.set_limit(value * 1024 * 1024 if value > 0 else None)

    def download(
        self, job: DownloadJob, control: DownloadControl, observer: DownloadObserver
    ) -> DownloadOutcome:
        try:
            job.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise storage_error_from_os(exc) from exc

        with requests.Session() as session:
            session.headers.update(
                {
                    "User-Agent": self._user_agent,
                    "Accept": "*/*",
                    "Accept-Encoding": "identity",
                }
            )
            try:
                return self._run(session, job, control, observer)
            except requests.RequestException as exc:
                raise translate_request_error(exc) from exc

    # ------------------------------------------------------------------ flow

    def _run(
        self,
        session: requests.Session,
        job: DownloadJob,
        control: DownloadControl,
        observer: DownloadObserver,
    ) -> DownloadOutcome:
        part_path = _existing_partial(job)
        offset = part_path.stat().st_size if part_path else 0

        if control.stop_requested:
            return self._stopped(control, part_path, offset, None)

        response, offset = self._open_response(session, job, offset)
        if response is None:
            return self._already_complete(job, part_path, offset, observer)
        with closing(response):
            return self._receive(response, job, control, observer, part_path, offset)

    def _open_response(
        self, session: requests.Session, job: DownloadJob, offset: int
    ) -> tuple[requests.Response | None, int]:
        """Issue the request, negotiating resume.

        Returns ``(response, offset)`` where ``offset`` is the byte position the body
        starts at (reset to 0 when the server does not honour the range), or
        ``(None, offset)`` when the partial file turns out to be the whole file.
        """
        for _ in range(_MAX_RANGE_ATTEMPTS):
            response = session.get(
                job.url,
                headers=_range_headers(job, offset),
                stream=True,
                timeout=(job.connect_timeout, job.read_timeout),
                proxies=None if job.use_system_proxy else {"http": "", "https": ""},
            )
            status = response.status_code

            if status == 416 and offset > 0:
                match = _RANGE_UNSATISFIED.match(response.headers.get("Content-Range", ""))
                response.close()
                if match and int(match.group(1)) == offset:
                    return None, offset
                logger.info("Range not satisfiable for %s; restarting from zero", job.url)
                offset = 0
                continue

            if status == 206:
                match = _CONTENT_RANGE.match(response.headers.get("Content-Range", ""))
                if match and int(match.group(1)) == offset:
                    return response, offset
                response.close()
                logger.info("Unexpected Content-Range for %s; restarting from zero", job.url)
                offset = 0
                continue

            if status == 200:
                if offset > 0:
                    logger.info("Server ignored Range for %s; restarting from zero", job.url)
                return response, 0

            response.close()
            raise HttpStatusError(status)

        raise NetworkError(
            "The server's responses to the resume request were inconsistent.",
            retryable=True,
        )

    def _receive(
        self,
        response: requests.Response,
        job: DownloadJob,
        control: DownloadControl,
        observer: DownloadObserver,
        part_path: Path | None,
        offset: int,
    ) -> DownloadOutcome:
        headers = response.headers
        resumed = response.status_code == 206 and offset > 0
        total = _total_size(response, offset)

        if part_path is None:
            name = (
                job.filename
                if job.filename_resolved
                else derive_filename(response.url, headers)
            )
            name, part_path = reserve_partial(job.directory, name)
        else:
            name = job.filename

        observer.metadata_received(
            TransferMetadata(
                filename=name,
                total_bytes=total,
                resumable=resumed or _accepts_ranges(headers),
                etag=headers.get("ETag"),
                last_modified=headers.get("Last-Modified"),
                resumed_from=offset if resumed else 0,
            )
        )

        start = offset if resumed else 0
        downloaded = start
        meter = SpeedMeter(initial_bytes=start)
        last_report = time.monotonic()
        stopped = False

        try:
            handle = open(part_path, "ab" if resumed else "wb")
        except OSError as exc:
            raise storage_error_from_os(exc) from exc

        iterator = response.iter_content(self._chunk_size)
        with handle:
            while True:
                if control.stop_requested:
                    stopped = True
                    break
                chunk = _next_chunk(iterator)
                if chunk is None:
                    break
                if self._speed_limiter.wait_for(len(chunk), control):
                    stopped = True
                    break
                try:
                    handle.write(chunk)
                except OSError as exc:
                    raise storage_error_from_os(exc) from exc
                downloaded += len(chunk)

                now = time.monotonic()
                if now - last_report >= self._progress_interval:
                    last_report = now
                    observer.progress(
                        ProgressSnapshot(downloaded, total, meter.update(downloaded))
                    )

        complete = total is None or downloaded == total
        if stopped and not (total is not None and downloaded == total):
            observer.progress(ProgressSnapshot(downloaded, total, 0.0))
            return self._stopped(control, part_path, downloaded, total)

        if not complete:
            raise NetworkError(
                "The server stopped sending data before the file was complete.",
                detail=f"Received {downloaded} of {total} bytes from {job.url}",
                retryable=True,
            )

        final_path = finalize_partial(part_path)
        observer.progress(ProgressSnapshot(downloaded, downloaded, 0.0))
        return DownloadOutcome(OutcomeKind.COMPLETED, final_path, downloaded, downloaded)

    # --------------------------------------------------------------- outcomes

    def _already_complete(
        self,
        job: DownloadJob,
        part_path: Path | None,
        size: int,
        observer: DownloadObserver,
    ) -> DownloadOutcome:
        assert part_path is not None  # a 416 is only possible after a ranged request
        observer.metadata_received(
            TransferMetadata(
                filename=job.filename,
                total_bytes=size,
                resumable=True,
                etag=job.etag,
                last_modified=job.last_modified,
                resumed_from=size,
            )
        )
        final_path = finalize_partial(part_path)
        return DownloadOutcome(OutcomeKind.COMPLETED, final_path, size, size)

    @staticmethod
    def _stopped(
        control: DownloadControl, part_path: Path | None, downloaded: int, total: int | None
    ) -> DownloadOutcome:
        if control.reason is StopReason.CANCEL:
            if part_path is not None:
                _remove_quietly(part_path)
            return DownloadOutcome(OutcomeKind.CANCELLED, None, 0, total)
        return DownloadOutcome(OutcomeKind.PAUSED, part_path, downloaded, total)


# ---------------------------------------------------------------------- helpers


def _existing_partial(job: DownloadJob) -> Path | None:
    if not job.filename_resolved:
        return None
    candidate = partial_path_for(job.directory, job.filename)
    return candidate if candidate.is_file() else None


def _range_headers(job: DownloadJob, offset: int) -> dict[str, str]:
    if offset <= 0:
        return {}
    headers = {"Range": f"bytes={offset}-"}
    # Weak ETags are not allowed in If-Range.
    validator = job.etag if job.etag and not job.etag.startswith("W/") else job.last_modified
    if validator:
        headers["If-Range"] = validator
    return headers


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _total_size(response: requests.Response, offset: int) -> int | None:
    if response.status_code == 206:
        match = _CONTENT_RANGE.match(response.headers.get("Content-Range", ""))
        if match and match.group(3) != "*":
            return int(match.group(3))
        length = _int_or_none(response.headers.get("Content-Length"))
        return offset + length if length is not None else None
    return _int_or_none(response.headers.get("Content-Length"))


def _accepts_ranges(headers: Mapping[str, str]) -> bool:
    return "bytes" in headers.get("Accept-Ranges", "").lower()


def _next_chunk(iterator) -> bytes | None:
    """Read the next chunk, converting transport failures into ``NetworkError``."""
    try:
        return next(iterator)
    except StopIteration:
        return None
    except requests.RequestException as exc:
        raise translate_request_error(exc, during_transfer=True) from exc
    except (OSError, urllib3.exceptions.HTTPError) as exc:
        raise NetworkError(
            "The connection was lost during the download.", detail=repr(exc), retryable=True
        ) from exc


def _remove_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete partial file %s", path, exc_info=True)


def translate_request_error(
    exc: requests.RequestException, *, during_transfer: bool = False
) -> AppError:
    detail = repr(exc)
    if isinstance(exc, (requests.exceptions.MissingSchema, requests.exceptions.InvalidSchema,
                        requests.exceptions.InvalidURL)):
        return InvalidUrlError("That address isn't a valid web link.", detail=detail)
    if isinstance(exc, requests.exceptions.Timeout):
        return NetworkError("The server took too long to respond.", detail=detail, retryable=True)
    if isinstance(exc, requests.exceptions.SSLError):
        return NetworkError(
            "A secure connection to the server couldn't be established (SSL error).",
            detail=detail,
        )
    if isinstance(exc, requests.exceptions.TooManyRedirects):
        return NetworkError("The server redirected too many times.", detail=detail)
    if during_transfer or isinstance(
        exc, (requests.exceptions.ChunkedEncodingError, requests.exceptions.ContentDecodingError)
    ):
        return NetworkError(
            "The connection was lost during the download.", detail=detail, retryable=True
        )
    if isinstance(exc, requests.exceptions.ConnectionError):
        return NetworkError(
            "Couldn't connect to the server. Check the address and your internet connection.",
            detail=detail,
            retryable=True,
        )
    return NetworkError("A network error occurred.", detail=detail)
