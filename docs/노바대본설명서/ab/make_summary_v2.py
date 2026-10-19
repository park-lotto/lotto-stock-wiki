"""measure_v2.json → 결과요약_v2.json · 결과요약_v2.md · pairs_v2.txt(스타일·소재별 A / B2 시안1 / B2 시안2 전문)"""
import json, os

import ab_run_v2 as R2

HERE = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(HERE, "measure_v2.json"), encoding="utf-8"))
NAME = {"jungche": "정체 숨김(55·65·74·75·76 통합)", "oyong": "오용·활용법(56·70~73 통합)", "60": "60 개발자도 무릎 탁", "66": "66 답답했잖아",
        "52": "52 가족갈등 반전형", "53": "53 단정 명령형", "54": "54 물건 발견형", "58": "58 금지경고형", "59": "59 사회증거형", "61": "61 정체의문형",
        "62": "62 무지후회형", "even": "이븐쇼핑", "hdn": "두유노홈디노"}


def row(d):
    made = sum(len(v) for v in (d.get("made") or {}).values())
    return {"chars": d["chars"], "first_score": d.get("first_score"), "fact": len(d.get("unsupported_fact") or []), "mood": len(d.get("unsupported_mood") or []),
            "made": made, "nonron": len(d.get("nonron") or []), "copy": len(d.get("copy") or []), "cta": d.get("cta", 0), "weak_end": len(d.get("weak_end") or []),
            "skel": d.get("skel_sim")}


items, md = [], ["| 스타일 | 소재 | 쪽 | 첫줄 점수(0~2) | 사실 지어냄(판정) | 분위기 과장(판정) | 고유명사·숫자 지어냄 | 논란 | 7자 겹침 | 댓글 줄 | 약한 끝 | 뼈대 유사도 | 글자 | 첫 줄 |",
                 "|" + "---|" * 14]
pairs = []
for cid in R2.CARDS:
    aid = R2.A_OF.get(cid, cid)
    for src in ("glasspaint", "wrap"):
        a, b = M.get("A_%s_%s" % (aid, src)), M.get("B2_%s_%s" % (cid, src))
        it = {"id": cid, "name": NAME[cid], "src": src, "A_id": aid, "A": [row(d) for d in (a or {}).get("drafts", [])][:1], "B2": [row(d) for d in (b or {}).get("drafts", [])]}
        items.append(it)
        for side, ds, raw in (("A", it["A"], (a or {}).get("drafts", [])[:1]), ("B2", it["B2"], (b or {}).get("drafts", []))):
            for i, (r, d) in enumerate(zip(ds, raw)):
                md.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    NAME[cid], src, side + ("" if side == "A" else " 시안%d" % (i + 1)), r["first_score"], r["fact"], r["mood"], r["made"], r["nonron"], r["copy"],
                    r["cta"], r["weak_end"], r["skel"], r["chars"], (d.get("first") or "").replace("|", "/")))
        pairs.append("## %s · %s (A = %s)" % (NAME[cid], src, aid))
        for side, raw in (("A", (a or {}).get("drafts", [])[:1]), ("B2", (b or {}).get("drafts", []))):
            for i, d in enumerate(raw):
                pairs.append("%s%s: %s" % (side, "" if side == "A" else " 시안%d" % (i + 1), " / ".join(d.get("lines_text") or [])))
        pairs.append("")


def avg(side, key):
    v = [r[key] for it in items for r in it[side] if isinstance(r.get(key), (int, float))]
    return round(sum(v) / len(v), 2) if v else None


tot = {s: {k: avg(s, k) for k in ("first_score", "fact", "mood", "made", "nonron", "copy", "cta", "weak_end", "skel", "chars")} for s in ("A", "B2")}
for s in ("A", "B2"):
    rs = [r for it in items for r in it[s]]
    tot[s]["n"] = len(rs)
    tot[s]["cta2plus"] = sum(1 for r in rs if r["cta"] >= 2)
    tot[s]["first_full"] = sum(1 for r in rs if r["first_score"] == 2)
json.dump({"평균": tot, "스타일별": items}, open(os.path.join(HERE, "결과요약_v2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(HERE, "결과요약_v2.md"), "w", encoding="utf-8").write("평균: " + json.dumps(tot, ensure_ascii=False) + "\n\n" + "\n".join(md) + "\n")
open(os.path.join(HERE, "pairs_v2.txt"), "w", encoding="utf-8").write("\n".join(pairs))
print(json.dumps(tot, ensure_ascii=False))
