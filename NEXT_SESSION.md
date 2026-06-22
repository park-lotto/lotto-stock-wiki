# NEXT_SESSION — 2026-06-22 (집PC · Opus 4.8)

## 세션 요약
대시보드를 **피드/시그널 2서비스로 분리**하고 둘 다 서버에 배포·검증 완료. 태린이 다운로드 자동화도 보강.

## ✅ 이번 세션 완료 (전부 배포·검증됨)

### 1. 피드/시그널 분리 (설계 → 구현 → 라이브)
- 설계 2건: `docs/superpowers/specs/2026-06-22-피드시그널-분리-design.md`
- 계획 2건: `docs/superpowers/plans/2026-06-22-피드-Tier-잠금.md`, `2026-06-22-시그널-깔때기.md`
- **`/feed`**: 소스 단계별 Tier 1~5 잠금(뉴스→블로그→유튜브→텔레→리포트). 잠긴 탭 🔒.
- **`/signal`**: 3단 깔때기(GO판정 → 섹터 → 종목 9점표). 독립 권한 `signal_access`.
- 권한 컬럼 `feed_tier`·`signal_access` 추가(가산 마이그레이션). 관리자 화면에서 유저별 지정 UI.
- 서버 커밋 3건(5e9ef2c, afc3be1, signal). 테스트 36개 통과. 운영자(빅팜) Tier5+시그널 부여.
- 시그널 데이터: 로컬 `pipeline/build_signal_snapshot.py`가 태린이 엑셀 → `signal_snapshot.json` 생성 → `scripts/sync_signal.py`로 서버 동기화 → 서버는 읽기만. **실데이터 363종목 검증.**

### 2. 태린이 다운로드 자동화 보강
- `scripts/mybox_links.json` URL 갱신(cafe·bingsu, 매주 월요일 변경). 14개 파일 다운로드 검증.
- `scripts/download_daily.py`: **폴더접근 차단 시 반드시 텔레그램 보고** 시스템 추가(check_access·_guard·report_problems).

## ❓ 검토/다음 작업 (운영자 확인 필요)
1. **Tier별 판매가** 매핑 (1~5 단계 가격) — 백엔드만 됨, 가격 미정
2. **시그널 9점 중 수동 4플래그**(판가·미국커플링·정책·D-30) 입력 방식 — 현재 기본 0(자동 5점만)
3. **STAGE 1 매크로**(GO/경계/NO) 자동소스 미연결 — 현재 "경계" 기본. `output/signal/macro_today.json` 수기 입력 시 반영
4. **STAGE 2 소르티노 자동화** — 현재 빈집분포 추정. 소르티노 파서 연결 시 정확↑
5. 관리자 비번 `admin/1234` 약함 — 변경 권장
6. 시그널 드릴다운 풀 4섹션(스코어보드/60일차트/멘트/위키) 시각화 — 현재 종목표까지. 후속

## 운영/접속
- 대시보드: http://3.39.179.148:8080 (admin/1234) — `/feed` 기본, `/signal` 시그널
- SSH: `ssh -i C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem ubuntu@3.39.179.148`
- 서버코드: `/home/ubuntu/kmong/crawling_bot/api/` (dashboard_server·dash_signal·dash_store·dash_feed)
- 서비스: `sudo systemctl restart stockbrain-dash`
- 시그널 갱신 루틴(수동): `python -m pipeline.build_signal_snapshot && python scripts/sync_signal.py`

## 미스케줄 (다음에 자동화)
- 07:55 ingest 뒤에 `build_signal_snapshot` + `sync_signal` 잇는 스케줄 추가 (현재 수동)
