import requests
import json
from datetime import datetime, timedelta, timezone
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
PUBLISHED_AFTER = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

KEYWORDS = ["주식", "급등주", "수급", "종목추천", "코스피", "반도체주식"]

def search_videos(keyword, max_results=10):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "regionCode": "KR",
        "relevanceLanguage": "ko",
        "order": "viewCount",
        "publishedAfter": PUBLISHED_AFTER,
        "videoDuration": "medium",
        "maxResults": max_results,
        "key": API_KEY,
    }
    res = requests.get(url, params=params)
    return res.json()

def get_video_stats(video_ids):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "statistics,snippet",
        "id": ",".join(video_ids),
        "key": API_KEY,
    }
    res = requests.get(url, params=params)
    return res.json()

def run():
    results = []
    for kw in KEYWORDS:
        data = search_videos(kw, max_results=5)
        items = data.get("items", [])
        ids = [i["id"]["videoId"] for i in items if i["id"].get("videoId")]
        if not ids:
            continue
        stats = get_video_stats(ids)
        for item in stats.get("items", []):
            title = item["snippet"]["title"]
            channel = item["snippet"]["channelTitle"]
            views = int(item["statistics"].get("viewCount", 0))
            published = item["snippet"]["publishedAt"][:10]
            vid_id = item["id"]
            results.append({
                "keyword": kw,
                "title": title,
                "channel": channel,
                "views": views,
                "published": published,
                "url": f"https://youtu.be/{vid_id}",
            })

    results.sort(key=lambda x: x["views"], reverse=True)

    print(f"\n{'='*60}")
    print(f"한국 주식 유튜브 트렌딩 (최근 30일) — {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*60}")
    for i, r in enumerate(results[:20], 1):
        print(f"\n{i}. [{r['keyword']}] {r['title']}")
        print(f"   채널: {r['channel']} | 조회수: {r['views']:,} | {r['published']}")
        print(f"   {r['url']}")

    out_path = "raw/yt/yt_trending_" + datetime.now().strftime("%Y%m%d") + ".json"
    os.makedirs("raw/yt", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n저장 완료: {out_path}")

if __name__ == "__main__":
    if not API_KEY:
        print("YOUTUBE_API_KEY 환경변수를 설정하세요.")
    else:
        run()
