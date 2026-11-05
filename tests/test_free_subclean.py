"""무료 자막 지우기 — 엔진 고르기·자리 없는 조각·흐름 연결 (관제 301)."""
from tools.calcopy import vmake_clean as VC
from tools.calcopy.hybrid import flow as F


def _env(mp, key="", free=False, via="member", pick=None):
    mp.setattr(VC, "member_key", lambda: key)
    mp.setattr(VC, "free_ok", lambda: free)
    mp.setattr(VC, "key_source", lambda: via)
    mp.delenv("SHORTEM_NO_PAID", raising=False)
    if pick:
        mp.setenv("SHORTEM_ERASE_ENGINE", pick)
    else:
        mp.delenv("SHORTEM_ERASE_ENGINE", raising=False)


def test_키_있으면_기존대로_VMake(monkeypatch):
    _env(monkeypatch, key="a:b", free=True)
    assert VC.ready("vmake")["via"] == "member"


def test_키_없고_무료_설치면_무료(monkeypatch):
    _env(monkeypatch, free=True)
    assert VC.ready("vmake") == {"mode": "vmake", "via": "free", "why": ""}


def test_키도_무료도_없으면_흐림(monkeypatch):
    _env(monkeypatch)
    assert VC.ready("vmake")["mode"] == "blur"


def test_회원이_무료를_고르면_키가_있어도_무료(monkeypatch):
    _env(monkeypatch, key="a:b", free=True, pick="free")
    assert VC.ready("vmake")["via"] == "free"


def test_흐림을_고른_회원은_무료가_있어도_흐림(monkeypatch):
    _env(monkeypatch, free=True)
    assert VC.ready("blur")["mode"] == "blur"


def test_자리_없는_조각은_지우지_않고_실패(tmp_path):
    f = tmp_path / "a__vm_1.00_2.00.mp4"
    f.write_bytes(b"x")
    r = VC.free_clean([f], {})
    assert r["cleaned"] == [] and "자리" in r["fail"][f.name]


def test_무료면_자리부터_묻고_답을_clean_text로_넘긴다():
    st = {"text_fix": {"mode": "vmake", "via": "free", "key": None, "done": {}}, "script": {"M": {"cuts": {}}},
          "version": "v", "shots": {}, "tries": {}, "log": []}
    r = F.f_render(st, {}, {}, None)
    assert r["then"] == "f_spots" and r["do"][0]["cmd"] == "spot_sheets"
    r = F.f_spots(st, {"spots": {"sheets": {"a.mp4": "_spots/a.jpg"}}}, {}, None)
    assert r["then"] == "f_spots_got" and r["review"][0]["need"] == ["bands"]
    F.f_spots_got(st, {}, {"spot_0": {"bands": [{"y0": .7, "y1": .8}], "emoji": []}}, None)
    r = F.f_render(st, {}, {}, None)
    assert r["then"] == "f_render_clean_got"
    assert r["do"][0]["spots"]["a.mp4"]["bands"][0]["y0"] == .7
