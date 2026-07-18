from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _property_map() -> dict[str, str]:
    raw = os.getenv("NOTION_PROPERTY_MAP", "").strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("NOTION_PROPERTY_MAP은 JSON 객체여야 합니다.")
    return {str(key): str(value) for key, value in parsed.items()}


@dataclass(slots=True)
class AppConfig:
    base_url: str = "https://www.gdweb.co.kr"
    lookback_days: int = 7
    max_pages: int = 3
    request_delay_seconds: float = 0.8
    timeout_seconds: float = 25.0
    user_agent: str = "gdweb-daily/0.1 (+personal research automation)"
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    notion_token: str = ""
    notion_data_source_id: str = ""
    notion_version: str = "2026-03-11"
    notion_property_map: dict[str, str] = field(default_factory=dict)
    dry_run: bool = True
    state_path: Path = Path("state/checkpoint.json")
    report_path: Path = Path("reports/latest.txt")
    dashboard_path: Path = Path("docs/data/latest.json")

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            base_url=os.getenv("GDWEB_BASE_URL", "https://www.gdweb.co.kr").rstrip("/"),
            lookback_days=int(os.getenv("GDWEB_LOOKBACK_DAYS", "7")),
            max_pages=int(os.getenv("GDWEB_MAX_PAGES", "3")),
            request_delay_seconds=float(
                os.getenv("GDWEB_REQUEST_DELAY_SECONDS", "0.8")
            ),
            timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "25")),
            user_agent=os.getenv(
                "HTTP_USER_AGENT", "gdweb-daily/0.1 (+personal research automation)"
            ),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini").strip(),
            notion_token=os.getenv("NOTION_TOKEN", "").strip(),
            notion_data_source_id=os.getenv("NOTION_DATA_SOURCE_ID", "").strip(),
            notion_version=os.getenv("NOTION_VERSION", "2026-03-11").strip(),
            notion_property_map=_property_map(),
            dry_run=_bool("DRY_RUN", True),
            state_path=Path(os.getenv("STATE_PATH", "state/checkpoint.json")),
            report_path=Path(os.getenv("REPORT_PATH", "reports/latest.txt")),
            dashboard_path=Path(
                os.getenv("DASHBOARD_PATH", "docs/data/latest.json")
            ),
        )

    @property
    def notion_enabled(self) -> bool:
        return bool(self.notion_token and self.notion_data_source_id)
