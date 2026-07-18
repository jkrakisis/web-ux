from __future__ import annotations

import time

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

    def get(self, url: str, **kwargs: object) -> requests.Response:
        self._wait()
        response = self.session.get(
            url,
            timeout=kwargs.pop("timeout", self.timeout_seconds),
            allow_redirects=True,
            **kwargs,
        )
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        return response

    def _wait(self) -> None:
        if not self._last_request_at or self.delay_seconds <= 0:
            return
        remaining = self.delay_seconds - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

