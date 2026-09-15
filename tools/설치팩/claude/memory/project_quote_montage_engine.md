---
name: project_quote_montage_engine
description: 전문가 인용 몽타주 영상 — 여러 전문가 영상서 골든발언+화면자료 뽑아 내 나레이션으로 인용·종합하는 포맷. 엔진 스파이크 실데이터 검증 완료
metadata: 
  node_type: memory
  type: project
  originSessionId: c8e41a63-dbf6-4d06-b1f1-0d7c75458402
---

**전문가 인용 몽타주** — 신뢰 전문가 유튜브 영상들에서 골든 발언 + 화면 자료(리포트/차트)를 뽑아, 배경엔 캡처+리모션, 위엔 "이 사람은 이렇게 본다"는 내 나레이션으로 인용·종합하는 영상 포맷. 채널 70/20/10의 **20%(방법론 데모=관점 종합 능력)**, 키컨텐츠 간접홍보. 리딩 아님 → "나는 이렇게 본다" 시각 판매 [[project_service_direction]].

**설계**: `docs/superpowers/specs/2026-07-05-전문가인용몽타주-design.md` (8단계 파이프라인, C안=하이브리드[캡처+나레이션, 결정적순간만 원본클립]).
- 골든 루브릭: 필수3(주장 명확·근거 동반·입장 존재) 통과=골든, 가점3(구체성·화면근거·화자신뢰). 양비론·잡담 자동탈락.
- 수집 3계층: **T1 자료구동(화면에 리포트)🥇 > T2 트래픽스파이크(heatmap)🥈 > T3 루브릭통과🥉**.
- 억지 금지: 발언→클러스터→내러티브 **발생**(부과X), 갈리면 갈린다고 정직하게 [[feedback_briefing_source_citation]].

**엔진 스파이크 완료 (2026-07-05, feat/briefing-engine, subagent-driven 7태스크)**: `scripts/yt_agents/quote_extractor.py` + `tests/yt_agents/test_quote_extractor.py`(23 passed). URL+주제 → `quotes_candidates.json`. 실데이터 검증(삼프로TV 4.5h 6fehifjxOcs):
- **yt-dlp 자막 O** — 15332세그, 봇차단 없음(메모리 경고와 반대, 단1표본). `python -m yt_dlp`(PATH바이너리 아님, 모듈).
- **heatmap(T2) 0 buckets** — 4.5h 라이브엔 미제공 → T1+T3 폴백 실동작 확인.
- **프레임캡처 O** — `python -m yt_dlp -g` 스트림URL + ffmpeg `-ss` 앞배치 seek → 640x360 PNG, `call_video` 폴백 불필요. detect_visuals(Gemini비전) has_visual 판정 실동작.
- **골든품질 O** — 육안 8/8 주장+근거+입장 뚜렷. 15332세그는 chunk_segments(max_chars=8000)로 청킹→~40 Gemini콜.
- 교훈: to_mmss가 ≥1h에서 깨졌던 버그(270:00) 최종검수서 발견·수정 — 실타깃이 4.5h라 앞7분 스모크로 못잡음. extract() 오케스트레이터 무테스트가 원인 → 테스트 추가.

**인용 스튜디오 MVP 완료 (2026-07-05, subagent-driven 3태스크)**: 플랜 `docs/superpowers/plans/2026-07-05-인용스튜디오-MVP.md`.
- 엔진: `quote_extractor.extract_stream`(진행이벤트 제너레이터) + `parse_video_id`. 25 테스트.
- 서버: `dashboard/server.py` 3엔드포인트 — `GET /yt/quote-studio` · `POST /yt/quote_extract`(SSE, /yt/teardown 패턴) · `POST /yt/quote_save`(→out/quote_studio/<vid>.json, gitignore됨). 4 TestClient 테스트.
- 화면: `dashboard/quote_studio.html`(URL→SSE진행→후보카드 tier순+스탠스뱃지→체크픽→저장).
- ⚠️ **라이브 렌더 미관찰**(file://차단+로컬미사용 [[feedback_server_dashboard_only]]) → 정적/백엔드만 검증. 라이브 시각검증은 서버 배포 시(refs창고처럼 미배포).
- 최종검수 픽스: 클라 resp.ok+try/finally(무한로딩·버튼잠김 방지), esc `"` 이스케이프.
- **배포 완료 (2026-07-05)**: feat/briefing-engine이 main과 646파일 갈라져(동시세션 다른브랜치+main미머지) 통짜머지 위험 → **임시 worktree에서 스튜디오 파일만 main에 포팅**(커밋 04328e90) → 서버 pull+restart. SSH키=`C:\Users\TheRose\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem` ubuntu@3.39.179.148, 서버 `/home/ubuntu/lotto-stock-wiki` main구동 systemd `stockbrain` :8090. 엔진 서버서 import OK 확인. 로그인벽 뒤라 시각확인은 사용자(admin/DASH_PASS).
- **교훈**: main엔 clip_teardown 없음 → import블록 all-or-nothing이 _qe까지 죽임(최종검수 #3이 실제 터짐). quote_extractor를 **독립 try/except**로 분리해 해결. 브랜치 이식 시 의존모듈 존재여부 먼저 확인.
- **서버 봇차단 해결 (2026-07-05, 커밋 c6680181)**: 서버(데이터센터 IP)는 **yt-dlp도 youtube_transcript_api도 다 봇차단**("Sign in to confirm you're not a bot"/RequestBlocked). YouTube Data API키로도 남영상 자막 불가(소유자OAuth 필요). → **해결 = Gemini `call_video`(영상 직접 시청, Gemini서버가 fetch하니 IP무관)**. `extract_stream`에 yt-dlp 실패시 call_video 폴백 추가(로컬=yt-dlp, 서버=call_video 자동전환). Gemini가 화면도 봐서 has_visual(T1) 직접 판별 = 프레임캡처보다 나음. **모델은 `gemini-2.5-flash` 필수** — `gemini-3-flash-preview`/`flash-latest`는 영상입력시 503 UNAVAILABLE 지속(프리뷰 붐빔), 18키도 소용없음(503은 모델과부하라 키무관). 서버 venv=`/home/ubuntu/venv`에 yt-dlp/youtube-transcript-api 설치함. E2E검증: 현대차영상→골든8개(약세, has_visual T1) 실제추출 성공.

**미구현(다음)**: 인용 픽 이후 → 클러스터/스토리 발생 → 씬빌드(hyperframes/Remotion 어댑터). 캡처 스트립·클립선택(스튜디오 phase2). refs창고 [[project_yt_reference_warehouse]] 합류는 나중. 서버 배포 후 라이브 E2E.
