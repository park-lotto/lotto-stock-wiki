# -*- coding: utf-8 -*-
"""자막 등장 효과 계약(2026-10-05, 관제 127 자막팩 2단계).

못 박는 것:
1. 효과 목록은 static/caption-motions.js 한 곳 — 서버 검증(scene_style.caption_motion_keys)이 그 파일을 읽는다(손으로 적은 짝 목록 금지).
2. 기존 7종(rise·grow·pop·slide·drop·fade·wide)은 그대로 남는다 — 고객이 저장해 둔 값이 거절되면 안 된다.
3. 편집기 화면은 계약 파일을 편집기 스크립트보다 먼저 싣고, 서버는 그 파일을 편집기 자산으로 내준다.
4. 편집기는 자기 목록을 따로 적지 않고 window.CAPTION_MOTIONS 를 쓴다.
결과물(렌더·완성 영상·편집기 화면) 검사는 tools/caption_pack/check_motions.py · check_editor_live.py.
"""
import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import scene_style
from shopping_shorts import app as app_module

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "shopping_shorts/static/caption-motions.js"


def _motions():
    return json.loads(CONTRACT.read_text(encoding="utf-8").split("/*JSON*/")[1])


def test_서버_검증은_계약_파일의_키를_쓴다():
    keys = scene_style.caption_motion_keys()
    assert keys == tuple(_motions())
    for old in ("rise", "grow", "pop", "slide", "drop", "fade", "wide"):
        assert old in keys
    snap = {"version": 1, "mode": "story", "presetId": "plain", "sceneIndex": 0, "frameKind": "hook"}
    for k in keys:
        assert scene_style.validate_snapshot({**snap, "bodyCaptionMotion": k})["bodyCaptionMotion"] == k
    with pytest.raises(ValueError):
        scene_style.validate_snapshot({**snap, "bodyCaptionMotion": "sky"})


def test_효과마다_필수칸과_단위값():
    for k, m in _motions().items():
        assert m["label"] and m["ms"] > 0 and len(m["frames"]) >= 2, k
        assert m.get("unit") in (None, "word", "char"), k


def test_편집기는_계약_파일을_먼저_싣고_자기_목록이_없다():
    html = (ROOT / "out/scene-style-ui-showcase.html").read_text(encoding="utf-8")
    assert html.index("caption-motions.js") < html.index("precision20-ui.js")
    js = (ROOT / "out/precision20-ui.js").read_text(encoding="utf-8")
    assert "const BODY_CAPTION_MOTIONS=window.CAPTION_MOTIONS" in js
    assert "rise:{label:" not in js


def test_서버가_계약_파일을_편집기_자산으로_내준다():
    c = TestClient(app_module.app)
    r = c.get("/api/produce/scene-style/assets/shopping_shorts/static/caption-motions.js")
    assert r.status_code == 200 and "CAPTION_MOTIONS" in r.text


def test_렌더러는_글자_단위_움직임도_굳혀_찍는다():
    js = (ROOT / "tools/render_scene_style.js").read_text(encoding="utf-8")
    assert ".cap-u" in js


# ── 자막팩(3단계) ────────────────────────────────────────────────────────────
def _packs():
    return json.loads(CONTRACT.read_text(encoding="utf-8").split("/*PACKS*/")[1])


def test_팩은_계약_파일_한_곳이고_칸_효과가_모두_있다():
    packs, motions = _packs(), _motions()
    assert scene_style.caption_pack_keys() == tuple(packs)
    for k, p in packs.items():
        slots = json.loads(CONTRACT.read_text(encoding="utf-8").split("root.CAPTION_SLOTS = ")[1].split(";")[0])
        assert set(p["slots"]) == set(slots), k   # 팩마다 모든 칸이 채워져 있다(빈 칸이면 그 장면만 등장이 빠진다)
        assert all(v in motions for v in p["slots"].values()), k


def test_서버는_팩_값을_저장하고_모르는_팩은_거절():
    snap = {"version": 1, "mode": "story", "presetId": "plain", "sceneIndex": 0, "frameKind": "hook"}
    for k in scene_style.caption_pack_keys():
        assert scene_style.validate_snapshot({**snap, "captionPack": k})["captionPack"] == k
    with pytest.raises(ValueError):
        scene_style.validate_snapshot({**snap, "captionPack": "nope"})


def test_렌더러는_등장_여부를_장면마다_편집기에_묻는다():
    # 저장값(bodyCaptionMotion·captionPack)으로 따로 짐작하면 '팩 없이 어둡게 강조만 켠 장면'처럼 편집기만 움직이고 완성본은 멈춘다(10-05 합본 실측)
    js = (ROOT / "tools/render_scene_style.js").read_text(encoding="utf-8")
    assert "const enter=await page.evaluate(()=>window.sceneStyle.captionEnterAt?.(100000)||0);" in js
    assert "request.snapshot.bodyCaptionMotion" not in js


# ── 자막팩 관리자 스위치(2026-10-06) ─────────────────────────────────────────
def test_스위치_뒤_항목은_계약_파일에_표시되고_옛_항목은_아니다():
    motions, wfx = _motions(), json.loads(CONTRACT.read_text(encoding="utf-8").split("/*WORDFX*/")[1])
    for old in ("rise", "grow", "pop", "slide", "drop", "fade", "wide"):
        assert not motions[old].get("pack"), old          # 고객이 쓰던 효과는 스위치와 무관하게 보인다
    assert not wfx["box"].get("pack") and not wfx["color"].get("pack")
    assert all(m.get("pack") for k, m in motions.items() if k not in ("rise", "grow", "pop", "slide", "drop", "fade", "wide"))


def test_자막팩_스위치는_관리자_설정이고_편집기에_알린다():
    src = (ROOT / "shopping_shorts/app.py").read_text(encoding="utf-8")
    assert '"caption_pack_enabled"' in src.split("_ADMIN_SETTING_KEYS")[1].split("}")[0]
    assert 'context["captionPackEnabled"] = bool(_setting_gate(Store(DB_PATH), "caption_pack_enabled", _cid(request)))' in src
    js = (ROOT / "out/precision20-ui.js").read_text(encoding="utf-8")
    assert "sceneContext?.captionPackEnabled!==false" in js
