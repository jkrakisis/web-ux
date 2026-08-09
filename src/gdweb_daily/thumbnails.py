from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


TRACKER_HOST_PARTS = (
    "doubleclick.net",
    "facebook.net",
    "google-analytics.com",
    "googletagmanager.com",
    "hotjar.com",
    "clarity.ms",
)
CAPTURE_STABILIZE_MS = 3_000


def _item_key(item: dict[str, object]) -> str:
    str_no = str(item.get("str_no") or "").strip()
    if str_no:
        return f"str_no:{str_no}"
    domain = str(item.get("domain") or "").strip().lower()
    registered_date = str(item.get("registered_date") or "").strip()
    return f"domain_date:{domain}:{registered_date}"


def latest_items(payload: dict[str, object], limit: int) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for collection_name in ("items", "preview_items"):
        collection = payload.get(collection_name, [])
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, dict):
                continue
            key = _item_key(item)
            if key == "domain_date::":
                continue
            merged[key] = {**merged.get(key, {}), **item}
    return sorted(
        merged.values(),
        key=lambda item: (
            str(item.get("registered_date") or ""),
            int(str(item.get("str_no") or "0"))
            if str(item.get("str_no") or "").isdigit()
            else 0,
        ),
        reverse=True,
    )[:limit]


def update_item(
    payload: dict[str, object],
    key: str,
    updates: dict[str, object],
) -> None:
    for collection_name in ("items", "preview_items"):
        collection = payload.get(collection_name, [])
        if not isinstance(collection, list):
            continue
        for item in collection:
            if isinstance(item, dict) and _item_key(item) == key:
                item.update(updates)


def clear_thumbnail(payload: dict[str, object], key: str) -> None:
    for collection_name in ("items", "preview_items"):
        collection = payload.get(collection_name, [])
        if not isinstance(collection, list):
            continue
        for item in collection:
            if isinstance(item, dict) and _item_key(item) == key:
                item.pop("thumbnail_url", None)


def _valid_live_url(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _thumbnail_name(item: dict[str, object]) -> str:
    str_no = str(item.get("str_no") or "").strip()
    if str_no:
        return f"{str_no}.jpg"
    domain = str(item.get("domain") or "site").replace(".", "-")
    registered_date = str(item.get("registered_date") or "unknown")
    return f"{domain}-{registered_date}.jpg"


def _route_request(route: Any) -> None:
    request = route.request
    url = request.url.lower()
    if any(part in url for part in TRACKER_HOST_PARTS):
        route.abort()
        return
    route.continue_()


def image_has_content(path: Path, minimum_ratio: float = 0.03) -> bool:
    from PIL import Image

    with Image.open(path) as source:
        image = source.convert("L")
        image.thumbnail((180, 120))
        histogram = image.histogram()
    total = sum(histogram)
    if not total:
        return False
    meaningful = sum(histogram[:242])
    return meaningful / total >= minimum_ratio


def _capture_page(page: Any, url: str, output_path: Path) -> str:
    navigation_warning = ""
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=12_000)
        if response is not None and response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")
    except Exception as exc:  # A usable first viewport can exist after a navigation timeout.
        if "Timeout" not in type(exc).__name__ and "timeout" not in str(exc).lower():
            raise
        navigation_warning = "navigation timeout"

    page.add_style_tag(
        content="""
        html { scroll-behavior: auto !important; }
        *, *::before, *::after {
          animation-duration: 0.01s !important;
          animation-delay: 0s !important;
          transition: none !important;
          caret-color: transparent !important;
        }
        """
    )
    # Give lazy hero images, fonts, and client-rendered content time to settle.
    page.wait_for_timeout(CAPTURE_STABILIZE_MS)
    page.evaluate(
        """
        () => {
          const height = Math.min(window.innerHeight * 0.75, document.documentElement.scrollHeight);
          window.scrollTo(0, height);
        }
        """
    )
    page.wait_for_timeout(500)
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(500)

    body_signal = page.evaluate(
        """
        () => ({
          text: (document.body?.innerText || '').trim().length,
          media: document.querySelectorAll('img, svg, canvas, video').length,
        })
        """
    )
    if body_signal["text"] < 10 and body_signal["media"] == 0:
        raise RuntimeError("empty first viewport")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".tmp.jpg")
    page.screenshot(
        path=str(temp_path),
        type="jpeg",
        quality=74,
        full_page=False,
        animations="disabled",
    )
    if not temp_path.exists() or temp_path.stat().st_size < 5_000:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError("thumbnail file is too small")
    if not image_has_content(temp_path):
        temp_path.unlink(missing_ok=True)
        raise RuntimeError("first viewport is visually empty")
    temp_path.replace(output_path)
    return navigation_warning


def capture_recent(
    dashboard_path: Path,
    output_dir: Path,
    report_path: Path,
    limit: int = 10,
    force: bool = False,
) -> dict[str, object]:
    payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
    targets = latest_items(payload, limit)
    results: list[dict[str, object]] = []
    attempted_at = datetime.now().astimezone().isoformat()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed; install .[thumbnail]") from exc

    channel = os.getenv("THUMBNAIL_BROWSER_CHANNEL", "").strip() or None
    launch_options: dict[str, object] = {
        "headless": True,
        "args": ["--disable-dev-shm-usage", "--no-sandbox"],
    }
    if channel:
        launch_options["channel"] = channel

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_options)
        try:
            for item in targets:
                key = _item_key(item)
                live_url = _valid_live_url(item.get("live_url"))
                filename = _thumbnail_name(item)
                output_path = output_dir / filename
                relative_url = f"thumbnails/{filename}"

                if (
                    not force
                    and item.get("thumbnail_status") == "success"
                    and output_path.exists()
                ):
                    results.append({"key": key, "site_name": item.get("site_name"), "status": "skipped"})
                    continue
                if not live_url:
                    clear_thumbnail(payload, key)
                    output_path.unlink(missing_ok=True)
                    updates = {
                        "thumbnail_status": "failed",
                        "thumbnail_error": "live URL missing",
                        "thumbnail_attempted_at": attempted_at,
                    }
                    update_item(payload, key, updates)
                    results.append({"key": key, "site_name": item.get("site_name"), **updates})
                    continue

                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    device_scale_factor=1,
                    locale="ko-KR",
                    reduced_motion="reduce",
                    ignore_https_errors=False,
                )
                page = context.new_page()
                page.route("**/*", _route_request)
                try:
                    warning = _capture_page(page, live_url, output_path)
                    updates = {
                        "thumbnail_url": relative_url,
                        "thumbnail_status": "success",
                        "thumbnail_error": warning,
                        "thumbnail_attempted_at": attempted_at,
                    }
                except Exception as exc:  # One site must never block the remaining captures.
                    clear_thumbnail(payload, key)
                    output_path.unlink(missing_ok=True)
                    updates = {
                        "thumbnail_status": "failed",
                        "thumbnail_error": str(exc)[:240],
                        "thumbnail_attempted_at": attempted_at,
                    }
                finally:
                    context.close()
                update_item(payload, key, updates)
                results.append({"key": key, "site_name": item.get("site_name"), **updates})
        finally:
            browser.close()

    dashboard_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "generated_at": attempted_at,
        "limit": limit,
        "success": sum(result.get("thumbnail_status") == "success" for result in results),
        "failed": sum(result.get("thumbnail_status") == "failed" for result in results),
        "skipped": sum(result.get("status") == "skipped" for result in results),
        "results": results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture first-viewport thumbnails for recent GDWEB items")
    parser.add_argument("--dashboard", type=Path, default=Path("docs/data/latest.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/thumbnails"))
    parser.add_argument("--report", type=Path, default=Path("reports/thumbnail-latest.json"))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    try:
        summary = capture_recent(
            dashboard_path=args.dashboard,
            output_dir=args.output_dir,
            report_path=args.report,
            limit=max(1, args.limit),
            force=args.force,
        )
    except Exception as exc:
        print(f"thumbnail capture unavailable: {exc}")
        return 0

    print(
        "thumbnail capture: "
        f"success={summary['success']} failed={summary['failed']} skipped={summary['skipped']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
