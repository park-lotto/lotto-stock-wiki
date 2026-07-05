# NEXT_SESSION — 전문가 인용 몽타주 (2026-07-05, 집PC)

## 한 줄
전문가 유튜브 영상 → 골든 발언+장면 자동 수집 → (앞으로) 스토리로 엮어 몽타주 영상.
채널 20%(방법론 데모=관점 종합) 콘텐츠. 리딩 아님, "나는 이렇게 본다" 시각 판매.

## 지금 어디까지 됐나 (✅ 라이브)

**설계**: `docs/superpowers/specs/2026-07-05-전문가인용몽타주-design.md` (8단계, 골든루브릭, T1>T2>T3, 억지금지)

**stage 1 — 수집·해체 엔진** ✅ (`scripts/yt_agents/quote_extractor.py`)
- URL+주제 → 골든 발언 후보(스탠스·근거·tier·화면근거). 29테스트.
- 골든 규칙: 필수3(주장·근거·입장) + 가점(구체성·화면근거).

**stage 1 웹 — 인용 스튜디오** ✅ **서버 라이브**
- https://stockbrain1.duckdns.org/yt/quote-studio (admin/1234, /market 로그인과 동일)
- URL→진행률(SSE)→골든카드(tier순·스탠스뱃지)→체크픽→저장
- 저장시 `<vid>.json` 브라우저 자동다운로드 + collect_scenes 명령 안내

**서버 봇차단 해결** ✅ (핵심)
- 서버(데이터센터IP)는 yt-dlp/youtube_transcript_api 다 봇차단. YouTube Data API키로도 남영상 자막 불가.
- → **Gemini `call_video`(영상 직접시청) 폴백**. 로컬=yt-dlp, 서버=call_video 자동전환.
- **모델 = `gemini-2.5-flash` 필수** (gemini-3-flash-preview/flash-latest는 영상입력시 503 지속).
- E2E검증: 현대차영상→골든8개(약세/자료구동 T1) 실제추출.

**stage 1.5 — 장면 수집** ✅ (`scripts/yt_agents/collect_scenes.py`, 로컬전용)
- `python scripts/yt_agents/collect_scenes.py <vid>.json` → 발언 ts마다 프레임PNG(배경)+클립MP4(핵심).
- yt-dlp --download-sections로 구간만 받음(긴영상 효율). 실측 2/2 생성확인.
- 서버는 봇차단+ffmpeg없어 로컬 전용(로컬은 둘다 OK).

**git 위생** ✅: atoms.db·상태json·pyc 추적해제+gitignore (dirty트리·바이너리충돌 해소).

## 미완료 (다음 — 사장님이 "차례대로" 하자 함)

**② stage 2 — 스토리 발생** ⬜ (설계 시작, 결정 대기)
- 여러 영상 인용풀 → stance/근거 클러스터 → 관점지도 → 내러티브 뼈대 → 나레이션 브릿지.
- **미결 질문(사장님 답 대기)**: stage 2 산출물이 A(설계도만)/B(설계도+나레이션대본, 추천)/C(설계도+관점지도 시각화)?
- 억지금지: 대본도 인용에서 발생한 것만.
- 참고: story_builder.py(다른세션 작업)는 커밋안돼 사라짐 → 새로 만들기.

**③ stage 3 — 씬 빌드** ⬜: quotes.json+장면 → hyperframes/Remotion 영상.

**UX 정리** ⬜: 세그먼트제한 칸 자동기본값/숨김, 주제 선택사항 (지금은 수동입력).

**브랜치 정리** ⬜ (⚠️): main(배포)과 feat/briefing-engine이 646파일 갈라짐. 동시세션이 main에 계속 커밋중이라 통합은 조용한때 조율해서. atoms.db 추적해제는 이미 함.

## 이어가는 법 (호출)
- 새 세션: 이 파일 자동으로 읽힘. 또는 "인용 몽타주 이어서" 라고 말하면 됨.
- 메모리 `project_quote_montage_engine.md`에 상세(모델·봇차단·배포 다 기록됨).
- 서버접속: `ssh -i "C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem" ubuntu@3.39.179.148`
- 배포: worktree(main)에서 수정→push→서버 `git pull [&& sudo systemctl restart stockbrain]`. 서버 venv=`/home/ubuntu/venv`.
- 로컬 테스트: `python -m pytest tests/yt_agents/test_quote_extractor.py -v` (29 passed 기준).

## 바로 써보기
1. https://stockbrain1.duckdns.org/yt/quote-studio (admin/1234)
2. 전문가영상 URL + 주제 → 추출 → 픽 → 저장(json 다운로드됨)
3. 로컬: `python scripts/yt_agents/collect_scenes.py <다운로드된 vid.json>` → 장면 수집
