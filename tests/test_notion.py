from gdweb_daily.notion import NotionClient


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

