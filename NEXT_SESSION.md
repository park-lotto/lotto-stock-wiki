# NEXT_SESSION — 다음 세션 인계 메모

> 이 파일이 있으면 세션 시작 즉시 읽는다. 읽은 후 내용을 요약 출력하고 작업 이어가기.
> 마감 시 `/session-close` 또는 "마감해줘" 로 자동 갱신.

---

## 📍 마지막 세션 정보

- **날짜**: 2026-06-04
- **PC**: 집PC
- **세션 요약**: 회사PC 미완 작업 파악 + 멀티에이전트 영상팀 브레인스토밍 진행 중

---

## ✅ 완료된 것

| 항목 | 상태 |
|------|------|
| `scripts/yt_agents/` 6단계 파이프라인 (회사PC) | ✅ 코드 완성 |
| YT_AI S01~S08 씬 TSC 에러 수정 (회사PC) | ✅ 완료 |
| `crawl_hot_clips.py` Gemini Search 크롤러 | ✅ 완료 |
| CLAUDE.md 160줄로 축소 + rules 분리 | ✅ 완료 |
| `channel_pipeline/` 다채널 집계 파이프라인 | ✅ 코드 완성 |
| NEXT_SESSION.md + session-close 스킬 | ✅ 방금 생성 |

---

## ⏳ 미완료 — 다음 세션에서 할 것

### 1순위 — 브레인스토밍 완료 (멀티에이전트 영상팀)
```
현재: superpowers:brainstorming 스킬 3/7단계 (명확화 질문 단계)
목표: CEO + Research + Creative + Validation + Production 팀 설계
기존 scripts/yt_agents/ 파이프라인을 이 팀 구조로 통합
→ brainstorming → writing-plans → executing-plans 순서
```

### 2순위 — scripts/yt_agents/ end-to-end 검증
```
파이프라인 코드는 완성됐지만 새 영상 1개를 처음부터 끝까지 돌린 적 없음
python make_yt_video.py --mode step 으로 테스트 필요
YT_AI 씬 m4a 녹음 없음 → 먼저 녹음 후 Whisper 단계 검증
```

### 3순위 — channel_pipeline/ 실전 테스트
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
scripts/channel_pipeline/pipeline.py  ← 채널 집계 파이프라인
make_yt_video.py                      ← 영상 파이프라인 CLI
remotion-stock/src/agents/            ← 완성된 TSX 씬 파일들
```

---

## 💬 컨텍스트 메모

회사PC 세션 종료 문제: 마감 커밋 후에도 계속 작업해서 인계 내용이 불일치했음.
앞으로는 `/session-close` 로 마감 → NEXT_SESSION.md 갱신 → git push.
