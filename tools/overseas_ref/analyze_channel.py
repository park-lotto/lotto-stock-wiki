"""해외 원본 채널 분석(관제 162): 쓸만한가 · 영상이 있나 · 해외에서 터지나.
사용: py -m tools.overseas_ref.analyze_channel <유튜브 채널 주소|@핸들|영상주소> ...
"""
import re, statistics, sys
from datetime import datetime, timezone
from shopping_shorts import youtube_client as yc

def analyze(seed):
    if re.search(r"(shorts/|v=)", seed):
        vid = re.search(r"(?:shorts/|v=)([\w-]{11})", seed).group(1)
        d, _ = yc._first_ok(yc._VIDEOS_URL, {"part": "snippet", "id": vid})
        seed = "https://www.youtube.com/channel/" + d["items"][0]["snippet"]["channelId"]
    cid, uploads = yc._resolve_channel(seed)
    ch, _ = yc._first_ok(yc._CHANNELS_URL, {"part": "snippet,statistics", "id": cid})
    c = ch["items"][0]; st = c["statistics"]
    pl, _ = yc._first_ok(yc._PLAYLIST_ITEMS_URL, {"part": "contentDetails", "playlistId": uploads, "maxResults": 50})
    ids = [i["contentDetails"]["videoId"] for i in pl.get("items", [])]
    vd, _ = yc._first_ok(yc._VIDEOS_URL, {"part": "snippet,contentDetails,statistics", "id": ",".join(ids)})
    vs = []
    for it in vd.get("items", []):
        secs = yc._parse_duration_secs(it["contentDetails"]["duration"]) or 0
        pub = datetime.fromisoformat(it["snippet"]["publishedAt"].replace("Z", "+00:00"))
        vs.append({"id": it["id"], "secs": secs, "views": int(it["statistics"].get("viewCount") or 0),
                   "days": (datetime.now(timezone.utc) - pub).days, "title": it["snippet"]["title"]})
    shorts = [v for v in vs if v["secs"] <= 180]
    subs = int(st.get("subscriberCount") or 0)
    med = statistics.median([v["views"] for v in shorts]) if shorts else 0
    hits = [v for v in shorts if subs and v["views"] >= subs]
    span = max(v["days"] for v in vs) if vs else 0
    print(f"■ {c['snippet']['title']} ({c['snippet'].get('country','?')}) https://youtube.com/channel/{cid}")
    print(f"  구독 {subs:,} · 총영상 {st.get('videoCount')} · 최근50중 쇼츠 {len(shorts)}편(최근 {span}일)")
    print(f"  쇼츠 조회 중앙값 {med:,.0f} (구독 대비 {med/subs if subs else 0:.2f}배) · 구독수 넘은 터진 영상 {len(hits)}편")
    for v in sorted(shorts, key=lambda v: -v["views"])[:5]:
        print(f"    {v['views']:>12,} {v['secs']}초 {v['days']}일전 {v['title'][:60]}")

if __name__ == "__main__":
    for s in sys.argv[1:]:
        try: analyze(s)
        except Exception as e: print("실패", s, repr(e)[:120])
