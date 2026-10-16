import requests

from gdweb_daily.http import HttpClient


def _response(status_code: int = 200, content: bytes = b"ok") -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = content
    response.encoding = "utf-8"
    return response


def test_get_retries_connection_timeout_with_configured_backoff(monkeypatch) -> None:
    client = HttpClient("test-agent", timeout_seconds=1)
    outcomes = [
        requests.ConnectTimeout("first"),
        requests.ConnectTimeout("second"),
        _response(),
    ]
    sleeps: list[float] = []

    def fake_get(*args, **kwargs):
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(client.session, "get", fake_get)
    monkeypatch.setattr("gdweb_daily.http.time.sleep", sleeps.append)

    response = client.get(
        "https://example.com",
        retry_attempts=3,
        retry_backoff_seconds=(5, 15, 30),
    )

    assert response.text == "ok"
    assert sleeps == [5, 15]
    assert outcomes == []


def test_get_stops_after_retry_limit(monkeypatch) -> None:
    client = HttpClient("test-agent", timeout_seconds=1)
    calls = 0
    sleeps: list[float] = []

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise requests.ConnectTimeout("still unavailable")

    monkeypatch.setattr(client.session, "get", fake_get)
    monkeypatch.setattr("gdweb_daily.http.time.sleep", sleeps.append)

    try:
        client.get(
            "https://example.com",
            retry_attempts=3,
            retry_backoff_seconds=(5, 15, 30),
        )
    except requests.ConnectTimeout:
        pass
    else:
        raise AssertionError("ConnectTimeout was not raised")

    assert calls == 4
    assert sleeps == [5, 15, 30]


def test_get_does_not_retry_non_transient_http_error(monkeypatch) -> None:
    client = HttpClient("test-agent", timeout_seconds=1)
    calls = 0

    def fake_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _response(404)

    monkeypatch.setattr(client.session, "get", fake_get)

    try:
        client.get("https://example.com", retry_attempts=3)
    except requests.HTTPError:
        pass
    else:
        raise AssertionError("HTTPError was not raised")

    assert calls == 1
