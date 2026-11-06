"""0.1초 소리·자막 칸 격자(표 #32·#33, Jev 해결 0.85·위험 0.23 · 11-06).

N=사람 목소리∧나레 줄 · A=사람 목소리∧나레 줄 아님(원음 대사) · S=자막∧목소리 없음 · C=자막 없음∧목소리 없음∧배경 · _=무음.
줄판독이 없으면 목소리 칸은 V(나레/원음 미구분).
"""
from tools.calcopy.engine import kal_analyze as KA


def _tear(voice, bg, spans):
    return {"probe": {"duration": len(voice) / 10}, "captions": {"spans": spans},
            "separation": {"voice": {"frames": voice}, "bg": {"frames": bg}}}


def test_states_and_metrics():
    voice = [1] * 10 + [0] * 10 + [1] * 10 + [0] * 10
    bg = [1] * 40
    spans = [[0.0, 2.0], [2.0, 3.0]]            # 0~3초 자막, 3~4초 자막 없음
    lines = [{"t0": 0.0, "t1": 1.0, "speaker": "나레"}, {"t0": 2.0, "t1": 3.0, "speaker": "원음"}]
    r = KA.state4_of(_tear(voice, bg, spans), lines)
    assert r["seq"] == "N" * 10 + "S" * 10 + "A" * 10 + "C" * 10
    assert r["share"] == {"N": 0.25, "S": 0.25, "A": 0.25, "C": 0.25}
    assert r["longest"]["N"]["sec"] == 1.0 and r["longest"]["C"]["pos_pct"] == 75
    assert r["switch_per_min"]["N↔S"] == 15.0          # 4초 동안 N↔S 1번 = 분당 15
    assert r["runs"]["n"] == 4 and r["trigram"][0][0] == "NSA"


def test_no_lineread_marks_v():
    r = KA.state4_of(_tear([1, 1, 0, 0], [0, 0, 0, 1], [[0.0, 0.3]]), None)
    assert r["seq"] == "VVSC"
    assert "미구분" in r["note"]


def test_no_separation_is_failed():
    r = KA.state4_of({"probe": {"duration": 1}, "captions": {"spans": []}}, None)
    assert r.get("failed")
