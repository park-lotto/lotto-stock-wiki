# NEXT SESSION

- **날짜**: 2026-06-21
- **세션 요약**: 크롤링봇 → SaaS 구독형 인사이트 대시보드 MVP 구현·배포 완료

## ✅ 완료 (이번 세션)
- **뉴스 RSS 피드 5개 → 15개 확장** (config.yaml). 주식 관련성 필터(부동산/분양 제외 + 주식맥락 필수) + 한국경제 UA 패치. 뉴스 발송 포맷 "제목+1~2줄" 간결화.
- **스탁브레인 대시보드 MVP 전체 구현** (서브에이전트 주도 13태스크, 30 테스트 통과, opus 최종리뷰 통과)
  - 서버: `api/dashboard_server.py`(FastAPI :8080) + dash_store/auth/feed/stats/briefing
  - 인증: JWT, 아이디/PW + 텔레그램 매직링크, 구독 만료 차단
  - API: 피드·브리핑(AI 일간요약+캐시)·통계(수집량/키워드빈도)·설정(키워드/채널 CRUD)·관리자(구독자 관리)
  - 프론트: 검정+골드, 5탭(브리핑/피드/통계/설정/관리자), Chart.js
  - 배포: systemd `stockbrain-dash` 상시가동. **외부 접속 검증 완료**(Lightsail TCP 8080 인바운드 Any IP 개방)
  - 기존 크롤링봇(main_v2) 무손상. 서버 git init(feat/dashboard→main 정리, dd9983e)
- 임시 admin 로그인: `admin` / `stockbrain2026!` (http://3.39.179.148:8080)

## ⏳ 다음 작업 (미완료) — 집에서 이어서

### 🎯 다음 세션 메인: 대시보드 개편 (UI + 위키 연계) — brainstorming으로 설계 시작
사용자가 구상방안 가져오면 brainstorming → writing-plans → 구현. 두 축:

**1) UI 인터페이스 변경**
- 현재는 기능 MVP 수준 기본 UI. 참고 레이아웃/디자인 이미지 사용자 지참 예정.
- 피드 필터 규칙 재설계(아래 피드 항목)도 여기서 함께.

**2) ⭐ 브리핑/인사이트에 "위키 폴더 연계" (핵심 차별화)**
- 현재: 브리핑·요약이 output/md(오늘 raw 크롤링)만 사용. 위키 축적지식 미사용.
- 목표: 오늘 raw + 위키 축적지식 결합 → 깊은 인사이트 (CLAUDE.md 분석 파이프라인 = 원자DB맥락+실시간+결합 을 대시보드에 이식. STOCK BRAIN 컨셉).
- **전제**: 위키 지식이 서버에 있어야 함(현재 위키는 로컬+GitHub만, 서버엔 없음). 위키→서버 동기화 방식 결정 필요(서버에서 위키 repo pull 등).
- **연계 깊이 2단계 중 택**:
  - ① 위키 파일 맥락: 서버가 위키 pull → 키워드 관련 섹터/종목 페이지를 AI에 같이 전달 (간단)
  - ② 원자DB RAG: `pipeline/atoms` 의미검색(이미 `python -m pipeline.atoms.query` 존재) → 서버에 chroma vector DB+의존성 올려 결합 (강력, "제2의 두뇌")
  - 결합 시 dash_briefing 프롬프트 재설계 필요.

**[UI개편 때 같이] 피드 필터 규칙 재설계**
- 현재 피드는 모든 카테고리를 "키워드"로 필터 → 텔레/블로그는 본문 매칭 안돼 안 뜸(뉴스만 보임)
- 결정 필요: 뉴스=키워드 / 텔레·유튜브·블로그=구독채널 기준 (or 수집된 것 전부)
- **파싱 버그(같이 수정)**: dash_feed.parse_md_file의 summary 정규식이 뉴스 `## 본문 요약`만 인식. 블로그=`## 본문`, 텔레=섹션없음(제목후 전체) → summary 빈값. 포맷 대응 필요.
- 참고: 빅팜 현재 tg/yt/blog 구독채널 0개, 수신설정 전부 0. 텔레/블로그 수집은 기존 config 기반(user_store union 비어있음).

### 🔧 집 PC 준비물
- 위키 repo: `git pull` (GitHub main 최신, a5f2a76)
- **SSH 키 파일 필수**: `LightsailDefaultKey-ap-northeast-2.pem` (git에 없음 — USB/Lightsail 재다운로드로 집PC에 복사). 없으면 서버 코드 수정 불가(대시보드 브라우저 보기는 가능).
- 대시보드는 서버 systemd로 24시간 가동 중(PC 무관). http://3.39.179.148:8080 (admin/1234)
- **[UI개편 때 같이] 피드 필터 규칙 재설계**:
  - 현재 피드는 모든 카테고리를 "키워드"로 필터 → 텔레/블로그는 키워드 본문 매칭 안돼 안 뜸(뉴스만 보임)
  - 결정 필요: 뉴스=키워드 필터 / 텔레·유튜브·블로그=구독채널 기준 (or 수집된 것 전부)
  - **파싱 버그(같이 수정 예정)**: dash_feed.parse_md_file의 summary 정규식이 뉴스 `## 본문 요약`만 인식. 블로그는 `## 본문`, 텔레는 섹션없음(제목후 전체본문) → summary 빈값. 텔레/블로그 포맷 대응 필요.
  - 참고: 빅팜은 현재 tg/yt/blog 구독채널 0개, 수신설정 전부 0. 텔레/블로그 수집은 기존 config 기반(user_store union 비어있음).
- 비밀번호 변경 UI 없음(MVP 제외) — 필요 시 추가
- 통계 "주도섹터 강도"는 후순위(데이터 누적 후)
- 결제 자동화는 범위 밖(현재 수동 등록 B안)

## 📁 관련 파일
- 설계: `docs/superpowers/specs/2026-06-21-stockbrain-saas-dashboard-design.md`
- 계획: `docs/superpowers/plans/2026-06-21-stockbrain-dashboard.md`
- 진행원장: `.superpowers/sdd/progress.md` (태스크별 미해결 findings 포함)
- 서버 코드: `/home/ubuntu/kmong/crawling_bot/api/dashboard_server.py` 등 (SSH only)

## 🔑 서버 접속
- SSH: `ssh -i C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem ubuntu@3.39.179.148`
- 대시보드: http://3.39.179.148:8080 / 서비스: `systemctl status stockbrain-dash`
- 대시보드 코드 수정 후 반영: 파일 scp → `sudo systemctl restart stockbrain-dash`
