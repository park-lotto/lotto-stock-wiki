# -*- coding: utf-8 -*-
"""채널 전수조사 — 고른 채널의 쇼츠(60초 이하)를 예전 것까지 전부 훑어 channel_survey 표에 넣는다(관제 137).

'채널별 터진 영상' 탭(store.channel_hit_items)의 재료다. 주 1회 돈다(2026-10-06 사장님 "주1회"):
    python3 -m shopping_shorts.channel_survey            # deploy/shopping-shorts-channel-survey.timer

★누구를 조사하나 = 채널 고정표의 썰쇼핑·홈템(Store.HIT_CATEGORIES) — 탭에 나오는 채널과 같은 한 곳.
★쿼터: 채널당 (쇼츠 수 ÷ 50) × 2 호출. 실측 2026-10-06: 205채널 · 31,825편 · 1,516 호출 · 7분.
★반쪽 결과는 저장하지 않는다 — 중간에 쿼터가 마르거나 한 장이 빠진 채널은 지난 조사분을 그대로 둔다.
  (반쪽을 넣으면 그 채널의 '평소'가 틀어져 엉뚱한 영상이 터진 것으로 뜬다.)
"""
import json
import sys
import time

from shopping_shorts.youtube_client import _first_ok, _parse_duration_secs, _PLAYLIST_ITEMS_URL, _VIDEOS_URL

MAX_SECS = 60          # 2026-10-06 사장님 "60초 넘는 건 하지 말고"


def _list_ids(cid):
    """채널의 쇼츠 id 전부 → (ids, 온전히 받았나). 쇼츠 전용 재생목록(UUSH…)을 끝까지, 비면 전체 업로드(UU…)."""
    for prefix in ("UUSH", "UU"):
        ids, tok, ok = [], None, True
        while True:
            p = {"part": "contentDetails", "playlistId": prefix + cid[2:], "maxResults": 50}
            if tok:
                p["pageToken"] = tok
            d, _ = _first_ok(_PLAYLIST_ITEMS_URL, p)
            if d is None:
                ok = False
                break
            ids += [(it.get("contentDetails") or {}).get("videoId") for it in d.get("items") or []]
            tok = d.get("nextPageToken")
            if not tok:
                break
        ids = [i for i in ids if i]
        if ids:
            return ids, ok
    return [], False


def survey_channel(cid):
    """한 채널의 60초 이하 쇼츠 전부 → [{id,title,at,secs,views,likes,comments,ch}] 또는 None(온전히 못 받음)."""
    ids, ok = _list_ids(cid)
    if not ids or not ok:
        return None
    out = []
    for i in range(0, len(ids), 50):
        d, _ = _first_ok(_VIDEOS_URL, {"part": "snippet,contentDetails,statistics", "id": ",".join(ids[i:i + 50])})
        if d is None:
            return None
        for it in d.get("items") or []:
            secs = _parse_duration_secs((it.get("contentDetails") or {}).get("duration"))
            if secs is None or secs > MAX_SECS:
                continue
            sn, st = it.get("snippet") or {}, it.get("statistics") or {}
            out.append({"id": it.get("id"), "title": sn.get("title"), "at": sn.get("publishedAt"), "secs": secs,
                        "views": int(st.get("viewCount") or 0), "likes": int(st.get("likeCount") or 0),
                        "comments": int(st.get("commentCount") or 0), "ch": sn.get("channelTitle")})
    return out


def run(store, limit=0, fetch=survey_channel):
    """고른 채널을 전부 다시 조사해 표에 넣는다. 결과 요약을 돌려주고 settings 에도 남긴다(다음 사람이 언제·몇 개 됐는지 본다)."""
    t0 = time.time()
    cids, unknown = store.hit_channel_ids()
    if limit:
        cids = cids[:limit]
    ok, fail, videos = 0, [], 0
    for cid in cids:
        vs = fetch(cid)
        if vs is None:
            fail.append(cid)          # 지난 조사분은 그대로 둔다
            continue
        videos += store.save_channel_survey(cid, vs)
        ok += 1
    res = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "channels": len(cids), "ok": ok, "fail": fail, "videos": videos,
           "unknown_ids": unknown, "hits": len(store.channel_hit_items()), "secs": round(time.time() - t0)}
    store.set_setting("channel_survey::last_run", json.dumps(res, ensure_ascii=False))
    return res


if __name__ == "__main__":
    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    r = run(Store(DB_PATH), limit=int(sys.argv[1]) if len(sys.argv) > 1 else 0)
    print("[채널 전수조사] 채널 %d개 중 %d개 갱신 · 쇼츠 %d편 · 탭에 나올 터진 영상 %d편 · %d초" % (
        r["channels"], r["ok"], r["videos"], r["hits"], r["secs"]))
    if r["fail"]:
        print("  못 받은 채널 %d개(지난 조사분 유지): %s" % (len(r["fail"]), ", ".join(r["fail"][:10])))
    if r["unknown_ids"]:
        print("  채널 ID 를 못 찾은 고정 채널 %d개: %s" % (len(r["unknown_ids"]), ", ".join(r["unknown_ids"][:10])))
    # 절반 넘게 못 받았으면 실패로 끝낸다 — systemd 가 실패로 기록해 조용히 넘어가지 않게.
    sys.exit(1 if r["channels"] and r["ok"] * 2 < r["channels"] else 0)
