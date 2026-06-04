# YT Trend Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** YouTube 급상승 주식 키워드 Top 20 수집 → Gemini 딥리서치 → 영상 심층 분석 → 소재 추출 → 대본 초안 자동 생성 5단계 파이프라인

**Architecture:** Python 스크립트 3개(Steps 1/3/4) + Claude Code 스킬 1개(Steps 2/5 포함 오케스트레이터). 각 단계 결과를 `raw/yt_trend/{날짜}/` 에 JSON/MD로 저장. 이미 완료된 단계는 자동 skip.

**Tech Stack:** `google-api-python-client` (YouTube Data API v3), `youtube-transcript-api 1.2.4`, `google-generativeai 0.8.6` (Gemini 2.0 Flash), `@rlabs-inc/gemini-mcp` (딥리서치), Claude Sonnet (대본). Python 3.14. 전부 이미 설치 완료.

---

## 파일 구조

```
scripts/yt_trend/
  step1_fetch.py          ← YouTube API → 급상승 Top 20 수집
  step3_analyze.py        ← 자막 추출 + Gemini 분석
  step4_extract.py        ← 소재 JSON 추출

.agents/skills/yt-trend/
  SKILL.md                ← Claude Code 스킬 (Step 2 MCP + Step 5 대본 오케스트레이터)

raw/yt_trend/{날짜}/
  step1_videos.json
  step2_research.md
  step3_analysis.json
  step4_ideas.json
  step5_draft.md
```

---

## Task 0: 디렉토리 구조 생성

**Files:**
- Create: `scripts/yt_trend/` 디렉토리
- Create: `.agents/skills/yt-trend/` 디렉토리

- [ ] **Step 1: 디렉토리 생성**

```powershell
New-Item -ItemType Directory -Force "scripts\yt_trend"
New-Item -ItemType Directory -Force ".agents\skills\yt-trend"
New-Item -ItemType Directory -Force "raw\yt_trend"
```

- [ ] **Step 2: 확인**

```powershell
ls scripts\yt_trend; ls .agents\skills\yt-trend; ls raw\yt_trend
```

Expected: 세 폴더 모두 존재

- [ ] **Step 3: Commit**

```bash
git add scripts/yt_trend .agents/skills/yt-trend raw/yt_trend
git commit -m "feat: yt-trend 파이프라인 디렉토리 구조 생성"
```

---

## Task 1: step1_fetch.py — YouTube API Top 20 수집

**Files:**
- Create: `scripts/yt_trend/step1_fetch.py`

- [ ] **Step 1: 파일 작성**

`scripts/yt_trend/step1_fetch.py`:

```python
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
BASE_DIR = Path(__file__).parent.parent.parent / "raw" / "yt_trend"

KEYWORDS = ["주식 급등", "급상승 종목", "수급 터진", "반도체 주식", "오늘 주식", "종목 추천"]


def _published_after():
    dt = datetime.now(timezone.utc) - timedelta(hours=48)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _search_videos(keyword):
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "regionCode": "KR",
        "relevanceLanguage": "ko",
        "order": "viewCount",
        "publishedAfter": _published_after(),
        "videoDuration": "medium",
        "maxResults": 10,
        "key": API_KEY,
    }
    r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params)
    r.raise_for_status()
    return r.json().get("items", [])


def _get_stats(video_ids):
    params = {
        "part": "statistics,snippet",
        "id": ",".join(video_ids),
        "key": API_KEY,
    }
    r = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params)
    r.raise_for_status()
    return r.json().get("items", [])


def run(date_str: str):
    if not API_KEY:
        print("❌ YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)

    out_dir = BASE_DIR / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "step1_videos.json"

    if out_file.exists():
        print(f"⏭  step1 already done: {out_file}")
        return

    seen: set = set()
    candidates = []

    for kw in KEYWORDS:
        items = _search_videos(kw)
        ids = [i["id"]["videoId"] for i in items if i["id"].get("videoId") and i["id"]["videoId"] not in seen]
        for vid_id in ids:
            seen.add(vid_id)
        if not ids:
            continue
        for item in _get_stats(ids):
            candidates.append({
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "views": int(item["statistics"].get("viewCount", 0)),
                "published_at": item["snippet"]["publishedAt"],
                "url": f"https://youtu.be/{item['id']}",
                "keyword": kw,
            })

    top20 = sorted(candidates, key=lambda x: x["views"], reverse=True)[:20]

    if not top20:
        print("❌ 수집된 영상이 없습니다. 키워드 또는 API 키를 확인하세요.")
        sys.exit(1)

    out_file.write_text(json.dumps(top20, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ step1 done: {len(top20)}개 → {out_file}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = p.parse_args()
    run(args.date)
```

- [ ] **Step 2: 실행 테스트**

```bash
python scripts/yt_trend/step1_fetch.py --date 2026-06-04
```

Expected: `raw/yt_trend/2026-06-04/step1_videos.json` 생성, 콘솔에 "✅ step1 done: 20개"

- [ ] **Step 3: skip 테스트 (재실행 시 skip 확인)**

```bash
python scripts/yt_trend/step1_fetch.py --date 2026-06-04
```

Expected: "⏭  step1 already done" 출력 후 종료

- [ ] **Step 4: Commit**

```bash
git add scripts/yt_trend/step1_fetch.py
git commit -m "feat: yt-trend step1 YouTube API Top20 수집"
```

---

## Task 2: step3_analyze.py — 자막 추출 + Gemini 영상 분석

**Files:**
- Create: `scripts/yt_trend/step3_analyze.py`

- [ ] **Step 1: 파일 작성**

`scripts/yt_trend/step3_analyze.py`:

```python
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

sys.stdout.reconfigure(encoding="utf-8")

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
YOUTUBE_KEY = os.environ.get("YOUTUBE_API_KEY", "")
BASE_DIR = Path(__file__).parent.parent.parent / "raw" / "yt_trend"


def _get_transcript(video_id: str):
    """Returns (hook_text, full_text) or (None, None) on failure."""
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "ko-KR"])
        hook = " ".join(s["text"] for s in segments if s["start"] < 30)
        full = " ".join(s["text"] for s in segments)
        return hook, full
    except (NoTranscriptFound, TranscriptsDisabled):
        return None, None


def _get_comments(video_id: str) -> list[str]:
    params = {
        "part": "snippet",
        "videoId": video_id,
        "order": "relevance",
        "maxResults": 10,
        "key": YOUTUBE_KEY,
    }
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/commentThreads", params=params, timeout=10)
        items = r.json().get("items", [])
        return [i["snippet"]["topLevelComment"]["snippet"]["textDisplay"] for i in items]
    except Exception:
        return []


def _analyze(model, title: str, hook: str, full: str, comments: list[str]) -> dict:
    comments_str = "\n".join(f"- {c}" for c in comments[:10])
    prompt = f"""다음 YouTube 영상을 분석해줘.

제목: {title}

훅 (첫 30초 자막):
{hook}

전체 자막 (앞부분):
{full[:2000]}

댓글 Top 10:
{comments_str}

아래 JSON 형식으로만 응답해줘 (마크다운 코드블록 없이):
{{
  "hook_type": "질문형/충격형/공감형/정보형 중 하나",
  "hook_text": "첫 30초 핵심 문장 1개",
  "structure": "전체 흐름 3줄 요약",
  "comment_reaction": "댓글 반응 핵심 키워드 3개"
}}"""
    resp = model.generate_content(prompt)
    text = resp.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"hook_type": "분석실패", "hook_text": hook[:80], "structure": "", "comment_reaction": ""}


def run(date_str: str):
    if not GEMINI_KEY:
        print("❌ GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)

    out_dir = BASE_DIR / date_str
    step1_file = out_dir / "step1_videos.json"
    out_file = out_dir / "step3_analysis.json"

    if out_file.exists():
        print(f"⏭  step3 already done: {out_file}")
        return

    if not step1_file.exists():
        print(f"❌ step1 결과 없음: {step1_file} — step1 먼저 실행하세요.")
        sys.exit(1)

    videos = json.loads(step1_file.read_text(encoding="utf-8"))
    top5 = videos[:5]

    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    results = []
    for v in top5:
        vid_id = v["video_id"]
        hook, full = _get_transcript(vid_id)
        if hook is None:
            print(f"⏭  자막 없음: {vid_id} ({v['title'][:30]})")
            continue
        comments = _get_comments(vid_id)
        analysis = _analyze(model, v["title"], hook, full, comments)
        analysis["video_id"] = vid_id
        analysis["title"] = v["title"]
        analysis["views"] = v["views"]
        results.append(analysis)
        print(f"✅ 분석: {v['title'][:40]}")

    if len(results) < 2:
        print(f"❌ 자막 추출 성공 {len(results)}개 — 최소 2개 필요. 종료.")
        sys.exit(1)

    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ step3 done: {len(results)}개 → {out_file}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = p.parse_args()
    run(args.date)
```

- [ ] **Step 2: 실행 테스트 (step1 결과 있는 날짜로)**

```bash
python scripts/yt_trend/step3_analyze.py --date 2026-06-04
```

Expected: `raw/yt_trend/2026-06-04/step3_analysis.json` 생성

- [ ] **Step 3: step1 없을 때 에러 확인**

```bash
python scripts/yt_trend/step3_analyze.py --date 1999-01-01
```

Expected: "❌ step1 결과 없음" 출력 후 exit(1)

- [ ] **Step 4: Commit**

```bash
git add scripts/yt_trend/step3_analyze.py
git commit -m "feat: yt-trend step3 자막추출+Gemini 영상 분석"
```

---

## Task 3: step4_extract.py — 소재 후보 3개 추출

**Files:**
- Create: `scripts/yt_trend/step4_extract.py`

- [ ] **Step 1: 파일 작성**

`scripts/yt_trend/step4_extract.py`:

```python
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import google.generativeai as genai

sys.stdout.reconfigure(encoding="utf-8")

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
BASE_DIR = Path(__file__).parent.parent.parent / "raw" / "yt_trend"

CHANNEL_NAME = "로또의 스탁브레인"


def run(date_str: str):
    if not GEMINI_KEY:
        print("❌ GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)

    out_dir = BASE_DIR / date_str
    step2_file = out_dir / "step2_research.md"
    step3_file = out_dir / "step3_analysis.json"
    out_file = out_dir / "step4_ideas.json"

    if out_file.exists():
        print(f"⏭  step4 already done: {out_file}")
        return

    missing = [str(f) for f in [step2_file, step3_file] if not f.exists()]
    if missing:
        print(f"❌ 누락 파일: {missing}")
        sys.exit(1)

    research = step2_file.read_text(encoding="utf-8")
    analysis = json.loads(step3_file.read_text(encoding="utf-8"))
    analysis_str = json.dumps(analysis, ensure_ascii=False, indent=2)

    prompt = f"""채널명: {CHANNEL_NAME}
채널 원칙: 70/20/10 (70% 순수정보, 20% 간접노출 방법론, 10% CTA는 S8 씬에만)

[시장 배경 리서치]
{research}

[경쟁 영상 분석 결과]
{analysis_str}

위 데이터를 기반으로 우리 채널에서 만들 영상 소재 3개를 추출해줘.
조건:
- 경쟁 영상과 각도가 다른 신선한 접근
- 주식 투자자에게 실질적 도움이 되는 정보
- 지금 트렌드에 올라탈 수 있는 타이밍

아래 JSON 배열로만 응답해줘 (마크다운 코드블록 없이):
[
  {{
    "rank": 1,
    "title_hook": "제목 방향 (훅 포함, 30자 이내)",
    "angle": "우리 채널만의 각도 (2줄 이내)",
    "key_points": ["핵심 포인트1", "핵심 포인트2", "핵심 포인트3"],
    "why_viral": "왜 터질 것 같은가 (1줄)"
  }},
  ...
]"""

    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
    resp = model.generate_content(prompt)

    text = resp.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        ideas = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"❌ Gemini 응답 파싱 실패: {e}\n원문:\n{resp.text[:500]}")
        sys.exit(1)

    out_file.write_text(json.dumps(ideas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ step4 done: {len(ideas)}개 소재 → {out_file}")
    for idea in ideas:
        print(f"  {idea['rank']}. {idea['title_hook']} — {idea['why_viral']}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = p.parse_args()
    run(args.date)
```

- [ ] **Step 2: 실행 테스트 (step2/step3 결과 있는 날짜로)**

```bash
python scripts/yt_trend/step4_extract.py --date 2026-06-04
```

Expected: `raw/yt_trend/2026-06-04/step4_ideas.json` 생성, 3개 소재 출력

- [ ] **Step 3: 누락 파일 에러 확인**

```bash
python scripts/yt_trend/step4_extract.py --date 1999-01-01
```

Expected: "❌ 누락 파일:" 출력 후 exit(1)

- [ ] **Step 4: Commit**

```bash
git add scripts/yt_trend/step4_extract.py
git commit -m "feat: yt-trend step4 Gemini 소재 추출"
```

---

## Task 4: .agents/skills/yt-trend/SKILL.md — 오케스트레이터 스킬

**Files:**
- Create: `.agents/skills/yt-trend/SKILL.md`

Step 2 (Gemini MCP 딥리서치) 와 Step 5 (Claude 대본 작성) 를 포함하는 전체 오케스트레이터.

- [ ] **Step 1: SKILL.md 작성**

`.agents/skills/yt-trend/SKILL.md`:

```markdown
---
name: yt-trend
description: YouTube 급상승 키워드 기반 영상 소재 발굴 → 대본 초안 자동 생성 파이프라인. 5단계: YouTube Top20 수집 → Gemini 딥리서치 → 자막 분석 → 소재 추출 → 대본 초안 S1~S8
metadata:
  tags: youtube, trend, 소재발굴, 파이프라인, gemini
---

# yt-trend

## 언제 실행하나

"오늘 유튜브 트렌드로 영상 소재 뽑아줘" / "YT 트렌드 파이프라인" / "급상승 키워드로 영상 기획해줘"

## 환경 변수 확인

실행 전 아래 두 변수가 설정되어 있는지 확인한다. 없으면 즉시 중단하고 설정 방법 안내.

- `YOUTUBE_API_KEY` — YouTube Data API v3
- `GEMINI_API_KEY` — Gemini MCP + Python 스크립트 공용

---

## Step 1 — YouTube API Top 20 수집

```bash
python scripts/yt_trend/step1_fetch.py --date {오늘 날짜 YYYY-MM-DD}
```

성공 조건: `raw/yt_trend/{날짜}/step1_videos.json` 존재, 1개 이상
이미 파일 존재: 자동 skip

---

## Step 2 — Gemini MCP 딥리서치

step1_videos.json 을 읽어 제목 상위 10개 추출 후 Gemini MCP 호출.

**입력 준비:**

`raw/yt_trend/{날짜}/step1_videos.json` 에서 title 필드 상위 10개를 추출해 아래 프롬프트에 삽입.

**Gemini MCP 프롬프트:**

```
다음은 오늘 한국 주식 YouTube에서 급상승 중인 영상 제목들이다.

{제목 목록 — 각 줄에 번호. 제목}

분석 요청:
1. 공통적으로 부각되는 주제/테마는 무엇인가?
2. 왜 오늘 이 키워드들이 동시에 급상승하는가? (시장 배경, 이슈, 섹터 흐름)
3. 이 트렌드는 며칠이나 지속될 것으로 보이나? 근거는?
4. 투자자들이 가장 궁금해하는 핵심 질문은 무엇인가?

한국어로 1~2페이지 분량으로 작성.
```

**Gemini MCP 도구:** `mcp__gemini__*` 중 딥리서치/생성 도구 사용

**저장:** Gemini 응답 전체를 `raw/yt_trend/{날짜}/step2_research.md` 에 저장 (Write 도구)

이미 파일 존재: skip

---

## Step 3 — 자막 추출 + Gemini 영상 분석

```bash
python scripts/yt_trend/step3_analyze.py --date {오늘 날짜 YYYY-MM-DD}
```

성공 조건: `raw/yt_trend/{날짜}/step3_analysis.json` 존재, 2개 이상 분석 결과
이미 파일 존재: 자동 skip

---

## Step 4 — 소재 추출

```bash
python scripts/yt_trend/step4_extract.py --date {오늘 날짜 YYYY-MM-DD}
```

성공 조건: `raw/yt_trend/{날짜}/step4_ideas.json` 존재, 3개 소재
이미 파일 존재: 자동 skip

---

## Step 5 — 대본 초안 (Claude 직접 작성)

`raw/yt_trend/{날짜}/step4_ideas.json` 에서 rank 1 소재를 읽어 아래 형식으로 대본 초안 작성.

**70/20/10 원칙 엄수:**
- S1~S6: 순수 정보 (서비스명 일절 금지)
- S7: 간접 노출 ("나는 이렇게 한다" 방법론)
- S8: CTA 단 한 번 (서비스 언급 유일 허용 씬)

**출력 형식:**

```markdown
# {소재 제목}
> 생성일: {날짜} | 출처: yt-trend 파이프라인

## 제목 후보 5개
1. 
2. 
3. 
4. 
5. 

## 썸네일 컨셉
- 메인 텍스트: 
- 배경/이미지: 
- 서브 텍스트: 

## 대본

### S1 — 훅 (0~30초)
[30초 안에 "왜 봐야 하나"를 증명하는 충격/질문/역설 오프닝]

### S2 — 문제 제기 (30초~1:30)
[시청자가 공감하는 문제 상황 + 오늘 영상의 핵심 약속]

### S3 — 핵심 인사이트 1 (1:30~3:00)
[첫 번째 핵심 포인트. 데이터·사례 포함]

### S4 — 핵심 인사이트 2 (3:00~5:00)
[두 번째 핵심 포인트. 더 깊게]

### S5 — 핵심 인사이트 3 (5:00~7:00)
[세 번째 핵심 포인트. 실전 적용 방법]

### S6 — 반론/검증 (7:00~8:30)
[예상 반론 해소 + 리스크 언급으로 신뢰 구축]

### S7 — 결론 (8:30~9:30)
["나는 이렇게 한다" 방법론으로 간접 노출]

### S8 — CTA (9:30~10:00)
[서비스 언급 유일 허용. 구독+알림 요청]
```

완성된 대본을 `raw/yt_trend/{날짜}/step5_draft.md` 에 저장 (Write 도구).

---

## 오류 처리

| 상황 | 대응 |
|------|------|
| API 키 없음 | 즉시 중단. 설정 방법 안내 |
| Step1 결과 0개 | 중단. 키워드 또는 API 할당량 확인 요청 |
| Step3 자막 2개 미만 | 경고 후 중단 |
| Step2 MCP 오류 | 오류 메시지 출력. 수동 리서치 후 step2_research.md 직접 작성 요청 |
| Step4 JSON 파싱 실패 | raw 응답 출력 후 중단 |

---

## 재실행 안내

각 step 출력 파일이 이미 존재하면 해당 단계를 자동 skip한다.

특정 단계부터 재실행하려면:
```bash
# step3부터 재실행: step3/4/5 파일 삭제 후 재실행
del raw\yt_trend\{날짜}\step3_analysis.json
del raw\yt_trend\{날짜}\step4_ideas.json
del raw\yt_trend\{날짜}\step5_draft.md
```
```

- [ ] **Step 2: 스킬 등록 확인**

```bash
ls .agents/skills/yt-trend/
```

Expected: `SKILL.md` 파일 존재

- [ ] **Step 3: Commit**

```bash
git add .agents/skills/yt-trend/
git commit -m "feat: yt-trend 오케스트레이터 스킬 (Step2 MCP + Step5 대본)"
```

---

## Task 5: 전체 파이프라인 통합 테스트

- [ ] **Step 1: API 키 확인**

```powershell
echo $env:YOUTUBE_API_KEY
echo $env:GEMINI_API_KEY
```

Expected: 두 값 모두 출력됨

- [ ] **Step 2: Step1 실행**

```bash
python scripts/yt_trend/step1_fetch.py --date 2026-06-04
```

Expected: `raw/yt_trend/2026-06-04/step1_videos.json` 생성, 20개 영상

- [ ] **Step 3: Step1 결과 검증**

```bash
python -c "import json; d=json.load(open('raw/yt_trend/2026-06-04/step1_videos.json',encoding='utf-8')); print(f'{len(d)}개'); [print(f\"  {i+1}. {v['title'][:40]} ({v['views']:,}뷰)\") for i,v in enumerate(d[:5])]"
```

Expected: Top 5 영상 제목+조회수 출력

- [ ] **Step 4: yt-trend 스킬 실행**

스킬 호출: `/yt-trend`

Expected: Step1 skip (이미 완료) → Step2 Gemini 딥리서치 → Step3 분석 → Step4 소재 → Step5 대본

- [ ] **Step 5: 결과 파일 모두 확인**

```bash
ls raw/yt_trend/2026-06-04/
```

Expected: `step1_videos.json`, `step2_research.md`, `step3_analysis.json`, `step4_ideas.json`, `step5_draft.md` 전부 존재

- [ ] **Step 6: Final Commit**

```bash
git add scripts/yt_trend/ .agents/skills/yt-trend/ raw/yt_trend/
git commit -m "feat: yt-trend 파이프라인 완성 및 통합 테스트"
```

---

## 자가검토

### Spec 커버리지

| Spec 요구사항 | 구현 Task |
|---|---|
| Step1: 키워드 6개, 48시간, viewCount, KR, 상위 20개 | Task 1 |
| Step2: Gemini MCP 딥리서치 | Task 4 (SKILL.md Step2) |
| Step3: 자막 Top5, 훅/구성/댓글, skip 처리 | Task 2 |
| Step4: step2+step3 기반 소재 3개, 70/20/10 | Task 3 |
| Step5: Claude 대본 S1~S8, 제목 5개, 썸네일 | Task 4 (SKILL.md Step5) |
| `--from-step` 재실행 (파일 존재 시 skip) | 각 Task skip 로직 |
| 오류 처리 (API 할당량, 자막 2개 미만) | Task 1/2 exit(1) |
| `raw/yt_trend/{날짜}/` 중간 파일 저장 | 전체 Tasks |

### 주의사항

- `GEMINI_API_KEY` 환경 변수: `.mcp.json` 의 `${GEMINI_API_KEY}` 와 Python 스크립트가 동일한 변수명 사용. 시스템 환경 변수에 설정 필요 (PowerShell: `$env:GEMINI_API_KEY="..."`)
- `youtube-transcript-api 1.2.4` API: `YouTubeTranscriptApi.get_transcript()` 시그니처가 구버전과 다를 수 있음. 오류 시 `YouTubeTranscriptApi().fetch()` 로 변경
- `gemini-2.0-flash` 모델명: `google-generativeai 0.8.6` 기준. API 키 및 버전에 따라 `gemini-2.0-flash-exp` 로 변경 필요할 수 있음
