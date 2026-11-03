"""2단계 스토리보드 대본 전수 점검 — 고객 작업(produce_works.state_json.sb.made)의 판 대본을 훑어 결함 꼴을 센다.

서버에서: ssh ... "cd lotto-stock-wiki && python3 -" < tools/storyboard_script_audit.py
(관제 216, 2026-10-16) 세는 것:
  price_stripped  사실 검수가 숫자 없는 가격 평가("가격 부담 없음"·"몇천 원")까지 지운 칸
  role_broken     지운 뒤 칸 이름이 price 인데 문장에 가격 말이 하나도 없는 칸
  mid_cta         cta 칸이 아닌데 "댓글"+"남기/달아" 가 있는 칸(마지막 칸 제외)
  dup_line        한 판에 같은 문장이 두 번
  empty_line      빈 문장
  desc_leak       장면 설명 말투("~하는 모습", "~장면")가 문장에 들어간 칸
"""
import json, re, sqlite3, sys
from collections import Counter

DB = "shopping_shorts/data/reference.db"
PRICE = re.compile(r"가격|원|값|가성비|저렴|싸")
DIGIT = re.compile(r"\d")
CTA = re.compile(r"댓글.{0,12}(남기|남겨|달아|적어)")
LEAK = re.compile(r"(하는|있는|되는) 모습|장면(이다|입니다|$)|클로즈업")


def boards(db):
    for wid, st in db.execute("select work_id, state_json from produce_works where state_json like '%\"made\"%'"):
        try:
            made = (json.loads(st).get("sb") or {}).get("made") or {}
        except Exception:
            continue
        for k, b in made.items():
            if isinstance(b, dict) and b.get("slots"):
                yield wid, k, b


def main(show=3):
    db = sqlite3.connect(DB)
    c, ex = Counter(), {}
    def hit(name, s):
        c[name] += 1
        if len(ex.setdefault(name, [])) < show:
            ex[name].append(s)
    for wid, k, b in boards(db):
        c["boards"] += 1
        sl = b["slots"]
        seen = Counter((x.get("line") or "").strip() for x in sl)
        if any(v > 1 and t for t, v in seen.items()):
            hit("dup_line", "%s:%s %s" % (wid, k, [t for t, v in seen.items() if v > 1 and t]))
        for i, x in enumerate(sl):
            line, before, why = (x.get("line") or "").strip(), x.get("line_before") or "", x.get("fixed_why") or ""
            name = str(x.get("slot") or "").split("_")[0].lower()
            c["slots"] += 1
            if not line:
                hit("empty_line", "%s:%s #%d %s" % (wid, k, i, name))
            if before and not why.startswith("흐름") and PRICE.search(before) and not DIGIT.search(before) and not PRICE.search(line):
                hit("price_stripped", "%s:%s #%d %r -> %r" % (wid, k, i, before, line))
            if name == "price" and line and not PRICE.search(line):
                hit("role_broken", "%s:%s #%d %r" % (wid, k, i, line))
            if name != "cta" and i < len(sl) - 1 and CTA.search(line):
                hit("mid_cta", "%s:%s #%d %s %r" % (wid, k, i, name, line))
            if LEAK.search(line):
                hit("desc_leak", "%s:%s #%d %r" % (wid, k, i, line))
    for name, v in c.most_common():
        print("%-15s %d" % (name, v))
        for s in ex.get(name, []):
            print("     ", s[:160])


if __name__ == "__main__":
    main()
