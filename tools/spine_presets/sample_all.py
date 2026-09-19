# 대본 스타일(스파인) **전부**를 같은 재료로 1편씩 실제로 뽑아 본다 — 렌더 없음 (2026-09-19 사장님
# "대본스타일들이 다 준비된건지 작동이 잘된건지 전체적으로 볼 수 있게").
# 사용(서버):  python3 sample_all.py [job_id] [spine_id,...]   → /tmp/spine_samples.json
# 결과는 spine_viewer.py 5번째 인자로 넘기면 스타일 카드마다 '실제로 뽑은 대본'이 붙는다.
import json, sys, time
sys.path.insert(0, "/tmp/ab")
from batch_scripts import NUM, COUNTRY, CLAIM, DB
from shopping_shorts.store import Store
from shopping_shorts import backbone_assemble as ba

JOB = sys.argv[1] if len(sys.argv) > 1 else "68dc7e13dc23"      # 볼펜(한셉트 제로) — 재료 7편
ONLY = {int(x) for x in sys.argv[2].split(",")} if len(sys.argv) > 2 else None

st = Store(DB)
job = st.get_mix_job(JOB)
srcs = ba.sources_from_extract(job.get("extract") or {})
ko = lambda t: sum(1 for c in t if "가" <= c <= "힣") / max(1, sum(1 for c in t if c.isalpha()))
bb = max([s for s in srcs if ko(s.get("full_text") or "") > 0.7] or srcs, key=lambda s: len(s.get("full_text") or ""))
src_text = " ".join((s.get("full_text") or "") + " " + " ".join(
    (g.get("scene_desc") or "") + (g.get("text") or "") for g in (s.get("segments") or [])) for s in srcs)

import sqlite3
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
ids = [r[0] for r in con.execute("select id from spine where status='approved' and templates_json is not null and templates_json not in ('','{}') order by id")]
out = {"job": JOB, "product_hint": (bb.get("full_text") or "")[:40], "spines": {}}
for sid in ids:
    if ONLY and sid not in ONLY:
        continue
    note, t0 = {}, time.time()
    try:
        given, bs, meta = ba.assemble(srcs, bb["video_id"], st, spine_id=sid, seed="sample" + JOB, note=note)
    except Exception as e:      # noqa: BLE001
        given, bs, meta = None, None, {}
        note["error"] = repr(e)[:200]
    r = {"sec": round(time.time() - t0, 1), "switched": note.get("style_switched")}
    if not given:
        r.update(ok=False, why=note.get("reason") or note.get("error") or str(note.get("detail") or "")[:160])
    else:
        lines = [l for l in given.split("\n") if l.strip()]
        segs = [len((b or {}).get("segs") or []) for b in (bs or [])]
        r.update(ok=True, lines=lines, spine=(meta.get("spine") or {}).get("name"),
                 cuts=sum(segs), empty_lines=sum(1 for n in segs if n == 0),
                 fake_num=[m.group(0) for l in lines for m in NUM.finditer(l) if m.group(0).strip() and m.group(0).split()[0] not in src_text],
                 country=[m.group(0) for l in lines for m in COUNTRY.finditer(l) if m.group(0) not in src_text],
                 claim=[m.group(0) for l in lines for m in CLAIM.finditer(l) if m.group(0) not in src_text],
                 leak=sum(1 for l in lines if "{" in l or "}" in l),
                 polite=sum(1 for l in lines if __import__("re").search(r"(요|니다|세요)[.!?]?$", l.strip())))
    out["spines"][str(sid)] = r
    print(sid, "OK" if r.get("ok") else "실패", r.get("sec"), r.get("why") or len(r.get("lines") or []), flush=True)
json.dump(out, open("/tmp/spine_samples.json", "w"), ensure_ascii=False, indent=1)
ok = [v for v in out["spines"].values() if v.get("ok")]
print("요약: 스타일 %d · 대본 나옴 %d · 실패 %d" % (len(out["spines"]), len(ok), len(out["spines"]) - len(ok)))
