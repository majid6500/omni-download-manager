"""Validation and framing shared by the browser bridge and desktop application."""

from __future__ import annotations

import json
import struct
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from omni_download_manager.core.errors import AppError
from omni_download_manager.engine.filenames import sanitize_filename
from omni_download_manager.utils.urls import validate_url

MAX_MESSAGE_BYTES = 1024 * 1024
MAX_URL_LENGTH = 16_384
MAX_FILENAME_LENGTH = 1024
MAX_REFERER_LENGTH = 16_384


def validate_message(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("Message must be a JSON object.")

    action = value.get("action")
    if action == "status":
        return {"action": "status"}
    if action != "download":
        raise ValueError("Unsupported browser integration action.")

    raw_url = value.get("url")
    if not isinstance(raw_url, str) or len(raw_url) > MAX_URL_LENGTH:
        raise ValueError("The download URL is missing or too long.")
    url = _validated_web_url(raw_url, "download URL")

    result = {"action": "download", "url": url}
    filename = value.get("filename")
    if filename is not None:
        if not isinstance(filename, str) or len(filename) > MAX_FILENAME_LENGTH:
            raise ValueError("The suggested filename is invalid.")
        cleaned = sanitize_filename(filename.strip())
        if cleaned != "download":
            result["filename"] = cleaned

    referer = value.get("referer")
    if referer is not None:
        if not isinstance(referer, str) or len(referer) > MAX_REFERER_LENGTH:
            raise ValueError("The referring page is invalid.")
        result["referer"] = _safe_referer(referer)
    return result


def encode_json(value: dict[str, Any]) -> bytes:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError("Message is too large.")
    return payload


def encode_frame(value: dict[str, Any]) -> bytes:
    payload = encode_json(value)
    return struct.pack("<I", len(payload)) + payload


def decode_json(payload: bytes) -> Any:
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError("Message is too large.")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Message is not valid UTF-8 JSON.") from exc


def decode_frame(frame: bytes) -> dict[str, Any]:
    if len(frame) < 4:
        raise ValueError("Message frame is incomplete.")
    length = struct.unpack("<I", frame[:4])[0]
    if length > MAX_MESSAGE_BYTES or len(frame) != length + 4:
        raise ValueError("Message frame has an invalid length.")
    value = decode_json(frame[4:])
    if not isinstance(value, dict):
        raise ValueError("Message must be a JSON object.")
    return value


def _safe_referer(raw: str) -> str:
    try:
        referer = _validated_web_url(raw, "referring page URL")
        parts = urlsplit(referer)
        return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
    except ValueError as exc:
        raise ValueError("The referring page URL is invalid.") from exc


def _validated_web_url(raw: str, label: str) -> str:
    try:
        value = validate_url(raw)
        parts = urlsplit(value)
    except AppError as exc:
        raise ValueError(exc.user_message) from exc
    if parts.username is not None or parts.password is not None:
        raise ValueError(f"The {label} must not contain embedded credentials.")
    return value
