from __future__ import annotations

import json
from dataclasses import asdict

import requests

from .models import Analysis, DetailItem, WebsiteEvidence


ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "purpose_target_ia": {"type": "string"},
        "ux_patterns": {"type": "string"},
        "strengths": {"type": "string"},
        "improvements": {"type": "string"},
        "tech_actions": {"type": "string"},
    },
    "required": [
        "purpose_target_ia",
        "ux_patterns",
        "strengths",
        "improvements",
        "tech_actions",
    ],
}


class OpenAIAnalyzer:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 60.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def analyze(self, detail: DetailItem, evidence: WebsiteEvidence) -> Analysis:
        if not self.api_key:
            return fallback_analysis(detail, evidence)

        payload = {
            "model": self.model,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "당신은 공공·기업 웹 UX 분석가다. 제공된 근거만 사용하고 추측은 "
                        "'확인 불가'로 표시한다. 한국어 공적/실무 톤으로 각 필드를 한 줄로 쓴다. "
                        "tech_actions에는 반드시 '기술/플러그인 키워드: ... + A) ... + B) ... "
                        "+ C) ... + D) ...' 순서를 지킨다. A는 메인 IA 퀵액션 재배치, "
                        "B는 전환/체류/탐색 KPI, C는 공공기관 Do/Don't, D는 오늘의 한 줄이다."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"gdweb": asdict(detail), "website": asdict(evidence)},
                        ensure_ascii=False,
                        default=str,
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "gdweb_analysis",
                    "strict": True,
                    "schema": ANALYSIS_SCHEMA,
                }
            },
        }
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        output_text = _response_text(data)
        parsed = json.loads(output_text)
        return Analysis(**parsed)


def _response_text(payload: dict[str, object]) -> str:
    for output in payload.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                return str(content.get("text", ""))
    raise ValueError("OpenAI 응답에서 구조화 텍스트를 찾지 못했습니다.")


def fallback_analysis(detail: DetailItem, evidence: WebsiteEvidence) -> Analysis:
    targets = ", ".join(detail.targets) or "확인 불가"
    menus = ", ".join(evidence.menu_labels[:8]) or "확인 불가"
    purpose = evidence.description or f"{detail.site_name}의 정보·서비스 제공"
    technologies = ", ".join(evidence.technologies) or "확인 불가"
    methods = ", ".join(detail.methods) or "확인 불가"
    concepts = ", ".join(detail.concepts) or "확인 불가"
    ctas = ", ".join(evidence.cta_labels[:5]) or "확인 불가"
    return Analysis(
        purpose_target_ia=f"목적: {purpose[:160]} / 타겟: {targets} / IA: {menus}",
        ux_patterns=f"메뉴 기반 탐색, 주요 CTA({ctas}), 표현 방식({methods})",
        strengths=f"GDWEB 근거상 {concepts} 컨셉과 {methods} 표현을 일관되게 활용",
        improvements="자동 근거 수집 범위 내 세부 사용성 검증이 제한되어 핵심 과업의 접근 단계·키보드 탐색·모바일 상태 추가 점검 필요",
        tech_actions=(
            f"기술/플러그인 키워드: {technologies} + "
            "A) 메인 IA 퀵액션은 최빈 과업을 첫 화면 상단에 우선 배치 + "
            "B) KPI는 CTA 전환율·핵심 콘텐츠 체류시간·메뉴 탐색 성공률로 측정 + "
            "C) 공공기관 Do: 명확한 과업명·접근성 제공 / Don't: 모션 의존·모호한 메뉴명 + "
            "D) 오늘의 한 줄: 근거가 확인되는 범위부터 작게 측정하고 개선"
        ),
    )


def format_six_lines(detail: DetailItem, analysis: Analysis) -> list[str]:
    live = detail.live_url or "확인 불가"
    return [
        (
            f"1) {detail.site_name} / {detail.registered_date.isoformat()} / "
            f"GDWEB 상세: {detail.detail_url} / 실사이트: {live}"
        ),
        f"2) {analysis.purpose_target_ia}",
        f"3) {analysis.ux_patterns}",
        f"4) {analysis.strengths}",
        f"5) {analysis.improvements}",
        f"6) {analysis.tech_actions}",
    ]

