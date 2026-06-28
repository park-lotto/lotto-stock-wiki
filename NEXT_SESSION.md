# NEXT_SESSION — 2026-06-28 (회사PC → 집PC 이어작업)

## ⚡ 집에서 바로 할 일

### 1. 딸깍 대시보드 편집 탭 실사용 확인 (최우선)
편집 탭 새로 완성됨. 써보고 UX 이상한 부분 피드백.
- 서버 실행: `python dashboard/server.py` → http://localhost:8090/market
- ⚙️ 편집 탭에서 섹터 추가/삭제/종목 추가 테스트

### 2. B단계 → C단계 (유튜브 자막 파이프라인)
전체 설계 = `docs/superpowers/specs/2026-06-28-유튜브-자막-원자-파이프라인-design.md` **(이거 먼저 읽기)**

#### A단계 완료
- 유튜브 크롤 → `## 주요 발언`에 `- [mm:ss] 화자: 발언원문` 8~16개 자동 생성
- Gemini가 영상 직접 시청 방식 (yt-dlp 서버 봇차단으로 폐기)

#### B단계 — 로컬 원자 추출 (할 일)
- 목표: 유튜브 md의 `[mm:ss] 화자: 발언`을 `atomizer.py`로 원자화
- `pipeline/atoms/atomizer.py` (atoms.db 스키마: id,date,source_type,source_name,layer,sector,asset,signal,content_type,content,certainty)
- speaker·stance·숫자를 원자에 살리기

#### C단계 — 발언카드 + /영상기획 (할 일)
- 발언카드: speaker/입장/핵심발언(인용)/근거/딥링크(`{url}&t=Ns`)
- `/영상기획 {주제}` 명령: 발언카드 모아 → [화자|입장|인용|근거|딥링크] 표 + 대본골격

---

## 이번 세션 완성물 (2026-06-28 회사PC)

### 딸깍 대시보드 `/market` 개선
- SVG 레전드 텍스트 뒤틀림 수정
- 즐겨찾기 탭 (localStorage 영속)
- 섹터/종목 정렬 (avg_rate 내림차순)
- NXT 통합 실시간가 (J 마켓코드)
- 탭 전환 속도 개선 (서버 TTL캐시 + 클라이언트 캐시 + 백그라운드 프리페치)
- **⚙️ 편집 탭 완성**
  - 섹터 숨김/표시 토글
  - 종목 추가(KRX 검색) / 삭제
  - 커스텀 섹터 신규 생성
  - 💾 저장 → `pipeline/sector_custom.json`

### 관련 파일
- `dashboard/market.html` — 편집 탭 UI
- `dashboard/server.py` — `/api/sector_custom`, `/api/stock_search`
- `scripts/sector_heatmap.py` — `_apply_custom_overrides()` 오버레이
- `pipeline/sector_custom.json` — 사용자 설정 저장소

### 크롤링 소스관리 대시보드 (`dashboard/sources`, 로컬 8090)
- 바탕화면 `크롤링소스관리.bat` → http://localhost:8090/sources

### 서버(크롤러) 구조
- **Lightsail `ubuntu@3.39.179.148` : `/home/ubuntu/kmong/crawling_bot/`**
- SSH키: `C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem`
  ⚠️ 집PC에 이 키 없으면 서버연동 버튼 작동 안 함

---
## ⚠️ 집PC 시작 시
1. `git pull` 최신화
2. 편집 탭 써보고 → 이어서 B단계
