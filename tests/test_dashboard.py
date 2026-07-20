import json
from datetime import datetime, timedelta, timezone

from gdweb_daily.runner import _merge_dashboard_items, _write_dashboard


KST = timezone(timedelta(hours=9))


def test_merge_dashboard_items_preserves_history_and_updates_duplicate() -> None:
    existing = [
        {"str_no": "100", "site_name": "이전 사이트", "registered_date": "2026-07-17"},
        {"str_no": "90", "site_name": "더 이전 사이트", "registered_date": "2026-07-16"},
    ]
    incoming = [
        {"str_no": "100", "site_name": "수정된 사이트", "registered_date": "2026-07-17"},
        {"str_no": "110", "site_name": "신규 사이트", "registered_date": "2026-07-20"},
    ]

    merged = _merge_dashboard_items(existing, incoming)

    assert [item["str_no"] for item in merged] == ["110", "100", "90"]
    assert merged[1]["site_name"] == "수정된 사이트"


def test_no_new_run_keeps_existing_dashboard_items(tmp_path) -> None:
    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "str_no": "100",
                        "site_name": "이전 사이트",
                        "registered_date": "2026-07-17",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _write_dashboard(
        path,
        datetime(2026, 7, 20, 10, 0, tzinfo=KST),
        dry_run=False,
        records=[],
        failures=[],
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "no_new"
    assert payload["new_count"] == 0
    assert payload["total_count"] == 1
    assert payload["items"][0]["site_name"] == "이전 사이트"
    assert payload["available_dates"] == ["2026-07-17"]
