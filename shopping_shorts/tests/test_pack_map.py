# -*- coding: utf-8 -*-
"""판 packs 칸·팩 합치기·목록 패치(관제 263 지시서 11 · 표준 §10-2·§10-3·§11-2 ⑰).

검사 대상(주인): tools/calcopy/hybrid/pack_map.py(merge·apply_to_style·snapshot_fields·cap_rank) · styles.py(load·_raw 목록 패치).
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import pack_map as PM  # noqa: E402
from tools.calcopy.hybrid import styles as ST  # noqa: E402

OLD = ("caption.pack", "sfx_files", "bgm.id", "bgm.candidates")


def _old(st):
    return {k: PM._get(st, k) for k in OLD}


@pytest.fixture()
def tmp_styles(tmp_path, monkeypatch):
    d = tmp_path / "styles"
    shutil.copytree(ST.DIR, d)
    monkeypatch.setattr(ST, "DIR", d)
    return d


def _edit(d: Path, name: str, fn):
    p = d / f"{name}.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    fn(raw)
    p.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")


def test_모든_판_packs_있고_옛칸과_같다():
    """변환 diff 0 — packs 를 정본으로 채운 옛 칸 = 판 파일에 적힌 옛 칸(옛 칸만으로 합친 값)."""
    for n in ST.names():
        st = ST.load(n)
        assert set(PM.PACK_KEYS) <= set(st["packs"]), n
        assert _old(st) == _old(ST.load(n, _skip_packs=True)), n


def test_판_파일마다_packs_칸_적힘():
    """모든 판 파일에 packs 칸 — 상속 판은 바탕과 다른 것만(잇템로그판_v2 = 결정 칸 없이 gap 만, 결정은 바탕 상속)."""
    miss = [n for n in ST.names() if "packs" not in json.loads(ST.path_of(n).read_text(encoding="utf-8"))]
    assert miss == []
    v2 = json.loads(ST.path_of("잇템로그판_v2").read_text(encoding="utf-8"))["packs"]
    assert not any(x in (v2.get(k) or {}) for k in PM.PACK_KEYS for x in PM.DECIDE)


def test_두벌_불일치는_load_거절(tmp_styles):
    _edit(tmp_styles, "키치잇판", lambda r: r["packs"]["caption"].__setitem__("pack", "starpick"))
    with pytest.raises(PM.PackError, match="두 벌 불일치 caption.pack"):
        ST.load("키치잇판")


def test_sfx_팩_바꾸면_옛칸과_불일치(tmp_styles):
    _edit(tmp_styles, "키치잇판", lambda r: r["packs"]["sfx"].__setitem__("pack", "팩05"))
    with pytest.raises(PM.PackError, match="sfx_files"):
        ST.load("키치잇판")


def test_없는_팩_항목은_거절():
    with pytest.raises(PM.PackError, match="자막팩에 없음"):
        ST.load("키치잇판", patch={"packs": {"caption": {"pack": "없는팩"}}})
    with pytest.raises(PM.PackError, match="slot 아님"):
        ST.load("키치잇판", patch={"packs": {"sfx": {"map": {"pop": "없는소리"}}}})
    with pytest.raises(PM.PackError, match="배경음 목록에 없음"):
        ST.load("키치잇판", patch={"packs": {"bgm": {"id": "nope"}}})
    with pytest.raises(PM.PackError, match="등장 효과팩 번호"):
        ST.load("키치잇판", patch={"packs": {"motion": {"pack": "dynamic_pop"}}})


def test_회원_patch_는_packs_만_뼈대칸_거절():
    with pytest.raises(ST.StyleError, match="packs 만"):
        ST.load("키치잇판", patch={"placement": {"rules": {}}})


def test_회원_patch_합치기_엔진기본_판_patch_순서와_원본불변():
    before = hashlib.sha256(ST.path_of("키치잇판").read_bytes()).hexdigest()
    base = ST.load("키치잇판")
    for _ in range(2):
        st = ST.load("키치잇판", patch={"packs": {"bgm": {"id": "sweets"}, "sfx": {"map": {"pop": "둥"}}, "motion": {"pack": "3"}}})
        assert st["bgm"]["id"] == "sweets"
        assert st["sfx_files"]["pop"] == "팩01/dung.wav" and st["sfx_files"]["ding"] == "팩01/ding.wav"   # 바꾼 칸만
        assert PM.snapshot_fields(st)["motionPack"] == "3"
    assert ST.load("키치잇판") == base
    assert hashlib.sha256(ST.path_of("키치잇판").read_bytes()).hexdigest() == before
    assert PM.merge()["motion"] == {"pack": "off", "graphics": "off"}


def test_상속판_목록패치_적용_잇템로그판_v2():
    v1 = ST.load("잇템로그판")["script"]
    v2 = ST.load("잇템로그판_v2")["script"]
    ids = [a["id"] for a in v2["audit"]]
    assert ids == [a["id"] for a in v1["audit"]] + ["has_line_jeonun"]
    last = next(a for a in v2["audit"] if a["id"] == "ending_last")
    assert "겠다" in last["pattern"] and last != next(a for a in v1["audit"] if a["id"] == "ending_last")
    assert len(v2["brief"]) == len(v1["brief"]) + 3
    assert "audit_patch" not in v2 and "brief_patch" not in v2


def test_상속판_통째목록은_거절(tmp_styles):
    _edit(tmp_styles, "잇템로그판_v2", lambda r: r["script"].__setitem__("audit", []))
    with pytest.raises(ST.StyleError, match="통째로"):
        ST.load("잇템로그판_v2")


def test_목록패치_없는_id_는_거절(tmp_styles):
    _edit(tmp_styles, "잇템로그판_v2", lambda r: r["script"]["audit_patch"].__setitem__("remove", ["없는규칙"]))
    with pytest.raises(ST.StyleError, match="없는규칙"):
        ST.load("잇템로그판_v2")


def test_모션그래픽팩은_render_bench_가_거절():
    st = ST.load("키치잇판")
    st["packs"]["motion"]["graphics"] = "dynamic_pop"
    with pytest.raises(PM.PackError, match="그리는 길 없음"):
        PM.snapshot_fields(st)


def test_snapshot_fields_는_validate_snapshot_통과():
    from shopping_shorts import scene_style
    for n in ST.names():
        st = ST.load(n)
        if st["renderer"] != "bench":
            continue
        f = PM.snapshot_fields(st)
        assert f["captionPack"] == st["caption"]["pack"]
        scene_style.validate_snapshot({"version": 1, "mode": "story", "presetId": "plain", "sceneIndex": 0, **f})


@pytest.mark.parametrize("name,own", [("키치잇판", "kitchit"), ("꿀템노트판", "kkultemnote"), ("스타픽룸판", "starpick"),
                                      ("굿레터판", "goodletter"), ("잇템로그판", "ititemlog")])
def test_칼카피_판_벤치실측_자막팩_1위는_자기팩(name, own):
    st = ST.load(name)
    R = PM.cap_rank(PM.bench_caption(PM.slug_of(st), st))
    assert R[0]["pack"] == own, R[:3]


def test_sfx_옛칸_파일이_실제로_있다():
    for n in ST.names():
        st = ST.load(n)
        for k, v in (st.get("sfx_files") or {}).items():
            if k in ("gain_db", "why") or str(v).startswith("meme_sfx:"):
                continue
            assert (PM.SFX_DIR / v).exists(), (n, k, v)


def test_팩요청_판마다_절_하나_다시써도_안덮는다(tmp_path, monkeypatch):
    monkeypatch.setattr(PM, "ROOT", tmp_path)
    r = [{"element": "자막팩", "owner": "235", "measure": "m", "frames": "f", "want": "w", "stand_in": "clean"}]
    PM.write_requests("A판", "x", r)
    PM.write_requests("B판", "x", r + r)
    PM.write_requests("A판", "x", r)
    t = (tmp_path / "channel/x/_kal/팩요청.md").read_text(encoding="utf-8")
    assert t.count("<!-- 판:A판 -->") == 1 and t.count("<!-- 판:B판 -->") == 1 and "B판#2" in t


def test_글꼴_잉크_실측이_벤치값과_같다():
    """키치잇 스타일분석 §1: Jalnan2 73px 잉크 높이 69~70(픽셀) — 팩 크기를 잉크로 바꾸는 자가 이 값과 맞아야 거리 px 항목이 뜻이 있다."""
    assert abs(PM.font_ink("Jalnan2", 73) - 69.5) <= 2


def test_자막크기는_팩변형으로만_없으면_거절():
    """표준 §11-3 ㉑: 크기 주인 = 자막팩 — packs.caption.variants 는 팩에 있는 변형만(ititemlog 에 size 변형 없음 → 거절, 팩요청)."""
    with pytest.raises(PM.PackError, match="그 변형 없음"):
        ST.load("잇템로그판", patch={"packs": {"caption": {"variants": {"size": "large"}}}})
    st = ST.load("키치잇판", patch={"packs": {"caption": {"variants": {"enter": "typing"}}}})
    assert st["packs"]["caption"]["variants"] == {"enter": "typing"}
    for n in ST.names():          # 판 caption 에 크기 칸을 만들지 않는다
        assert not {"size", "px", "font_size"} & set(json.loads(ST.path_of(n).read_text(encoding="utf-8")).get("caption") or {}), n


def test_업그레이드판_상위편_큰자막은_팩요청_gap():
    st = ST.load("잇템로그판_v2")
    assert any("size:large" in g for g in st["packs"]["caption"]["gap"])
    assert st["packs"]["caption"]["pack"] == "ititemlog" and st["caption"]["pack"] == "ititemlog"
    t = (PM.ROOT / "channel/ititemlog/_kal/팩요청.md").read_text(encoding="utf-8")
    assert "잇템로그판_v2#" in t and "size:large" in t
