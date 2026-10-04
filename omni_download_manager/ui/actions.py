"""Which actions a download offers in each state (Qt-free, shared by buttons and menus)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from omni_download_manager.core.models import DownloadItem, DownloadStatus, StopReason

S = DownloadStatus


class ItemAction(str, Enum):
    START = "start"
    RESUME = "resume"
    PAUSE = "pause"
    CANCEL = "cancel"
    RETRY = "retry"
    REMOVE = "remove"
    OPEN_FILE = "open_file"
    OPEN_FOLDER = "open_folder"
    COPY_URL = "copy_url"


@dataclass(frozen=True)
class ActionSpec:
    action: ItemAction
    icon: str
    label: str
    tooltip: str
    enabled: bool = True
    danger: bool = False


def _spec(action: ItemAction, icon: str, label: str, tooltip: str | None = None, **kw) -> ActionSpec:
    return ActionSpec(action, icon, label, tooltip or label, **kw)


def row_buttons(item: DownloadItem) -> list[ActionSpec]:
    """Up to three icon buttons shown on the download card."""
    stopping = item.stop_reason is not None
    status = item.status
    if status is S.QUEUED:
        return [_spec(ItemAction.CANCEL, "x", "Cancel", danger=True),
                _spec(ItemAction.REMOVE, "trash", "Remove", danger=True)]
    if status is S.PENDING:
        if item.scheduled_at is not None:
            return [
                _spec(ItemAction.START, "play", "Start now"),
                _spec(ItemAction.REMOVE, "trash", "Remove", danger=True),
            ]
        return [_spec(ItemAction.START, "play", "Start"), _spec(ItemAction.REMOVE, "trash", "Remove", danger=True)]
    if status in (S.CONNECTING, S.DOWNLOADING):
        can_pause = item.resumable is not False and not stopping
        pause_tip = "Pause" if item.resumable is not False else "This server doesn't support pausing"
        return [
            _spec(ItemAction.PAUSE, "pause", "Pause", pause_tip, enabled=can_pause),
            _spec(ItemAction.CANCEL, "x", "Cancel", enabled=item.stop_reason is not StopReason.CANCEL, danger=True),
        ]
    if status is S.PAUSED:
        return [_spec(ItemAction.RESUME, "play", "Resume"), _spec(ItemAction.CANCEL, "x", "Cancel", danger=True)]
    if status is S.COMPLETED:
        return [
            _spec(ItemAction.OPEN_FILE, "external", "Open file"),
            _spec(ItemAction.OPEN_FOLDER, "folder", "Show in folder"),
            _spec(ItemAction.REMOVE, "trash", "Remove from list", danger=True),
        ]
    if status is S.FAILED:
        return [_spec(ItemAction.RETRY, "refresh", "Retry"), _spec(ItemAction.REMOVE, "trash", "Remove", danger=True)]
    return [_spec(ItemAction.RETRY, "refresh", "Download again"), _spec(ItemAction.REMOVE, "trash", "Remove", danger=True)]


def menu_actions(item: DownloadItem) -> list[ActionSpec | None]:
    """Entries of the context menu; ``None`` marks a separator."""
    entries: list[ActionSpec | None] = []
    if item.status is S.COMPLETED:
        entries += [
            _spec(ItemAction.OPEN_FILE, "external", "Open file"),
            _spec(ItemAction.OPEN_FOLDER, "folder", "Show in folder"),
        ]
    else:
        entries += [b for b in row_buttons(item) if b.action is not ItemAction.REMOVE]
        entries.append(_spec(ItemAction.OPEN_FOLDER, "folder", "Open download folder"))
    entries += [
        _spec(ItemAction.COPY_URL, "copy", "Copy link"),
        None,
        _spec(ItemAction.REMOVE, "trash", "Remove from list…", danger=True),
    ]
    return entries
