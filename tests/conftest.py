from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class FakeResponse:
    payload: Any
    status_code: int = 200
    text: str = ""

    def json(self) -> Any:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class RecordingRunner:
    def __init__(self, diff_returncode: int = 1):
        self.commands = []
        self.diff_returncode = diff_returncode

    def __call__(self, command, **kwargs):
        self.commands.append((list(command), kwargs))
        return subprocess.CompletedProcess(command, self.diff_returncode if "diff" in command else 0)
