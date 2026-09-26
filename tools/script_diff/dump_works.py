# -*- coding: utf-8 -*-
"""이야기 작가로 대본이 나온 최근 작업을 **읽기만** 해서 떠 온다 — compare.py의 입력.
  (서버, repo 폴더에서) python3 tools/script_diff/dump_works.py <작업수> <출력.json> [일수=4]

작업마다: 씨앗 원문·제품·고른 스타일 id·그때 나온 대본(라이브)·매칭 job(추출). 제품이 겹치면 하나만(다양하게).
"""
import sys, json, sqlite3, datetime
sys.path.insert(0, ".")
from shopping_shorts.store import Store
N, OUT = int(sys.argv[1]), sys.argv[2]
DAYS = float(sys.argv[3]) if len(sys.argv) > 3 else 4
st = Store("shopping_shorts/data/reference.db")
c = sqlite3.connect("file:shopping_shorts/data/reference.db?mode=ro", uri=True)
since = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=DAYS)).isoformat()
sp_all = {s.get("id"): s for s in st.list_spines()}
out, seen = {"works": [], "spines": {}}, set()
for wid, jid, sj in c.execute("select work_id, job_id, state_json from produce_works where updated_at>? order by updated_at desc", (since,)):
    try:
        s2 = json.loads(sj or "{}").get("s2") or {}
    except Exception:
        continue
    ds = [d for d in s2.get("drafts") or [] if d.get("made_by") == "이야기작가"]
    seed = (s2.get("seed") or {}).get("text") or ""
    prod = (s2.get("materials") or {}).get("topic_product") or ""
    if not ds or len(seed) < 80 or not jid or prod in seen:
        continue
    job = st.get_mix_job(jid)
    if not job or not job.get("extract"):
        continue
    seen.add(prod)
    ids = [d.get("style_id") for d in ds if d.get("style_id") is not None]
    out["works"].append({"work_id": wid, "job_id": jid, "seed_text": seed, "product": prod, "style_ids": ids,
                         "old_drafts": ds, "job": {"job_id": jid, "extract": job.get("extract"),
                                                   "backbone_main": job.get("backbone_main"), "urls": job.get("urls")}})
    for i in ids:
        out["spines"][str(i)] = sp_all.get(i)
    if len(out["works"]) >= N:
        break
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, default=str)
print("works", len(out["works"]), [w["product"] for w in out["works"]])
