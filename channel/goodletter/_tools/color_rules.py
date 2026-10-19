# -*- coding: utf-8 -*-
"""굿레터 자막 채움색 규칙 세기(관제 097) — 줄판독 fill_hex 를 색 가족(흰·노랑·호박·주황·민트·기타)으로 접어 편·역할·화자·자리·연속 간격별로 센다.
    PYTHONUTF8=1 py channel/goodletter/_tools/color_rules.py [줄판독 폴더] [출력 json]
kal_analyze rules 의 emph 칸은 워커마다 적는 법이 달라(낱말 vs 줄 전체) 색 줄을 덜 센다 → 채움색으로 직접 센다."""
import sys, json, glob, colorsys, statistics as st
from collections import Counter, defaultdict
from pathlib import Path

def fam(h):
    h = (h or "").strip().lstrip("#")
    if len(h) < 6: return "기타"
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    H, S, V = colorsys.rgb_to_hsv(r, g, b)
    if S < 0.15: return "흰"
    d = H * 360
    if 150 <= d <= 190: return "민트"
    if 20 <= d < 33: return "주황"
    if 33 <= d < 44: return "호박"
    if 44 <= d < 65: return "노랑"
    return "기타"

def main(folder, out):
    rows = []
    per = {}
    for f in sorted(glob.glob(str(Path(folder) / "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        L = [l for l in d["lines"] if not str(l.get("layer", "")).startswith("원본")]
        big = [l for l in L if any(k in str(l.get("variant", "")) for k in ("제품명", "제품 이름", "큰글"))]
        talk = [l for l in L if l not in big]
        fams = [fam(l.get("fill_hex")) for l in talk]
        idx = [i for i, x in enumerate(fams) if x != "흰"]
        gaps = [b - a - 1 for a, b in zip(idx, idx[1:])]
        dur = float(d["dur"]); first = next((talk[i]["t0"] for i in idx), None)
        per[d["id"]] = {"talk_lines": len(talk), "colored": len(idx), "share": round(len(idx) / max(1, len(talk)), 2),
                        "families": dict(Counter(x for x in fams if x != "흰")), "white_gap_between_colored": gaps,
                        "first_colored_t": first, "last_line_colored": bool(fams and fams[-1] != "흰"),
                        "special_lines": [{"t0": l["t0"], "text": l["text"], "variant": l.get("variant"), "fill": l.get("fill_hex")} for l in big]}
        for i, l in enumerate(talk):
            pos = "훅" if l["t0"] < 3 else ("끝" if l["t0"] >= 0.85 * dur else "본문")
            rows.append({"id": d["id"], "fam": fams[i], "colored": fams[i] != "흰", "role": str(l.get("role", "")).split("·")[0],
                         "role_detail": l.get("role_detail"), "sp": str(l.get("speaker", ""))[:2], "pos": pos,
                         "q": "?" in l["text"], "text": l["text"]})
    def tab(key):
        c = defaultdict(lambda: [0, 0])
        for r in rows:
            c[r[key]][1] += 1; c[r[key]][0] += r["colored"]
        return {k: f"{a}/{n} ({a / n:.2f})" for k, (a, n) in sorted(c.items(), key=lambda kv: -kv[1][1])}
    res = {"per_video": per, "by_role": tab("role"), "by_speaker": tab("sp"), "by_pos": tab("pos"), "by_question": tab("q"),
           "overall": f"{sum(r['colored'] for r in rows)}/{len(rows)}",
           "family_total": dict(Counter(r["fam"] for r in rows)),
           "gap_median": st.median([g for v in per.values() for g in v["white_gap_between_colored"]] or [0]),
           "colored_texts": {fm: [f"{r['id'][:4]}:{r['text']}" for r in rows if r["fam"] == fm] for fm in ("노랑", "호박", "주황", "민트", "기타")}}
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k in ("overall", "family_total", "gap_median", "by_role", "by_speaker", "by_pos", "by_question"): print(k, res[k])
    for k, v in per.items(): print(k, {a: v[a] for a in ("talk_lines", "colored", "share", "families", "first_colored_t", "last_line_colored")}, [s["text"] for s in v["special_lines"]])

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "channel/goodletter/줄판독", sys.argv[2] if len(sys.argv) > 2 else "channel/goodletter/_kal/색규칙.json")
