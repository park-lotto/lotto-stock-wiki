"""검색어 눈덩이 실측(관제 162): 해외 영상 1편 → 판매자 태그 + 관련 검색어(EN) → 유튜브 조회수순 검색 → 채널.
사용: py -m tools.overseas_ref.kw_snowball <video_id> [기간일=90]
렌즈 비용 0 — 제미니 1회 + 유튜브 search(100단위/회).
"""
import re, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from shopping_shorts import youtube_client as yc, config
from shopping_shorts.video_analysis import expand_search_keywords

HANGUL = re.compile(r"[가-힣]")

def main(vid, days=90):
    vd, _ = yc._first_ok(yc._VIDEOS_URL, {"part": "snippet", "id": vid})
    sn = vd["items"][0]["snippet"]
    tags = list(dict.fromkeys(re.findall(r"#(\w+)", sn["title"] + " " + sn.get("description", ""))))[:4]
    cands = expand_search_keywords(sn["title"] + "\n" + sn.get("description", "")[:300], n=5)
    en = [c.get("en") for c in cands if c.get("en")]
    kws = tags + en
    print("씨앗:", sn["channelTitle"], "|", sn["title"][:60]); print("검색어:", kws)
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ch = defaultdict(lambda: {"title": "", "hits": 0, "kws": set(), "views": 0})
    vids = {}
    for kw in kws:
        for tok in config.YOUTUBE_API_KEYS:
            code, items = yc._search_page(kw, after, 50, tok, region="US", lang="en")
            if code == 200:
                break
        items = items or []
        new = 0
        for it in items:
            if HANGUL.search(it["title"] or ""):
                continue
            c = ch[it["channel_id"]]; c["title"] = it["channel_title"]; c["hits"] += 1; c["kws"].add(kw)
            new += it["channel_id"] not in vids.values()
            vids[it["video_id"]] = it["channel_id"]
        print(f"  {kw!r}: {len(items)}편")
    # 조회수·구독자
    ids = list(vids)
    for i in range(0, len(ids), 50):
        d, _ = yc._first_ok(yc._VIDEOS_URL, {"part": "statistics", "id": ",".join(ids[i:i+50])})
        for it in (d or {}).get("items", []):
            ch[vids[it["id"]]]["views"] += int(it["statistics"].get("viewCount") or 0)
    cids = list(ch)
    subs = {}
    for i in range(0, len(cids), 50):
        d, _ = yc._first_ok(yc._CHANNELS_URL if hasattr(yc, "_CHANNELS_URL") else "https://www.googleapis.com/youtube/v3/channels",
                            {"part": "statistics", "id": ",".join(cids[i:i+50])})
        for it in (d or {}).get("items", []):
            subs[it["id"]] = int(it["statistics"].get("subscriberCount") or 0)
    rows = sorted(ch.items(), key=lambda kv: -kv[1]["views"])
    print(f"\n해외 영상 {len(vids)}편 · 채널 {len(ch)}개 · 10만+ 구독 {sum(1 for c in cids if subs.get(c,0)>=100000)}개")
    for cid, c in rows[:30]:
        print(f"  {c['views']:>12,}뷰 {subs.get(cid,0):>10,}구독 {c['hits']}편 {c['title'][:28]:28} https://youtube.com/channel/{cid}")

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 90)
