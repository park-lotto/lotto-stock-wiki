"""A/B 결과를 같은 자로 잰다 — out/*.json → measure.json · measure.md
기계 측정: 글자 수(공백 제외) · 줄 수 · 첫 줄 글자 수 · 빈 칸 · 숫자/판매처/나라 지어냄(근거·장면 글에 없는 낱말) ·
          소재 제목과 7자 이상 같은 구절 · 시안끼리 첫 줄 유사도.
모델 판정(같은 버텍스 모델): ①근거 없는 객관 주장 수 = 숏템메이커 script_generate._speaker_judge(_CLAIM_JUDGE_RULE) 그대로
                            ②불편(고충) 서술 줄 수 — 줄마다 "제품을 쓰기 전 겪던 불편·고충을 말하는 줄인가" 1회.
사용: py ab_measure.py [--side A,B] [--no-judge]"""
import argparse, difflib, glob, json, os, re

import ab_common as C

SELLERS = ["코스트코", "다이소", "쿠팡", "이마트", "홈플러스", "올리브영", "아마존", "알리", "테무", "네이버"]
NATIONS = ["일본", "미국", "독일", "중국", "한국", "프랑스", "영국", "스웨덴", "이탈리아", "대만"]
PAIN_SCHEMA = {"type": "object", "properties": {"pain_lines": {"type": "array", "items": {"type": "integer"}}}, "required": ["pain_lines"]}


def nospace(t):
    return re.sub(r"\s", "", t or "")


def common7(a, b):
    a, b = nospace(a), nospace(b)
    m = difflib.SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b))
    return a[m.a:m.a + m.size] if m.size >= 7 else ""


def evidence(inp):
    items = [{"id": f["id"], "kind": "verified_product_facts", "text": f["text"]} for f in inp["facts"]]
    items += [{"id": c, "kind": "source_observations", "text": t} for c, t in inp["texts"].items()]
    return {"items": items}


def judge(text, inp):
    from shopping_shorts import script_generate as sg
    r = sg._speaker_judge(text, inp["product"], evidence(inp)) or {}
    bad = [x for x in (r.get("claim_checks") or []) if x.get("kind") == "objective" and not x.get("supported")]
    return {"unsupported": len(bad), "unsupported_claims": [x.get("claim") for x in bad], "judged": bool(r)}


def pain_count(lines):
    body = "\n".join("%d. %s" % (i, l) for i, l in enumerate(lines))
    d = C.vertex_json("쇼핑 쇼츠 대본의 줄 목록이다. **제품을 쓰기 전에 겪던 불편·고충·괴로운 장면**을 말하는 줄의 번호만 pain_lines 에 담아라"
                      "(제품 효과·화제·감탄·정체 공개 줄은 빼라).\n" + body, PAIN_SCHEMA, tag="measure:pain")
    return len(d.get("pain_lines") or [])


def measure_draft(dr, inp, do_judge):
    lines = [l.get("text") or "" for l in dr.get("lines") or []]
    text = "\n".join(lines)
    ev = " ".join([f["text"] for f in inp["facts"]] + list(inp["texts"].values()))
    nums = [n for n in re.findall(r"\d+(?:\.\d+)?", text) if n not in ev]
    m = {"chars": len(nospace(text)), "lines": len(lines), "first": lines[0] if lines else "", "first_chars": len(nospace(lines[0])) if lines else 0,
         "empty_slots": sum(1 for l in lines if len(nospace(l)) < 3),
         "made_numbers": nums, "made_sellers": [s for s in SELLERS if s in text and s not in ev],
         "made_nations": [s for s in NATIONS if s in text and s not in ev],
         "copy_source_title": common7(lines[0] if lines else "", inp["source_title"])}
    if do_judge and text.strip():
        m.update(judge(text, inp))
        m["pain_lines"] = pain_count(lines)
    return m


def _card_strings(o):
    if isinstance(o, dict):
        return " ".join(_card_strings(v) for v in o.values())
    if isinstance(o, list):
        return " ".join(_card_strings(v) for v in o)
    return o if isinstance(o, str) else ""


def measure_v2():
    """2차 판 측정(checks_v2 ①~⑦ + 사실 지어냄/분위기 과장 분리) — A(1차 결과 재사용) vs B2 → measure_v2.json"""
    import checks_v2 as K
    import ab_run_v2 as R2
    inps = {k: json.load(open(os.path.join(C.HERE, "inputs", k + ".json"), encoding="utf-8")) for k in ("glasspaint", "wrap")}
    old = json.load(open(os.path.join(C.HERE, "measure.json"), encoding="utf-8"))
    path = os.path.join(C.HERE, "measure_v2.json")
    res = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    jobs = []
    for cid in R2.CARDS:
        aid = R2.A_OF.get(cid, cid)
        for src in ("glasspaint", "wrap"):
            jobs.append(("A", aid, src, os.path.join(C.HERE, "out", "A_%s_%s.json" % (aid, src))))
            jobs.append(("B2", cid, src, os.path.join(C.HERE, "out", "B2_%s_%s.json" % (cid, src))))
    for side, sid, src, f in jobs:
        key = "%s_%s_%s" % (side, sid, src)
        if key in res or not os.path.exists(f):
            continue
        r = json.load(open(f, encoding="utf-8"))
        inp = inps[src]
        ev = " ".join([x["text"] for x in inp["facts"]] + list(inp["texts"].values()))
        if side == "A":
            source = r.get("prompt") or ""
            prev = (old.get("A_%s_%s" % (sid, src)) or {}).get("drafts") or [{}]
        else:
            source = _card_strings(json.load(open(R2.card_file(sid), encoding="utf-8")))
            prev = []
        ds = []
        for i, dr in enumerate(r.get("drafts") or []):
            lines = [l.get("text") or "" for l in dr.get("lines") or []]
            m = {"lines_text": lines, "chars": len(nospace("".join(lines))), "lines": len(lines), "first": lines[0] if lines else "",
                 "nonron": K.has_nonron(lines), "copy": K.copy_fragments(lines, source, ev), "cta": K.cta_count(lines),
                 "made": K.made_facts(lines, ev), "weak_end": K.weak_ending(lines)}
            if i < len(prev) and prev[i].get("judged"):
                claims = prev[i].get("unsupported_claims") or []
            else:
                claims = judge("\n".join(lines), inp).get("unsupported_claims") or []
            mood, fact = K.split_claims(claims)
            m.update(unsupported_mood=mood, unsupported_fact=fact)
            sc, why = K.judge_first(m["first"], C.vertex_json) if m["first"] else (0, {})
            m.update(first_score=sc, first_why=why.get("why", ""))
            ds.append(m)
        res[key] = {"side": side, "id": sid, "src": src, "drafts": ds}
        json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        d0 = ds[0] if ds else {}
        print("%-22s 첫줄 %s · 사실지어냄 %d · 논란 %d · 7자겹침 %d · CTA %d · 약한끝 %s" % (key, d0.get("first_score"), len(d0.get("unsupported_fact") or []),
              len(d0.get("nonron") or []), len(d0.get("copy") or []), d0.get("cta", 0), d0.get("weak_end")), flush=True)
    # ⑥ 같은 소재 스타일끼리 뼈대 유사도(같은 쪽 안에서)
    for key, v in res.items():
        others = {k2: v2["drafts"][0]["lines_text"] for k2, v2 in res.items() if k2 != key and v2["side"] == v["side"] and v2["src"] == v["src"]
                  and v2["drafts"] and v2["id"] != v["id"]}
        for d in v["drafts"]:
            d["skel_sim"], d["skel_with"] = K.skeleton_sim(d["lines_text"], others)
    json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    import time
    json.dump(C.CALLS, open(os.path.join(C.HERE, "out", "_calls_measure_v2_%d.json" % int(time.time())), "w", encoding="utf-8"), ensure_ascii=False)
    print("판정 호출 %d" % len(C.CALLS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", default="A,B")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--mfile", default="measure.json")
    ap.add_argument("--only", default="")
    ap.add_argument("--v2", action="store_true", help="2차 판 측정(checks_v2) → measure_v2.json")
    a = ap.parse_args()
    if a.v2:
        C.patch_shortem()
        return measure_v2()
    C.patch_shortem()
    inps = {k: json.load(open(os.path.join(C.HERE, "inputs", k + ".json"), encoding="utf-8")) for k in ("glasspaint", "wrap")}
    path = os.path.join(C.HERE, a.mfile)
    res = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for side in a.side.split(","):
        for f in sorted(glob.glob(os.path.join(C.HERE, "out", "%s_*.json" % side))):
            name = os.path.basename(f)[:-5]
            if a.only and not any(name.startswith("%s_%s_" % (side, x)) for x in a.only.split(",")):
                continue
            if name.startswith(side + "_") and name.count("_") >= 2 and not name.startswith("_") and name not in res:
                r = json.load(open(f, encoding="utf-8"))
                if "drafts" not in r:
                    continue
                inp = inps[r["src"]]
                ds = [measure_draft(d, inp, not a.no_judge) for d in r["drafts"]]
                sim = round(difflib.SequenceMatcher(None, nospace(ds[0]["first"]), nospace(ds[1]["first"])).ratio(), 2) if len(ds) > 1 else None
                res[name] = {"side": side, "id": r["id"], "src": r["src"], "drafts": ds, "first_sim": sim,
                             "same_as": r.get("same_as"), "engine_status": r.get("engine_status")}
                json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                d0 = ds[0]
                print("%-22s %3d자 %2d줄 근거없음 %s 불편줄 %s 지어냄 %s" % (name, d0["chars"], d0["lines"], d0.get("unsupported", "-"), d0.get("pain_lines", "-"),
                                                             (d0["made_numbers"] + d0["made_sellers"] + d0["made_nations"]) or ""), flush=True)
    rows = ["| 결과 | 글자 | 줄 | 첫 줄 글자 | 근거 없음 | 불편 줄 | 지어낸 숫자·판매처·나라 | 소재 제목 베낌 | 시안 첫 줄 유사도 |", "|---|---|---|---|---|---|---|---|---|"]
    for k in sorted(res):
        v = res[k]
        for i, d in enumerate(v["drafts"]):
            rows.append("| %s%s | %d | %d | %d | %s | %s | %s | %s | %s |" % (k, "" if len(v["drafts"]) == 1 else " 시안%d" % (i + 1), d["chars"], d["lines"], d["first_chars"],
                        d.get("unsupported", "-"), d.get("pain_lines", "-"), ", ".join(d["made_numbers"] + d["made_sellers"] + d["made_nations"]) or "-",
                        d["copy_source_title"] or "-", v["first_sim"] if v["first_sim"] is not None else "-"))
    open(os.path.join(C.HERE, "measure.md"), "w", encoding="utf-8").write("\n".join(rows) + "\n")
    import time
    json.dump(C.CALLS, open(os.path.join(C.HERE, "out", "_calls_measure_%d.json" % int(time.time())), "w", encoding="utf-8"), ensure_ascii=False)
    print("판정 호출 %d" % len(C.CALLS))


if __name__ == "__main__":
    main()
