from __future__ import annotations

import difflib
from collections.abc import Iterable
from typing import Any

import requests

from .analysis import format_six_lines
from .models import ProcessedRecord


ALIASES: dict[str, tuple[str, ...]] = {
    "site_name": ("사이트명", "이름", "Name", "제목", "Title"),
    "registered_date": ("등록일", "선정일", "Date", "Registration Date"),
    "gdweb_url": ("GDWEB URL", "GDWEB 상세", "상세 URL", "GDWEB"),
    "live_url": ("실사이트 URL", "사이트 URL", "Live URL", "웹사이트"),
    "str_no": ("GDWEB str_no", "str_no", "GDWEB 번호", "식별자"),
    "domain": ("도메인", "Domain", "실사이트 도메인"),
    "agency": ("제작사", "Agency"),
    "targets": ("타겟층", "타겟", "Target"),
    "methods": ("표현방법", "표현 방법", "Method"),
    "concepts": ("디자인 컨셉", "컨셉", "Concept"),
    "colors": ("주색상", "색상", "Color"),
    "technologies": ("기술 키워드", "기술/플러그인", "Technology"),
    "summary": ("6줄 요약", "요약", "Summary"),
    "status": ("처리 상태", "상태", "Status"),
    "collected_at": ("수집 시각", "확인 시각", "Collected At"),
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
        return False

    def create_record(self, record: ProcessedRecord, collected_at: str) -> str:
        self._ensure_schema()
        lines = format_six_lines(record.detail, record.analysis)
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

