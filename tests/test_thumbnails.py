from PIL import Image, ImageDraw

from gdweb_daily.thumbnails import clear_thumbnail, image_has_content, latest_items, update_item


def test_latest_items_merges_preview_and_sorts() -> None:
    payload = {
        "items": [
            {"str_no": "2", "site_name": "기존", "registered_date": "2026-08-01", "thumbnail_url": "old.jpg"},
            {"str_no": "3", "site_name": "세 번째", "registered_date": "2026-08-02"},
        ],
        "preview_items": [
            {"str_no": "2", "site_name": "갱신", "registered_date": "2026-08-01"},
            {"str_no": "4", "site_name": "최신", "registered_date": "2026-08-03"},
        ],
    }

    items = latest_items(payload, limit=2)

    assert [item["str_no"] for item in items] == ["4", "3"]
    merged = latest_items(payload, limit=3)[2]
    assert merged["site_name"] == "갱신"
    assert merged["thumbnail_url"] == "old.jpg"


def test_update_item_updates_items_and_preview() -> None:
    payload = {
        "items": [{"str_no": "7", "site_name": "사이트"}],
        "preview_items": [{"str_no": "7", "site_name": "사이트 미리보기"}],
    }

    update_item(payload, "str_no:7", {"thumbnail_status": "success", "thumbnail_url": "thumbnails/7.jpg"})

    assert payload["items"][0]["thumbnail_url"] == "thumbnails/7.jpg"
    assert payload["preview_items"][0]["thumbnail_status"] == "success"


def test_clear_thumbnail_removes_url_from_items_and_preview() -> None:
    payload = {
        "items": [{"str_no": "7", "thumbnail_url": "thumbnails/7.jpg"}],
        "preview_items": [{"str_no": "7", "thumbnail_url": "thumbnails/7.jpg"}],
    }

    clear_thumbnail(payload, "str_no:7")

    assert "thumbnail_url" not in payload["items"][0]
    assert "thumbnail_url" not in payload["preview_items"][0]


def test_image_has_content_rejects_blank_viewport(tmp_path) -> None:
    blank = tmp_path / "blank.jpg"
    Image.new("RGB", (320, 200), "white").save(blank)

    assert image_has_content(blank) is False


def test_image_has_content_accepts_visible_page(tmp_path) -> None:
    visible = tmp_path / "visible.jpg"
    image = Image.new("RGB", (320, 200), "white")
    ImageDraw.Draw(image).rectangle((0, 40, 320, 200), fill="#707070")
    image.save(visible)

    assert image_has_content(visible) is True
