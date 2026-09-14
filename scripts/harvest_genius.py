"""'천재의 발명품·활용법' 계열 썰쇼핑 채널 발굴 (2026-09-14 사장님 캡처 "이쪽으로 더 수집").

① 이 계열 제목 어휘로 유튜브 검색(쇼츠·최근 30일·조회수순) → 채널 후보
② 후보 채널의 최근 쇼츠(최대 50편)를 categorize()로 채점 — 썰쇼핑(제품정체형·오용형)이
   3편 이상 & 20% 이상인 채널만 통과. ★어휘 하나로 붙이지 않는다: 채널의 **실제 영상들**로 판정
③ 통과 채널을 /tmp/style_candidates.json['썰쇼핑']에 합쳐 둔다 →
   등록은 scripts/register_discovered_styles.py 한 곳에서만 한다(0순위-B)

비용: 검색 100u × 키워드 수 + 후보 채널당 2u.
실행: python3 -m scripts.harvest_genius
"""
import json
import os
from datetime import datetime, timedelta, timezone

from shopping_shorts.categorize import categorize
from shopping_shorts.config import DB_PATH
from shopping_shorts.store import Store
from shopping_shorts.youtube_client import fetch_channel_shorts, fetch_subscribers, search_shorts

KEYWORDS = [
    "천재의 발명품", "천재가 발명한", "천재 활용법", "천재 주부의 활용법",
    "제조사도 놀란", "제조사도 예상못한", "제조사도 당황한", "다이소도 놀란 발명품",
    "상품팀도 벤치마킹한", "일본 천재의 발명품", "한국 천재 활용법", "미친 발명품",
    "개발자도 놀란 활용법", "이케아도 놀란", "물리치료사도 놀란", "그래피티도 당황한",
]
SSUL = ("제품정체형", "오용형")
MIN_HITS, MIN_RATIO = 3, 0.2
CAND = "/tmp/style_candidates.json"


def main():
    store = Store(DB_PATH)
    after = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = search_shorts(KEYWORDS, after, max_per_kw=50)
    cands = {}
    for r in raw:
        if r.get("channel_id"):
            cands.setdefault(r["channel_id"], r.get("channel_title") or "")
    with store._conn() as c:
        known = {r[0] for r in c.execute("SELECT channel_id FROM channel_styles WHERE style='썰쇼핑'")}
    blocked = store.removed_usernames()
    todo = {k: v for k, v in cands.items() if k not in known and k.lower() not in blocked}
    print(f"[genius] 검색 영상 {len(raw)} · 채널 {len(cands)} · 이미 썰 {len(cands) - len(todo)} · 검사 {len(todo)}")

    passed = []
    for cid, title in todo.items():
        vids = fetch_channel_shorts(f"https://www.youtube.com/channel/{cid}")
        if not vids:
            continue
        hits = sum(1 for v in vids if categorize(v.get("channel_title"), v.get("title", "")) in SSUL)
        if hits >= MIN_HITS and hits / len(vids) >= MIN_RATIO:
            passed.append({"cid": cid, "title": title, "score": hits, "n": len(vids),
                           "sample": [v["title"] for v in vids[:3]]})
    subs = fetch_subscribers([p["cid"] for p in passed])
    for p in passed:
        p["subs"] = int(subs.get(p["cid"]) or 0)
    passed.sort(key=lambda p: -p["score"])
    for p in passed:
        print(f"  통과 {p['title'][:18]:18} 썰 {p['score']}/{p['n']} 구독 {p['subs']:,}  {p['sample'][0][:30]}")

    data = {}
    if os.path.exists(CAND):
        try:
            data = json.load(open(CAND))
        except ValueError:
            data = {}
    rows = {r["cid"]: r for r in data.get("썰쇼핑", [])}
    for p in passed:
        rows[p["cid"]] = {k: p[k] for k in ("cid", "title", "subs", "score")}
    data["썰쇼핑"] = list(rows.values())
    json.dump(data, open(CAND, "w"), ensure_ascii=False)
    print(f"[genius] 통과 {len(passed)}채널 → {CAND} (등록: register_discovered_styles.py --apply)")


if __name__ == "__main__":
    main()
