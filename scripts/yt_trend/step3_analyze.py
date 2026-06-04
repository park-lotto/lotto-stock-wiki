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
