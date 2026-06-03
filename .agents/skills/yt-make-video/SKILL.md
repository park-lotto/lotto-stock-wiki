---
name: yt-make-video
description: Use when making any YouTube video from scratch — orchestrates the full pipeline from topic research to final render. Entry point for all video production.
metadata:
  tags: youtube, 영상제작, 파이프라인, 기획, 대본, remotion, 편집
---

# yt-make-video — 영상 제작 전체 파이프라인

## 명령어

- `/make-video` / `/영상만들자` / "영상 만들자"

---

## 전체 파이프라인

```
[사용자] 아이디어 OR "영상 만들자"
    ↓
[STEP 1] yt-content-research  ← 소재 탐색 + 이슈 타이밍 체크
    ↓ 주제 + 각도 확정
[STEP 2] yt-deep-research     ← YouTube 유사영상 + 기사 + 데이터 + 비교/응용/예시 수집
    ↓ 리서치 브리프
[STEP 3] yt-planner           ← 씬 구성 + 기획서 (리서치 브리프 기반)
    ↓ 기획서 컨펌 (사용자 확인)
[STEP 4] yt-script-writer     ← 대본 (리서치 브리프 + wiki 데이터 활용)
    ↓
[STEP 4] Remotion 씬 작성     ← videoagent-director or 직접 TSX
    ↓
[STEP 5] 실화면 촬영           ← 사용자 직접 (AI 불가)
    ↓
[STEP 6] 녹음                 ← 사용자 직접 (AI 불가)
    ↓
[STEP 7] yt-editor            ← Whisper 싱크 + 렌더
    ↓
[STEP 8] yt-publisher         ← YouTube 업로드 + 텔레그램 공지
```

**사용자 개입**: STEP 2 컨펌, STEP 5 실화면 촬영, STEP 6 녹음 (총 3회)

---

## 각 STEP별 사용 스킬

| STEP | 스킬 | 도구 |
|------|------|------|
| 1. 소재 탐색 | `yt-content-research` | WebSearch + gstack:browse + visual-companion |
| 2. 씬 구성 | `yt-planner` | superpowers:brainstorming |
| 3. 대본 | `yt-script-writer` | wiki 참조 |
| 4. Remotion | `remotion-best-practices` + `videoagent-director` | TSX 작성 |
| 5. 실화면 | — | 사용자 직접 |
| 6. 녹음 | — | 사용자 직접 |
| 7. 편집 | `yt-editor` | Whisper + remotion render |
| 8. 배포 | `yt-publisher` | YouTube API + 텔레그램 |

---

## 이슈 타이밍 판단 (전체 파이프라인에 영향)

영상 종류별 제작 가능 시간:

| 영상 유형 | 제작 가능 기간 | 이유 |
|---------|-------------|------|
| 이슈형 (젠슨황, 공시, 이벤트) | 이슈 당일 ~ +2일 | 이후 조회수 급감 |
| 트렌드형 (피지컬AI, 로봇 섹터) | 2주 이내 | 검색량 유지되는 기간 |
| 교육형 (수급빈집 원리, 시스템 소개) | 상시 | 이슈 무관 |
| 종목 분석형 | 이슈 전 D-3 이상 미리 준비 | 이슈 터지는 날 업로드 |

> **원칙**: 이슈가 터진 날 = 업로드 해야 하는 날.  
> 이슈 터지고 3일 지나면 유사 영상이 이미 100개 — 무조건 차별화 각도 필요.

---

## 재사용 가능한 Remotion 컴포넌트

`remotion-stock/src/agents/` 에 완성된 컴포넌트:

| 컴포넌트 | 용도 |
|---------|------|
| `AG_S01_Hook_done.tsx` | 훅 씬 (타임라인 + 어두운 배경) |
| `AG_S02_Empathy_done.tsx` | 공감 씬 (3분할 실화면) |
| `AG_S03_Declaration_done.tsx` | 선언 씬 (에이전트 카드) |
| `AG_S04_*_done.tsx` | 데모 씬 (터미널, 스코어카드, 브리핑) |
| `AG_S05_Climax_done.tsx` | 클라이맥스 (24시간 타임라인) |
| `AG_S06_Awareness_done.tsx` | 자각 씬 |
| `AG_S07_Tease_done.tsx` | 여운 씬 |
| `AG_S08_CTA_done.tsx` | CTA 씬 |

신규 영상은 위 컴포넌트를 참고해서 변형 — 처음부터 만들지 말 것.

---

## 진행 중인 영상 현황

| 영상 | 상태 | 남은 작업 |
|------|------|---------|
| 에이전트직원 10명 | Remotion ✅ 대본 ✅ | 실화면 촬영 + 녹음 → yt-editor |
| SpaceX IPO | 대본 ⚠️(씬7·9 빈칸) | 수급 데이터 → 대본 완성 → Remotion → 촬영 |

---

## 완료 후 로그

```
wiki/log.md 기록:
[날짜] 영상 제작 완료 — {제목} | 조회수 목표: {N}만 | 업로드: {YouTube URL}
```
