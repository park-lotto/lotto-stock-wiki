# NEXT_SESSION — 사람 브레인 (Person Brain)

**날짜**: 2026-07-02 · **주제**: 채널 운영자 사고 복제 = 제2의 브레인

## 이번 세션 요약 (핵심 비전 전부 달성)

브레인스토밍 → 설계 → 계획 → 서브에이전트 구현 → 로드맵 A~E 전 단계 완성.
`pipeline/people/` 패키지 + 대시보드 🧠 브레인 탭 (127.0.0.1:8090/brain). **tests 46/46.**

### 완성된 것
- **질의 엔진** `persona.py` — "이 종목 태린이라면?"(stock_verdict) / "지금 비중?"(market_verdict).
  판정 + `[데이터]/[추론]/[발언]` 라벨. LLM 없이 결정론적(할루시네이션 0).
- **종목선정 퍼널** `funnel.py` — 빈집×컨센×주도주(RS)×소라티노 4축(his모드). 적중률 0.15→0.25.
- **오늘의 루틴 재구성** `brain_view.routine_today` — 정적 루틴을 오늘 데이터로 채움(🟢).
- **검증+추세+자동스냅샷** `track.py` + atom_pipeline STEP7 (매일 자동 누적 → 자동 수렴).
- **3버킷** 시장인사이트(27)·방법론·재료검색. **2축 대시보드**(데이터/사고).
- **2호 채널** pokara61 등록 — 발언만으로 브레인 복제(범용 스키마 검증됨).
- **다운로드 근본수정** — download_mybox.mjs가 python3(Store스텁)로 압축해제 실패하던 것 수정.
  소라티노(etf상대강도)·RS(종목상대강도) 파일 복구.

### 데이터/운영 메모
- RS = 유동성체크 '주도주찾기' 시트. 소라티노 = etf상대강도데이터.xlsx(scan_sortino 재사용).
- 원자 taxonomy: content_type=fact/opinion/analysis/data/news. **스탠스=stance_key, 층=asset_level**(market/macro/stock/sector/method/stance).
- 서버 재시작: `Get-NetTCPConnection -LocalPort 8090` → Stop-Process → Start-Process(`python.exe dashboard/server.py`, -WorkingDirectory 프로젝트).
- 실제 python: `C:/Users/TheRose/AppData/Local/Python/bin/python.exe` (bare python=Store스텁 exit49).

## 미완료 / 다음 할 것 (폴리시·확장)
- [ ] **비중 산출** — 후보에 그의 비중 규칙 적용(종목선정 → 실제 매매 크기)
- [ ] **채널 더 추가** — 실전 채널 등록(people.json 한 줄 + 인제스트돼 원자 있어야)
- [ ] **매도 규칙 감시** — 이평선 이탈 → 축소 (가격/MA 데이터 필요)
- [ ] **LLM 자연어 phrasing** — 판정을 그의 말투로(선택)
- [ ] 현금언급 탐지 정확도(market_verdict), 컨센 완화(주도주 up>down)
- [ ] track 스냅샷 며칠 쌓이면 임계값 자동튜닝

## 관련 파일
- 설계: `docs/superpowers/specs/2026-07-02-태린이아빠-브레인-design.md`
- 코드: `pipeline/people/` (registry·people_query·build_brain·brain_view·funnel·rs_data·sortino_data·track·persona·routines/)
- 대시보드: `dashboard/brain.html` + server.py `/api/brain/*`
- 메모리: `project_person_brain`
