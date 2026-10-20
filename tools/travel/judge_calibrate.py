# -*- coding: utf-8 -*-
"""채점자 보정 — 실제 터진 릴스·안 터진 릴스·우리 대본을 섞어 '눈 가리고' 같은 채점자에 넣는다 (관제 239).

묻는 것: 우리 대본 40점대가 정말 모자란가, 채점자가 짠가.
  - 상위(조회 100만+)가 하위(1만 이하)보다 확실히 높게 나와야 채점자를 믿을 수 있다.
  - 사진이 없는 글만 보므로 '화면 일치'는 빼고 나머지 5기준(50점)만 — 기준 문장은 운영 채점자(travel_build._JUDGE_PROMPT_SCRIPT)에서 그대로 떼어 쓴다.

사용: py tools/travel/judge_calibrate.py <all_scripts.json> <state.json> [상위N=8] [하위N=8]
"""
import json
import random
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from shopping_shorts import travel_build as tb  # noqa: E402

CRIT = [c for c in tb.JUDGE_CRITERIA if c != "화면 일치"]


def criteria_text():
    """운영 채점 기준에서 '화면 일치' 줄만 빼고 그대로 — 기준이 다르면 보정이 아니다."""
    p = tb._JUDGE_PROMPT_SCRIPT
    body = p[p.index("기준("): p.index("본보기")]
    body = re.sub(r"화면 일치 = .*?/ ", "", body, flags=re.S)
    return body.replace("이 숙소에서", "이 상품·장소로")


def sample(all_scripts, n_top, n_low, seed=7):
    S = [x for x in all_scripts if x.get("url") and "instagram" in x["url"] and x.get("views")
         and 150 <= len(x["text"]) <= 330 and len(re.findall(r"[.?!]|요\s", x["text"])) >= 3]
    S.sort(key=lambda x: -x["views"])
    rnd = random.Random(seed)
    top = rnd.sample([x for x in S if x["views"] >= 1_000_000], n_top)
    low = rnd.sample([x for x in S if x["views"] <= 10_000], n_low)
    return top, low


def main():
    A = json.load(open(sys.argv[1], encoding="utf-8"))
    state = json.load(open(sys.argv[2], encoding="utf-8"))
    n_top = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    n_low = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    top, low = sample(A, n_top, n_low)
    items = [{"grp": "상위", "views": x["views"], "text": x["text"]} for x in top]
    items += [{"grp": "하위", "views": x["views"], "text": x["text"]} for x in low]
    for key in ("script", "script_card4", "script_card3"):          # 우리 최근 판(카드 2판 이후)
        for v in (state.get(key) or {}).get("versions") or []:
            items.append({"grp": "우리", "views": 0, "text": " ".join(v["lines"]), "type": v.get("type")})
    random.Random(11).shuffle(items)
    crit = criteria_text()
    for i in range(0, len(items), 7):
        chunk = items[i:i + 7]
        cand = "\n\n".join("%d) %s" % (k + 1, it["text"]) for k, it in enumerate(chunk))
        prompt = ("인스타 쇼핑 릴스 대본 후보들을 채점한다(출처·조회수는 알려 주지 않는다).\n" + crit +
                  "\n\n후보:\n" + cand + "\n\nJSON: {\"scores\": [{\"v\": 후보번호, " +
                  ", ".join("\"%s\": n" % c for c in CRIT) + "}]}")
        got = tb.claude_call([], prompt)
        for s in got.get("scores") or []:
            k = int(s.get("v", 0)) - 1
            if 0 <= k < len(chunk):
                chunk[k]["score"] = {c: int(s.get(c) or 0) for c in CRIT}
                chunk[k]["total"] = sum(chunk[k]["score"].values())
        print("채점 %d/%d" % (min(i + 7, len(items)), len(items)), flush=True)
    print("\n그룹 | 편수 | 합(50점) 중앙 · 평균 · 최소~최대")
    for g in ("상위", "하위", "우리"):
        t = [it["total"] for it in items if it["grp"] == g and "total" in it]
        if t:
            print("%s | %d | %.1f · %.1f · %d~%d" % (g, len(t), st.median(t), st.mean(t), min(t), max(t)))
    print("\n기준별 평균(상위 / 하위 / 우리)")
    for c in CRIT:
        row = [st.mean([it["score"][c] for it in items if it["grp"] == g and "score" in it] or [0]) for g in ("상위", "하위", "우리")]
        print("  %-6s %.1f / %.1f / %.1f" % (c, *row))
    out = Path(sys.argv[2]).with_name("calibration.json")
    out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n자세히:", out)


if __name__ == "__main__":
    main()
