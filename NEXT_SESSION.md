# NEXT SESSION

날짜: 2026-06-29 (집PC 재부팅 후)
PC: DESKTOP-T8CB1GG (집PC)
세션 요약: 딸깍 대시보드 시장 패널 완성 (시간표기+그래프 수정)

---

## ✅ 완료

- HTS vs API 데이터 불일치 수정 (stex_tp=1, inds_cd=001/101)
- price 음수 버그 수정 (abs 처리)
- 장마감 배지 오타 수정 (isClose 조건식)
- 섹터 카드 더보기/접기 + 같은 행 동기화
- 종목 정렬 상단으로 변경
- topbar 새로고침 버튼 추가
- 로딩 속도 해결: localStorage stale-while-revalidate + 서버 논블로킹 + prewarm 병렬화
- localStorage 버전 관리 (_LS_VER="v3") → 배포 시 캐시 자동 무효화
- 섹터 카드 스파크라인 우상단 배치 (KIS API 일봉 종가)
- 투자자 누적 추이 X축 시간 레이블 (ts 기반)
- 프로그램 순매수 X축 시간 레이블
- 분봉 차트(miniLine) X축 시간 레이블 (09:00~15:30 추정)
- 글로벌 지표 차트 X축 시간 레이블
- 프로그램 순매수 레이블 중복 제거
- 누적 추이 그래프: 데이터 없을 때 안내 문구 표시 / 1포인트일 때 "15분 후 생성" 표시

## ⏳ 미결

- 누적 추이 그래프: 장중에 서버 켜두면 자동 누적 (지금은 장외라 1포인트)
- 딸깍 장중 2단계 (한투 API 연동)
- 딸깍 마감 버튼

## 관련 파일

- `dashboard/market.html` — 시장 패널 메인
- `dashboard/server.py` — FastAPI :8090
- `scripts/kiwoom_api.py` — 키움 API
- `scripts/kis_api.py` — KIS API (get_daily_bars 추가)
- `scripts/sector_heatmap.py` — 섹터 히트맵 + bars 병렬 조회
