# -*- coding: utf-8 -*-
"""모션그래픽팩(관제 222) — 저장값 검사·캡컷 판정·편집기 파일 허용·관리자 스위치.
그림 대조(레퍼런스 vs 완성본·썸네일·캡컷)는 tools/mograph/check_countdown.py 가 결과물로 잰다."""
import re
from pathlib import Path

import pytest

from shopping_shorts import scene_style

PACK = Path(__file__).resolve().parents[1] / "static" / "motion-graphics-pack.js"


def _snap(mask):
    return {"version": 1, "mode": "story", "presetId": "t11", "effects": {"1": {"masks": [mask]}}}


def _mask(**kw):
    return {"kind": "mograph", "mograph": "countdown321", "l": 27.6, "t": 42.7, "w": 44.8, "h": 25.2,
            "shape": "rect", "fx": "solid", "color": "#FFFFFF", "op": 100, "soft": 0, "rot": 0, **kw}


def test_validate_keeps_mograph_item():
    out = scene_style.validate_snapshot(_snap(_mask()))
    m = out["effects"]["1"]["masks"][0]
    assert m["kind"] == "mograph" and m["mograph"] == "countdown321"
    assert (m["l"], m["t"], m["w"], m["h"]) == (27.6, 42.7, 44.8, 25.2)


def test_validate_rejects_bad_mograph_name():
    with pytest.raises(ValueError, match="모션그래픽"):
        scene_style.validate_snapshot(_snap(_mask(mograph="../x")))


def test_capcut_bakes_mograph_scene():
    # 움직임이 본체라 캡컷 정지 그림으로 멈추면 안 된다 — 완성본에서 떠 온다
    assert scene_style._needs_bake({"masks": [_mask()]}, {})
    assert not scene_style._needs_bake({"masks": [{**_mask(), "kind": "graphic", "graphic": "check"}]}, {})


def test_pack_ids_fit_server_rule():
    # 팩 파일의 효과 이름은 서버 검사 규칙([a-z0-9_]{1,32})에 맞아야 저장된다
    src = PACK.read_text(encoding="utf-8")
    body = src[src.index("const ITEMS={"):src.index("};", src.index("const ITEMS={"))]
    ids = re.findall(r"^\s{2}([A-Za-z0-9_]+):\{", body, re.M)
    assert ids and all(re.fullmatch(r"[a-z0-9_]{1,32}", i) for i in ids)


def test_editor_can_load_pack_file_and_font():
    from shopping_shorts import app
    assert app.api_scene_style_asset("shopping_shorts/static/motion-graphics-pack.js").status_code == 200
    assert app.api_scene_style_asset("shopping_shorts/static/fonts/Righteous-Regular.ttf").status_code == 200


def test_admin_switch_key():
    from shopping_shorts import app
    assert "mograph_enabled" in app._ADMIN_SETTING_KEYS
