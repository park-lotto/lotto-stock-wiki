"""검증 3 — 같은 상품이 한 번 터진 뒤 다른 영상에서 또 터지나(따라 터짐).
터진 상품 키워드별로 올라온 날짜를 줄 세워, 첫 히트 뒤 N일 안에 두 번째 히트가 나오는 비율을 잰다.
입력 work/hits_products.json + work/hits_dump.json · 출력 work/follow_check.json"""
import collections, datetime, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE, "..", "work")
dump = json.load(open(os.path.join(WORK, "hits_dump.json"), encoding="utf-8"))
meta = {x.get("shortcode"): x for v in dump.values() for x in v}
def day(t):
    try: return datetime.date.fromtimestamp(float(t)) if str(t).replace(".", "").isdigit() else datetime.date.fromisoformat(str(t)[:10])
    except Exception: return None
g = collections.defaultdict(list)
for r in json.load(open(os.path.join(WORK, "hits_products.json"), encoding="utf-8")):
    if not (r.get("is_product") and r.get("kw")): continue
    m = meta.get(r["shortcode"], {}); d = day(m.get("upload_ts") or m.get("first_seen"))
    if d: g[r["kw"].split(",")[0].strip()].append((d, r.get("views") or 0, m.get("owner") or m.get("username") or ""))
multi = {k: sorted(v) for k, v in g.items() if len(v) >= 2}
gaps = [(v[1][0] - v[0][0]).days for v in multi.values()]
out = {"keywords": len(g), "multi_hit_keywords": len(multi), "share_multi": round(100 * len(multi) / max(1, len(g))),
       "second_within_14d": sum(1 for x in gaps if x <= 14), "second_within_30d": sum(1 for x in gaps if x <= 30),
       "second_within_60d": sum(1 for x in gaps if x <= 60),
       "examples": sorted([{"kw": k, "n": len(v), "dates": [str(d) for d, _, _ in v][:6], "views": [w for _, w, _ in v][:6]}
                           for k, v in multi.items()], key=lambda e: -e["n"])[:25]}
json.dump(out, open(os.path.join(WORK, "follow_check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: v for k, v in out.items() if k != "examples"})
for e in out["examples"][:15]: print(" ", e)
