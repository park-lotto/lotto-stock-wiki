"""회원 꾸미기 값 → 판 틀(styles.member_frame 주인) — 값이 없으면 판 그대로, 안 고른 줄 색은 프리셋 색."""
import json
from tools.calcopy.hybrid import styles as STY


def test_없으면_그대로_있으면_덮는다(tmp_path, monkeypatch):
    monkeypatch.delenv("SHORTEM_MEMBER_PACK", raising=False)
    base = STY.load("잇템로그판")
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"1": {"brand": {"colors": {"bg": [1, 2, 3]}},
                                   "text": {"title_font": "BMJUA", "title_colors": ["#FF0000", None], "title_scale": 0.5}}}), encoding="utf-8")
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(p))
    st = STY.load("잇템로그판")
    a, b = st["frame"]["title"], base["frame"]["title"]
    assert st["frame"]["bg"] == [1, 2, 3]
    assert a[0]["font"] == "BMJUA.ttf" and a[0]["color"] == "#FF0000" and a[0]["px"] == round(b[0]["px"] * 0.5)
    assert a[1]["color"] == b[1]["color"]


def test_코드가_고른_1안은_썸네일_3안_규칙에_안_걸린다():
    from tools.calcopy.hybrid import thumb_rule
    assert thumb_rule.check({"options": [{"id": "A", "auto": True}]}, n_parts=5) == []
    assert thumb_rule.check({"options": [{"id": "A"}]}, n_parts=5)
