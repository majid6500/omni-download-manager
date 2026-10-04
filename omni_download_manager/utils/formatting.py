"""Human-readable formatting of sizes, speeds and times."""

from __future__ import annotations

from datetime import datetime

_UNITS = ("B", "KB", "MB", "GB", "TB")


def format_size(num_bytes: int | float | None) -> str:
    if num_bytes is None:
        return "Unknown size"
    value = float(max(0, num_bytes))
    unit = 0
    while value >= 1024 and unit < len(_UNITS) - 1:
        value /= 1024
        unit += 1
    if unit == 0:
        return f"{int(value)} B"
    return f"{value:.1f} {_UNITS[unit]}" if value < 100 else f"{value:.0f} {_UNITS[unit]}"


def format_speed(bytes_per_second: float) -> str:
    return f"{format_size(bytes_per_second)}/s"


def format_eta(seconds: float | None) -> str:
    if seconds is None:
        return ""
    total = int(round(seconds))
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes:02d}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


def format_percent(fraction: float | None) -> str:
    if fraction is None:
        return ""
    return f"{int(fraction * 100)}%"


def format_when(timestamp: float, now: datetime | None = None) -> str:
    moment = datetime.fromtimestamp(timestamp)
    today = (now or datetime.now()).date()
    days_ago = (today - moment.date()).days
    if days_ago == 0:
        return f"Today {moment:%H:%M}"
    if days_ago == 1:
        return f"Yesterday {moment:%H:%M}"
    return f"{moment.day} {moment:%b %Y}"
