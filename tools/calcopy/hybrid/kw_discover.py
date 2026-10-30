"""검색어로 해외 원본 소재 찾기 — 영어 검색어를 단어를 바꿔 가며(사장님 10-27 "영어로 키워드를 해서 찾아봐 / 한국 화장품 반응 → 단어를 바꿔서
한국 화장품 소재로 재미있는 에피소드들 반응들").

    py tools/calcopy/hybrid/kw_discover.py [--pool C:/숏템_칼카피/of_pool] [--min-views 500000] [--n 12]

① 검색어 = 제품 × 반응 꼴(QUERIES — 사람이 고른 씨앗) ② 유튜브 쇼츠(runner_ops._search)·틱톡·인스타(runner_ops._web_links) — 코드, 토큰 0
③ 정보(조회·채널·제목, runner_ops._metas) → 조회 --min-views 이상·해외(origin_find.is_korean 아님)만 ④ 판정(소넷, 못 하면 오푸스 — 글만)
결과 = <pool>/검색소재.json {영상 주소: {q, platform, channel, views, title, judge}} — 판정한 영상은 다시 안 본다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

QUERIES = [
    "trying korean skincare for the first time", "korean sunscreen white cast test", "korean makeup fail", "weird korean beauty products",
    "korean face mask reaction", "korean pimple patch results", "korean cushion foundation dark skin", "korean lip tint reaction",
    "korean nose pore strip gross", "korean peeling gel reaction", "korean toothpaste review", "olive young haul reaction",
    "daiso korea beauty test", "korean glass skin before after", "korean color changing foundation", "korean beauty gadget test",
    "korean hair treatment shocked", "korean eye patch reaction", "korean body scrub italy towel", "korean beauty hack viral",
]

QUERIES_EMOTION = [       # 10-27 2회: 1회 검색어('results'·'review')가 광고성 리뷰만 불러 — 터진 원본 제목의 감정 말로
    "korean makeup made me cry", "this korean product scared me", "korean beauty products are insane", "i wasn't ready for this korean skincare",
    "korean skincare ruined my face", "i tried the viral korean", "korean product actually worked shocked", "korean beauty is on another level",
    "why is no one talking about this korean", "korean cosmetics freaked me out", "my mom tried korean skincare", "boyfriend tries korean makeup",
    "korean makeup transformation shocked", "korean skincare changed my skin", "korean sunscreen surprised me", "i can't believe this korean product",
    "korean beauty hack gone wrong", "korean pore cleansing satisfying", "trying korean makeup as a black woman", "korean product turned my skin",
]

ASK = """너는 우리 쇼츠 소재 감별 담당이다. 우리 대표 판 = 잇템로그: 외국인이 **한국 화장품·K제품**을 써 보고 놀라거나 반응하는 해외 영상에 한국어 나레를 얹는다.
아래 해외 영상(검색어·제목·조회·채널)마다 판정해라(글만 보고):
- korean_product: 한국 제품을 실제로 쓰는 영상인가 true/false
- episode: 재미있는 에피소드·반응인가 "strong"(반전·큰 리액션·전후 차이)|"some"|"none"(설명·광고·평범한 리뷰)
- product: 제품 한 줄 짐작
- score: 0~10(잇템로그로 바로 만들 가치)
- note: 한 줄
JSON 하나: {"videos": [{"key": "<키 그대로>", "korean_product": true, "episode": "...", "product": "...", "score": 7, "note": "..."}]}"""


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="C:/숏템_칼카피/of_pool")
    ap.add_argument("--min-views", type=int, default=500_000)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--set", default="base", choices=["base", "emotion"], help="검색어 묶음")
    a = ap.parse_args(argv)
    from tools.calcopy import origin_find as OF
    from tools.calcopy.hybrid import runner_ops as R
    from tools.calcopy.hybrid import treasure_judge as T
    pool = Path(a.pool)
    outp = pool / "검색소재.json"
    book = json.loads(outp.read_text(encoding="utf-8")) if outp.exists() else {}
    t0 = time.time()
    raw: dict[str, dict] = {}
    qs = QUERIES_EMOTION if a.set == "emotion" else QUERIES
    for q in qs:
        for e in R._search([q], a.n, shorts=True):
            if e.get("id"):
                u = f"https://www.youtube.com/shorts/{e['id']}"
                raw.setdefault(u, {"q": q, "platform": "yt", "title": e.get("title"), "channel": e.get("channel"), "views": e.get("views")})
    print(f"[검색] 유튜브 {len(raw)}편 ({time.time() - t0:.0f}초)", flush=True)
    web = []
    for i in range(0, len(qs), R.WEB_QN):      # _web_links 는 검색어를 앞 WEB_QN 개만 돈다(10-27 1회차: 20개 중 6개만 틱톡·인스타로 갔다)
        web += R._web_links(qs[i:i + R.WEB_QN], 15)
    for x in web:
        k = OF.vkey(x["url"])
        if k:
            raw.setdefault(OF.url_of(k[0], k[1], x["url"]), {"q": x.get("q"), "platform": k[0]})
    print(f"[검색] 틱톡·인스타 포함 {len(raw)}편 ({time.time() - t0:.0f}초)", flush=True)
    need = [u for u, v in raw.items() if v.get("views") is None and u not in book]
    ms = R._metas(need) if need else {}
    for u in need:
        m = ms.get(u) or {}
        raw[u].update({k: m.get(k) for k in ("title", "channel", "views") if m.get(k) is not None})
    keep = {u: v for u, v in raw.items() if u not in book and int(v.get("views") or 0) >= a.min_views
            and not OF.is_korean(str(v.get("title") or ""), str(v.get("channel") or ""))}
    print(f"[검색] 정보 {time.time() - t0:.0f}초 · 조회 {a.min_views:,}+ 해외 {len(keep)}편", flush=True)
    items = list(keep.items())
    for i in range(0, len(items), T.BATCH):
        bt = [(str(j + 1), {**v, "url": u}) for j, (u, v) in enumerate(items[i:i + T.BATCH])]
        rows = "\n".join(f"- 키 {k} · {v['platform']} @{v.get('channel')} · {int(v.get('views') or 0):,}회 · 검색어 '{v.get('q')}' · 제목: {str(v.get('title') or '')[:120]}"
                         for k, v in bt)
        got = {}
        for model in ("sonnet", "opus"):         # 소넷이 못 하면 오푸스(사장님 10-27)
            ans = T._ask(ASK + "\n\n" + rows + "\n\n답은 JSON 하나만.", model)
            got = {str(x.get("key")): {**x, "model": model} for x in ans.get("videos") or [] if x.get("key")}
            if len(got) >= len(bt) // 2:
                break
        for k, v in bt:
            book[v["url"]] = {**v, "judge": got.get(k), "t": time.strftime("%Y-%m-%d %H:%M")}
        outp.write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[검색] 판정 {min(i + T.BATCH, len(items))}/{len(items)}", flush=True)
    good = sorted([v for v in book.values() if (v.get("judge") or {}).get("korean_product") and (v["judge"].get("score") or 0) >= 7],
                  key=lambda v: (-(v["judge"].get("score") or 0), -int(v.get("views") or 0)))
    print(f"[검색] 끝 {time.time() - t0:.0f}초 · 한국 제품·7점+ {len(good)}편")
    for v in good[:25]:
        j = v["judge"]
        print(f"  {j.get('score')} {j.get('episode')} {v['platform']} @{v.get('channel')} {int(v.get('views') or 0):,} | {str(v.get('title'))[:60]} | {j.get('product')} | {v['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
