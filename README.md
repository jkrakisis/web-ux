# Web UX Archive

A personal UX research pipeline that automatically collects new GDWEB winners, analyzes UX patterns, and archives insights into Notion.

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
cd C:\Users\kim\Documents\gdweb-daily
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

예약은 한국시간 평일 08:37입니다. `LIVE_ENABLED=true`가 없으면 예약은 안전한 드라이런으로 실행되며 Notion에 쓰지 않습니다. 체크포인트는 실등록 성공 실행 후 `state/checkpoint.json`에 자동 커밋됩니다. 한 항목의 실패는 다른 항목을 막지 않지만, 실패 항목이 있으면 workflow를 실패 처리하여 확인 가능하게 합니다.

각 실행은 `docs/data/latest.json`을 갱신하고 같은 workflow에서 GitHub Pages 대시보드를 배포합니다. 페이지에는 공개된 GDWEB·실사이트 분석 결과만 포함하며 API 키와 Notion 토큰은 포함하지 않습니다.

## 출력

- 처리 대상이 없으면 `신규 없음`만 출력합니다.
- 신규 항목은 정확히 6줄로 출력합니다.
- 자동 등록이 불가능하면 `자동 등록 실패`와 Notion에 붙여넣을 수 있는 프로퍼티 목록을 출력합니다. 이 목록의 URL에는 프로토콜이 포함되지 않습니다.
