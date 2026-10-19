"""measure.json + out/*.json → 결과요약.json (스타일별 A vs B, 소재별) · 결과요약.md"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(HERE, "measure.json"), encoding="utf-8"))
STY = [52, 53, 54, 55, 56, 58, 59, 60, 61, 62, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, "even", "hdn"]


def pick(d):
    return {k: d.get(k) for k in ("chars", "lines", "first", "first_chars", "unsupported", "unsupported_claims", "pain_lines", "empty_slots",
                                   "made_numbers", "made_sellers", "made_nations", "copy_source_title")}


def name_of(sid):
    for f in os.listdir(os.path.join(HERE, "..", "cards")):
        if f.endswith(".json") and (f.startswith("%s_" % sid) or (sid == "even" and f.startswith("calcopy")) or (sid == "hdn" and f.startswith("hdn"))):
            return json.load(open(os.path.join(HERE, "..", "cards", f), encoding="utf-8")).get("name") or f
    return str(sid)


out, rows = [], ["| 스타일 | 소재 | A 글자 | B 글자(시안1/2) | A 근거없음 | B 근거없음 | A 지어냄 | B 지어냄 | A 불편줄 | B 불편줄 | A 빈칸 | B 빈칸 | B 시안 첫줄 유사도 | A 첫 줄 | B 첫 줄(시안1 / 시안2) |",
                 "|" + "---|" * 15]
for sid in STY:
    for src in ("glasspaint", "wrap"):
        a, b = M.get("A_%s_%s" % (sid, src)), M.get("B_%s_%s" % (sid, src))
        if not a and not b:
            continue
        ad = pick(a["drafts"][0]) if a else {}
        bd = [pick(x) for x in (b or {}).get("drafts", [])]
        item = {"id": sid, "name": name_of(sid), "src": src, "A": ad, "A_same_as": (a or {}).get("same_as"), "A_engine_status": (a or {}).get("engine_status"),
                "B": bd, "B_first_sim": (b or {}).get("first_sim")}
        out.append(item)
        made = lambda d: len((d.get("made_numbers") or []) + (d.get("made_sellers") or []) + (d.get("made_nations") or [])) if d else "-"
        rows.append("| %s %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            sid, item["name"], src, ad.get("chars", "-"), "/".join(str(x["chars"]) for x in bd) or "-",
            ad.get("unsupported", "-"), "/".join(str(x.get("unsupported", "-")) for x in bd) or "-",
            made(ad), "/".join(str(made(x)) for x in bd) or "-",
            ad.get("pain_lines", "-"), "/".join(str(x.get("pain_lines", "-")) for x in bd) or "-",
            ad.get("empty_slots", "-"), "/".join(str(x["empty_slots"]) for x in bd) or "-",
            item["B_first_sim"] if item["B_first_sim"] is not None else "-",
            (ad.get("first") or "-").replace("|", "/"), " / ".join((x["first"] or "").replace("|", "/") for x in bd) or "-"))


def avg(side, key):
    v = []
    for it in out:
        ds = [it["A"]] if side == "A" else it["B"]
        v += [d.get(key) for d in ds if d and isinstance(d.get(key), (int, float))]
    return round(sum(v) / len(v), 2) if v else None


tot = {s: {k: avg(s, k) for k in ("chars", "unsupported", "pain_lines", "empty_slots", "first_chars")} for s in ("A", "B")}
for s in ("A", "B"):
    ds = [d for it in out for d in ([it["A"]] if s == "A" else it["B"]) if d]
    tot[s]["made_any"] = sum(1 for d in ds if (d.get("made_numbers") or d.get("made_sellers") or d.get("made_nations")))
    tot[s]["n"] = len(ds)
sims = [it["B_first_sim"] for it in out if it["B_first_sim"] is not None]
tot["B"]["first_sim_avg"] = round(sum(sims) / len(sims), 2) if sims else None
json.dump({"평균": tot, "스타일별": out}, open(os.path.join(HERE, "결과요약.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(HERE, "결과요약.md"), "w", encoding="utf-8").write("평균: " + json.dumps(tot, ensure_ascii=False) + "\n\n" + "\n".join(rows) + "\n")
print(json.dumps(tot, ensure_ascii=False))
