# 히트작 대본 → 칸별 템플릿 (2026-09-19 사장님 "대본템플릿화가 전혀 안 되었고 어떻게 일반화시켜 착착 맞게").
# 사용(서버):  python3 templatize_hits.py hits_cls.json 지인증언형 out.json
#
# 한 편마다 모델이 ①고정 칸으로 자르고 ②제품 이야기를 고정 빈칸으로 바꾼다. 그 뒤 **코드가 검증**한다:
#   (a) 칸 원문이 대본에 실제로 있다(띄어쓰기 무시)  (b) 빈칸에 원래 값을 다시 넣으면 칸 원문과 똑같다
#   (c) 빈칸은 고정 목록 안의 이름만.  하나라도 어기면 그 칸 템플릿은 버린다(모델이 고쳐 쓴 문장 차단).
import json, re, sys, time
sys.path.insert(0, "/tmp/ab")
from shopping_shorts import script_generate as sg

ROLES = ["훅", "계기", "불편", "전환", "작동", "심지어", "감정", "CTA"]
SLOTS = {"인물": "등장 인물(와이프·친구·옆 텐트 형님)", "장소": "장소·상황(캠핑·집들이)", "반응": "놀란 반응(소리질렀어요)",
         "제품군": "제품 종류 이름(책상·지퍼백)", "기존물건": "대신하던 물건(숯·토치)", "불편": "기존의 불편",
         "동작": "쓰는 동작(버튼 누르기)", "효능1": "첫 효능", "효능2": "두 번째 효능", "효능3": "세 번째 효능",
         "수치": "구체 숫자(1.3KG·24시간)", "출처": "출처·권위(일본·무인양품·약사)", "결과": "쓴 뒤 달라진 것", "키워드": "CTA 댓글 단어"}
SCHEMA = {"type": "object", "properties": {"cells": {"type": "array", "items": {"type": "object", "properties": {
    "role": {"type": "string", "enum": ROLES}, "original": {"type": "string"}, "template": {"type": "string"},
    "values": {"type": "array", "items": {"type": "object", "properties": {"slot": {"type": "string"}, "value": {"type": "string"}},
                                          "required": ["slot", "value"]}}},
    "required": ["role", "original", "template", "values"]}}}, "required": ["cells"]}


def prompt(text):
    slots = "\n".join("- {%s}: %s" % kv for kv in SLOTS.items())
    return f"""쇼핑 숏폼 대본을 칸으로 자르고, 칸마다 제품에 따라 바뀌는 부분만 빈칸으로 바꿔라.

칸(순서대로, 반복·생략 가능): {", ".join(ROLES)}
- original: 그 칸에 해당하는 대본 원문을 **한 글자도 고치지 말고** 그대로 복사
- template: original에서 제품마다 달라질 말만 아래 빈칸으로 바꾼 것. 나머지 말투·어미·연결어는 **그대로 둔다**
- values: 각 빈칸에 원래 들어있던 말(template의 빈칸에 이 값을 넣으면 original과 정확히 같아야 한다)
빈칸(이 이름만 쓸 것):
{slots}

대본:
{text}"""


def norm(s):
    return re.sub(r"\s+", "", s or "")


def check(cell, text):
    o, t = cell.get("original") or "", cell.get("template") or ""
    names = re.findall(r"\{([^{}]+)\}", t)
    if not o or norm(o) not in norm(text):
        return "원문에 없음"
    if any(n not in SLOTS for n in names):
        return "모르는 빈칸"
    vals = {}
    for v in cell.get("values") or []:
        vals.setdefault((v.get("slot") or "").strip("{} "), []).append(v.get("value") or "")
    filled = t
    for n in names:
        if not vals.get(n):
            return "값 없음"
        filled = filled.replace("{%s}" % n, vals[n].pop(0), 1)
    if norm(filled) != norm(o):
        return "복원 불일치"
    if not names and cell.get("role") not in ("감정", "전환", "CTA"):
        return "빈칸 없음(제품 말이 그대로)"
    return ""


def recheck(dst):
    d = json.load(open(dst, encoding="utf-8"))
    for x in d:
        for c in x["cells"]:
            c["why_bad"] = check(c, x["text"])
    json.dump(d, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    import collections
    print(collections.Counter(c["why_bad"] or "통과" for x in d for c in x["cells"]))


def main():
    if sys.argv[1] == "--recheck":
        return recheck(sys.argv[2])
    src, typ, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    R = [r for r in json.load(open(src, encoding="utf-8")) if r.get("type") == typ
         and sum(1 for c in r["text"][:80] if "가" <= c <= "힣") >= 15]
    R.sort(key=lambda r: -r["views"])
    try:
        done = {d["id"]: d for d in json.load(open(dst, encoding="utf-8"))}
    except Exception:      # noqa: BLE001
        done = {}
    for i, r in enumerate(R):
        if r["id"] in done:
            continue
        out = sg._call_json(prompt(r["text"]), SCHEMA) or {}
        cells = []
        for c in out.get("cells") or []:
            c["why_bad"] = check(c, r["text"])
            cells.append(c)
        done[r["id"]] = {"id": r["id"], "user": r.get("user"), "views": r["views"], "platform": r.get("platform"),
                         "text": r["text"], "cells": cells}
        ok = sum(1 for c in cells if not c["why_bad"])
        print("%d/%d %s 칸 %d · 통과 %d" % (i + 1, len(R), r["id"], len(cells), ok), flush=True)
        json.dump(list(done.values()), open(dst, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
