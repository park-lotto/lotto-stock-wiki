# -*- coding: utf-8 -*-
"""인스타 전용 작가 — **상황극**으로 쓴다 (2026-09-22 사장님
   "인스타가 오히려 더 스토리성으로 퀄리티가 올라가야한다 표현력이 상황극모두").

★썰(유튜브)과 뼈대가 다르다. 썰은 정보를 쌓아 올리고, 인스타는 **겪은 일을 이야기한다.**
  그래서 고조 공식(순간→벌어지는일→없애버림)을 그대로 쓰면 어미가 꼬인다
  (2026-09-22 실측: erased가 "~하기"·"~버리게"로 끊겼다 — 썰은 "~버렸다는 거"로 끊는 게 맞지만
   인스타는 "~더라고요"로 끝나야 한다).

★실측(인스타 641편 · 메종+홈테리어픽 95편, 2026-09-22):
  - **따옴표 대사는 0%**다. 상황극을 **간접화법**으로 만든다:
      "비결이 뭐냐니까 … 바른 거래요" · "괜찮냐고 했더니 … 지워진다고요"
      "놀라서 뭐 했냐고 물어봤더니 … 타고 있다는 거예요"
  - 시간 표지 37% (얼마 전·어느 날·요즘·처음엔) · 감탄 도입 38% (와…)
  - 고조 신호는 **썰과 다르다**: 심지어 73 · 게다가 39 · 대박인 건 21 · 거기다 7 · 무엇보다 6
    (썰의 "진짜 미친 포인트는"·"이게 말도 안 되는게"는 인스타에 거의 없다)
  - 결과를 숫자가 아니라 **장면**으로 말한다: "이거 들고 간 날부터 물에서 나오지를 않아요"
  - 감각·추억으로 말한다: "수제비의 짜릿함을 바다에서 다시 느꼈어요", "신혼 때로 돌아간 것 같아요"

쓰기(서버, env 필요):
  python3 tools/seed_analyzer/insta_writer.py --case 뮤지엄젤 --n 2
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
sys.path.insert(0, HERE)

from cases import CASES  # noqa: E402

# 인스타 고조 신호 — 실측 5가지뿐(썰 사전을 쓰면 안 된다)
INSTA_SIGNALS = {
    "A": ["", "심지어", "무엇보다"],
    "B": ["게다가", "", "대박인 건"],
    "C": ["", "거기다", "심지어"],
    "D": ["심지어", "", "게다가"],
    "E": ["", "대박인 건", "거기다"],
}

SCHEMA = {
    "type": "object",
    "properties": {
        "opening": {"type": "string"},      # 감탄 + 그날 무슨 일이 있었나
        "scene": {"type": "string"},        # 내가 본 장면 / 남이 쓰고 있던 모습
        "ask": {"type": "string"},          # 물어본 것 → 들은 답 (간접화법, 없으면 빈칸)
        "reveal": {"type": "string"},       # 정체
        "beats": {"type": "array", "items": {"type": "object", "properties": {
            "before": {"type": "string"},   # 그전에 내가 어떻게 하고 있었나(겪은 일)
            "after": {"type": "string"},    # 이걸 쓰고 나서 어떻게 달라졌나(장면으로)
            "from_pain": {"type": "string"},
        }, "required": ["before", "after", "from_pain"]}},
        "feeling": {"type": "string"},      # 지금 내 생활이 어떻게 바뀌었나(감각·추억)
        "cta": {"type": "string"},          # 댓글 유도(없으면 빈칸)
    },
    "required": ["opening", "scene", "ask", "reveal", "beats", "feeling", "cta"],
}

BRIEF = """너는 인스타 릴스 쇼핑 대본 작가다. **겪은 일을 이야기하듯** 써라.

■ 이건 설명이 아니라 **상황극**이다
제품 설명서를 쓰지 마라. 내가 그날 무엇을 보고 어떻게 놀랐는지를 말한다.
  X 이 제품은 콩알만큼 떼어 붙이면 고정되는 기능이 있습니다
  O 어느 날 언니네 갔더니 식탁 위 소품들이 하나도 안 굴러다니길래 뭐 했냐고 물어봤거든요

■ 말투 (인스타 641편 실측)
- 존댓말 1인칭. 문장 끝은 **~더라고요 / ~거든요 / ~어요 / ~습니다**.
- 유튜브 썰 어미(`~다는데` · `~버렸다는 거` · `~는 거임`)를 쓰면 인스타가 아니다.
- 감탄으로 여는 편이 많다(38%): "와…", "아니 이거".

■ 대사는 **따옴표 없이 간접화법**으로 (실측: 따옴표 대사 0%)
물어보고 들은 내용을 문장 안에 녹인다.
  "비결이 뭐냐니까 창문에 그냥 이 페인트를 바른 거래요"
  "전세 집인데 괜찮냐고 했더니 나중에 뜯으면 흔적도 없이 지워진다고요"
  "놀라서 뭐 했냐고 물어봤더니 트레이너한테 추천 받았다는 거예요"
ask 칸이 이 자리다. 물어볼 상대가 재료에 없으면 **빈칸으로 둬라**(인물을 지어내지 마라).

■ beats — 겪은 일을 before/after로
  before  이걸 모를 때 내가 어떻게 하고 있었나. 그 장면과 짜증을 그대로.
  after   쓰고 나서 어떻게 달라졌나. **기능이 아니라 장면으로.**
          X 균일하게 도포됩니다
          O 빗질 한 번 하고 나면 손에 아무것도 안 묻어 있더라고요
  from_pain  근거로 삼은 재료의 '이게 없을 때' 문장을 그대로 적어라. 댈 게 없으면 그 칸을 만들지 마라.
칸 수를 채우려 하지 마라. 1개여도 2개여도 된다.

■ feeling — 결과를 숫자가 아니라 **생활의 장면**으로
  "이거 들고 간 날부터 물에서 나오지를 않아요"
  "요즘 와이프랑 둘이 앉아서 하루종일 게임하는데 간만에 신혼 때로 돌아간 것 같아요"
  "이 나이에 이렇게 뛰어다닐 줄은 저도 몰랐습니다"
감각·추억으로 말해도 좋다. 없는 사실을 지어내지는 마라.

■ 지키는 것
- 재료에 없는 수치·효능·인물·사연을 지어내지 마라. 가격은 재료에 값이 있을 때만(실측 10%).
- 시간 표지를 자연스럽게(37%): 얼마 전 · 어느 날 · 요즘 · 처음엔.
- 문장을 길게 이어 붙여라. 딱딱 끊으면 이야기가 아니라 목록이 된다."""

_YT_ENDING = re.compile(r"다는 거[.]?$|버렸다는 거|다는데[.]?$|는 거임|었음[.]?$")
_FLAT = re.compile(r"기능이 있|사용할 수 있습니다|(있어|덕분에)\s*(편리|간편)")


def build(d, cta=True):
    rows = ["[제품] %s" % d["product"], "",
            "[씨앗 — 이 제품으로 터진 인스타 영상의 말]", d["seed"].strip(), "",
            "[재료]"]
    for f in d["feats"]:
        rows.append("- %s — %s" % (f["name"], f["claim"]))
        if f.get("pain"):
            rows.append("    이게 없을 때: %s" % f["pain"])
    tail = ("\n■ 마지막은 댓글 유도다: \"궁금하시면 댓글에 'OO' 남겨주세요\" 꼴로 cta에 써라."
            if cta else "\n■ cta는 빈칸으로 두고 feeling으로 닫아라.")
    return BRIEF + tail + "\n\n" + "\n".join(rows)


def to_lines(o, sig_set="A"):
    sigs = INSTA_SIGNALS.get(sig_set, INSTA_SIGNALS["A"])
    out = [("도입", o.get("opening")), ("장면", o.get("scene"))]
    if (o.get("ask") or "").strip():
        out.append(("물어봄", o["ask"]))
    out.append(("정체", o.get("reveal")))
    for i, b in enumerate(o.get("beats") or []):
        if i < len(sigs) and sigs[i]:
            out.append(("고조%d" % (i + 1), sigs[i]))
        for k in ("before", "after"):
            if (b.get(k) or "").strip():
                out.append(("고조%d" % (i + 1), b[k]))
    out += [("소감", o.get("feeling")), ("댓글", o.get("cta"))]
    return [{"beat": b, "text": t.strip()} for b, t in out if (t or "").strip()]


def audit(lines, o, feats):
    pains = [(f.get("pain") or "").strip() for f in feats if (f.get("pain") or "").strip()]
    bs = o.get("beats") or []
    ung = []
    for b in bs:
        fp = re.sub(r"\s+", "", b.get("from_pain") or "")
        if not fp or not any(re.sub(r"\s+", "", p)[:8] in fp or fp[:8] in re.sub(r"\s+", "", p)
                             for p in pains):
            ung.append(b.get("from_pain") or "(빈칸)")
    yt = [l["text"] for l in lines if _YT_ENDING.search(l["text"])]
    flat = [l["text"] for l in lines if _FLAT.search(l["text"])]
    insta_end = sum(1 for l in lines if re.search(r"(더라고요|거든요|어요|습니다|네요|예요)[.!?]?$", l["text"]))
    return {"beats": len(bs), "pain": len(pains), "ungrounded": ung,
            "yt_ending": yt, "flat": flat,
            "insta_end_rate": round(100 * insta_end / max(1, len(lines)))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="뮤지엄젤")
    ap.add_argument("--n", type=int, default=2)
    a = ap.parse_args()
    from shopping_shorts import script_generate as _sg
    d = CASES[a.case]
    p = build(d)
    print("[인스타 전용] 프롬프트 %d자\n" % len(p))
    names = sorted(INSTA_SIGNALS)
    for i in range(a.n):
        o = _sg._call_json(p, SCHEMA) or {}
        st = names[i % len(names)]
        lines = to_lines(o, st)
        au = audit(lines, o, d["feats"])
        print("=== %d편 · %d줄 · 고조 %d칸(재료 불편 %d) · 신호세트 %s ==="
              % (i + 1, len(lines), au["beats"], au["pain"], st))
        print("    인스타 어미 %d%% · 썰 어미 %d줄 · 설명문 %d · 근거없음 %d"
              % (au["insta_end_rate"], len(au["yt_ending"]), len(au["flat"]), len(au["ungrounded"])))
        for l in lines:
            print("  [%s] %s" % (l["beat"], l["text"]))
        if au["yt_ending"]:
            print("  * 썰 어미가 섞인 줄:", au["yt_ending"])
        print()


if __name__ == "__main__":
    main()
