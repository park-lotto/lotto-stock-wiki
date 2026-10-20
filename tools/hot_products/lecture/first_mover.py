"""검증 — '먼저 올린 사람이 조회수를 다 가져간다'(강의 CvcAM7EelXE). 같은 상품 키워드로 터진 영상들을 올라온 순으로 세워
첫 영상 조회수 vs 뒤따른 영상 조회수를 비교한다. 입력 work/follow_check 와 같은 정답지(hits_products + hits_dump)."""
import collections, datetime, json, os, statistics, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.join(HERE, "..", "work")
dump = json.load(open(os.path.join(WORK, "hits_dump.json"), encoding="utf-8"))
meta = {x.get("shortcode"): x for v in dump.values() for x in v}
def ts(m):
    t = m.get("upload_ts") or m.get("first_seen")
    try: return float(t) if str(t).replace(".", "").isdigit() else datetime.datetime.fromisoformat(str(t)[:19]).timestamp()
    except Exception: return None
g = collections.defaultdict(list)
for r in json.load(open(os.path.join(WORK, "hits_products.json"), encoding="utf-8")):
    if r.get("is_product") and r.get("kw"):
        m = meta.get(r["shortcode"], {}); t = ts(m)
        if t: g[r["kw"].split(",")[0].strip()].append((t, m.get("views") or 0, m.get("username") or ""))
rows = []
for k, v in g.items():
    if len(v) < 2: continue
    v.sort(); first = v[0][1]; rest = [x[1] for x in v[1:]]
    rows.append((k, first, statistics.median(rest), len(v), len({x[2] for x in v})))
share = [f / (f + sum(x[1] for x in g[k][1:])) for k, f, _, _, _ in rows]
print("여러 번 터진 상품", len(rows), "| 첫 영상이 뒤따른 영상 중앙값보다 큼", sum(1 for _, f, m, _, _ in rows if f > m), "/", len(rows))
print("첫 영상이 그 상품 전체 조회수에서 차지한 몫 중앙값", round(100 * statistics.median(share)), "%")
for k, f, m, n, u in sorted(rows, key=lambda x: -x[3])[:15]: print(f"  {k:<14} 영상{n} 계정{u} 첫 {f:,} / 뒤 중앙 {int(m):,}")
