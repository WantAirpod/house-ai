# home-decision-ai

부부가 실거주 아파트 매수를 준비하기 위한 부동산 인텔리전스 플랫폼입니다.

목표는 Railway에 배포 가능한 웹/API 서비스, Postgres 기반 데이터 저장소, 일간/주간 리포트 생성 파이프라인, Notion 게시 연동을 갖춘 실거주 매수 의사결정 시스템을 만드는 것입니다.

## 사용자 목표

- 1년 이내 실거주 아파트 매수
- 최대 예산 10억 ~ 10.5억
- 네이버 본사(정자동) 출퇴근 고려
- 관심 지역: 용인 수지, 용인 기흥, 용인 처인, 서울 내 판교 출퇴근 가능 지역
- 관심 평형: 59, 84
- 선호 연식: 12년 이하, 입지가 좋으면 구축도 검토

## 제품 범위

포함:

- 사용자/배우자 선호도 YAML 설정
- 관심 지역 및 관심 단지 YAML 관리
- Railway 배포 가능한 FastAPI 앱
- Railway Postgres 연동 경계
- 일간/주간/알림 리포트 프롬프트 템플릿
- 스케줄러 워커 구조
- Notion 게시 연동 경계
- 수동 입력 데이터와 자동 수집 데이터를 모두 수용하는 구조

아직 직접 구현 전인 영역:

- 실거래가 공식 API 수집기
- 호가 수집기
- 커뮤니티 반응 수집기
- Notion API 실제 게시 호출
- 프로덕션 인증/권한

## 설치

Python 3.12와 uv가 필요합니다.

```bash
cd home-decision-ai
uv sync
```

## 로컬 실행

설정 확인 CLI:

```bash
uv run home-decision-ai
```

웹/API 서버:

```bash
uv run uvicorn home_decision_ai.api.app:create_app --factory --reload
```

헬스 체크:

```bash
curl http://localhost:8000/health
```

## Railway 배포

Railway 프로젝트에 Postgres를 추가하고, 앱 서비스에 다음 환경변수를 설정합니다.

- `DATABASE_URL`
- `HOME_DECISION_AI_ENV=production`
- `HOME_DECISION_AI_CONFIG_DIR=config`
- `OPENAI_API_KEY` 또는 사용하는 LLM provider 키
- `NOTION_API_KEY`
- `NOTION_PARENT_PAGE_ID`

이 저장소는 `Procfile`을 통해 웹 프로세스를 실행합니다.

## 데이터 운영 방식

- `data/manual/`: 사람이 직접 정리한 매물, 호가, 커뮤니티 반응, 정책 메모
- `data/raw/`: 향후 API 또는 파일 기반 원천 데이터 저장 위치
- `data/processed/`: 정규화된 분석용 데이터 저장 위치
- `reports/daily/`: 일간 리포트
- `reports/weekly/`: 주간 리포트
- `reports/alerts/`: 조건 기반 알림 리포트

## 데이터 원칙

- 출처와 관측일이 없는 가격 데이터는 분석에 사용하지 않습니다.
- 실거래가는 국토교통부 실거래가 공개시스템 같은 공식 출처를 우선합니다.
- 호가와 매물 수는 관측일, 출처, 중복 가능성 메모를 함께 저장합니다.
- 커뮤니티 반응은 단독 근거가 아니라 보조 리스크 신호로만 사용합니다.
- AI 의견은 `verified` 또는 `manually_checked` 데이터에만 강한 결론을 붙입니다.

## 향후 개발 TODO

- TODO: Alembic 마이그레이션 도입
- TODO: 수동 입력용 CSV/YAML 스키마 정의
- TODO: 공식 실거래 API 수집기 구현
- TODO: 호가 변화 및 매물 증감 분석기 구현
- TODO: 정책/대출/금리 메모를 리포트에 반영하는 요약기 구현
- TODO: Notion 게시 클라이언트 구현
- TODO: Railway cron 또는 별도 worker 프로세스로 일간/주간 작업 자동화
- TODO: 데이터 출처, 관측일, 신뢰도 필드를 모든 입력 데이터에 포함
