from __future__ import annotations

import requests
import pytest

from http_client import RetryingHttpClient, TokenPruned
from tests.conftest import FakeResponse, FakeSession


def test_retries_timeout_500_429_and_keeps_token() -> None:
    sleeps = []
    session = FakeSession(
        [
            requests.Timeout("slow"),
            FakeResponse({}, status_code=500),
            FakeResponse({}, status_code=429),
            FakeResponse({"ok": True}, status_code=200),
        ]
    )
    client = RetryingHttpClient(
        session=session,
        sleeper=sleeps.append,
        jitter=lambda: 0.0,
        clock=lambda: 0.0,
    )

    response = client.get("https://api.example.com/jobs", token="tok")

    assert response.json() == {"ok": True}
    assert len(session.requests) == 4
    assert all(call[2]["timeout"] == 10.0 for call in session.requests)
    assert 0.5 in sleeps
    assert 1.0 in sleeps
    assert 2.0 in sleeps
    assert any(delay >= 0.35 for delay in sleeps)


def test_404_prunes_without_retrying() -> None:
    pruned = []
    session = FakeSession([FakeResponse({}, status_code=404)])
    client = RetryingHttpClient(session=session, sleeper=lambda _seconds: None, jitter=lambda: 0.0)

    with pytest.raises(TokenPruned):
        client.get("https://api.example.com/jobs", token="bad-token", prune_callback=pruned.append)

    assert pruned == ["bad-token"]
    assert len(session.requests) == 1
