# Web UX Archive

A personal UX research pipeline that automatically collects new GDWEB winners, analyzes UX patterns, and archives insights into Notion.

채용용 요약: [CASE_STUDY.md](CASE_STUDY.md)

제품 및 기술 구현 과정: [TECHNICAL_JOURNEY.md](TECHNICAL_JOURNEY.md)

## Features

- ✔ GitHub Actions Scheduler
- ✔ Notion API
- ✔ Duplicate Detection
- ✔ Schema Validation
- ✔ UX Insight Generation
- ✔ Dashboard

## GDWEB Daily

GDWEB의 WEB 부문 신규 선정작을 평일마다 확인하고, GDWEB 상세 및 실사이트의 근거를 모아 6줄로 요약한 뒤 Notion Data Source에 중복 없이 등록하는 자동화입니다.

대시보드: `https://jkrakisis.github.io/web-ux/`

## 동작 원칙

- 목록과 상세 페이지는 `str_no`를 기본 식별자로 사용합니다.
- 등록일이 일 단위이므로 최근 7일을 겹쳐 확인한 후 로컬 체크포인트와 Notion에서 중복을 제거합니다.
- GDWEB 상세의 실사이트·제작사·표현방법·컨셉·색상을 우선 근거로 사용합니다.
- 기술 키워드는 실사이트 HTML, script 경로, 응답 헤더에서 확인된 값만 사용합니다.
- Notion 생성 전 Data Source 스키마를 읽고, select/multi_select는 기존 옵션 `id`만 전송합니다. 유사 옵션이 없으면 해당 값만 제외합니다.
- GDWEB 상세에서 실사이트를 확정하지 못하면 등록하지 않고 프로토콜 없는 필드-값 목록을 출력합니다.

## 로컬 실행

Python 3.11 이상이 필요합니다.

```powershell
cd D:\codex\gdweb-daily
py -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m gdweb_daily --dry-run --no-ai
```

`py` 명령이 없는 PC에서는 설치된 Python 실행 파일 경로로 같은 명령을 실행하면 됩니다. 프로그램은 결과 출력을 UTF-8로 고정합니다.

실제 Notion 등록 전 환경 변수를 설정합니다.

```powershell
$env:OPENAI_API_KEY = "..."
$env:NOTION_TOKEN = "..."
$env:NOTION_DATA_SOURCE_ID = "..."
$env:DRY_RUN = "false"
.\.venv\Scripts\python -m gdweb_daily --live
```

`NOTION_PROPERTY_MAP`은 기존 DB의 프로퍼티명이 기본 별칭과 다를 때만 지정합니다.

```powershell
$env:NOTION_PROPERTY_MAP = '{"site_name":"프로젝트명","str_no":"고유 번호","status":"진행 상태"}'
```

## Notion 준비

1. Notion 내부 통합을 만들고 대상 DB에 연결 권한을 부여합니다.
2. 브라우저 URL 또는 API 조회 결과에서 Data Source ID를 확인합니다.
3. 다음 프로퍼티 중 필요한 항목을 기존 DB에 둡니다. 이름이 달라도 `NOTION_PROPERTY_MAP`으로 연결할 수 있습니다.

권장 프로퍼티: 사이트명(title), 등록일(date), GDWEB URL(url), 실사이트 URL(url), GDWEB str_no(rich_text 또는 number), 도메인(rich_text), 제작사(select 또는 rich_text), 타겟층/표현방법/디자인 컨셉/주색상/기술 키워드(multi_select 또는 rich_text), 6줄 요약(rich_text), 처리 상태(select), 수집 시각(date).

등록 과정은 DB에 없는 select 옵션을 생성하지 않습니다. 매핑되지 않는 값은 그 프로퍼티에서만 제외되고 6줄 본문에는 근거 텍스트로 유지됩니다.

## GitHub Actions 배포

1. 이 폴더를 비공개 GitHub 저장소로 푸시합니다.
2. Repository Secrets에 `OPENAI_API_KEY`, `NOTION_TOKEN`, `NOTION_DATA_SOURCE_ID`를 추가합니다.
3. 필요하면 Repository Variables에 `OPENAI_MODEL`, `NOTION_PROPERTY_MAP`을 추가합니다.
4. Actions의 `GDWEB weekday collector`를 `dry_run=true`로 한 번 수동 실행합니다.
5. 결과 artifact를 확인한 뒤 `dry_run=false`로 수동 실행합니다.
6. 예약 실행까지 Notion 실등록으로 전환하려면 Repository Variable `LIVE_ENABLED`를 `true`로 추가합니다.

예약은 한국시간 평일 18:30입니다. GDWEB 안내 운영시간인 10:00–18:00 이후에 실행해 당일 늦게 등록되는 항목까지 한 번에 수집하는 구성입니다. `LIVE_ENABLED=true`가 없으면 예약은 안전한 드라이런으로 실행되며 Notion에 쓰지 않습니다. 체크포인트는 실등록 성공 실행 후 `state/checkpoint.json`에 자동 커밋됩니다. 한 항목의 실패는 다른 항목을 막지 않지만, 실패 항목이 있으면 workflow를 실패 처리하여 확인 가능하게 합니다.

각 실행은 `docs/data/latest.json`을 갱신하고 같은 workflow에서 GitHub Pages 대시보드를 배포합니다. 페이지에는 공개된 GDWEB·실사이트 분석 결과만 포함하며 API 키와 Notion 토큰은 포함하지 않습니다.

## 대시보드 표시

- 1–5번 분석은 목적·타겟·IA, UX 패턴, 강점과 개선점 순서로 표시합니다.
- 6번은 `기술·플러그인`, `A · IA 퀵액션`, `B · 핵심 KPI`, `C · 공공기관 Do/Don’t`, `D · 오늘의 한 줄`로 분리합니다.
- 기술 키워드는 개별 칩으로 표시합니다.
- 최근 10건은 실사이트 첫 화면 캡처에 성공한 경우에만 제목 옆에 작은 썸네일을 표시합니다.
- 캡처 실패 또는 이미지 로드 오류 시 이미지 요소 전체를 제거해 빈 공간을 남기지 않습니다.
- 데스크톱에서 A와 B는 2열, C와 D는 각각 전체 너비를 사용합니다.
- 모바일에서는 모든 하위 영역을 1열로 표시합니다.

썸네일 시험 실행:

```powershell
cd D:\codex\gdweb-daily
.\.venv\Scripts\python -m pip install -e ".[thumbnail,dev]"
$env:THUMBNAIL_BROWSER_CHANNEL = "msedge"
.\.venv\Scripts\python -m gdweb_daily.thumbnails --limit 10
```

GitHub Actions에서는 설치된 Chrome으로 같은 작업을 수행합니다. 사이트별 제한시간과 실패를 격리하고, 추적·분석 요청은 차단하되 첫 화면 영상은 허용하며 페이지 진입 후 3초 동안 안정화를 기다린 뒤 JPEG로 저장합니다. 실패 정보는 `thumbnail_status`와 `thumbnail_error`에 남고 수집 및 Notion 등록 결과에는 영향을 주지 않습니다.

## 최근 업데이트 — 2026-08-09

- 최신 사이트 10건을 대상으로 제목 옆 썸네일 시험 적용
- 8건 캡처 성공, 1건 시각적 빈 화면 감지, 1건 HTTP 403 차단 확인
- 빈 화면·작은 파일 검증과 사이트별 실패 격리 추가
- 캡처 실패 시 이미지와 레이아웃 공간을 모두 제거
- GitHub Actions에서 신규 실행마다 최근 10건의 미생성 썸네일을 보충하도록 구성
- 실행 안내 문구를 평일 18:30 KST로 수정

## 최근 업데이트 — 2026-07-29

- 평일 1회 예약을 08:37에서 18:30으로 변경
- 오전 실행 이후 같은 날 추가된 GDWEB 항목 2건을 확인하고 늦은 등록 누락 사례 기록
- 최근 7일 중첩 조회와 `str_no` 중복 제거를 이용한 다음 실행 복구 원칙 재확인
- 기술/플러그인 및 A–D 제안을 독립 카드로 분리해 긴 6번 문장의 가독성 개선
- C · 공공기관 Do/Don’t와 D · 오늘의 한 줄을 전체 너비로 확장
- 누적 63건, 등록일 28일, 드라이런 신규 2건, 실패 0건 검증

## 출력

- 처리 대상이 없으면 `신규 없음`만 출력합니다.
- 신규 항목은 정확히 6줄로 출력합니다.
- 자동 등록이 불가능하면 `자동 등록 실패`와 Notion에 붙여넣을 수 있는 프로퍼티 목록을 출력합니다. 이 목록의 URL에는 프로토콜이 포함되지 않습니다.
