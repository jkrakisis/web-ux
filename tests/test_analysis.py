import json
from datetime import date

import requests

from gdweb_daily.analysis import OpenAIAnalysisError, OpenAIAnalyzer
from gdweb_daily.models import DetailItem, WebsiteEvidence


def _response(status_code: int = 200) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "purpose_target_ia": "목적",
                                    "ux_patterns": "패턴",
                                    "strengths": "강점",
                                    "improvements": "개선",
                                    "tech_actions": "기술",
                                },
                                ensure_ascii=False,
                            ),
                        }
                    ]
                }
            ]
        },
        ensure_ascii=False,
    ).encode("utf-8")
    response._content_consumed = True
    response.encoding = "utf-8"
    return response


def _analyze(analyzer: OpenAIAnalyzer):
    return analyzer.analyze(
        DetailItem("1", "테스트", date(2026, 10, 20), "detail"),
        WebsiteEvidence(),
    )


def test_openai_retries_transient_http_error(monkeypatch) -> None:
    analyzer = OpenAIAnalyzer("key", "model", retry_backoff_seconds=(5, 15, 30))
    outcomes = [_response(503), _response(429), _response(200)]
    sleeps: list[float] = []

    monkeypatch.setattr("gdweb_daily.analysis.requests.post", lambda *a, **k: outcomes.pop(0))
    monkeypatch.setattr("gdweb_daily.analysis.time.sleep", sleeps.append)

    result = _analyze(analyzer)

    assert result.strengths == "강점"
    assert sleeps == [5, 15]
    assert outcomes == []


def test_openai_stops_immediately_on_permanent_http_error(monkeypatch) -> None:
    analyzer = OpenAIAnalyzer("key", "model")
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _response(400)

    monkeypatch.setattr("gdweb_daily.analysis.requests.post", fake_post)

    try:
        _analyze(analyzer)
    except OpenAIAnalysisError as exc:
        assert str(exc) == "OpenAI HTTP 400"
    else:
        raise AssertionError("OpenAIAnalysisError was not raised")

    assert calls == 1


def test_openai_reports_safe_status_after_retry_limit(monkeypatch) -> None:
    analyzer = OpenAIAnalyzer("key", "model", retry_backoff_seconds=(0, 0, 0))
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _response(503)

    monkeypatch.setattr("gdweb_daily.analysis.requests.post", fake_post)

    try:
        _analyze(analyzer)
    except OpenAIAnalysisError as exc:
        assert str(exc) == "OpenAI HTTP 503"
        assert "key" not in str(exc)
    else:
        raise AssertionError("OpenAIAnalysisError was not raised")

    assert calls == 4
