"""해외 레퍼런스 추적 실측(관제 162): 국내 씨앗 채널 → 잘된 숏츠 → 첫 장면 렌즈 → 해외 채널.
사용: py -m tools.overseas_ref.probe <유튜브 채널 URL> [영상수=5]
"""
import json, os, re, subprocess, sys, tempfile
from collections import Counter
from shopping_shorts import youtube_client as yc, lens_discover as ld, config

HANGUL = re.compile(r"[가-힣]")

def first_frame(video_id, workdir):
    out = os.path.join(workdir, f"{video_id}.mp4")
    subprocess.run(["yt-dlp", "-q", "-f", "bv[height<=720][ext=mp4]/bv/b", "--download-sections", "*0-3",
                    "-o", out, f"https://www.youtube.com/shorts/{video_id}"], timeout=120)
    if not os.path.exists(out):
        return None
    jpg = out[:-4] + ".jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.5", "-i", out,
                    "-frames:v", "1", jpg], timeout=60)
    return open(jpg, "rb").read() if os.path.exists(jpg) else None

_CK = []
def live_lens(img, caption):
    """라이브 /api/lens/search 를 관리자로 부른다 — 실제 키 풀(keyroute)·한도 가드를 그대로 탄다."""
    import requests
    from tools.live_admin import admin_cookie, BASE
    if not _CK:
        _CK.append(admin_cookie())
    r = requests.post(BASE + "/api/lens/search", cookies={"dash_auth": _CK[0]},
                      files={"frame": ("f.jpg", img, "image/jpeg")},
                      data={"source_caption": caption}, timeout=180)
    d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200:
        print("  렌즈 실패", r.status_code, str(d)[:200])
    return d.get("items") or []

def channel_shorts(seed, max_secs=180):
    """채널 최근 업로드 50개 중 쇼츠(≤3분, 2024-10 이후 쇼츠 상한) — 조회수 포함."""
    _, uploads = yc._resolve_channel(seed)
    pl, _ = yc._first_ok(yc._PLAYLIST_ITEMS_URL, {"part": "contentDetails", "playlistId": uploads, "maxResults": 50})
    ids = [i["contentDetails"]["videoId"] for i in (pl or {}).get("items", [])]
    vd, _ = yc._first_ok(yc._VIDEOS_URL, {"part": "snippet,contentDetails,statistics", "id": ",".join(ids)})
    out = []
    for it in (vd or {}).get("items", []):
        secs = yc._parse_duration_secs(it["contentDetails"].get("duration"))
        if secs is None or secs > max_secs:
            continue
        out.append({"video_id": it["id"], "title": it["snippet"]["title"],
                    "views": int(it["statistics"].get("viewCount") or 0)})
    return out

def channel_of(r):
    """렌즈 결과 1건 → (플랫폼, 채널키). 유튜브는 나중에 API로 일괄 해석."""
    u, t = r["url"], r.get("title") or ""
    if r["platform"] == "tiktok":
        m = re.search(r"tiktok\.com/@([^/?]+)", u)
        return ("tiktok", "@" + m.group(1)) if m else None
    if r["platform"] == "instagram":
        m = re.search(r"\(@([A-Za-z0-9_.]+)\)", t) or re.search(r"instagram\.com/([A-Za-z0-9_.]+)/(?:reel|p)/", u)
        return ("instagram", "@" + m.group(1)) if m else None
    return None

def main(seed, n=5):
    vids = sorted(channel_shorts(seed), key=lambda v: -v["views"])[:n]
    print(f"씨앗 {seed}: 숏츠 상위 {len(vids)}")
    found, wd = [], tempfile.mkdtemp()
    for v in vids:
        img = first_frame(v["video_id"], wd)
        res = live_lens(img, v["title"]) if img else []
        print(f"- {v['views']:>10,} {v['title'][:40]!r} 프레임={'O' if img else 'X'} 렌즈={len(res)}")
        for r in res:
            r["seed_video"] = v["video_id"]
        found += res
    yt = [r for r in found if r["platform"] == "youtube"]
    ych = {c["channel_url"]: c for c in yc.channels_from_video_urls([r["url"] for r in yt])}
    chans = Counter()
    for r in found:
        k = channel_of(r)
        if k:
            chans[k] += 1
    for c in ych.values():
        chans[("youtube", c["channel_title"] + " " + c["channel_url"])] += 1
    over = [r for r in found if not HANGUL.search(r.get("title") or "")]
    print(f"\n렌즈 결과 {len(found)}건 · 플랫폼 {dict(Counter(r['platform'] for r in found))}")
    print(f"제목에 한글 없음(해외 후보) {len(over)}건")
    print(f"채널 해석 {len(chans)}개:")
    for (p, k), c in chans.most_common():
        print(f"  {p:9} {c}회 {k}")
    json.dump(found, open(os.path.join(os.path.dirname(__file__), "_last_probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5)
