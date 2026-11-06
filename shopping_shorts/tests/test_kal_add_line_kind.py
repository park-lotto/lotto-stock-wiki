"""자막 줄 종류 초안 — 받아쓰기 일치·y 군집·채움색 세 증거(표 #30, Jev 해결 0.68·위험 0.43 · 11-06)."""
from tools.calcopy.engine import kal_analyze as KA


def _l(t0, t1, text, y):
    return {"t0": t0, "t1": t1, "text": text, "y": [y, None]}


def test_groups_and_guess():
    lines = [_l(0, 1, "안녕하세요 여러분", 1200), _l(1, 2, "오늘은 이걸 봐요", 1200), _l(2, 3, "쾅 터졌다", 600), _l(3, 4, "대박 사건", 600)]
    tr = {"segments": [{"start": 0.0, "end": 2.0, "text": "안녕하세요 여러분 오늘은 이걸 봐요"}]}
    r = KA.line_kind_draft(lines, tr, {}, 1920)
    g = [x["guess"] for x in r]
    assert g[0] == g[1] == "말과 같은 자막(대사·나레)"
    assert g[2] == g[3] == "말과 다른 자막(해설·효과)"
    assert r[0]["y_group"] == r[1]["y_group"] != r[2]["y_group"]
    assert r[0]["asr_part"] >= 0.62 and r[2]["asr_part"] < 0.62


def test_no_transcript_groups_only():
    r = KA.line_kind_draft([_l(0, 1, "가나다", 1200)], {"failed": "x"}, {}, 1920)
    assert r[0]["guess"].startswith("군집만") and r[0]["asr_part"] is None


def test_color_splits_same_y():
    lines = [_l(0, 1, "가나다", 1200), _l(1, 2, "라마바", 1200)]
    fx = {"per_crop": [{"caption": 0, "fill_rgb": [255, 255, 255]}, {"caption": 1, "fill_rgb": [255, 220, 0]}]}
    r = KA.line_kind_draft(lines, {"failed": "x"}, fx, 1920, idx=[0, 1])
    assert r[0]["color_group"] != r[1]["color_group"]
