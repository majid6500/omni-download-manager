"""Application exceptions.

Every error that can reach the user derives from :class:`AppError` and carries a
short, human-readable ``user_message``. The technical detail (``str(exc)``) goes to the
log instead of the UI.
"""

from __future__ import annotations

import errno


class AppError(Exception):
    def __init__(self, user_message: str, *, detail: str | None = None) -> None:
        super().__init__(detail or user_message)
        self.user_message = user_message


class InvalidUrlError(AppError):
    """The address is not something the application can download."""


class NetworkError(AppError):
    """Connection problems, timeouts, interrupted transfers."""

    def __init__(
        self, user_message: str, *, detail: str | None = None, retryable: bool = False
    ) -> None:
        super().__init__(user_message, detail=detail)
        self.retryable = retryable


class HttpStatusError(AppError):
    def __init__(self, status_code: int) -> None:
        super().__init__(describe_http_status(status_code), detail=f"HTTP {status_code}")
        self.status_code = status_code


class StorageError(AppError):
    """Problems writing to disk (permissions, space, bad paths)."""


class PersistenceError(AppError):
    """The download database or settings file could not be read or written."""


class InvalidOperationError(AppError):
    """The requested action is not valid for the download's current state."""


def describe_http_status(code: int) -> str:
    known = {
        401: "The server requires a login for this file (HTTP 401).",
        403: "Access to this file was denied (HTTP 403).",
        404: "The file was not found on the server (HTTP 404).",
        410: "The file is no longer available (HTTP 410).",
        429: "The server is limiting requests. Try again later (HTTP 429).",
    }
    if code in known:
        return known[code]
    if 500 <= code < 600:
        return f"The server had a problem (HTTP {code}). Try again later."
    return f"The server responded with an error (HTTP {code})."


def storage_error_from_os(exc: OSError) -> StorageError:
    """Translate a low-level ``OSError`` into a message a user can act on."""
    if exc.errno == errno.ENOSPC:
        message = "There isn't enough free disk space to continue."
    elif isinstance(exc, PermissionError) or exc.errno in (errno.EACCES, errno.EPERM):
        message = "Omni Download Manager doesn't have permission to write to that location."
    elif isinstance(exc, FileNotFoundError):
        message = "The destination folder could not be found."
    elif exc.errno == errno.ENAMETOOLONG:
        message = "The file name or folder path is too long."
    else:
        message = f"The file couldn't be saved ({exc.strerror or exc.__class__.__name__})."
    return StorageError(message, detail=repr(exc))
