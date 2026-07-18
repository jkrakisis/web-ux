from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from .analysis import OpenAIAnalyzer, fallback_analysis, format_six_lines
from .config import AppConfig
from .gdweb import GdwebCollector
from .http import HttpClient
from .models import Analysis, ProcessedRecord, WebsiteEvidence
from .notion import NotionClient
from .state import RunState
from .website import inspect_website


KST = timezone(timedelta(hours=9), name="Asia/Seoul")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GDWEB WEB 선정작 평일 자동 기록")
    parser.add_argument("--since", help="확인 시작 시각(ISO 8601). 미지정 시 체크포인트 사용")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Notion 미등록·상태 미변경")
    mode.add_argument("--live", action="store_true", help="Notion 실제 등록")
    parser.add_argument("--no-ai", action="store_true", help="OpenAI 없이 근거 기반 폴백 요약")
    return parser


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def _without_protocol(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme:
        return f"{parsed.netloc}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")
    return url.removeprefix("//")


def _failure_fields(detail: object, reason: str) -> list[str]:
    values = {
        "사이트명": getattr(detail, "site_name", "확인 불가"),
        "등록일": getattr(detail, "registered_date", "확인 불가"),
        "GDWEB str_no": getattr(detail, "str_no", "확인 불가"),
        "GDWEB URL": _without_protocol(getattr(detail, "detail_url", "")),
        "실사이트 URL": _without_protocol(getattr(detail, "live_url", "")) or "확인 불가",
        "제작사": getattr(detail, "agency", "") or "확인 불가",
        "표현방법": ", ".join(getattr(detail, "methods", [])) or "확인 불가",
        "디자인 컨셉": ", ".join(getattr(detail, "concepts", [])) or "확인 불가",
        "주색상": ", ".join(getattr(detail, "colors", [])) or "확인 불가",
        "처리 상태": "자동 등록 실패",
        "실패 사유": reason,
    }
    return [f"{key}: {value}" for key, value in values.items()]


def _write_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _write_dashboard(
    path: Path,
    generated_at: datetime,
    dry_run: bool,
    records: list[ProcessedRecord],
    failures: list[str],
) -> None:
    items: list[dict[str, object]] = []
    for record in records:
        detail = record.detail
        items.append(
            {
                "str_no": detail.str_no,
                "site_name": detail.site_name,
                "registered_date": detail.registered_date.isoformat(),
                "detail_url": detail.detail_url,
                "live_url": detail.live_url,
                "domain": detail.domain,
                "agency": detail.agency,
                "targets": detail.targets,
                "methods": detail.methods,
                "concepts": detail.concepts,
                "colors": detail.colors,
                "technologies": record.evidence.technologies,
                "evidence": record.evidence.evidence,
                "website_reachable": record.evidence.reachable,
                "lines": format_six_lines(detail, record.analysis),
            }
        )
    status = "partial" if failures else ("success" if items else "no_new")
    payload = {
        "generated_at": generated_at.isoformat(),
        "mode": "dry-run" if dry_run else "live",
        "status": status,
        "new_count": len(items),
        "failure_count": len(failures),
        "items": items,
        "failures": [{"text": failure} for failure in failures],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run(config: AppConfig, since: str = "", no_ai: bool = False) -> tuple[int, str]:
    started_at = datetime.now(KST)
    state = RunState.load(config.state_path)
    if since:
        window_start = _parse_datetime(since)
    elif state.previous_run_started_at:
        window_start = _parse_datetime(state.previous_run_started_at)
    else:
        window_start = started_at - timedelta(days=config.lookback_days)

    # 등록일이 일 단위로만 제공되므로 최근 구간을 겹쳐 조회하고 str_no로 중복 제거한다.
    safety_start = started_at.date() - timedelta(days=config.lookback_days)
    earliest_date = min(window_start.date(), safety_start)

    if not config.dry_run and not config.notion_enabled:
        raise RuntimeError("실등록에는 NOTION_TOKEN과 NOTION_DATA_SOURCE_ID가 필요합니다.")
    if not config.dry_run and not no_ai and not config.openai_api_key:
        raise RuntimeError("실등록 분석에는 OPENAI_API_KEY가 필요합니다.")

    http = HttpClient(
        config.user_agent,
        timeout_seconds=config.timeout_seconds,
        delay_seconds=config.request_delay_seconds,
    )
    collector = GdwebCollector(config.base_url, http)
    analyzer = OpenAIAnalyzer(
        "" if no_ai else config.openai_api_key,
        config.openai_model,
    )
    notion: NotionClient | None = None
    if config.notion_enabled:
        notion = NotionClient(
            config.notion_token,
            config.notion_data_source_id,
            config.notion_version,
            config.notion_property_map,
        )
        # 생성 전에 반드시 스키마와 기존 select/multi_select 옵션을 먼저 읽는다.
        notion.load_schema()

    listings = collector.fetch_recent(earliest_date, config.max_pages)
    processed = set(state.processed_str_nos)
    output_blocks: list[str] = []
    failures: list[str] = []
    dashboard_records: list[ProcessedRecord] = []

    for listing in listings:
        if listing.str_no in processed:
            continue
        try:
            detail = collector.fetch_detail(listing)
        except Exception as exc:
            reason = f"GDWEB 상세 접근/파싱 실패: {type(exc).__name__}"
            failures.append(
                "\n".join(
                    [f"자동 등록 실패 — {listing.site_name}", *_failure_fields(listing, reason)]
                )
            )
            continue

        if not detail.live_url:
            failures.append(
                "\n".join(
                    [
                        f"자동 등록 실패 — {detail.site_name}",
                        *_failure_fields(detail, "GDWEB 상세에서 실사이트 URL을 확정하지 못함"),
                    ]
                )
            )
            continue

        empty_record = ProcessedRecord(
            detail=detail,
            evidence=WebsiteEvidence(),
            analysis=Analysis("", "", "", "", ""),
        )
        try:
            if notion and notion.duplicate_exists(empty_record):
                processed.add(detail.str_no)
                continue
        except Exception as exc:
            failures.append(
                "\n".join(
                    [
                        f"자동 등록 실패 — {detail.site_name}",
                        *_failure_fields(detail, f"Notion 중복 조회 실패: {type(exc).__name__}"),
                    ]
                )
            )
            continue

        evidence = inspect_website(detail.live_url, http)
        try:
            analysis = analyzer.analyze(detail, evidence)
        except Exception as exc:
            if config.dry_run:
                analysis = fallback_analysis(detail, evidence)
            else:
                failures.append(
                    "\n".join(
                        [
                            f"자동 등록 실패 — {detail.site_name}",
                            *_failure_fields(detail, f"6줄 분석 실패: {type(exc).__name__}"),
                        ]
                    )
                )
                continue

        record = ProcessedRecord(detail=detail, evidence=evidence, analysis=analysis)
        lines = format_six_lines(detail, analysis)
        if not config.dry_run and notion:
            try:
                notion.create_record(record, started_at.isoformat())
            except Exception as exc:
                failures.append(
                    "\n".join(
                        [
                            f"자동 등록 실패 — {detail.site_name}",
                            *_failure_fields(detail, f"Notion 생성 실패: {type(exc).__name__}"),
                        ]
                    )
                )
                continue

        output_blocks.append("\n".join(lines))
        dashboard_records.append(record)
        if not config.dry_run:
            processed.add(detail.str_no)

    if not config.dry_run:
        state.processed_str_nos = sorted(processed, key=lambda value: int(value))
        state.mark_completed(started_at, datetime.now(KST))
        state.save(config.state_path)

    if output_blocks or failures:
        report = "\n\n".join([*output_blocks, *failures])
        exit_code = 1 if failures else 0
    else:
        report = "신규 없음"
        exit_code = 0
    _write_report(config.report_path, report)
    _write_dashboard(
        config.dashboard_path,
        datetime.now(KST),
        config.dry_run,
        dashboard_records,
        failures,
    )
    return exit_code, report


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    config = AppConfig.from_env()
    if args.dry_run:
        config.dry_run = True
    elif args.live:
        config.dry_run = False
    try:
        exit_code, report = run(config, since=args.since or "", no_ai=args.no_ai)
    except Exception as exc:
        print(f"실행 실패: {exc}", file=sys.stderr)
        return 2
    print(report)
    return exit_code
