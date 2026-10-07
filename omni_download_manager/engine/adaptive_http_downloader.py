"""Selects single- or multi-part HTTP download strategies with safe fallback."""

from __future__ import annotations

from omni_download_manager.engine.base import (
    DownloadControl,
    DownloadJob,
    DownloadObserver,
    DownloadOutcome,
)
from omni_download_manager.engine.http_downloader import HttpDownloader, _existing_partial
from omni_download_manager.engine.multipart_http_downloader import MultiPartHttpDownloader
from omni_download_manager.engine.segments import has_segment_files
from omni_download_manager.engine.speed import DownloadSpeedLimiter


class AdaptiveHttpDownloader:
    """Application-facing :class:`Downloader` that probes for multi-part when appropriate."""

    def __init__(
        self,
        *,
        chunk_size: int = 128 * 1024,
        progress_interval: float = 0.2,
        user_agent: str | None = None,
    ) -> None:
        self._limiter = DownloadSpeedLimiter()
        self._single = HttpDownloader(
            chunk_size=chunk_size,
            progress_interval=progress_interval,
            user_agent=user_agent,
            speed_limiter=self._limiter,
        )
        self._multi = MultiPartHttpDownloader(
            chunk_size=chunk_size,
            progress_interval=progress_interval,
            user_agent=user_agent,
            speed_limiter=self._limiter,
            single=self._single,
        )

    def set_speed_limit_mib(self, value: float) -> None:
        self._single.set_speed_limit_mib(value)

    def download(
        self, job: DownloadJob, control: DownloadControl, observer: DownloadObserver
    ) -> DownloadOutcome:
        if job.transfer_mode == "single":
            return self._single.download(job, control, observer)
        if job.transfer_mode == "multipart" or job.multipart_resume is not None:
            return self._multi.download(job, control, observer)
        if job.filename_resolved and has_segment_files(job.directory, job.filename):
            return self._multi.download(job, control, observer)
        if _existing_partial(job) is not None:
            return self._single.download(job, control, observer)
        return self._multi.download(job, control, observer)
