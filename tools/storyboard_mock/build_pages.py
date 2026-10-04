# 1단계(재료) · 2단계(스토리보드=대본) 페이지 틀 — 3.6 시험 결과(/tmp/sbtrial_*.json)와 실제 썸네일로. 손으로 고친 내용 없음.
import json, os, io
T = os.environ["TEMP"]
D = json.load(open(os.path.join(T, "mock_data.json"), encoding="utf-8"))
JOBS = []
for jid, title in (("f3d86941c30b", "스마트폰 CPL 편광 필터"), ("9fed785a6af4", "소금빵 (레몬·유자 크림)")):
    R = json.load(open(os.path.join(T, "sbtrial_%s.json" % jid), encoding="utf-8"))
    pieces = {}
    for v in D[jid]:
        for s in v["segs"]:
            pieces[s["id"]] = {"th": s["th"], "sec": s["sec"], "desc": s["desc"], "vid": v["vid"]}
    S36 = json.load(open(os.path.join(T, "story36.json"), encoding="utf-8"))[jid]
    vids = [{"vid": v["vid"], "prod": (v["brief"].get("product") or "")[:22], "th": v["segs"][0]["th"] if v["segs"] else "", "n": len(v["segs"]),
             "brief": v["brief"], "story": (S36.get(v["vid"]) or {}).get("story") or [], "dur": (S36.get(v["vid"]) or {}).get("dur"),
             "talk": (S36.get(v["vid"]) or {}).get("talk")} for v in D[jid]]
    JOBS.append({"jid": jid, "title": title, "kind": R["inventory"].get("kind"), "vids": vids, "pieces": pieces,
                 "groups": R["inventory"]["groups"], "tag_of": R["inventory"].get("tag_of") or {}, "missing": R["inventory"].get("missing") or [],
                 "star": R["star"], "styles": R["styles"], "boards": R["boards"], "fam_names": R["family_names"], "fam_first": R.get("family_first") or {},
                 "secs": R["secs"]})
data = json.dumps(JOBS, ensure_ascii=False)
html = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages_tpl.html"), encoding="utf-8").read().replace("/*DATA*/[]", data).replace("/*FAMS*/[]", open(os.path.join(T, "sb_fams.json"), encoding="utf-8").read().strip())
dst = r"C:/Users/TheRose/Desktop/1·2단계_페이지틀_20261004.html"
io.open(dst, "w", encoding="utf-8").write(html)
print("ok", os.path.getsize(dst))
