"""주제 검색어 묶음 → 해외 채널 점수(관제 162). 주제와 검색어는 Claude가 만든다(사장님이 주지 않는다).
사용: py -m tools.overseas_ref.topic_search  (아래 TOPICS 전부)
"""
import json, os, re
from datetime import datetime, timedelta, timezone
from shopping_shorts import youtube_client as yc, config
from tools.overseas_ref import find_similar as fs

TOPICS = {
    "한국뷰티": ["korean skincare routine", "trying korean skincare", "olive young haul", "k beauty products review",
               "korean sunscreen review", "glass skin routine", "korean makeup tutorial", "medicube review"],
    "한국음식": ["trying korean food", "korean convenience store food", "buldak challenge", "korean street food reaction",
               "korean mukbang", "trying korean snacks", "korean bbq first time", "cooking korean recipe"],
    "한국제품·생활": ["korean products you need", "living in korea as a foreigner", "things only in korea",
                  "korean gadgets", "daiso korea haul", "korea vs america", "foreigner in seoul", "coupang haul korea"],
}

def run(per_topic_cap=40):
    after = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = {}
    for topic, qs in TOPICS.items():
        cand = {}
        for q in qs:
            for tok in config.YOUTUBE_API_KEYS:
                code, items = yc._search_page(q, after, 50, tok, region="US", lang="en")
                if code == 200: break
            for it in items or []:
                if not fs.H.search(it["title"] or ""): cand.setdefault(it["channel_id"], q)
        rows = []
        for cid in list(cand)[:per_topic_cap * 2]:
            ch = fs.recent(f"https://www.youtube.com/channel/{cid}")
            if not ch: continue
            sc, m = fs.score(ch)
            if sc > 0:
                rows.append({"title": ch["title"], "country": ch["country"], "subs": ch["subs"], "score": sc, "hits": m["hits"],
                             "median": m["median"], "avg_secs": m["avg_secs"], "top": m["top"]["id"],
                             "top_views": m["top"]["views"], "top_title": m["top"]["title"], "query": cand[cid], "cid": cid})
        rows.sort(key=lambda r: -r["score"])
        res[topic] = rows
        print(f"[{topic}] 후보 {len(cand)} → 점수>0 {len(rows)}")
    json.dump(res, open(os.path.join(os.path.dirname(__file__), "_topics.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    run()
