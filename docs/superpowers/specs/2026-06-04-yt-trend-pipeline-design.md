# YT Trend Pipeline — Design Spec

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 주식 키워드 급상승 YouTube 영상 Top 20 수집 → Gemini 딥리서치 → 영상 심층 분석 → 소재 추출 → 대본 초안 자동 생성

**Architecture:** 5단계 파이프라인. 각 단계 결과를 `raw/yt_trend/{날짜}/` 에 JSON/MD로 저장해 중간 재실행 지원. Step 2는 `@rlabs-inc/gemini-mcp` Claude Code 스킬로, Steps 1/3/4는 Python, Step 5는 Claude 직접 작성.

**Tech Stack:** YouTube Data API v3, youtube-transcript-api, Gemini MCP (`@rlabs-inc/gemini-mcp`), Gemini 2.5 Flash (Python), Claude Sonnet (대본)

---

## 파일 구조

```
scripts/yt_trend/
  step1_fetch.py          ← YouTube API → 급상승 Top 20 수집
  step3_analyze.py        ← 자막 추출 + Gemini 분석
  step4_extract.py        ← 소재 JSON 추출

.agents/skills/yt-trend   ← Claude Code 스킬 (Step 2, 5 포함 오케스트레이터)

raw/yt_trend/{날짜}/
  step1_videos.json       ← Top 20 영상 목록
  step2_research.md       ← Gemini 딥리서치 결과
  step3_analysis.json     ← 영상별 훅/구성/댓글 분석
  step4_ideas.json        ← 소재 후보 3개
  step5_draft.md          ← 최종 대본 초안 (S1~S8)
```

---

## Step 1 — YouTube API 수집 (`step1_fetch.py`)

- 키워드 6개: `["주식 급등", "급상승 종목", "수급 터진", "반도체 주식", "오늘 주식", "종목 추천"]`
- 파라미터: `publishedAfter=48시간전`, `order=viewCount`, `regionCode=KR`, `videoDuration=medium`
- 각 키워드당 최대 10개 → 중복 제거 → 조회수 상위 20개
- 출력: `step1_videos.json`

```json
[
  {
    "video_id": "xxx",
    "title": "...",
    "channel": "...",
    "views": 120000,
    "published_at": "2026-06-04T08:00:00Z",
    "url": "https://youtu.be/xxx"
  }
]
```

## Step 2 — Gemini 딥리서치 (Claude Code 스킬 내 MCP 호출)

- 입력: step1_videos.json 의 제목/키워드 목록
- MCP 도구: `mcp__gemini__*` (gemini 딥리서치 명령)
- 프롬프트: "왜 이 키워드들이 오늘 동시에 급상승하는가? 시장 배경, 이슈, 섹터 흐름 분석"
- 출력: `step2_research.md` (1~2페이지 텍스트)

## Step 3 — 영상 심층 분석 (`step3_analyze.py`)

- 입력: step1_videos.json 중 조회수 Top 5
- `youtube-transcript-api`로 자막 추출 (실패 시 해당 영상 skip)
- YouTube Data API로 Top 댓글 10개 수집
- Gemini 2.5 Flash로 영상별 분석:
  - 훅: 첫 30초 구조 (질문형/충격형/공감형)
  - 구성: 전체 흐름 3줄 요약
  - 댓글 반응: 핵심 감정/반응 키워드
- 출력: `step3_analysis.json`

```json
[
  {
    "video_id": "xxx",
    "hook_type": "질문형",
    "hook_text": "첫 30초 내용",
    "structure": "전체 흐름 3줄",
    "comment_reaction": "댓글 반응 요약"
  }
]
```

## Step 4 — 소재 추출 (`step4_extract.py`)

- 입력: step2_research.md + step3_analysis.json
- Gemini 2.5 Flash로 우리 채널 70/20/10 원칙 기준 소재 3개 추출
- 출력: `step4_ideas.json`

```json
[
  {
    "rank": 1,
    "title_hook": "제목 방향",
    "angle": "영상 각도",
    "key_points": ["핵심 포인트 3개"],
    "why_viral": "왜 터질 것 같은가"
  }
]
```

## Step 5 — 대본 초안 (Claude 직접 작성, 스킬 내)

- 입력: step4_ideas.json rank 1 소재
- 출력:
  - 제목 후보 5개
  - 썸네일 컨셉 1개
  - S1~S8 대본 초안 (8~10분, 70/20/10 원칙)
- 저장: `step5_draft.md`

---

## 스킬 구조 (`.agents/skills/yt-trend`)

```
yt-trend 실행
  1. Bash → python scripts/yt_trend/step1_fetch.py --date {오늘}
  2. gemini MCP 딥리서치 호출 → step2_research.md 저장
  3. Bash → python scripts/yt_trend/step3_analyze.py --date {오늘}
  4. Bash → python scripts/yt_trend/step4_extract.py --date {오늘}
  5. Claude 직접 → step5_draft.md 작성
```

`--from-step N` 옵션으로 특정 단계부터 재실행 가능 (이미 완료된 단계 파일 있으면 로드).

---

## 오류 처리

- Step 1: API 할당량 초과 시 에러 메시지 출력 후 중단
- Step 3: 자막 추출 실패 영상은 skip, 최소 2개 이상 성공 필요
- 각 step: 출력 파일 이미 존재하면 skip (재실행 방지)
