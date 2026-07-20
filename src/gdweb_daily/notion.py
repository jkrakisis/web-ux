from __future__ import annotations

import ast
import difflib
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import requests

from .analysis import format_six_lines
from .models import ProcessedRecord


ALIASES: dict[str, tuple[str, ...]] = {
    "site_name": ("사이트명", "이름", "Name", "제목", "Title"),
    "registered_date": ("등록일", "선정일", "Date", "Registration Date"),
    "gdweb_url": ("GDWEB URL", "GDWEB 상세", "상세 URL", "GDWEB"),
    "live_url": ("실사이트", "실사이트 URL", "사이트 URL", "Live URL", "웹사이트"),
    "str_no": ("GDWEB str_no", "str_no", "GDWEB 번호", "식별자"),
    "domain": ("도메인", "Domain", "실사이트 도메인"),
    "agency": ("제작사", "Agency"),
    "targets": ("타겟층", "타겟", "Target"),
    "methods": ("표현방법", "표현 방법", "Method"),
    "concepts": ("디자인 컨셉", "컨셉", "Concept"),
    "colors": ("주색상", "색상", "Color"),
    "technologies": (
        "기술/플러그인 키워드",
        "기술 키워드",
        "기술/플러그인",
        "Technology",
    ),
    "summary": ("요약(6줄)", "6줄 요약", "요약", "Summary"),
    "status": ("처리 상태", "상태", "Status"),
    "collected_at": (
        "Last check 시각",
        "수집 시각",
        "확인 시각",
        "Collected At",
    ),
    "purpose": ("목적", "Purpose"),
    "ia": ("IA(메뉴)", "IA", "메뉴"),
    "ux_patterns": ("핵심 UX 패턴", "UX 패턴"),
    "strengths": ("강점", "Strengths"),
    "improvements": ("개선 포인트", "개선점", "Improvements"),
    "observations": ("근거(관찰)", "근거", "Evidence"),
    "quick_action": ("A) IA 퀵액션",),
    "kpi": ("B) KPI",),
    "public_do_dont": ("C) 공공 Do/Don't",),
    "one_line": ("D) 오늘의 한 줄",),
    "month_text": ("월_YYYYMM",),
    "is_new": ("신규여부", "신규"),
    "is_weekend": ("주말",),
}


class NotionClient:
    def __init__(
        self,
        token: str,
        data_source_id: str,
        notion_version: str = "2026-03-11",
        property_map: dict[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.data_source_id = data_source_id
        self.timeout_seconds = timeout_seconds
        self.property_map_override = property_map or {}
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": notion_version,
                "Content-Type": "application/json",
            }
        )
        self.schema: dict[str, dict[str, Any]] = {}
        self.semantic_names: dict[str, str] = {}

    def load_schema(self) -> dict[str, dict[str, Any]]:
        response = self.session.get(
            f"https://api.notion.com/v1/data_sources/{self.data_source_id}",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        self.schema = payload.get("properties", {})
        self.semantic_names = self._resolve_semantic_names()
        return self.schema

    def _resolve_semantic_names(self) -> dict[str, str]:
        resolved: dict[str, str] = {}
        lower_names = {name.casefold(): name for name in self.schema}
        for semantic, aliases in ALIASES.items():
            override = self.property_map_override.get(semantic)
            if override and override in self.schema:
                resolved[semantic] = override
                continue
            for alias in aliases:
                actual = lower_names.get(alias.casefold())
                if actual:
                    resolved[semantic] = actual
                    break
        if "site_name" not in resolved:
            title_name = next(
                (name for name, prop in self.schema.items() if prop.get("type") == "title"),
                "",
            )
            if title_name:
                resolved["site_name"] = title_name
        return resolved

    def duplicate_exists(self, record: ProcessedRecord) -> bool:
        self._ensure_schema()
        str_no_name = self.semantic_names.get("str_no")
        if str_no_name:
            query_filter = self._equals_filter(str_no_name, record.detail.str_no)
            if query_filter and self._query_any(query_filter):
                return True

        domain_name = self.semantic_names.get("domain")
        date_name = self.semantic_names.get("registered_date")
        if domain_name and date_name and record.detail.domain:
            domain_filter = self._equals_filter(domain_name, record.detail.domain)
            date_filter = self._equals_filter(
                date_name, record.detail.registered_date.isoformat()
            )
            if domain_filter and date_filter:
                return self._query_any({"and": [domain_filter, date_filter]})

        live_url_name = self.semantic_names.get("live_url")
        if live_url_name and date_name and record.detail.live_url:
            variants = _url_variants(record.detail.live_url)
            live_filters = [
                candidate
                for candidate in (
                    self._equals_filter(live_url_name, variant) for variant in variants
                )
                if candidate
            ]
            date_filter = self._equals_filter(
                date_name, record.detail.registered_date.isoformat()
            )
            if live_filters and date_filter:
                url_filter: dict[str, object]
                if len(live_filters) == 1:
                    url_filter = live_filters[0]
                else:
                    url_filter = {"or": live_filters}
                return self._query_any({"and": [url_filter, date_filter]})
        return False

    def create_record(self, record: ProcessedRecord, collected_at: str) -> str:
        self._ensure_schema()
        lines = format_six_lines(record.detail, record.analysis)
        actions = _action_parts(record.analysis.tech_actions)
        values: dict[str, object] = {
            "site_name": record.detail.site_name,
            "registered_date": record.detail.registered_date.isoformat(),
            "gdweb_url": record.detail.detail_url,
            "live_url": record.detail.live_url,
            "str_no": record.detail.str_no,
            "domain": record.detail.domain,
            "agency": record.detail.agency,
            "targets": record.detail.targets,
            "methods": record.detail.methods,
            "concepts": record.detail.concepts,
            "colors": record.detail.colors,
            "technologies": record.evidence.technologies,
            "summary": "\n".join(lines),
            "status": "완료",
            "collected_at": collected_at,
            "purpose": record.analysis.purpose_target_ia,
            "ia": ", ".join(record.evidence.menu_labels),
            "ux_patterns": record.analysis.ux_patterns,
            "strengths": record.analysis.strengths,
            "improvements": record.analysis.improvements,
            "observations": "; ".join(record.evidence.evidence),
            "quick_action": actions.get("A", ""),
            "kpi": actions.get("B", ""),
            "public_do_dont": actions.get("C", ""),
            "one_line": actions.get("D", ""),
            "month_text": record.detail.registered_date.strftime("%Y-%m"),
            "is_new": True,
            "is_weekend": record.detail.registered_date.weekday() >= 5,
        }
        properties: dict[str, object] = {}
        for semantic, value in values.items():
            property_name = self.semantic_names.get(semantic)
            if not property_name or value in (None, "", []):
                continue
            encoded = self._encode_property(property_name, value)
            if encoded is not None:
                properties[property_name] = encoded

        title_name = self.semantic_names.get("site_name")
        if not title_name or title_name not in properties:
            raise ValueError("Notion DB에서 title 프로퍼티를 확인할 수 없습니다.")

        children = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": self._rich_text(line)},
            }
            for line in lines
        ]
        response = self.session.post(
            "https://api.notion.com/v1/pages",
            json={
                "parent": {
                    "type": "data_source_id",
                    "data_source_id": self.data_source_id,
                },
                "properties": properties,
                "children": children,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return str(response.json().get("id", ""))

    def list_dashboard_items(self) -> list[dict[str, object]]:
        """노션 DB의 전체 비보관 행을 공개 대시보드 형식으로 변환한다."""
        self._ensure_schema()
        items: list[dict[str, object]] = []
        start_cursor = ""
        while True:
            body: dict[str, object] = {
                "page_size": 100,
                "sorts": [
                    {
                        "property": self.semantic_names.get("registered_date", "등록일"),
                        "direction": "descending",
                    }
                ],
            }
            if start_cursor:
                body["start_cursor"] = start_cursor
            response = self.session.post(
                f"https://api.notion.com/v1/data_sources/{self.data_source_id}/query",
                json=body,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            for page in payload.get("results", []):
                item = self._dashboard_item(page)
                if item:
                    items.append(item)
            if not payload.get("has_more"):
                break
            start_cursor = str(payload.get("next_cursor") or "")
            if not start_cursor:
                break
        return items

    def _dashboard_item(self, page: dict[str, Any]) -> dict[str, object] | None:
        site_name = str(self._page_value(page, "site_name") or "").strip()
        registered_date = str(
            self._page_value(page, "registered_date") or ""
        ).strip()
        if not site_name or not registered_date:
            return None

        detail_url = _absolute_url(str(self._page_value(page, "gdweb_url") or ""))
        live_url = _absolute_url(str(self._page_value(page, "live_url") or ""))
        str_no_match = re.search(r"[?&]str_no=(\d+)", detail_url, flags=re.IGNORECASE)
        str_no = str_no_match.group(1) if str_no_match else ""
        domain = urlparse(live_url).netloc.casefold().removeprefix("www.")
        targets = _as_text_list(self._page_value(page, "targets"))
        technologies = _as_text_list(self._page_value(page, "technologies"))
        summary = str(self._page_value(page, "summary") or "").strip()
        lines = [line.strip() for line in summary.splitlines() if line.strip()]
        if not lines:
            lines = _dashboard_lines(
                site_name=site_name,
                registered_date=registered_date,
                detail_url=detail_url,
                live_url=live_url,
                purpose=str(self._page_value(page, "purpose") or "").strip(),
                targets=targets,
                ia=str(self._page_value(page, "ia") or "").strip(),
                ux_patterns=str(self._page_value(page, "ux_patterns") or "").strip(),
                strengths=str(self._page_value(page, "strengths") or "").strip(),
                improvements=str(
                    self._page_value(page, "improvements") or ""
                ).strip(),
                technologies=technologies,
                quick_action=str(
                    self._page_value(page, "quick_action") or ""
                ).strip(),
                kpi=str(self._page_value(page, "kpi") or "").strip(),
                public_do_dont=str(
                    self._page_value(page, "public_do_dont") or ""
                ).strip(),
                one_line=str(self._page_value(page, "one_line") or "").strip(),
            )
        return {
            "str_no": str_no,
            "site_name": site_name,
            "registered_date": registered_date[:10],
            "detail_url": detail_url,
            "live_url": live_url,
            "domain": domain,
            "targets": targets,
            "technologies": technologies,
            "lines": lines[:6],
            "notion_url": str(page.get("url") or ""),
            "source": "notion",
        }

    def _page_value(self, page: dict[str, Any], semantic: str) -> object:
        property_name = self.semantic_names.get(semantic)
        if not property_name:
            return ""
        prop = page.get("properties", {}).get(property_name, {})
        prop_type = str(
            prop.get("type")
            or self.schema.get(property_name, {}).get("type")
            or ""
        )
        value = prop.get(prop_type)
        if prop_type in {"title", "rich_text"}:
            return "".join(str(part.get("plain_text") or "") for part in value or [])
        if prop_type == "url":
            return value or ""
        if prop_type == "date":
            return (value or {}).get("start", "")
        if prop_type == "checkbox":
            return bool(value)
        if prop_type == "select":
            return (value or {}).get("name", "")
        if prop_type == "multi_select":
            return [
                str(option.get("name") or "")
                for option in value or []
                if option.get("name")
            ]
        if prop_type == "number":
            return value
        return ""

    def _ensure_schema(self) -> None:
        if not self.schema:
            self.load_schema()

    def _query_any(self, query_filter: dict[str, object]) -> bool:
        response = self.session.post(
            f"https://api.notion.com/v1/data_sources/{self.data_source_id}/query",
            json={"filter": query_filter, "page_size": 1},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return bool(response.json().get("results"))

    def _equals_filter(self, property_name: str, value: object) -> dict[str, object] | None:
        prop_type = self.schema[property_name].get("type")
        filter_type = {
            "title": "title",
            "rich_text": "rich_text",
            "url": "url",
            "date": "date",
            "number": "number",
            "select": "select",
        }.get(str(prop_type))
        if not filter_type:
            return None
        normalized: object = value
        if prop_type == "number":
            try:
                normalized = float(str(value))
            except ValueError:
                return None
        return {"property": property_name, filter_type: {"equals": normalized}}

    def _encode_property(self, property_name: str, value: object) -> dict[str, object] | None:
        prop = self.schema[property_name]
        prop_type = str(prop.get("type", ""))
        if prop_type == "title":
            return {"title": self._rich_text(str(value))}
        if prop_type == "rich_text":
            return {"rich_text": self._rich_text(str(value))}
        if prop_type == "url":
            return {"url": str(value)}
        if prop_type == "date":
            return {"date": {"start": str(value)}}
        if prop_type == "number":
            try:
                return {"number": float(str(value))}
            except ValueError:
                return None
        if prop_type == "checkbox":
            return {"checkbox": bool(value)}
        if prop_type == "select":
            option = self._closest_existing_option(prop, str(value))
            return {"select": {"id": option["id"]}} if option else None
        if prop_type == "multi_select":
            values = value if isinstance(value, list) else [str(value)]
            options = [
                option
                for option in (
                    self._closest_existing_option(prop, str(item)) for item in values
                )
                if option
            ]
            return {
                "multi_select": [{"id": option["id"]} for option in _unique_options(options)]
            } if options else None
        return None

    @staticmethod
    def _rich_text(value: str) -> list[dict[str, object]]:
        # Notion은 rich_text 한 조각당 2,000자 제한이 있으므로 분할한다.
        return [
            {"type": "text", "text": {"content": value[index : index + 2000]}}
            for index in range(0, len(value), 2000)
        ] or [{"type": "text", "text": {"content": ""}}]

    @staticmethod
    def _closest_existing_option(
        prop: dict[str, Any], desired: str, cutoff: float = 0.74
    ) -> dict[str, str] | None:
        prop_type = str(prop.get("type", ""))
        options = prop.get(prop_type, {}).get("options", [])
        desired_folded = desired.strip().casefold()
        if not desired_folded:
            return None
        for option in options:
            if str(option.get("name", "")).strip().casefold() == desired_folded:
                return option
        scored = sorted(
            (
                difflib.SequenceMatcher(
                    None, desired_folded, str(option.get("name", "")).casefold()
                ).ratio(),
                option,
            )
            for option in options
        )
        if scored and scored[-1][0] >= cutoff:
            return scored[-1][1]
        return None


def _unique_options(options: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for option in options:
        unique[str(option["id"])] = option
    return list(unique.values())


def _url_variants(url: str) -> list[str]:
    stripped = url.strip()
    if not stripped:
        return []
    variants = [stripped]
    if stripped.endswith("/"):
        variants.append(stripped.rstrip("/"))
    else:
        variants.append(stripped + "/")
    return list(dict.fromkeys(variants))


def _action_parts(value: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for segment in re.split(r"\s*\+\s*(?=[ABCD]\))", value):
        match = re.match(r"([ABCD])\)\s*(.*)", segment, flags=re.DOTALL)
        if match:
            parts[match.group(1)] = match.group(2).strip()
    return parts


def _absolute_url(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    if stripped.startswith(("http://", "https://")):
        return stripped
    return f"https://{stripped.lstrip('/')}"


def _as_text_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [part.strip() for part in text.split(",") if part.strip()]


def _dashboard_lines(
    *,
    site_name: str,
    registered_date: str,
    detail_url: str,
    live_url: str,
    purpose: str,
    targets: list[str],
    ia: str,
    ux_patterns: str,
    strengths: str,
    improvements: str,
    technologies: list[str],
    quick_action: str,
    kpi: str,
    public_do_dont: str,
    one_line: str,
) -> list[str]:
    target_text = ", ".join(targets) or "확인 불가"
    technology_text = ", ".join(technologies) or "확인 불가"
    return [
        f"1) {site_name} / {registered_date[:10]} / GDWEB 상세: {detail_url or '확인 불가'} / 실사이트: {live_url or '확인 불가'}",
        f"2) 목적·타겟·IA: {purpose or '확인 불가'} / 타겟: {target_text} / IA: {ia or '확인 불가'}",
        f"3) 핵심 UX 패턴: {ux_patterns or '확인 불가'}",
        f"4) 강점: {strengths or '확인 불가'}",
        f"5) 개선 포인트: {improvements or '확인 불가'}",
        f"6) 기술/플러그인 키워드: {technology_text} + A) {quick_action or '확인 불가'} + B) {kpi or '확인 불가'} + C) {public_do_dont or '확인 불가'} + D) {one_line or '확인 불가'}",
    ]
