"""URL validation."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from omni_download_manager.core.errors import InvalidUrlError

SUPPORTED_SCHEMES = ("http", "https")


def validate_url(raw: str) -> str:
    """Return a cleaned download URL or raise :class:`InvalidUrlError`.

    A leading ``www.`` is treated as https. The fragment is dropped because it is never
    sent to the server.
    """
    text = (raw or "").strip()
    if not text:
        raise InvalidUrlError("Enter a download link.")
    if re.search(r"\s", text):
        raise InvalidUrlError("The link contains spaces. Check that it was copied completely.")
    if text.lower().startswith("www."):
        text = "https://" + text
    try:
        parts = urlsplit(text)
        _ = parts.port  # raises ValueError for an invalid port
    except ValueError as exc:
        raise InvalidUrlError("That doesn't look like a valid link.", detail=str(exc)) from exc
    if parts.scheme.lower() not in SUPPORTED_SCHEMES:
        raise InvalidUrlError("Only http:// and https:// links are supported.")
    if not parts.hostname:
        raise InvalidUrlError("The link is missing a website address.")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
