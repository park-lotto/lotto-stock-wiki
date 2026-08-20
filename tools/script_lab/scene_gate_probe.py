# -*- coding: utf-8 -*-
"""장면 근거 게이트 실측 — **모델 호출 0회**라 로컬에서 돈다.

사장님 지적("장면에도 없는 대본이 나오는 거 아닌가")을 눈으로 확인하는 자리다.
같은 재료를 게이트 전/후로 조립해 **무엇이 빠지고 무엇이 남는지** 대조한다.

실행: python tools/script_lab/scene_gate_probe.py
"""
import io
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))

from shopping_shorts import insta_facts, spine_fill          # noqa: E402
from tools.script_lab.daiso_spine import DAISO_INSIDER       # noqa: E402

# ── 실측 재료 (2026-08-19 욕실세정제 5편, insta_facts_probe 결과) ──────────
#    ★일부러 **화면에 없는 값**을 섞어 뒀다 — 게이트가 그것만 골라 버리는지 본다.
FACTS = {
    "how_to":  ["욕실에 칙칙 뿌리고 물로 싹 뿌려주기",
                "세탁기에 한 스푼 넣고 돌리기"],          # ← 화면에 세탁기가 없다
    "targets": ["욕실 수전 물때", "오래된 욕실 곰팡이",
                "누렇게 변한 흰 양말"],                   # ← 화면에 양말이 없다
    "pain":    ["아무리 닦아도 안 지워지던 곰팡이"],
    "effects": ["완전 새 것처럼 닦이는"],
    "numbers": ["5분"],
    "edge":    ["다이소 욕실 청소 세제 판매 1위 제품"],
    "price":   ["단돈 몇 천 원"],
}

# 장면 인벤토리 — 영상에 실제로 찍힌 것(app이 sources[].segments로 이미 싣고 있다)
SEGMENTS = [
    {"scene_desc": "욕실 수전에 세제를 뿌리는 모습"},
    {"scene_desc": "곰팡이가 낀 욕실 타일을 보여주는 장면"},
    {"scene_desc": "물때가 사라진 수전을 닦아내는 모습"},
    {"scene_desc": "깨끗해진 욕실 전체를 비추는 화면"},
]


def _hangul(s):
    return len(re.sub(r"[^가-힣0-9]", "", s))


def show(name, facts):
    slots = spine_fill.slots_from_insta(facts)
    beats, missing = spine_fill.fill(DAISO_INSIDER, slots)
    full = " ".join(b["text"] for b in beats)
    print("\n" + "=" * 72)
    print("[%s]  칸 %d/%d  ·  %d자"
          % (name, len(beats), len(DAISO_INSIDER["beat_roles"]), _hangul(full)))
    for b in beats:
        print("  [%-8s] %s" % (b["role"], b["text"]))
    if missing:
        print("  ⚠️ 못 채운 칸: %s" % ", ".join(missing))
    return full


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    print("장면 인벤토리(scene_desc) %d컷:" % len(SEGMENTS))
    for s in SEGMENTS:
        print("   · %s" % s["scene_desc"])

    before = show("게이트 OFF — 지금까지 나가던 것", FACTS)

    gated = insta_facts.gate_by_scene(FACTS, SEGMENTS)
    after = show("게이트 ON — 화면에 있는 것만", gated)

    print("\n" + "=" * 72)
    print("[재료 대조]")
    for k in ("how_to", "targets", "pain", "effects", "numbers", "edge", "price"):
        b, a = FACTS.get(k, []), gated.get(k, [])
        mark = "버림" if len(a) < len(b) else ("면제" if k not in insta_facts._SCENE_GATED else "유지")
        print("  %-8s %d개 → %d개  [%s]%s"
              % (k, len(b), len(a), mark,
                 ("  버린 값: " + " / ".join(x for x in b if x not in a)) if len(a) < len(b) else ""))

    # 빈 인벤토리 = 모르는 것이지 없는 게 아니다 → 그대로 통과해야 한다
    same = insta_facts.gate_by_scene(FACTS, [])
    print("\n[안전장치] 장면 인벤토리가 비면 그대로 통과: %s"
          % ("OK" if same == FACTS else "★깨졌다"))
    print("[대조] 게이트로 바뀐 문장이 있나: %s" % ("있다" if before != after else "없다"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
