from __future__ import annotations

import time
from collections.abc import Sequence

import requests


class HttpClient:
    def __init__(
        self,
        user_agent: str,
        timeout_seconds: float = 25.0,
        delay_seconds: float = 0.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
            }
        )
        self._last_request_at = 0.0

    def get(
        self,
        url: str,
        *,
        retry_attempts: int = 0,
        retry_backoff_seconds: Sequence[float] = (5.0, 15.0, 30.0),
        **kwargs: object,
    ) -> requests.Response:
        timeout = kwargs.pop("timeout", self.timeout_seconds)
        transient_statuses = {429, 500, 502, 503, 504}

        for attempt in range(retry_attempts + 1):
            self._wait()
            try:
                response = self.session.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                    **kwargs,
                )
                self._last_request_at = time.monotonic()
                if response.status_code in transient_statuses and attempt < retry_attempts:
                    response.close()
                    self._sleep_before_retry(attempt, retry_backoff_seconds)
                    continue
                response.raise_for_status()
                if not response.encoding or response.encoding.lower() == "iso-8859-1":
                    response.encoding = response.apparent_encoding or "utf-8"
                return response
            except (requests.ConnectionError, requests.Timeout):
                if attempt >= retry_attempts:
                    raise
                self._sleep_before_retry(attempt, retry_backoff_seconds)

        raise RuntimeError("HTTP retry loop exhausted unexpectedly")

    @staticmethod
    def _sleep_before_retry(attempt: int, backoff_seconds: Sequence[float]) -> None:
        if not backoff_seconds:
            return
        delay = backoff_seconds[min(attempt, len(backoff_seconds) - 1)]
        if delay > 0:
            time.sleep(delay)

    def _wait(self) -> None:
        if not self._last_request_at or self.delay_seconds <= 0:
            return
        remaining = self.delay_seconds - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

