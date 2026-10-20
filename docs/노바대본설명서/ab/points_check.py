"""잉?·와우 포인트 검사(버텍스 없음, 2026-10-20) — 설명서 ing_wow 칸 지도로 대본을 잰다.
잉: 숨기는 칸이 앞 1/3 안에 있고 · 그 칸들에 답 칸의 제품 낱말이 새지 않았고 · 답 칸이 뒤에 있나
와우: 와우 칸을 다 채웠나 · 연결어 머리가 정해진 칸은 그 머리로 시작하나 · 와우끼리 같은 말머리 반복 없나
사용: py points_check.py --side B4fix [--cards ../cards_v4]  → points_<side>.json"""
import argparse, glob, json, os, re

import first_line_check as F

HERE = os.path.dirname(os.path.abspath(__file__))


def ns(t):
    return re.sub(r"\s", "", t or "")


def check(lines, pm):
    slots = [l.get("slot") for l in lines]
    texts = [l.get("text", "") for l in lines]
    out = []
    ing_idx = [i for i, s in enumerate(slots) if s in pm["ing"]]
    ans = [i for i, s in enumerate(slots) if s in pm["answer"].split("|")]
    if not ing_idx or min(ing_idx) >= max(2, len(lines) // 3 + 1):
        out.append("잉 없음(앞 1/3)")
    if not ans or (ing_idx and ans[0] <= min(ing_idx)):
        out.append("잉 답 칸 없음")
    else:
        m = re.search(r"(?:이건\s*)?바로\s*(.+)$", texts[ans[0]])
        words = [w for w in (m.group(1).split()[:-1] if m else []) if len(w) >= 2]   # 마지막 낱말 = 제품군(랩·페인트)은 제목에 써도 된다
        leak = [w for w in words if any(w in texts[i] for i in ing_idx)]
        if leak:
            out.append("잉 칸에 정체 샘(%s)" % ",".join(leak))
    got = [k for k in pm["wow"] if any(s in k.split("|") for s in slots)]
    if len(got) < len(pm["wow"]):
        out.append("와우 %d/%d" % (len(got), len(pm["wow"])))
    heads = []
    for k, h in zip(pm["wow"], pm["wow_heads"]):
        idx = [i for i, s in enumerate(slots) if s in k.split("|")]
        if h and len(idx) > 1:          # 'limit|solve' — 연결어가 붙은 쪽을 와우 줄로 본다
            hit = [i for i in idx if any(ns(texts[i]).startswith(ns(x.replace("(진짜) ", "")).strip()) or ns(texts[i]).startswith(ns(x.replace("(진짜) ", "진짜 "))) for x in h.split("/"))]
            idx = hit or idx
        if not idx:
            continue
        t = ns(texts[idx[0]])
        heads.append(t[:4])
        if h and not any(t.startswith(ns(re.sub(r"\(진짜\)\s*", "", x)).strip()) or t.startswith(ns(x.replace("(진짜) ", "진짜 ")))
                         for x in h.split("/")):
            out.append("와우 머리 다름(%s)" % k)
    if len(heads) != len(set(heads)):
        out.append("와우 말머리 반복")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", default="B4fix")
    ap.add_argument("--cards", default=os.path.join(HERE, "..", "cards_v4"))
    a = ap.parse_args()
    res, n, bad = {}, 0, 0
    for f in sorted(glob.glob(os.path.join(HERE, "out", "%s_*_*.json" % a.side))):
        base = os.path.basename(f)[:-5]
        cid = base.split("_")[1]
        pm = F.card_for(cid, a.cards).get("ing_wow", {}).get("이 스타일 칸")
        if not pm:
            print("카드에 ing_wow 없음", base); continue
        for i, dd in enumerate(json.load(open(f, encoding="utf-8")).get("drafts") or []):
            p = check(dd["lines"], pm)
            n += 1; bad += bool(p)
            res["%s#%d" % (base, i + 1)] = p
            if p:
                print(" %s#%d %s" % (base, i + 1, " · ".join(p)))
    print("[%s] 대본 %d편 · 잉·와우 통과 %d" % (a.side, n, n - bad))
    json.dump(res, open(os.path.join(HERE, "points_%s.json" % a.side), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
