"""좋은 해외 채널 → 비슷한 채널 찾기 + 점수(관제 162, 2026-10-08 사장님 "잘되는 해외채널 찾는게 제일 중요").
씨앗 채널 상위 쇼츠 제목(앞 6단어)으로 유튜브 검색(미국·영어·최근 120일) → 걸린 해외 채널마다 최근 50편을 열어 점수.
점수 기준(사장님 예시 Laro Notes·MissDarcei·Rankit 에서 뽑음):
  ① 구독수 이상·10만 이상 쇼츠가 여러 편(계속 터지나) + 조회 중앙값  ② 최근 30일 안에 올림(살아있나)
  ③ 쇼츠 평균 25초 이상(원테이크로 붙일 시간)  ④ 한글 제목 아님(해외)
사용: py -m tools.overseas_ref.find_similar <채널주소> [검색어수=6] [후보상한=40]
"""
import json, re, statistics, sys
from datetime import datetime, timedelta, timezone
from shopping_shorts import youtube_client as yc, config

H = re.compile(r"[가-힣]")

def recent(cid_or_seed):
    cid, up = yc._resolve_channel(cid_or_seed)
    ch, _ = yc._first_ok(yc._CHANNELS_URL, {"part": "snippet,statistics", "id": cid})
    if not ch or not ch.get("items"): return None
    c = ch["items"][0]
    pl, _ = yc._first_ok(yc._PLAYLIST_ITEMS_URL, {"part": "contentDetails", "playlistId": up, "maxResults": 50})
    ids = [i["contentDetails"]["videoId"] for i in (pl or {}).get("items", [])]
    if not ids: return None
    vd, _ = yc._first_ok(yc._VIDEOS_URL, {"part": "snippet,contentDetails,statistics", "id": ",".join(ids)})
    now = datetime.now(timezone.utc); vs = []
    for it in (vd or {}).get("items", []):
        s = yc._parse_duration_secs(it["contentDetails"]["duration"]) or 0
        if s > 180: continue
        pub = datetime.fromisoformat(it["snippet"]["publishedAt"].replace("Z", "+00:00"))
        vs.append({"id": it["id"], "secs": s, "views": int(it["statistics"].get("viewCount") or 0),
                   "days": (now - pub).days, "title": it["snippet"]["title"]})
    return {"cid": cid, "title": c["snippet"]["title"], "country": c["snippet"].get("country", "?"),
            "subs": int(c["statistics"].get("subscriberCount") or 0), "shorts": vs}

def score(ch):
    vs, subs = ch["shorts"], max(ch["subs"], 1)
    if not vs: return 0, {}
    # 터진 영상 = 구독수 이상 **그리고** 10만 이상(구독 수백 명 채널은 모든 영상이 '구독 초과'라 거짓 1등이 됐다, 10-08 실측)
    hits = sum(v["views"] >= max(subs, 100_000) for v in vs)
    m = {"hits": hits, "median": int(statistics.median(v["views"] for v in vs)),
         "last_days": min(v["days"] for v in vs), "avg_secs": int(sum(v["secs"] for v in vs) / len(vs)),
         "top": max(vs, key=lambda v: v["views"]), "korean": sum(bool(H.search(v["title"])) for v in vs) > len(vs) / 3}
    sc = hits * 10 + min(m["median"] / 100_000, 5) * 10
    if m["last_days"] > 30: sc *= 0.3
    if m["avg_secs"] < 25: sc *= 0.4
    if m["korean"]: sc = 0
    return round(sc, 1), m

def queries(seed_ch, n):
    out = []
    for v in sorted(seed_ch["shorts"], key=lambda v: -v["views"]):
        w = re.sub(r"#\S+|[^\w\s']", " ", v["title"]).split()[:6]
        q = " ".join(w).lower()
        if len(w) >= 3 and q not in out: out.append(q)
        if len(out) >= n: break
    return out

def main(seed, nq=6, cap=40):
    s = recent(seed)
    print(f"### 씨앗 {s['title']} (구독 {s['subs']:,})")
    after = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cand = {}
    for q in queries(s, nq):
        for tok in config.YOUTUBE_API_KEYS:
            code, items = yc._search_page(q, after, 50, tok, region="US", lang="en")
            if code == 200: break
        n0 = len(cand)
        for it in items or []:
            if it["channel_id"] != s["cid"] and not H.search(it["title"] or ""):
                cand.setdefault(it["channel_id"], q)
        print(f"  검색 '{q}' → 새 후보 {len(cand)-n0}")
    rows = []
    for cid in list(cand)[:cap]:
        ch = recent(f"https://www.youtube.com/channel/{cid}")
        if not ch: continue
        sc, m = score(ch)
        if sc > 0: rows.append((sc, ch, m, cand[cid]))
    rows.sort(key=lambda r: -r[0])
    print(f"  후보 {min(len(cand), cap)}개 분석 → 점수>0 {len(rows)}개")
    for sc, ch, m, q in rows[:10]:
        t = m["top"]
        print(f"  {sc:>5} | {ch['title'][:26]:26} ({ch['country']}) 구독 {ch['subs']:>10,} | 터진 {m['hits']:>2}편 · 중앙 {m['median']:>9,} · 평균 {m['avg_secs']}초 · 최근 {m['last_days']}일전")
        print(f"        최고 {t['views']:,} https://youtube.com/shorts/{t['id']} {t['title'][:55]}")
        print(f"        https://youtube.com/channel/{ch['cid']}/shorts  (검색어: {q})")
    return rows

if __name__ == "__main__":
    main(sys.argv[1], *(int(a) for a in sys.argv[2:4]))
