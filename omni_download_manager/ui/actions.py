"""Which actions a download offers in each state (Qt-free, shared by buttons and menus)."""

from __future__ import annotations

from dataclasses import dataclass, replace
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
        return [
            _spec(ItemAction.PAUSE, "pause", "Pause", "Take out of the queue"),
            _spec(ItemAction.CANCEL, "x", "Cancel", danger=True),
            _spec(ItemAction.REMOVE, "trash", "Remove", danger=True),
        ]
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


# ------------------------------------------------------------------ toolbar
# The fixed top toolbar replaces the buttons that used to live on each card.
# Its state is derived only from the current selection, so it can never drift
# away from what the controller will actually accept.

TOOLBAR_SPECS: tuple[ActionSpec, ...] = (
    _spec(ItemAction.RESUME, "play-02", "Start / Continue", "Start or continue download"),
    _spec(ItemAction.PAUSE, "pause-02", "Pause", "Pause download"),
    _spec(ItemAction.RETRY, "retry-02", "Restart", "Restart download from the beginning"),
    _spec(ItemAction.CANCEL, "cancel-02", "Cancel", "Cancel download", danger=True),
    _spec(ItemAction.REMOVE, "trash-bin-02", "Delete", "Delete download"),
    _spec(ItemAction.OPEN_FOLDER, "folder-02", "Open folder", "Open the containing folder"),
    _spec(ItemAction.OPEN_FILE, "external", "Open file", "Open the downloaded file"),
)

# Actions the controller supports for a whole selection at once (``perform_bulk``).
_BULK_ACTIONS = frozenset(
    {ItemAction.PAUSE, ItemAction.RESUME, ItemAction.CANCEL, ItemAction.REMOVE}
)

_STARTABLE = frozenset({S.PENDING, S.QUEUED})
_RETRYABLE = frozenset({S.FAILED, S.CANCELLED})


def _enabled_for(action: ItemAction, items: list[DownloadItem]) -> bool:
    if action in _BULK_ACTIONS:
        if action is ItemAction.PAUSE:
            return any(
                (item.is_active or item.status is S.QUEUED) and item.resumable is not False
                for item in items
            )
        if action is ItemAction.RESUME:
            playable = _STARTABLE | {S.PAUSED}
            return any(item.status in playable for item in items)
        if action is ItemAction.CANCEL:
            return any(item.status not in (S.COMPLETED, S.CANCELLED) for item in items)
        return True  # REMOVE always applies to a selection
    if len(items) != 1:
        # Start/retry/open only exist as single-item operations in the controller.
        return False
    item = items[0]
    if action is ItemAction.START:
        return item.status in _STARTABLE
    if action is ItemAction.RETRY:
        return item.status in _RETRYABLE
    if action is ItemAction.OPEN_FILE:
        return item.status is S.COMPLETED
    return True  # OPEN_FOLDER: useful for any download that has a destination


def toolbar_enabled(items: list[DownloadItem]) -> dict[ItemAction, bool]:
    """Which toolbar actions the given selection allows, in ``TOOLBAR_SPECS`` order."""
    return {spec.action: bool(items) and _enabled_for(spec.action, items) for spec in TOOLBAR_SPECS}


def toolbar_specs(items: list[DownloadItem]) -> list[ActionSpec]:
    """``TOOLBAR_SPECS`` with ``enabled`` resolved for the current selection."""
    enabled = toolbar_enabled(items)
    return [replace(spec, enabled=enabled[spec.action]) for spec in TOOLBAR_SPECS]
