from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .http import HttpClient
from .models import WebsiteEvidence


TECH_RULES: dict[str, tuple[str, ...]] = {
    "Google Analytics": ("googletagmanager.com/gtag", "google-analytics.com"),
    "Google Tag Manager": ("googletagmanager.com/gtm.js",),
    "React": ("react.production.min.js", "_next/static", "data-reactroot"),
    "Next.js": ("/_next/", "__next_data__"),
    "Vue": ("vue.runtime", "vue.global", "data-v-"),
    "Nuxt": ("/_nuxt/", "__nuxt__"),
    "jQuery": ("jquery.min.js", "jquery-") ,
    "GSAP": ("gsap.min.js", "greensock", "scrolltrigger"),
    "Swiper": ("swiper-bundle", "swiper.min"),
    "WordPress": ("/wp-content/", "/wp-includes/"),
    "Cafe24": ("cafe24.com", "cafe24api"),
}


def _clean_labels(values: Iterable[str], limit: int) -> list[str]:
    result: list[str] = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", value).strip()
        if not cleaned or len(cleaned) > 40 or cleaned in result:
            continue
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def inspect_website(url: str, http: HttpClient) -> WebsiteEvidence:
    if not url:
        return WebsiteEvidence(error="실사이트 URL 없음")
    try:
        response = http.get(url)
    except Exception as exc:  # 네트워크/인증/차단을 항목별 실패로 격리
        return WebsiteEvidence(error=f"실사이트 접근 실패: {type(exc).__name__}")

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower() and "xhtml" not in content_type.lower():
        return WebsiteEvidence(
            reachable=True,
            final_url=response.url,
            error=f"HTML이 아닌 응답: {content_type or '미상'}",
        )

    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description_node = soup.select_one('meta[name="description"], meta[property="og:description"]')
    description = str(description_node.get("content", "")).strip() if description_node else ""

    menu_nodes = soup.select("nav a, header a, [role='navigation'] a")
    menu_labels = _clean_labels((node.get_text(" ", strip=True) for node in menu_nodes), 20)
    cta_nodes = soup.select("a, button, [role='button']")
    cta_labels = _clean_labels(
        (
            node.get_text(" ", strip=True)
            for node in cta_nodes
            if any(
                keyword in node.get_text(" ", strip=True).lower()
                for keyword in (
                    "신청", "예약", "문의", "구매", "가입", "시작", "더보기",
                    "apply", "book", "contact", "buy", "join", "start",
                )
            )
        ),
        12,
    )

    lowered = html.lower()
    technologies: list[str] = []
    evidence: list[str] = []
    for technology, needles in TECH_RULES.items():
        matched = next((needle for needle in needles if needle in lowered), "")
        if matched:
            technologies.append(technology)
            evidence.append(f"{technology}: HTML에서 '{matched}' 확인")
    powered_by = response.headers.get("x-powered-by", "").strip()
    if powered_by:
        technologies.append(powered_by)
        evidence.append(f"응답 헤더 x-powered-by={powered_by}")

    return WebsiteEvidence(
        reachable=True,
        final_url=response.url,
        title=title,
        description=description[:500],
        menu_labels=menu_labels,
        cta_labels=cta_labels,
        technologies=list(dict.fromkeys(technologies)),
        evidence=evidence[:20],
    )

