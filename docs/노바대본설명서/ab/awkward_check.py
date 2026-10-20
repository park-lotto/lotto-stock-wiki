"""어색한 줄 검사(2026-10-20 사장님 '어색한건 검사하고') — out/<side>_*.json 전체를 버텍스 1회로 본다.
판정 기준: 한국어 문법·조사 틀림 / 앞뒤가 안 이어짐 / 말이 안 되는 낱말 조합 / 같은 말 반복 / 소리 내 읽기 어색.
분위기 과장·전언 말투·쇼츠 말버릇(이게 말도 안 되는 게 등)은 어색함으로 치지 않는다.
+ 기계 검사: 같은 파일(소재) 안에서 마무리 줄·미끼 앞 12자가 겹치는 시안.
사용: py awkward_check.py --side B4  → awkward_<side>.json
      py awkward_check.py --side B4 --apply  → 버텍스 없이 고친 줄을 끼워 out/<side>fix_*.json (고친 줄엔 fixed_from)"""
import argparse, glob, json, os, re
from collections import Counter

import ab_common as C

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = {"type": "object", "properties": {"flags": {"type": "array", "items": {"type": "object", "properties": {
    "key": {"type": "string"}, "line": {"type": "string"}, "why": {"type": "string"}, "fix": {"type": "string"}},
    "required": ["key", "line", "why", "fix"]}}}, "required": ["flags"]}


def ns(t):
    return re.sub(r"\s", "", t or "")


def apply(side):
    flags = json.load(open(os.path.join(HERE, "awkward_%s.json" % side), encoding="utf-8"))["flags"]
    n = 0
    for f in sorted(glob.glob(os.path.join(HERE, "out", "%s_*_*.json" % side))):
        base = os.path.basename(f)[:-5]
        d = json.load(open(f, encoding="utf-8"))
        for i, dd in enumerate(d.get("drafts") or []):
            for x in flags:
                if x["key"] != "%s#%d" % (base, i + 1):
                    continue
                for l in dd["lines"]:
                    if ns(l["text"]) == ns(x["line"]):
                        l["fixed_from"], l["text"], l["fix_why"] = l["text"], x["fix"].replace(",", ""), x["why"]
                        n += 1
        d["side"] = side + "fix"
        json.dump(d, open(os.path.join(HERE, "out", base.replace(side + "_", side + "fix_", 1) + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("고친 줄 %d / 판정 %d" % (n, len(flags)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", default="B4")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.apply:
        return apply(a.side)
    items, dup = [], {}
    for f in sorted(glob.glob(os.path.join(HERE, "out", "%s_*_*.json" % a.side))):
        base = os.path.basename(f)[:-5]
        d = json.load(open(f, encoding="utf-8"))
        lands, baits = Counter(), Counter()
        for i, dd in enumerate(d.get("drafts") or []):
            ls = [l["text"] for l in dd["lines"]]
            items.append("[%s#%d]\n%s" % (base, i + 1, "\n".join(ls)))
            lands[ns(ls[-1])[:12]] += 1
            if len(ls) > 1:
                baits[ns(ls[1])[:12]] += 1
        dup[base] = {"마무리 겹침": {k: v for k, v in lands.items() if v > 1}, "미끼 겹침": {k: v for k, v in baits.items() if v > 1}}
    prompt = ("너는 한국어 쇼츠 대본 교정자다. 아래 대본들에서 **어색한 줄만** 골라라.\n"
              "어색함 = 문법·조사 틀림 / 앞뒤가 안 이어짐 / 말이 안 되는 낱말 조합 / 한 줄 안 같은 말 반복 / 소리 내 읽으면 걸림.\n"
              "어색함이 아닌 것 = 분위기 과장(난리·떼돈·돈방석), 실물 히트 말버릇(좁아 죽겠나요·턱이 빠졌대요), 전언 말투(~다고·~다는데·~했다더라), 쇼츠 연결어(이게 말도 안 되는 게·심지어·근데 진짜 충격적인 포인트는).\n"
              "key 는 대괄호 안 이름 그대로, line 은 원문 그대로, why 는 한 줄, fix 는 고친 줄.\n\n" + "\n\n".join(items))
    r = C.vertex_json(prompt, SCHEMA, tag="awkward:%s" % a.side)
    flags = r.get("flags") or []
    json.dump({"flags": flags, "dup": dup, "calls": len(C.CALLS)}, open(os.path.join(HERE, "awkward_%s.json" % a.side), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("대본 %d편 · 어색한 줄 %d · 버텍스 %d회" % (len(items), len(flags), len(C.CALLS)))
    for x in flags:
        print(" %s | %s\n    → %s (%s)" % (x["key"], x["line"], x["fix"], x["why"]))
    for k, v in dup.items():
        if v["마무리 겹침"] or v["미끼 겹침"]:
            print(" 겹침", k, v)


if __name__ == "__main__":
    main()
