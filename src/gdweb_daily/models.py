from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlparse


@dataclass(slots=True)
class ListingItem:
    str_no: str
    site_name: str
    registered_date: date
    detail_url: str


@dataclass(slots=True)
class DetailItem(ListingItem):
    live_url: str = ""
    agency: str = ""
    targets: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    award_name: str = ""
    certificate_no: str = ""

    @property
    def domain(self) -> str:
        if not self.live_url:
            return ""
        return urlparse(self.live_url).netloc.lower().removeprefix("www.")


@dataclass(slots=True)
class WebsiteEvidence:
    reachable: bool = False
    final_url: str = ""
    title: str = ""
    description: str = ""
    menu_labels: list[str] = field(default_factory=list)
    cta_labels: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    error: str = ""


@dataclass(slots=True)
class Analysis:
    purpose_target_ia: str
    ux_patterns: str
    strengths: str
    improvements: str
    tech_actions: str


@dataclass(slots=True)
class ProcessedRecord:
    detail: DetailItem
    evidence: WebsiteEvidence
    analysis: Analysis

