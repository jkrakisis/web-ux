from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class RunState:
    previous_run_started_at: str = ""
    last_completed_at: str = ""
    processed_str_nos: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "RunState":
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            previous_run_started_at=str(payload.get("previous_run_started_at", "")),
            last_completed_at=str(payload.get("last_completed_at", "")),
            processed_str_nos=[str(value) for value in payload.get("processed_str_nos", [])],
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "previous_run_started_at": self.previous_run_started_at,
            "last_completed_at": self.last_completed_at,
            "processed_str_nos": self.processed_str_nos[-2000:],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def mark_completed(self, started_at: datetime, completed_at: datetime) -> None:
        self.previous_run_started_at = started_at.isoformat()
        self.last_completed_at = completed_at.isoformat()

