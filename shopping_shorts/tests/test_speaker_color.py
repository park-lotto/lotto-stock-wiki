# -*- coding: utf-8 -*-
"""원음 대사 자막 인물색(11-07 썰반장 칼카피 — 벤치 원음 157줄 중 122줄 화자색, 같은 화자 한 색 25/35).
판단 주인 = render_bench.speaker_variant(S, st, L, j) 하나: 대본 speakers[caps_who[j]].color → 판 caption.speaker_colors 팔레트 →
자막팩 variants 중 text.color 가 같은 변형 이름. timeline 은 그 값을 원음 덩어리 variant_force 로 싣기만 하고 placement 는 그대로 받는다.
Jev(q_color3): 뿌리 0.86 · 근본해결 0.71 · 한줄기 0.80 · 두더지 0.15 — 통과."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid.common import StageError  # noqa: E402

PAL = {"흰": "#FFFFFF", "노랑": "#F9F95B", "연두": "#38FF19"}
PACKS = {"p": {"text": {"color": "#FFFFFF"}, "variants": {"spk_white": {"text": {"color": "#FFFFFF"}}, "spk_yellow": {"text": {"color": "#f9f95b"}},
                                                           "spk_green": {"text": {"color": "#38FF19"}}}}}
ST = {"caption": {"pack": "p", "speaker_colors": PAL}}
S = {"speakers": {"레지나": {"color": "노랑"}, "피터": {"color": "#FFFFFF"}}}
L = {"id": "O1", "kind": "orig", "caps_rel": [["a", 0, 1], ["b", 1, 2]], "caps_who": ["레지나", "피터"]}


def test_color_from_script_speaker_to_pack_variant():
    assert RB.speaker_variant(S, ST, L, 0, PACKS) == "spk_yellow"       # 팔레트 이름표
    assert RB.speaker_variant(S, ST, L, 1, PACKS) == "spk_white"        # hex 그대로


def test_no_palette_keeps_old_behaviour():
    assert RB.speaker_variant(S, {"caption": {"pack": "p"}}, L, 0, PACKS) is None     # 판에 색 칸 없음 = 옛 동작(변형 없음)
    assert RB.speaker_variant({}, ST, {"id": "O9", "kind": "orig", "caps_rel": [["a", 0, 1]]}, 0, PACKS) is None   # 대본에 caps_who 없음
    assert RB.speaker_variant(S, ST, {"id": "N1", "kind": "tts", "tts": "x", "caps": ["x"]}, 0, PACKS) is None   # 나레 줄


@pytest.mark.parametrize("S2,L2,why", [
    ({"speakers": {}}, L, "인물"),                                                         # 대본 speakers 에 없는 인물
    ({"speakers": {"레지나": {"color": "#123456"}, "피터": {"color": "흰"}}}, L, "팔레트"),   # 팔레트 밖 색
    (S, {**L, "caps_who": ["레지나"]}, "caps_who"),                                         # 덩어리 수와 안 맞음
])
def test_bad_input_stops(S2, L2, why):
    with pytest.raises(StageError, match=why):
        RB.speaker_variant(S2, ST, L2, 0, PACKS)


def test_palette_color_missing_in_pack_stops():
    st = {"caption": {"pack": "p", "speaker_colors": {**PAL, "하늘": "#85C0F9"}}}
    with pytest.raises(StageError, match="자막팩"):
        RB.speaker_variant({"speakers": {"레지나": {"color": "하늘"}}}, st, {**L, "caps_who": ["레지나", "레지나"]}, 0, PACKS)


def test_placement_keeps_speaker_variant():
    """variant_force 로 실린 화자색 변형이 배치를 지나 자막팩 줄(caption_rows)까지 그대로 간다."""
    from tools.calcopy.hybrid import styles as STY
    st = STY.load("썰반장판")
    rows = [{"line": "N1", "j": 0, "speaker": "narr", "text": "남편이 숨긴다", "t0": 0.0, "t1": 1.0},
            {"line": "O1", "j": 0, "speaker": "orig", "text": "뭔가 숨기고 있어", "t0": 1.1, "t1": 2.0, "variant_force": "spk_yellow"},
            {"line": "O1", "j": 1, "speaker": "orig", "text": "그래서 무서워", "t0": 2.0, "t1": 3.0}]
    placed = __import__("tools.calcopy.hybrid.placement", fromlist=["place"]).place(rows, st, "t")
    for r, t in zip(placed["rows"], rows):
        r["show"] = [t["t0"], t["t1"]]
    got = [r["variant"] for r in RB.caption_rows(placed, st)]
    assert got == ["", "spk_yellow", ""], got


def test_sseolbanjang_pan_palette_all_in_pack():
    """썰반장판 팔레트 색은 전부 썰반장 자막팩 변형에 있다(판·팩 짝)."""
    from tools.calcopy.hybrid import styles as STY
    st = STY.load("썰반장판")
    packs = RB.caption_packs()
    for name in st["caption"]["speaker_colors"]:
        L1 = {"id": "O", "kind": "orig", "caps_rel": [["a", 0, 1]], "caps_who": ["x"]}
        assert RB.speaker_variant({"speakers": {"x": {"color": name}}}, st, L1, 0, packs).startswith("spk_")
