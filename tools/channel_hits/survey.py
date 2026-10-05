# -*- coding: utf-8 -*-
"""고른 채널의 쇼츠(60초 이하)를 예전 것까지 전부 훑어 조회수를 모은다(관제 134 후속 조사, 읽기 전용).
사용: python3 survey.py <채널ID목록.txt> <결과폴더> [최대채널수]
채널마다 <결과폴더>/<채널ID>.json 을 남긴다(이미 있으면 건너뜀 = 이어하기)."""
import json, os, sys, time
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from shopping_shorts.youtube_client import _first_ok, _parse_duration_secs, _PLAYLIST_ITEMS_URL, _VIDEOS_URL
from concurrent.futures import ThreadPoolExecutor
CALLS = [0]

def api(url, params):
    CALLS[0] += 1
    return _first_ok(url, params)

def list_ids(cid):
    """쇼츠 전용 재생목록(UUSH…)을 끝까지. 비면 전체 업로드 목록(UU…)으로."""
    for prefix in ("UUSH", "UU"):
        ids, tok, quota = [], None, False
        while True:
            p = {"part": "contentDetails", "playlistId": prefix + cid[2:], "maxResults": 50}
            if tok: p["pageToken"] = tok
            d, saw403 = api(_PLAYLIST_ITEMS_URL, p)
            if d is None:
                quota = quota or saw403; break
            ids += [(it.get("contentDetails") or {}).get("videoId") for it in d.get("items") or []]
            tok = d.get("nextPageToken")
            if not tok: break
        ids = [i for i in ids if i]
        if ids: return ids, prefix, quota
    return [], "", quota

def survey(cid, outdir):
    path = os.path.join(outdir, cid + ".json")
    if os.path.exists(path): return cid, "skip", 0
    ids, src, quota = list_ids(cid)
    vids, miss = [], 0
    for i in range(0, len(ids), 50):
        d, saw403 = api(_VIDEOS_URL, {"part": "snippet,contentDetails,statistics", "id": ",".join(ids[i:i + 50])})
        if d is None:
            miss += 1; quota = quota or saw403; continue
        for it in d.get("items") or []:
            secs = _parse_duration_secs((it.get("contentDetails") or {}).get("duration"))
            if secs is None or secs > 60: continue
            sn, st = it.get("snippet") or {}, it.get("statistics") or {}
            vids.append({"id": it.get("id"), "title": sn.get("title"), "at": sn.get("publishedAt"), "secs": secs,
                         "views": int(st.get("viewCount") or 0), "likes": int(st.get("likeCount") or 0),
                         "comments": int(st.get("commentCount") or 0), "ch": sn.get("channelTitle")})
    ok = bool(ids) and not miss
    if ok:      # 온전히 받은 채널만 저장한다 — 반쪽 결과를 남기면 이어하기가 그걸 완성본으로 믿는다
        json.dump({"cid": cid, "src": src, "listed": len(ids), "videos": vids, "at": time.strftime("%Y-%m-%dT%H:%M:%S")},
                  open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return cid, ("ok" if ok else ("quota" if quota else ("empty" if not ids else "partial"))), len(vids)

if __name__ == "__main__":
    ids = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    outdir = sys.argv[2]; os.makedirs(outdir, exist_ok=True)
    if len(sys.argv) > 3: ids = ids[:int(sys.argv[3])]
    t0 = time.time(); res = []
    with ThreadPoolExecutor(3) as ex:
        for r in ex.map(lambda c: survey(c, outdir), ids):
            res.append(r); print(r, flush=True)
    import collections
    print("끝", dict(collections.Counter(r[1] for r in res)), "쇼츠", sum(r[2] for r in res), "API호출", CALLS[0], "초", round(time.time() - t0))
