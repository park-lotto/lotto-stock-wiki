# -*- coding: utf-8 -*-
"""표현 중심 작가 프롬프트 시험대 (2026-09-22 사장님 "표현집중해서 시작해봐 / 테스트를 계속해보자").

★노바 작가 대본 정독으로 확정된 것: 고조 한 칸은 단문이 아니라 **3~4줄짜리 작은 이야기**다
  (신호→장면→고통 키움→없애버림). 설명문("A는 B 기능이 있어 편리합니다")은 한 줄도 없다.
  표현 재료는 썰계열 261편 + 스파인 368개(17.8만 자) 실측 사전에서 온다 —
  의태어 14 · 강한동사 14 · 고통 감정어 6 · 증언 6. **골라 쓰는 것**이고 억지로 끼우지 않는다.

★왜 pain이 필요한가: 지금 특징 분석은 기능(claim)만 뽑는다. 기능만 나열하면
  "빗 뒷면에 앰플을 채운다"처럼 심심해진다. 불편(pain)이 짝으로 있어야
  "손에 다 묻고 머리만 떡지던 걸 없앴다"가 된다 — 고조의 재료는 기능이 아니라 **불편-해결 짝**이다.

쓰기(서버, env 필요):
  python3 tools/seed_analyzer/try_writer.py --demo --n 3
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")

LINES_SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
        "beat": {"type": "string", "enum": ["훅", "미끼", "공개", "고조1", "고조2",
                                            "고조3", "고조4", "반전", "마무리"]},
        "text": {"type": "string"},
    }, "required": ["beat", "text"]}}},
    "required": ["lines"],
}

# 설명문 지문 — 이런 꼴이 나오면 표현이 죽은 것이다(지시만 있고 판정이 없으면 안 지켜진다)
_FLAT = re.compile(r"(있어|있어서|때문에|덕분에)\s*(편리|간편|좋|유용)|"
                   r"기능이 있|사용할 수 있습니다|해 줍니다$|됩니다$|입니다$")


def build_prompt(seed_text, feats, product):
    brief = open(os.path.join(HERE, "writer_brief.txt"), encoding="utf-8").read().strip()
    blocks = ["[제품] %s" % product, "",
              "[씨앗 — 이 제품으로 터진 영상의 말]", seed_text.strip(), "",
              "[재료 — 우리가 쓸 장면과 그 장면이 없앤 불편]"]
    for f in feats:
        pain = ("\n    이게 없을 때: %s" % f["pain"]) if f.get("pain") else ""
        blocks.append("- %s — %s%s" % (f["name"], f["claim"], pain))
    return "%s\n\n%s" % (brief, "\n".join(blocks))


def flat_lines(lines):
    """설명문으로 떨어진 줄."""
    return [l["text"] for l in lines if _FLAT.search(l.get("text") or "")]


_MONEY = re.compile(r"\d[\d,]*\s*원|가격|할인|반값|만 ?원대|돈으로|값싸")


def escalation_audit(lines, feats):
    """고조가 재료의 불편(pain)에 근거하나 — 개수가 아니라 **근거**를 본다.
    ★칸 수를 강제하면 재료가 모자랄 때 모델이 없는 효능을 지어낸다(2026-09-22 사장님).
    그래서 '많이 썼나'가 아니라 '근거 있는 것만 썼나'로 판정한다."""
    esc = [l for l in lines if str(l.get("beat") or "").startswith("고조")]
    n_pain = sum(1 for f in feats if (f.get("pain") or "").strip())
    n_beats = len({l.get("beat") for l in esc})
    # 한 칸이 1줄로 뭉쳤나 — 설명문으로 퇴화한 신호
    per = {}
    for l in esc:
        per[l.get("beat")] = per.get(l.get("beat"), 0) + 1
    thin = [b for b, c in per.items() if c < 2]
    return {"beats": n_beats, "pain": n_pain,
            "over": max(0, n_beats - n_pain),      # 근거보다 많이 만든 칸
            "thin": thin}                          # 1줄로 뭉친 칸


def missing_beats(lines):
    """훅·미끼·공개가 빠지면 대본이 아니라 고조 묶음이다."""
    got = {l.get("beat") for l in lines}
    return [b for b in ("훅", "미끼", "공개", "반전", "마무리") if b not in got]


def money_lines(lines):
    """재료에 값이 없는데 돈 얘기를 했나."""
    return [l["text"] for l in lines if _MONEY.search(l.get("text") or "")]


def opener_runs(lines):
    """신호어가 몇 칸 연속 붙었나 — 매 칸에 붙으면 기계처럼 보인다."""
    sig = re.compile(r"^(이게|심지어|게다가|거기다|근데|더 대박|진짜)")
    run = best = 0
    for l in lines:
        if sig.match((l.get("text") or "").strip()):
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


DEMO = {
    "product": "두피 앰플 빗",
    "seed": ("두피 에센스 손에 다 묻고 머리만 떡져서 빡쳤던 분들 이거 보세요. "
             "빗 뒷면에 앰플을 그냥 부어 넣으면 되고 빗질할 때마다 롤러볼이 굴러가면서 "
             "머리카락 사이사이로 쏙쏙 들어가요. 손에는 하나도 안 묻고 두피에만 발라지는데 "
             "빗질하면서 마사지까지 되니까 저녁마다 이것만 쓰게 되더라고요."),
    "feats": [
        {"name": "앰플 충전", "claim": "빗 뒷면 덮개를 열어 앰플을 부어 넣는다",
         "pain": "튜브를 손에 짜서 바르다 손가락 사이로 흘러내리고 머리만 떡짐"},
        {"name": "균일 도포", "claim": "빗살과 롤러볼이 머리카락 사이로 앰플을 밀어 넣는다",
         "pain": "손으로는 한쪽만 뭉치고 정작 두피엔 안 닿음"},
        {"name": "손 안 묻음", "claim": "손에 묻히지 않고 두피에만 발린다",
         "pain": "바르고 나면 손 씻으러 가야 하고 끈적임이 남음"},
        {"name": "두피 마사지", "claim": "빗질하면서 두피 마사지가 된다",
         "pain": "따로 마사지기를 또 사서 써야 했음"},
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    from shopping_shorts import script_generate as _sg
    d = DEMO
    prompt = build_prompt(d["seed"], d["feats"], d["product"])
    print("프롬프트 %d자\n" % len(prompt))
    rows = []
    for i in range(a.n):
        out = _sg._call_json(prompt, LINES_SCHEMA) or {}
        lines = [l for l in (out.get("lines") or []) if (l.get("text") or "").strip()]
        flat = flat_lines(lines)
        run = opener_runs(lines)
        miss = missing_beats(lines)
        money = money_lines(lines)
        esc = escalation_audit(lines, d["feats"])
        rows.append({"lines": lines, "flat": flat, "opener_run": run,
                     "missing": miss, "money": money, "esc": esc})
        print("=== %d편 · %d줄 · 설명문 %d · 빠진칸 %s · 돈언급 %d ==="
              % (i + 1, len(lines), len(flat), ",".join(miss) or "없음", len(money)))
        print("    고조 %d칸 (재료 불편 %d개) · 근거없이 늘린 칸 %d · 1줄로 뭉친 칸 %s"
              % (esc["beats"], esc["pain"], esc["over"], ",".join(esc["thin"]) or "없음"))
        for l in lines:
            print("  [%s] %s" % (l.get("beat", ""), l.get("text", "")))
        for tag, arr in (("설명문", flat), ("재료에 없는 돈 얘기", money)):
            if arr:
                print("  * %s:" % tag)
                for t in arr:
                    print("     -", t)
        print()
    if a.out:
        json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
