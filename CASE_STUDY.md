# Web UX Archive — Product Case Study

> 반복적인 웹 레퍼런스 수집을 실행 이력과 누적 데이터가 남는 UX 리서치 서비스로 전환한 프로젝트

## Problem

매일 새로운 웹사이트를 참고하기 위해 GPT 예약 기능과 Notion을 함께 사용했지만 실제 운영에서는 세 가지 문제가 반복됐다.

- 예약 실행이 누락되거나 원하는 시점에 결과가 도착하지 않았다.
- Notion은 저장에는 적합하지만 여러 레퍼런스를 날짜별로 빠르게 탐색하기 어려웠다.
- 신규 사이트 확인, 근거 수집, 분석 초안 작성, 중복 검사와 기록이 반복 작업으로 남았다.

필요한 것은 단순한 예약 작업이 아니라 실행 여부를 추적하고, 실패 후 복구하며, 누적 데이터를 웹에서 탐색할 수 있는 작은 서비스였다.

## My Role

**Product Owner · UX Researcher · AI-assisted Builder**

- 반복 업무에서 핵심 문제와 자동화 요구사항 정의
- 신규 기준, 6줄 분석 형식, 중복 방지 및 Notion 등록 규칙 설계
- GitHub Actions·Notion·GitHub Pages 기반 운영 구조 선택
- 결과 품질, 공개 범위, 장애 상황과 대시보드 사용성 검증
- Codex와 협업해 코드 구현, 테스트, 배포와 장애 원인 분석 진행

## Solution

기존의 `GPT 예약 → Notion 저장` 흐름을 다음 구조로 전환했다.

```text
GDWEB 수집 → UX 근거 추출 → AI 기반 6줄 분석 초안
→ Notion 등록·전체 이력 동기화 → 일별 웹 아카이브
```

GitHub Actions가 평일마다 GDWEB 신규 선정작을 확인한다. GDWEB 상세와 실사이트 HTML에서 확인 가능한 근거를 수집하고, AI가 그 근거 안에서 목적·타겟·IA, UX 패턴, 강점, 개선점과 KPI 제안 초안을 생성한다. 결과는 Notion에 중복 없이 등록되며 GitHub Pages에서 날짜별로 탐색할 수 있다.

현재 자동화는 **근거 수집과 분석 초안 생성**까지 담당한다. 정식 사용성 테스트, 시각적 휴리스틱 평가, 접근성·성능 감사와 종합 AI UX Audit은 향후 범위다.

## Key Technical Decisions

- **Serverless operation:** 별도 서버 대신 GitHub Actions와 GitHub Pages 사용
- **Evidence first:** GDWEB 메타와 실사이트 HTML에서 확인된 정보만 AI 입력으로 사용
- **Schema safety:** Notion 등록 전 스키마를 읽고 기존 select 옵션만 매핑
- **Duplicate protection:** GDWEB `str_no`, 또는 실사이트 도메인과 등록일로 중복 방지
- **Resilient history:** 신규 0건이나 GDWEB 오류가 발생해도 기존 Notion 이력 유지
- **Private credentials:** API 키와 Notion 토큰은 GitHub Secrets에서만 사용

## Result

| 결과 | 검증값 |
| --- | --- |
| 누적 UX 레퍼런스 | 54건 |
| 탐색 가능한 등록일 | 23일 |
| 자동화 테스트 | 10 passed |
| 최신 수동 실행 | collect·deploy-pages 성공 |
| 신규가 없는 날 | 기존 아카이브 유지 |
| 데이터 접근 | 날짜 필터·전체 보기·검색 제공 |

반복 확인 작업이 줄었고, 실행 누락과 실패 원인을 GitHub에서 추적할 수 있게 됐다. Notion의 구조화된 저장 장점은 유지하면서 웹에서는 레퍼런스를 더 빠르게 탐색할 수 있게 됐다.

## Product Roadmap

```text
현재: GDWEB 수집 → UX 근거 추출 → AI 기반 분석 초안 → UX 아카이브
Next: 패턴 분류 → 산업·유형별 비교 → UX Pattern Archive
Future: AI UX Audit → 분석 리포트 → 비교 가능한 UX 데이터셋 축적
```

## Links

- [Live Dashboard](https://jkrakisis.github.io/web-ux/)
- [GitHub Repository](https://github.com/jkrakisis/web-ux)
- [Full Technical Journey](TECHNICAL_JOURNEY.md)
