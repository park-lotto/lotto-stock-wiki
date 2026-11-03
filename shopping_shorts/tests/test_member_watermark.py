"""#3951·#3952(11-04 김효준): 회원이 채널명 워터마크의 자리·크기·투명도를 정한다 — brand.watermark{cx,cy,px,alpha}.
판단 주인 = preview_request.check(저장 전 범위) · styles.member_frame(틀에 넣기). 그림은 render_bench.frame_png 가 이미 cx·cy·px·alpha 로 그린다.
결과물 검사 = 실제 틀 그림(frame_png)에서 정한 자리에 글자 잉크가 생기고, 원래 자리(상단 가운데)에는 없어진다."""
import json
from PIL import Image
from tools.calcopy import preview_request as PR
from tools.calcopy.hybrid import render_bench as RB, styles as STY

S = {"title": ["아무도 몰랐던", "이 제품 뒷이야기"], "title_lines": ["아무도 몰랐던", "이 제품 뒷이야기"], "source_label": "출처"}
CAT = None   # 진짜 목록(preview_request.catalog)


def _load(tmp_path, monkeypatch, brand, name="외국인+한국제품반응판"):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"member": {"brand": brand}}), encoding="utf-8")
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(p))
    return STY.load("잇템로그판")


def _ink(png, box):
    im = Image.open(png).convert("L").crop(box)
    return sum(1 for v in im.getdata() if v > 200)


def test_저장_검사_범위(tmp_path):
    ok = {"brand": {"channel_name": "RoaShop", "watermark": {"cx": 540, "cy": 1500, "px": 58, "alpha": 120}}}
    assert [e for e in PR.check(ok, CAT) if "워터마크" in e or "watermark" in e] == []
    for bad in ({"cx": 2000}, {"px": 5}, {"alpha": 300}, {"cx": 1000, "cy": 60}, {"size": 3}, {"cx": "가운데"}):
        errs = PR.check({"brand": {"channel_name": "RoaShop", "watermark": bad}}, CAT)
        assert errs, f"거절해야 한다: {bad}"


def test_정한_자리에_그려진다(tmp_path, monkeypatch):
    st = _load(tmp_path, monkeypatch, {"channel_name": "RoaShop", "watermark": {"cx": 540, "cy": 1500, "px": 58, "alpha": 120}})
    W = st["frame"]["watermark"]
    assert (W["cx"], W["cy"], W["px"], W["alpha"], W["text"]) == (540, 1500, 58, 120, "RoaShop")
    out = RB.frame_png(S, st, tmp_path / "wm.png")
    st0 = _load(tmp_path, monkeypatch, {"channel_name": "RoaShop"})
    out0 = RB.frame_png(S, st0, tmp_path / "base.png")
    box = (300, 1460, 780, 1540)
    assert _ink(out, box) > _ink(out0, box) + 50, "정한 자리(cy1500)에 글자 잉크가 생겨야 한다"


def test_채널명이_없으면_워터마크도_없다(tmp_path, monkeypatch):
    st = _load(tmp_path, monkeypatch, {"watermark": {"cx": 540, "cy": 1500, "px": 58, "alpha": 120}})
    assert not st["frame"].get("watermark")
