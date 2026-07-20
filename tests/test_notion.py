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


def test_notion_page_is_converted_to_dashboard_item() -> None:
    client = NotionClient("token", "data-source")
    client.schema = {
        "사이트명": {"type": "title"},
        "등록일": {"type": "date"},
        "GDWEB 상세": {"type": "url"},
        "실사이트": {"type": "url"},
        "기술/플러그인 키워드": {"type": "rich_text"},
        "요약(6줄)": {"type": "rich_text"},
    }
    client.semantic_names = client._resolve_semantic_names()
    page = {
        "url": "https://notion.so/page",
        "properties": {
            "사이트명": {"type": "title", "title": [{"plain_text": "샘플"}]},
            "등록일": {"type": "date", "date": {"start": "2026-07-17"}},
            "GDWEB 상세": {
                "type": "url",
                "url": "gdweb.co.kr/sub/view.asp?str_no=27271",
            },
            "실사이트": {"type": "url", "url": "example.com"},
            "기술/플러그인 키워드": {
                "type": "rich_text",
                "rich_text": [{"plain_text": "['GSAP', 'Swiper']"}],
            },
            "요약(6줄)": {
                "type": "rich_text",
                "rich_text": [
                    {
                        "plain_text": "1) 샘플\n2) 목적\n3) 패턴\n4) 강점\n5) 개선\n6) 기술"
                    }
                ],
            },
        },
    }

    item = client._dashboard_item(page)

    assert item is not None
    assert item["str_no"] == "27271"
    assert item["domain"] == "example.com"
    assert item["technologies"] == ["GSAP", "Swiper"]
    assert len(item["lines"]) == 6
