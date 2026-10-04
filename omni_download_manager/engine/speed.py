"""Moving-window transfer speed."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

from omni_download_manager.engine.base import DownloadControl


class SpeedMeter:
    """Average speed over the last few seconds.

    A short window reacts to real changes while smoothing the bursty chunk arrivals
    that make an instantaneous reading jump around.
    """

    def __init__(
        self,
        initial_bytes: int = 0,
        window_seconds: float = 4.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window = window_seconds
        self._clock = clock
        self._samples: deque[tuple[float, int]] = deque([(clock(), initial_bytes)])

    def update(self, total_bytes: int) -> float:
        now = self._clock()
        self._samples.append((now, total_bytes))
        while len(self._samples) > 2 and now - self._samples[0][0] > self._window:
            self._samples.popleft()
        first_time, first_bytes = self._samples[0]
        elapsed = now - first_time
        if elapsed <= 0:
            return 0.0
        return max(0.0, (total_bytes - first_bytes) / elapsed)


class DownloadSpeedLimiter:
    """Thread-safe token bucket shared by all active HTTP downloads."""

    def __init__(
        self,
        rate_bytes_per_second: float | None = None,
        *,
        max_burst_bytes: int = 128 * 1024,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rate = rate_bytes_per_second
        self._max_burst = max_burst_bytes
        self._clock = clock
        self._lock = threading.Lock()
        self._last_refill = clock()
        self._tokens = 0.0

    def set_limit(self, rate_bytes_per_second: float | None) -> None:
        with self._lock:
            self._rate = rate_bytes_per_second if rate_bytes_per_second and rate_bytes_per_second > 0 else None
            self._tokens = 0.0
            self._last_refill = self._clock()

    def wait_for(self, byte_count: int, control: DownloadControl) -> bool:
        """Wait until this chunk's tokens are available; return early on pause/cancel."""
        while True:
            with self._lock:
                if self._rate is None:
                    return False
                now = self._clock()
                capacity = max(float(self._max_burst), float(byte_count))
                elapsed = max(0.0, now - self._last_refill)
                self._tokens = min(capacity, self._tokens + elapsed * self._rate)
                self._last_refill = now
                if self._tokens >= byte_count:
                    self._tokens -= byte_count
                    return False
                delay = (byte_count - self._tokens) / self._rate
            if control.wait_for_stop(delay):
                return True
