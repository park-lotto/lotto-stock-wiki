# NEXT_SESSION — 다음 세션 인계 메모

> 이 파일이 있으면 세션 시작 즉시 읽는다. 읽은 후 내용을 요약 출력하고 작업 이어가기.
> 마감 시 `마감해줘` 로 자동 갱신.

---

## 📍 마지막 세션 정보

- **날짜**: 2026-06-04
- **PC**: 집PC
- **세션 요약**: 회사PC 미완 작업 파악 + NEXT_SESSION/session-close 시스템 구축 + 멀티에이전트 영상팀 설계 브리핑까지

---

## ✅ 완료된 것

| 항목 | 상태 |
|------|------|
| `scripts/yt_agents/` 6단계 파이프라인 (회사PC) | ✅ 코드 완성 |
| YT_AI S01~S08 씬 TSC 에러 수정 (회사PC) | ✅ 완료 |
| `crawl_hot_clips.py` Gemini Search 크롤러 | ✅ 완료 |
| `channel_pipeline/` 다채널 집계 파이프라인 | ✅ 코드 완성 |
| CLAUDE.md 마감 루틴 추가 | ✅ 완료 |
| NEXT_SESSION.md 시스템 구축 | ✅ 완료 |

---

## ⏳ 다음 세션 — 1순위: 멀티에이전트 영상팀 설계

### 설계 대상

```
CEO 에이전트
├── Research Team    → 소재 수집 (텔레그램·블로그·리포트·유튜브 요약)
├── Creative Team    → 기획·대본·Remotion TSX 생성
├── Validation Team  → QC 검수 (기획/대본/연출 품질)
└── Production Team  → Whisper 싱크 → 렌더 → 배포
```

기존 `scripts/yt_agents/` 6단계를 이 팀 구조로 재편·확장하는 것.

### 결정해야 할 첫 번째 질문

> 기존 코드와의 관계를 먼저 결정해야 함:
> - A. 래퍼: 기존 코드 그대로, CEO 오케스트레이터만 위에 얹기
> - B. 통합: 기존 6단계를 팀 구조 안으로 흡수해서 재편
> - C. 검증 먼저: 팀 설계 전에 기존 파이프라인 end-to-end 검증 먼저

### 진행 방법 (회사PC에서)

```
superpowers:brainstorming 스킬로 시작
→ 위 A/B/C 방향 결정
→ writing-plans
→ executing-plans
```

---

## 2순위 — scripts/yt_agents/ end-to-end 검증

```
python make_yt_video.py --mode step 으로 새 영상 1개 처음부터 끝까지 테스트
YT_AI 씬 m4a 녹음 없음 → 먼저 녹음 후 Whisper 단계 검증
```

## 3순위 — channel_pipeline/ 실전 테스트

```
raw/inbox/ 에 파일 넣고 pipeline.py 실행 테스트
트리거: "채널파이프라인 이어서"
```

---

## 🗂 관련 파일 경로

```
scripts/yt_agents/pipeline.py         ← 영상 파이프라인 진입점
scripts/yt_agents/agent_plan.py       ← 기획 에이전트 (Gemini, QC=7/10)
scripts/yt_agents/agent_script.py     ← 대본 에이전트 (Gemini, QC=8/10)
scripts/yt_agents/agent_remotion.py   ← TSX 자동생성 + tsc 자동수정
scripts/yt_agents/agent_whisper.py    ← Whisper 자막 싱크
scripts/yt_agents/agent_render.py     ← Remotion 렌더링
make_yt_video.py                      ← 영상 파이프라인 CLI
scripts/channel_pipeline/pipeline.py  ← 채널 집계 파이프라인
remotion-stock/src/agents/            ← 완성된 TSX 씬 파일들
```
