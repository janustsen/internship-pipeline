from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

import requests


class TokenPruned(RuntimeError):
    def __init__(self, token: str | None, url: str):
        super().__init__(f"token pruned after 404: {token or url}")
        self.token = token
        self.url = url


class RetryableHttpError(RuntimeError):
    pass


@dataclass
class RetryingHttpClient:
    session: Any = field(default_factory=requests.Session)
    timeout: float = 10.0
    max_retries: int = 3
    politeness_delay: float = 0.35
    sleeper: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    jitter: Callable[[], float] = lambda: random.uniform(0.0, 0.1)

    def __post_init__(self) -> None:
        self._last_by_host: dict[str, float] = {}

    @property
    def max_attempts(self) -> int:
        return self.max_retries + 1

    def get(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self.request("POST", url, **kwargs)

    def request(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        prune_callback: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            self._respect_politeness(url)
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                raise RetryableHttpError(str(exc)) from exc

            status = getattr(response, "status_code", None)
            if status == 404:
                if token and prune_callback:
                    prune_callback(token)
                raise TokenPruned(token, url)
            if status == 429 or (status is not None and 500 <= status <= 599):
                last_error = RetryableHttpError(f"{method} {url} returned {status}")
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                raise last_error
            if status is not None and status >= 400:
                response.raise_for_status()
            return response
        raise RetryableHttpError(str(last_error) if last_error else f"{method} {url} failed")

    def _respect_politeness(self, url: str) -> None:
        host = urlparse(url).netloc
        if not host:
            return
        now = self.clock()
        last = self._last_by_host.get(host)
        if last is not None:
            elapsed = now - last
            if elapsed < self.politeness_delay:
                self.sleeper(self.politeness_delay - elapsed)
        self._last_by_host[host] = self.clock()

    def _backoff(self, attempt: int) -> None:
        delay = 0.5 * (2**attempt)
        self.sleeper(delay + self.jitter())
