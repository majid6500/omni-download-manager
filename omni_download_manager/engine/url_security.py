"""URL checks and bounded redirects shared by the resolver and download engines."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import requests

from omni_download_manager.core.errors import NetworkError

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 20


def validate_resolved_url(url: str) -> None:
    """Reject non-web URLs, embedded credentials, and private resolved destinations."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise NetworkError(
            "The intermediate page returned an invalid download address.",
            detail=str(exc),
        ) from exc
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise NetworkError(
            "The intermediate page returned an unsupported download address.",
            detail=f"Resolved URL: {url!r}",
        )
    if parts.username is not None or parts.password is not None:
        raise NetworkError(
            "The intermediate page returned an unsafe download address.",
            detail="Embedded credentials are not allowed in resolved URLs.",
        )

    hostname = parts.hostname.rstrip(".").lower()
    addresses = _addresses(hostname, port or (443 if parts.scheme == "https" else 80))
    if hostname == "localhost" or hostname.endswith(".localhost") or not addresses:
        _raise_private_target(hostname)
    if any(not address.is_global for address in addresses):
        _raise_private_target(hostname)


def request_with_safe_redirects(
    session: requests.Session,
    method: str,
    url: str,
    *,
    source_url: str,
    **kwargs,
) -> requests.Response:
    """Send a request while checking each redirect before issuing its next hop."""
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        request = session.head if method.upper() == "HEAD" else session.get
        response = request(current, allow_redirects=False, **kwargs)
        if response.status_code not in _REDIRECT_STATUSES:
            return response

        location = response.headers.get("Location")
        if not location:
            return response
        target = urljoin(response.url or current, location)
        _validate_redirect_target(target, source_url)
        response.close()
        current = target

    raise NetworkError(
        "The server redirected too many times.",
        detail=f"Redirect limit of {_MAX_REDIRECTS} exceeded for {url!r}",
    )


def _validate_redirect_target(target: str, source_url: str) -> None:
    source = urlsplit(source_url)
    destination = urlsplit(target)
    same_origin = (
        source.scheme.lower() == destination.scheme.lower()
        and (source.hostname or "").lower() == (destination.hostname or "").lower()
        and source.port == destination.port
    )
    if same_origin and source.hostname and _is_explicit_local_host(source.hostname):
        return
    validate_resolved_url(target)


def _is_explicit_local_host(hostname: str) -> bool:
    host = hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False


def _addresses(hostname: str, port: int) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return {ipaddress.ip_address(hostname)}
    except ValueError:
        try:
            return {
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(hostname, port)
            }
        except OSError as exc:
            raise NetworkError(
                "The intermediate page's download address could not be checked.",
                detail=str(exc),
                retryable=True,
            ) from exc


def _raise_private_target(hostname: str) -> None:
    raise NetworkError(
        "ODM blocked a redirect to a local or private network address.",
        detail=f"Resolved host: {hostname}",
    )
