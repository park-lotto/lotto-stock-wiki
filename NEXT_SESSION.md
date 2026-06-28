# NEXT_SESSION — 2026-06-28 (회사PC → 집PC 이어작업)

## ⚡ 집에서 바로 할 일: B단계 → C단계 (유튜브 자막 파이프라인)

전체 설계 = `docs/superpowers/specs/2026-06-28-유튜브-자막-원자-파이프라인-design.md` **(이거 먼저 읽기)**

### 지금까지 (A단계 완료)
- 유튜브 크롤 → 영상마다 `## 주요 발언`에 **`- [mm:ss] 화자: 발언원문`** 8~16개 자동 생성됨
- 방식: **Gemini가 영상 직접 시청**(yt-dlp 자막은 서버 봇차단으로 폐기) — 서버 `processors/gemini_summarizer.py` 프롬프트 수정 (Lightsail에 이미 적용·검증됨)
- 적용범위: **지금부터 크롤되는 새 영상**. 며칠 쌓이면 실데이터로 B 설계가 정확함.

### B단계 — 로컬 원자 추출 (할 일)
- 목표: 새 유튜브 md의 `[mm:ss] 화자: 발언`을 `atomizer.py`로 원자화
- 위치: `pipeline/atoms/atomizer.py` (추출 프롬프트 있음 / atoms.db 스키마: id,date,source_type,source_name,layer,sector,asset,signal,content_type(fact/data/analysis/opinion),content,certainty 등)
- 보강 포인트: 분석가 자막엔 **화자(speaker)·stance(입장)·숫자**를 원자에 살리기 (지금 atomizer는 source_name=채널만)
- 유튜브 크롤파일이 로컬 ingest로 atoms.db에 들어가는지 먼저 확인 (안 되면 연결)

### C단계 — 발언카드 + /영상기획 (할 일)
- **발언카드**: speaker / 입장 / 핵심발언(인용) / 근거 / 시간 / **딥링크(`{url}&t=Ns`)** ← [mm:ss]를 초로 변환
- **`/영상기획 {주제}` 명령**: 주제별 발언카드 모아 → [화자|입장|인용|근거|딥링크] 표 + 70/20/10 대본골격(인용90+내인사이트10)
- 사용자 영상컨셉: "권위자 발언 인용 90% + 내 인사이트 10%". 주제 예: "지금 반도체 고점인가"
- D단계(선택): 발언 시간으로 ffmpeg 프레임 캡쳐 → 서버에 ffmpeg 설치 필요(현재 미설치)

---

## 이번 세션 완성물 (참고)

### 크롤링 소스관리 대시보드 (`dashboard/`, 로컬 8090)
- 바탕화면 `크롤링소스관리.bat` → http://localhost:8090/sources
- 추가/삭제(링크 또는 이름) → **로컬 레지스트리 + 서버 config.yaml 자동 연동**
- 버튼: 📥지금 받아오기(전체 다운로드) / 🔄소스 동기화(폴더스캔 자동등록) / ▶전체크롤(카테고리) / ▶(채널별 크롤)
- 소스 동기화로 등록목록 = 실제 크롤 일치 (텔레19·뉴스4·블로그4·유튜브5)

### 시황부장 챗봇 + 마스코트
- 바탕화면 `스탁브레인.bat`(대시보드+채팅) / `스탁브레인_부장.bat`(마스코트 창)
- `dashboard/agents/시황부장.md`, claude -p 헤드리스, 캐릭터=`dashboard/assets/시황부장.png`

### 서버(크롤러) 구조 — 중요
- **Lightsail `ubuntu@3.39.179.148` : `/home/ubuntu/kmong/crawling_bot/`** 에서 실제 크롤 (main.py + APScheduler)
- 스케줄(config.yaml): 뉴스 매시 / 텔레 30분(증분=seen_urls.json) / 유튜브·블로그 9·12·15·18·21시(3시간)
- 로컬 `client.py`(crawling_bot_client)가 5분마다 새 파일 다운로드 (last_sync 증분)
- 서버에 설치한 스크립트: `add_source.py` `del_source.py` `crawl_run.py` (config.yaml 안전수정·백업·중복방지)
- SSH키: `C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem`
  ⚠️ **집PC에 이 키 없으면** 대시보드의 서버연동(추가/삭제/크롤버튼) 작동 안 함. B·C(로컬 원자/발언카드)는 키 불필요.

### notebooklm MCP
- 설치됨(user scope). 단 첫 구글로그인(`setup_auth`) 미완 + 오디오전용. 인사이트 분석엔 형님 위키+원자DB가 메인.

---
## ⚠️ 집PC 시작 시
1. `git pull` (이 repo 최신화 — 대시보드/spec/이 파일)
2. spec 읽고 → B단계부터
3. 서버측(gemini_summarizer, *_source.py, crawl_run.py)은 Lightsail에 이미 있음 (git 아님, 서버 공유)
