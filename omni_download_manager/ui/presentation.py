"""Turns a :class:`DownloadItem` into the texts shown on a download card (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from omni_download_manager.constants import MAX_AUTOMATIC_RETRIES
from omni_download_manager.core.models import DownloadItem, DownloadStatus, StopReason
from omni_download_manager.utils.formatting import (
    format_eta,
    format_percent,
    format_size,
    format_speed,
    format_when,
)

S = DownloadStatus


class Tone(str, Enum):
    ACCENT = "accent"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    MUTED = "muted"


@dataclass(frozen=True)
class CardText:
    status: str
    tone: Tone
    detail: str
    # Shown in the bottom row instead of the progress bar (completed/failed/cancelled).
    footer: str | None = None
    footer_tone: Tone = Tone.MUTED


def shows_progress_bar(item: DownloadItem) -> bool:
    return item.status in (S.PENDING, S.CONNECTING, S.DOWNLOADING, S.PAUSED)


def is_indeterminate(item: DownloadItem) -> bool:
    if item.status is S.CONNECTING:
        return item.downloaded_bytes == 0
    return item.status is S.DOWNLOADING and item.progress is None


def percent_text(item: DownloadItem) -> str:
    return format_percent(item.progress) if item.status is not S.PENDING else "0%"


def _sizes(item: DownloadItem) -> str:
    if item.total_bytes:
        return f"{format_size(item.downloaded_bytes)} of {format_size(item.total_bytes)}"
    return format_size(item.downloaded_bytes) if item.downloaded_bytes else ""


def _join(*parts: str) -> str:
    return "  ·  ".join(p for p in parts if p)


def describe(item: DownloadItem) -> CardText:
    status = item.status
    if item.stop_reason is StopReason.CANCEL:
        return CardText("Cancelling…", Tone.MUTED, "")
    if item.stop_reason is StopReason.PAUSE:
        return CardText("Pausing…", Tone.WARNING, _sizes(item))

    if status is S.PENDING:
        if item.scheduled_at is not None:
            return CardText(
                "Scheduled",
                Tone.WARNING,
                f"Starts {datetime.fromtimestamp(item.scheduled_at):%a, %b %d %Y at %H:%M}",
            )
        return CardText("Ready", Tone.MUTED, "Waiting to start")
    if status is S.QUEUED:
        return CardText("Queued", Tone.WARNING, "Waiting for an available download slot")
    if status is S.CONNECTING:
        if item.retry_attempt:
            return CardText(
                f"Retrying ({item.retry_attempt}/{MAX_AUTOMATIC_RETRIES})…",
                Tone.WARNING,
                item.error_message or "",
            )
        label = "Resuming…" if item.downloaded_bytes else "Connecting…"
        return CardText(label, Tone.ACCENT, _sizes(item))
    if status is S.DOWNLOADING:
        speed = format_speed(item.speed_bps) if item.speed_bps > 0 else ""
        eta = format_eta(item.eta_seconds)
        return CardText("Downloading", Tone.ACCENT, _join(_sizes(item), speed, f"{eta} left" if eta else ""))
    if status is S.PAUSED:
        return CardText("Paused", Tone.WARNING, _sizes(item))
    if status is S.COMPLETED:
        when = format_when(item.completed_at) if item.completed_at else ""
        return CardText("Completed", Tone.SUCCESS, _join(format_size(item.total_bytes), when), item.directory)
    if status is S.FAILED:
        return CardText("Failed", Tone.DANGER, _sizes(item), item.error_message or "The download failed.", Tone.DANGER)
    return CardText("Cancelled", Tone.MUTED, "", item.directory)
