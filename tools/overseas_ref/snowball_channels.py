"""채널 눈덩이(관제 162, 2026-10-08 사장님 "하나하나 내가 알려줄 거면 내가 하지").
좋은 채널이 다음 좋은 채널을 찾는다: 씨앗 → find_similar(검색+점수) → 점수 기준 넘은 채널만 새 씨앗 → 반복.
주제는 사람이 안 준다 — 통과한 채널의 상위 영상 제목이 다음 검색어가 된다(기준 못 넘으면 번지지 않음).
사용: py -m tools.overseas_ref.snowball_channels <씨앗 채널주소...> [--seeds 15] [--min 120]
"""
import argparse, json, os
from tools.overseas_ref import find_similar as fs

def run(seeds, max_seeds=15, min_score=120, nq=4, cap=30):
    queue = list(seeds); done, found = set(), {}
    while queue and len(done) < max_seeds:
        seed = queue.pop(0)
        if seed in done: continue
        done.add(seed)
        rows = fs.main(seed, nq, cap)
        for sc, ch, m, q in rows:
            if ch["cid"] in found: continue
            found[ch["cid"]] = {"title": ch["title"], "country": ch["country"], "subs": ch["subs"], "score": sc,
                                "hits": m["hits"], "median": m["median"], "avg_secs": m["avg_secs"],
                                "top": m["top"]["id"], "top_views": m["top"]["views"], "top_title": m["top"]["title"],
                                "query": q, "from": seed}
            if sc >= min_score:
                queue.append(f"https://www.youtube.com/channel/{ch['cid']}")
    out = sorted(found.values(), key=lambda r: -r["score"])
    p = os.path.join(os.path.dirname(__file__), "_snowball.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n씨앗 {len(done)}개 돌림 · 채널 {len(out)}개 · 기준({min_score}) 통과 {sum(r['score']>=min_score for r in out)}개 → {p}")
    return out

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("seeds", nargs="+"); a.add_argument("--seeds", dest="n", type=int, default=15)
    a.add_argument("--min", type=int, default=120); x = a.parse_args()
    run(x.seeds, x.n, x.min)
