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
    dt = datetime.now(timezone.utc) - timedelta(hours=12)
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
