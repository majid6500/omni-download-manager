"""Decides whether an HTTP response really carries the requested file.

``200 OK`` is not proof of a successful download. Expired links, sign-in walls and
security challenges all answer with a small HTML page that would otherwise be saved
as a finished file and reported as completed in the history.

The rules are deliberately conservative: markup/error bodies that clearly are not the
requested file are rejected, while anything ambiguous is accepted. The point is to
stop the obvious false success, not to build a file-identification system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

# Content types that mean "this is a document the server generated", not a payload.
HTML_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml"})
JSON_CONTENT_TYPES = frozenset({"application/json", "text/json", "application/problem+json"})

# Markup / JSON is only *expected* when the resolved file name says so.
MARKUP_SUFFIXES = (".html", ".htm", ".xhtml")
JSON_SUFFIXES = (".json", ".js", ".map")

# Enough to name what arrived in the error detail, without growing into a
# full file-signature database.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "pdf"),
    (b"PK\x03\x04", "zip"),
    (b"\x1f\x8b", "gzip"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"ID3", "mp3"),
    (b"\xff\xfb", "mp3"),
    (b"OggS", "ogg"),
    (b"Rar!\x1a\x07", "rar"),
    (b"7z\xbc\xaf\x27\x1c", "7z"),
    (b"MSCF", "cab"),
    (b"\xd0\xcf\x11\xe0", "ole"),
    (b"\x7fELF", "elf"),
    (b"#!", "script"),
    (b"RIFF", "riff"),
)

# Opening tokens that only occur in markup documents. Kept specific so a plain text
# file that merely starts with "<" is not mistaken for a web page.
_MARKUP_PREFIXES = (
    b"<!doctype html", b"<html", b"<head", b"<body", b"<meta", b"<title",
    b"<script", b"<!--", b"<div", b"<table", b"<center", b"<form", b"<style",
    b"<h1", b"<h2", b"<p>", b"<ul", b"<ol", b"<li>", b"<span", b"<a href",
    b"<img", b"<br", b"<input", b"<button", b"<label", b"<select", b"<iframe",
    b"<noscript", b"<svg", b"<section", b"<article", b"<header", b"<footer",
    b"<nav", b"<main", b"<strong", b"<blockquote", b"<pre", b"<link", b"<base",
)

_BOM = b"\xef\xbb\xbf"
_LEADING_SPACE = b" \t\r\n"
_WHITESPACE = re.compile(r"\s+")
_PREVIEW_CHARS = 300


@dataclass(frozen=True)
class ResponseVerdict:
    """Outcome of :func:`analyze_response`."""

    ok: bool
    # Short machine key: ``html`` or ``empty``. ``None`` when ``ok``.
    reason: str | None = None
    # Everything worth keeping for the log and the user-facing error detail.
    detail: str | None = None


def sniff_signature(first: bytes | None) -> str | None:
    """Best-effort name of the payload from its first bytes, or ``None``."""
    if not first:
        return None
    if len(first) >= 8 and first[4:8] == b"ftyp":
        return "mp4"
    for prefix, name in _SIGNATURES:
        if first.startswith(prefix):
            return name
    return None


def looks_like_markup(first: bytes | None) -> bool:
    """True when the body opens like a generated HTML document."""
    if not first:
        return False
    sample = first[:1024].lstrip(_BOM).lstrip(_LEADING_SPACE).lower()
    return sample.startswith(_MARKUP_PREFIXES)


def _content_type(headers: Mapping[str, str]) -> str:
    return (headers.get("Content-Type") or "").split(";")[0].strip().lower()


def _wants(filename: str | None, suffixes: tuple[str, ...]) -> bool:
    return bool(filename) and filename.lower().endswith(suffixes)


def _is_textual(first: bytes) -> bool:
    sample = first[:512]
    if b"\x00" in sample:
        return False
    printable = sum(1 for byte in sample if 32 <= byte < 127 or byte in (9, 10, 13))
    return printable / len(sample) >= 0.85


def _describe_body(first: bytes | None) -> str:
    if not first:
        return "body=<empty>"
    head = first[:16].hex(" ")
    if not _is_textual(first):
        return f"first-bytes={head}"
    text = _WHITESPACE.sub(" ", first[:_PREVIEW_CHARS * 2].decode("utf-8", "replace"))
    return f"first-bytes={head} preview={text.strip()[:_PREVIEW_CHARS]!r}"


def analyze_response(
    *,
    headers: Mapping[str, str],
    final_url: str,
    first_chunk: bytes | None,
    offset: int,
    declared_total: int | None,
    filename: str | None,
) -> ResponseVerdict:
    """Classify the first response of a transfer.

    ``first_chunk`` is the first body slice (``None`` when the body is empty) and
    ``filename`` is the name the transfer would end up using, which is what makes an
    HTML body acceptable when the caller really is downloading a web page.

    Only called for successful statuses (200/206); error statuses never get here.
    """
    content_type = _content_type(headers)
    sniffed = sniff_signature(first_chunk)
    detail = (
        f"content-type={headers.get('Content-Type')!r}, final-url={final_url!r}, "
        f"sniffed={sniffed}, {_describe_body(first_chunk)}"
    )

    if first_chunk is None and offset == 0 and declared_total is None:
        # No Content-Length and no bytes: nothing was transferred at all.
        return ResponseVerdict(False, "empty", detail)

    if content_type in HTML_CONTENT_TYPES and not _wants(filename, MARKUP_SUFFIXES):
        return ResponseVerdict(False, "html", detail)

    if looks_like_markup(first_chunk) and not _wants(filename, MARKUP_SUFFIXES):
        return ResponseVerdict(False, "html", detail)

    if content_type in JSON_CONTENT_TYPES and not _wants(filename, JSON_SUFFIXES):
        return ResponseVerdict(False, "html", detail)

    return ResponseVerdict(True, None, detail)
