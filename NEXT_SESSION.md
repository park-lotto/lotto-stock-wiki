# NEXT_SESSION — 여러 병렬 세션(아래 최신순) / YT 대시보드 ①기획 (Task5 남음, 다른 세션)

## [세션 C, 2026-07-03] pytest 수집버그 수정 + 브랜드 스타일 인포그래픽 실험 — 완료

**주제**: (1) 일일검증(daily_verify.py) 텔레알림이 fail/ok를 오가던 원인 진단·수정,
(2) 골루프 인포그래픽에 실제 브랜드(클로드/클레이) CI/BI 스타일 입히기 실험.

### ✅ 완료 — pytest 수집 에러 4건
- 원인 3가지: `scripts/_c2_test.py`·`_kis_test.py`(이름만 test패턴, 실제론 수동스크립트)가
  자동수집돼 win32com/KIS_APP_KEY 참조로 항상 에러 / `pandas` 서버venv 미설치 /
  `dashboard.server`를 pytest가 root에서 import할 때 `dashboard/` sys.path 누락.
- 수정: `conftest.py`에 `collect_ignore_glob`+`dashboard/` sys.path 추가, venv에 pandas 설치.
- 결과: 수집에러 0건, "7 failed, 446 passed"로 정상화(남은 7개는 atoms/ingest 파이프라인
  기존 test-source 드리프트, 오늘 작업과 무관 — 미해결로 남김, 사용자가 여기까지만 하기로 함).

### ✅ 완료 — 브랜드 스타일 인포그래픽 (`scripts/nlm_bridge.py`)
- `create_infographic()`에 `brand=` 파라미터 추가 — 기존엔 커스텀 focus를 줘도 항상
  `_BRAND_DESIGN`(라임그린 HUD)이 같이 붙어 스타일이 섞이는 버그였음(예: 클로드 실험 시
  크림+라임그린 혼합) → `BRAND_STYLE_PRESETS` dict로 완전 대체 가능하게 고침.
- 등록된 프리셋 3종(전부 텔레그램 전송·사용자 확인 완료): `claude`(크림+코랄 에디토리얼),
  `claude_terminal`(다크+픽셀아웃라인폰트+터미널창, 이미지소스 없이도 재현됨), `clay`
  (3D클레이메이션+채도색카드순환, clay.com 실이미지 3장을 노트북소스로 추가해서 성공).
- 부수 발견: `studio status` 폴링이 `arts[-1]`(최고참)을 봐서 예전 완료본을 오판하던 버그 수정
  (`arts[0]`으로, API가 최신순 응답). `nlm download infographic` CLI가 `--profile` 옵션
  자체를 미지원(create/status는 지원) — 다른 계정 다운로드 시 `nlm login switch`로 임시전환 후
  즉시 원복하는 우회 필요. 계정 2개(default=parklotto12, secondary=parklotto20) 운용 중,
  하나가 rate limit 걸리면 다른 계정으로 전환.
- 참고: `scripts/goal_loop/design_refs/{claude,clay}_design.md`, `clay_images/`(원본 3장).
  메모리: `project_brand_style_infographics.md`, `feedback_brand_style_workflow.md`.
- **다음**: 애플/구글 등 추가 스타일 원하면 질문지 먼저 드리고 컨펌 후 진행(사용자 요청 절차).

### ✅ 완료 — wiki 건강검진 후속조치 3건(별개 작업, 같은 세션)
BRAIN_INDEX.md 6개 레이어 링크 전부 깨져있던 것 수정 / `raw/캡처본`(오타폴더) 정리 /
`wiki/stock_현대백화점_20260507.md`(루트 고아파일) → `L5_섹터/소비내수/stock/`로 정식 이전.

---

## [세션 B] 텔레그램 뉴스릴레이 파이프라인 + 일일검증 에이전트 (완료)

**날짜**: 2026-07-03 · **PC**: DESKTOP-T8CB1GG

## 이번 세션(텔레그램+검증에이전트+대시보드UI) 요약 — 전부 완료·배포됨

### ✅ 텔레그램 뉴스릴레이 → 히트맵 파이프라인 실전검증·버그수정
- 4개 채널(주식픽/실시간속보단독뉴스/실시간주식뉴스/그로쓰리서치특징주) 실채널 데이터로
  검증 → 진짜 버그 3개 발견·수정: 중복재게시 필터, 언론 관용약칭(삼전/하닉) 매칭,
  `stock_sector_map.json` 자기참조 항목(시장/자동차 등 18개) 종목 오탐
  (`scripts/telegram_news_filter.py`, `tests/test_telegram_news_filter.py`)
- 크롤 주기 하루5번→**15분마다(7~23시)**로 상향, "주식픽" 타임아웃 40s→90s,
  텔레그램 전용 경량 동기화 스크립트 신설(`scripts/sync_telegram_only.py`, 크론 15분)
- 섹터 키워드 오탐 2건 실사례 발견·수정: "증권"(→증권주 등 구체화), "엔씨"(→엔씨소프트,
  "지엔씨에너지" 종목명 부분매칭 오탐 원인) — `pipeline/sector_news_keywords.json`

### ✅ 일일 검증 에이전트 신설·배포 (사용자 요청: 매일 자동 오류검사+보고 시스템)
- 스펙: `docs/superpowers/specs/2026-07-03-daily-verify-agent-design.md`
- 계획: `docs/superpowers/plans/2026-07-03-daily-verify-agent.md`
- 구현: `scripts/daily_verify.py` + `tests/test_daily_verify.py`(20 테스트) — 크롤신선도(요일별
  4주평균)+pytest회귀+stockbrain서비스상태(재시작1회시도) → 텔레그램 통합보고
- 원격서버 크론 등록: `45 21 * * *`(마지막 인제스트 21:35 이후로 — 최초 21:30 오타 수정함)
- **실행검증 중 실버그 2개 추가 발견·수정**: (1) cp949 콘솔 print 크래시, (2) 원격서버엔
  `python` 명령어가 없는데(`python3`만 존재) 하드코딩 호출→FileNotFoundError가 "측정
  실패=경보아님"으로 조용히 삼켜져 체커가 매일 "정상"으로 오보고할 뻔함 → `sys.executable`
  사용으로 수정. **교훈: 이런 유형의 "체커 자체가 무력화되는 버그"가 제일 위험 — 로컬
  개발환경과 배포환경 차이를 항상 실배포 후 재검증할 것.**
- 외부 도달성(서버 자체 네트워크 장애) 체크는 명시적으로 범위 밖 — 같은 날 실제로 서버가
  2번 다운됐는데(AWS 네트워크단 장애, 원인불명) 온서버 체커로는 원리적으로 감지 불가함이
  실증됨. 필요시 UptimeRobot 등 외부서비스 가입 권장(안내만 함, 계정 필요해 대신 못 함).

### ✅ 대시보드 UI 개선 3건
- 섹터상세 팝오버: 종목 등락률(`kis_api.get_price`) 추가 + 폭 300→420px 확장.
  KIS API 500 일시장애 대응 1회 재시도 추가(5분 캐시라 실패시 오래 굳는 문제 발견·수정)
- AI 요약 출처 표기 "Gemini"→"STOCK BRAIN" (2곳)
- AI 요약 프롬프트에서 "유튜브 채널 애널리스트/시청자" 프레이밍 제거 → 대시보드에
  "안녕하세요 시청자 여러분" 같은 영상 인트로가 섞여 나오던 문제 수정(섹터+종목 요약 2곳)

### 배포 상태
전부 `git push` + 원격서버(stockbrain1.duckdns.org) pull+재시작 완료, 브라우저로 실제
렌더링 확인 완료. 남은 작업 없음.

### 🚨 동시세션 충돌 패턴 (이번 세션에도 반복 발생 — 계속 주의)
원격서버 배포 시 `git pull`이 여러 번 다른 세션의 커밋(YT 대시보드/클레이 프리셋/기타)과
충돌 — 매번 `git stash push -u` → pull → `stash pop` → (충돌시 `atoms.db`/캐시성 JSON 등
데이터파일은 `--ours` 유지, 코드파일은 없었음) 패턴으로 안전 처리함. **다음 세션도 배포 전
항상 이 패턴 사용.**

---

## [다른 세션 기록, 미완료] YT 대시보드 ①기획단계 — Task 5 남음

**주제**: 유튜브 영상제작(기획→대본→리모션→녹음→자막→렌더) 통합 대시보드 첫 단계.
Task 1-4 완료(hot_clips.py, /yt/hot_clips, plan_stage.py, /yt/generate_plan SSE),
**Task 5**(`dashboard/yt.html` + `GET /yt` 라우트)만 미시작 — HTML/CSS/JS는 계획서에
이미 작성돼 있어 transcription+테스트만 하면 됨. **render 산출물이라 실제 브라우저
구동 확인 필수(자동테스트만으로 완료 처리 금지).**

- 스펙: `docs/superpowers/specs/2026-07-03-yt-기획단계-대시보드-design.md`
- 계획: `docs/superpowers/plans/2026-07-03-yt-기획단계-대시보드.md`
- 원장: `.superpowers/sdd/progress.md`
- Task 5 리뷰 → 전체 브랜치 최종 리뷰 → `superpowers:finishing-a-development-branch`
- 배포: git push만 완료, Lightsail 서버 배포는 Task5 완성 후 별도 진행
- ②대본 ③리모션 ④녹음 ⑤자막 ⑥렌더는 범위 밖(①기획 확인 후 별도 사이클)
