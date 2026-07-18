from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .http import HttpClient
from .models import DetailItem, ListingItem


DATE_SHORT = re.compile(r"\b(\d{2}\.\d{2}\.\d{2})\b")
STR_NO = re.compile(r"(?:[?&]str_no=|\bval=[\"'])(\d+)")


class GdwebCollector:
    def __init__(self, base_url: str, http: HttpClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = http

    def fetch_list_page(self, page: int = 1) -> list[ListingItem]:
        url = (
            f"{self.base_url}/sub/list.asp?Page={page}&displayrow=60"
            "&Txt_fgbn=5&Txt_key=all"
        )
        return parse_listing_html(self.http.get(url).text, self.base_url)

    def fetch_recent(self, earliest_date: date, max_pages: int = 3) -> list[ListingItem]:
        found: dict[str, ListingItem] = {}
        for page in range(1, max_pages + 1):
            items = self.fetch_list_page(page)
            if not items:
                break
            for item in items:
                if item.registered_date >= earliest_date:
                    found[item.str_no] = item
            if min(item.registered_date for item in items) < earliest_date:
                break
        return sorted(
            found.values(),
            key=lambda item: (item.registered_date, int(item.str_no)),
        )

    def fetch_detail(self, listing: ListingItem) -> DetailItem:
        html = self.http.get(listing.detail_url).text
        return parse_detail_html(html, listing)


def _str_no_from_box(box: Tag) -> str:
    button = box.select_one("a.btn_link[val]")
    if button and button.get("val"):
        return str(button.get("val"))
    for anchor in box.select("a[href]"):
        href = str(anchor.get("href", ""))
        match = STR_NO.search(href)
        if match:
            return match.group(1)
    return ""


def parse_listing_html(html: str, base_url: str) -> list[ListingItem]:
    soup = BeautifulSoup(html, "html.parser")
    results: dict[str, ListingItem] = {}
    for box in soup.select(".thumnail-box"):
        str_no = _str_no_from_box(box)
        subject = box.select_one(".subject")
        date_node = box.select_one(".date")
        if not str_no or not subject or not date_node:
            continue
        match = DATE_SHORT.search(date_node.get_text(" ", strip=True))
        if not match:
            continue
        registered = datetime.strptime(match.group(1), "%y.%m.%d").date()
        detail_url = urljoin(base_url, f"/sub/view.asp?str_no={str_no}")
        results[str_no] = ListingItem(
            str_no=str_no,
            site_name=subject.get_text(" ", strip=True),
            registered_date=registered,
            detail_url=detail_url,
        )
    return list(results.values())


def _table_value(soup: BeautifulSoup, label: str) -> tuple[str, list[str]]:
    for row in soup.select(".content-info tr"):
        header = row.find("th")
        cell = row.find("td")
        if not header or not cell or header.get_text(" ", strip=True) != label:
            continue
        linked_values = [
            node.get_text(" ", strip=True) for node in cell.select("span") if node.get_text(strip=True)
        ]
        text = cell.get_text(" ", strip=True)
        return text, list(dict.fromkeys(linked_values))
    return "", []


def parse_detail_html(html: str, listing: ListingItem) -> DetailItem:
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one(".view-area .title-box .txt .title")
    live_anchor = soup.select_one(".view-area .title-box .url a[href]")
    if not title_node:
        raise ValueError(f"GDWEB 상세 제목을 찾지 못했습니다: {listing.detail_url}")

    registered_text, _ = _table_value(soup, "등록일")
    registered_date = listing.registered_date
    date_match = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", registered_text)
    if date_match:
        registered_date = date(*(int(value) for value in date_match.groups()))

    agency_text, agency_values = _table_value(soup, "제작사")
    award_name, _ = _table_value(soup, "수상명")
    certificate_no, _ = _table_value(soup, "선정증서번호")
    _, targets = _table_value(soup, "타겟층")
    _, methods = _table_value(soup, "표현방법")
    _, concepts = _table_value(soup, "디자인 컨셉")
    _, colors = _table_value(soup, "주색상")

    live_url = str(live_anchor.get("href", "")).strip() if live_anchor else ""
    if live_url and not urlparse(live_url).scheme:
        live_url = "https://" + live_url.lstrip("/")

    return DetailItem(
        str_no=listing.str_no,
        site_name=title_node.get_text(" ", strip=True) or listing.site_name,
        registered_date=registered_date,
        detail_url=listing.detail_url,
        live_url=live_url,
        agency=(agency_values[0] if agency_values else agency_text).strip(),
        targets=targets,
        methods=methods,
        concepts=concepts,
        colors=colors,
        award_name=re.sub(r"\s*\(.*", "", award_name).strip(),
        certificate_no=re.sub(r"\s*\(.*", "", certificate_no).strip(),
    )

