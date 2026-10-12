"""Resolve common intermediate download pages before handing files to the engine."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

from omni_download_manager.core.errors import (
    HttpStatusError,
    NetworkError,
)
from omni_download_manager.engine.base import DownloadControl, ScopedCookie
from omni_download_manager.engine.http_downloader import (
    DEFAULT_USER_AGENT,
    MAX_REDIRECTS,
    apply_session_headers,
    translate_request_error,
)
from omni_download_manager.engine.filenames import derive_filename
from omni_download_manager.engine.response import analyze_response
from omni_download_manager.engine.url_security import (
    validate_resolved_url as _validate_resolved_url,
)

logger = logging.getLogger(__name__)

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_MAX_PAGE_BYTES = 2 * 1024 * 1024
_MAX_HTML_REDIRECTS = 8
_MAX_BROWSER_WAIT_MS = 15_000
_LOCATION_ASSIGNMENT = re.compile(
    r"""(?ix)
    (?:window\s*\.\s*)?location(?:\s*\.\s*href)?\s*=\s*
    (?P<quote>['"])(?P<url>[^'"]+)(?P=quote)
    |(?:window\s*\.\s*)?location\s*\.\s*replace\s*\(\s*
    (?P<quote2>['"])(?P<url2>[^'"]+)(?P=quote2)\s*\)
    """
)


@dataclass(frozen=True)
class ResolvedDownloadTarget:
    """A URL and the narrowly scoped browser context needed by the HTTP engine."""

    url: str
    referer: str | None = None
    cookies: tuple[ScopedCookie, ...] = ()


class _MetaRefreshParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.target: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        values = {name.lower(): value for name, value in attrs}
        if (values.get("http-equiv") or "").strip().lower() != "refresh":
            return
        content = values.get("content") or ""
        match = re.search(r"""(?i)(?:^|;)\s*url\s*=\s*(['"]?)(.*?)\1\s*$""", content)
        if match and match.group(2).strip():
            self.target = match.group(2).strip()


class SmartLinkResolver:
    """HTTP-first resolver with an optional, isolated Playwright fallback."""

    def __init__(self, *, user_agent: str | None = None) -> None:
        self._user_agent = user_agent or DEFAULT_USER_AGENT

    def resolve(
        self,
        url: str,
        control: DownloadControl,
        *,
        referer: str | None,
        connect_timeout: float,
        read_timeout: float,
        use_system_proxy: bool,
    ) -> ResolvedDownloadTarget:
        """Return a target only after finding a safe redirect or browser download URL."""
        if control.stop_requested:
            raise NetworkError("Link resolution was cancelled.", retryable=False)

        with requests.Session() as session:
            apply_session_headers(session, user_agent=self._user_agent, referer=referer)
            current = url
            proxies = None if use_system_proxy else {"http": "", "https": ""}
            http_redirects = 0
            html_redirects = 0

            for _ in range(MAX_REDIRECTS + _MAX_HTML_REDIRECTS + 1):
                if control.stop_requested:
                    raise NetworkError("Link resolution was cancelled.", retryable=False)
                try:
                    response = session.get(
                        current,
                        allow_redirects=False,
                        stream=True,
                        timeout=(connect_timeout, read_timeout),
                        proxies=proxies,
                    )
                except requests.RequestException as exc:
                    raise translate_request_error(exc) from exc

                with response:
                    if response.status_code in _REDIRECT_STATUSES:
                        http_redirects += 1
                        if http_redirects > MAX_REDIRECTS:
                            raise NetworkError(
                                "The server redirected too many times.",
                                detail=f"HTTP redirect limit of {MAX_REDIRECTS} exceeded.",
                            )
                        location = response.headers.get("Location")
                        if not location:
                            raise NetworkError(
                                "The intermediate page returned a redirect without a destination.",
                                detail=f"HTTP {response.status_code} from {current}",
                            )
                        target = urljoin(current, location)
                        _validate_resolved_url(target)
                        current = target
                        continue
                    if response.status_code >= 400:
                        raise HttpStatusError(response.status_code)

                    iterator = response.iter_content(64 * 1024)
                    try:
                        first = next(iterator, None)
                    except requests.RequestException as exc:
                        raise translate_request_error(exc, during_transfer=True) from exc
                    name = derive_filename(response.url, response.headers, url)
                    verdict = analyze_response(
                        headers=response.headers,
                        final_url=response.url,
                        first_chunk=first,
                        offset=0,
                        declared_total=_content_length(response.headers.get("Content-Length")),
                        filename=name,
                    )
                    if verdict.ok:
                        return ResolvedDownloadTarget(
                            current, referer, _scoped_cookies(session)
                        )
                    if verdict.reason != "html":
                        raise NetworkError(
                            "The intermediate page did not provide a usable download response.",
                            detail=verdict.detail,
                        )

                    body = _read_bounded(                    iterator, _MAX_PAGE_BYTES, first or b"", control)
                    html = body.decode(response.encoding or "utf-8", "replace")
                    static_target = _html_redirect(html)
                    if static_target:
                        html_redirects += 1
                        if html_redirects > _MAX_HTML_REDIRECTS:
                            raise NetworkError(
                                "The link uses too many intermediate redirects.",
                                detail=(
                                    f"HTML redirect limit of {_MAX_HTML_REDIRECTS} exceeded."
                                ),
                            )
                        target = urljoin(current, static_target)
                        _validate_resolved_url(target)
                        current = target
                        continue

                    return self._resolve_with_browser(
                        current,
                        html,
                        control,
                        referer,
                        (connect_timeout, read_timeout),
                        proxies,
                        _scoped_cookies(session),
                    )

            raise NetworkError(
                "The link uses too many intermediate redirects.",
                detail=(
                    f"Resolution stopped after {MAX_REDIRECTS} HTTP and "
                    f"{_MAX_HTML_REDIRECTS} HTML redirects."
                ),
            )

    def _resolve_with_browser(
        self,
        page_url: str,
        html: str,
        control: DownloadControl,
        referer: str | None,
        timeout: tuple[float, float],
        proxies: dict[str, str] | None,
        cookies: tuple[ScopedCookie, ...],
    ) -> ResolvedDownloadTarget:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise NetworkError(
                "This page may need JavaScript to identify its download. Install ODM's optional "
                "browser support (Playwright and its Chromium runtime), then try again.",
                detail="Optional dependency playwright is not installed.",
            ) from exc

        try:
            with sync_playwright() as playwright:
                launch_options: dict[str, object] = {"headless": True}
                if proxies is not None:
                    launch_options["args"] = ["--no-proxy-server"]
                browser = playwright.chromium.launch(channel="chromium", **launch_options)
                try:
                    context = browser.new_context(
                        accept_downloads=True,
                        user_agent=self._user_agent,
                    )
                    if cookies:
                        context.add_cookies(
                            [
                                {
                                    "name": cookie.name,
                                    "value": cookie.value,
                                    "domain": cookie.domain,
                                    "path": cookie.path,
                                    "secure": cookie.secure,
                                }
                                for cookie in cookies
                            ]
                        )
                    page = context.new_page()
                    candidates: list[str] = []
                    initial_page_pending = [True]

                    def guard_browser_request(route) -> None:
                        request = route.request
                        if (
                            initial_page_pending[0]
                            and request.url == page_url
                            and request.is_navigation_request()
                            and request.redirected_from is None
                        ):
                            initial_page_pending[0] = False
                            route.fulfill(
                                status=200,
                                content_type="text/html; charset=utf-8",
                                body=html,
                            )
                            return
                        try:
                            _validate_resolved_url(request.url)
                        except NetworkError:
                            logger.warning(
                                "Blocked unsafe browser subrequest to %s", request.url
                            )
                            route.abort("blockedbyclient")
                            return
                        if request.is_navigation_request():
                            candidates.append(request.url)
                            route.abort("aborted")
                            return
                        route.continue_()

                    page.route("**/*", guard_browser_request)
                    context.on(
                        "page", lambda popup: popup.route("**/*", guard_browser_request)
                    )
                    try:
                        page.goto(
                            page_url,
                            wait_until="domcontentloaded",
                            timeout=max(1000, int(timeout[0] * 1000)),
                            referer=referer,
                        )
                    except PlaywrightTimeoutError:
                        logger.info(
                            "Timed out waiting for intermediate page navigation: %s", page_url
                        )
                    except PlaywrightError:
                        if not candidates:
                            raise
                    if not candidates:
                        deadline = time.monotonic() + min(
                            _MAX_BROWSER_WAIT_MS / 1000,
                            max(1.0, timeout[1]),
                        )
                        while not candidates and not control.stop_requested:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                break
                            page.wait_for_timeout(min(250, int(remaining * 1000)))
                    if control.stop_requested:
                        raise NetworkError("Link resolution was cancelled.", retryable=False)
                    if not candidates:
                        raise NetworkError(
                            "The page ran JavaScript, but no downloadable navigation was detected. "
                            "Flows that download through a JavaScript blob or a POST response "
                            "cannot be handed to ODM's HTTP engine.",
                            detail=f"Browser page: {page_url}",
                        )
                    target_url = candidates[0]
                    _validate_resolved_url(target_url)
                    scoped_cookies = tuple(
                        ScopedCookie(
                            name=cookie["name"],
                            value=cookie["value"],
                            domain=cookie["domain"],
                            path=cookie["path"] or "/",
                            secure=bool(cookie["secure"]),
                        )
                        for cookie in context.cookies(target_url)
                    )
                    return ResolvedDownloadTarget(
                        target_url,
                        page.url if page.url.startswith(("http://", "https://")) else page_url,
                        scoped_cookies,
                    )
                finally:
                    browser.close()
        except NetworkError:
            raise
        except PlaywrightError as exc:
            raise NetworkError(
                "The browser could not resolve this intermediate page. Install its Chromium "
                "runtime with `python -m playwright install chromium` if it is missing.",
                detail=str(exc),
            ) from exc


def _read_bounded(
    iterator,
    limit: int,
    initial: bytes,
    control: DownloadControl,
) -> bytes:
    body = bytearray(initial[:limit])
    if control.stop_requested:
        raise NetworkError("Link resolution was cancelled.", retryable=False)
    if len(initial) >= limit:
        logger.info("Intermediate HTML exceeded the %d-byte inspection limit", limit)
        return bytes(body)
    try:
        for chunk in iterator:
            if control.stop_requested:
                raise NetworkError("Link resolution was cancelled.", retryable=False)
            if not chunk:
                continue
            remaining = limit - len(body)
            body.extend(chunk[:remaining])
            if len(chunk) > remaining or len(body) >= limit:
                logger.info("Intermediate HTML exceeded the %d-byte inspection limit", limit)
                break
    except requests.RequestException as exc:
        raise translate_request_error(exc, during_transfer=True) from exc
    return bytes(body)


def _content_length(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _html_redirect(html: str) -> str | None:
    parser = _MetaRefreshParser()
    parser.feed(html)
    if parser.target:
        return parser.target
    match = _LOCATION_ASSIGNMENT.search(html)
    if match:
        return match.group("url") or match.group("url2")
    return None


def _scoped_cookies(session: requests.Session) -> tuple[ScopedCookie, ...]:
    return tuple(
        ScopedCookie(
            name=cookie.name,
            value=cookie.value,
            domain=cookie.domain,
            path=cookie.path or "/",
            secure=bool(cookie.secure),
        )
        for cookie in session.cookies
        if cookie.domain
    )
