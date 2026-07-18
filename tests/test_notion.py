from gdweb_daily.notion import NotionClient, _action_parts, _url_variants


def test_select_uses_existing_exact_option() -> None:
    prop = {
        "type": "select",
        "select": {"options": [{"id": "green-id", "name": "완료"}]},
    }
    assert NotionClient._closest_existing_option(prop, "완료") == {
        "id": "green-id",
        "name": "완료",
    }


def test_unknown_select_is_excluded() -> None:
    prop = {
        "type": "multi_select",
        "multi_select": {"options": [{"id": "photo-id", "name": "사진"}]},
    }
    assert NotionClient._closest_existing_option(prop, "완전히 다른 신규 옵션") is None


def test_current_database_aliases_are_resolved() -> None:
    client = NotionClient("token", "data-source")
    client.schema = {
        "사이트명": {"type": "title"},
        "실사이트": {"type": "url"},
        "요약(6줄)": {"type": "rich_text"},
        "기술/플러그인 키워드": {"type": "rich_text"},
        "Last check 시각": {"type": "date"},
    }
    resolved = client._resolve_semantic_names()
    assert resolved["site_name"] == "사이트명"
    assert resolved["live_url"] == "실사이트"
    assert resolved["summary"] == "요약(6줄)"
    assert resolved["technologies"] == "기술/플러그인 키워드"
    assert resolved["collected_at"] == "Last check 시각"


def test_actions_and_url_variants() -> None:
    value = "기술: GSAP + A) 예약 우선 + B) 전환율 + C) Do/Don't + D) 한 줄"
    assert _action_parts(value) == {
        "A": "예약 우선",
        "B": "전환율",
        "C": "Do/Don't",
        "D": "한 줄",
    }
    assert _url_variants("https://example.com/") == [
        "https://example.com/",
        "https://example.com",
    ]
