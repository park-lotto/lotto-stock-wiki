# -*- coding: utf-8 -*-
"""완성본(compose)이 장면 영상에 입히는 효과마다 캡컷이 싣는 법이 정해져 있나(관제 191).

compose 에 새 효과가 생겼는데 scene_style.CAPCUT_SCENE_FX 에 줄이 없으면 실패한다 —
캡컷에서만 조용히 빠지던 일(흐림 가림막·영상 칸 밖 검정·장면 강조·틀 카메라)을 다시 못 하게."""
import inspect
import re

from shopping_shorts import scene_style

# compose·그 도우미가 읽는 키 중 효과가 아닌 것(파일 자리·시간)
_NOT_FX = {"file", "pattern", "start", "end", "level", "sec", "fx", "zoom_in"}


def _keys(fn):
    src = inspect.getsource(fn)
    return set(re.findall(r"""(?:effect|layer|\(effect or \{\}\)|\(layer or \{\}\))(?:\.get\(|\[)["'](\w+)["']""", src))


def test_every_compose_effect_has_capcut_route():
    used = set()
    for fn in (scene_style.compose, scene_style.media_geometry, scene_style.zoom_move_vf,
               scene_style.shock_vf, scene_style.dim_of):
        used |= _keys(fn)
    missing = sorted(used - _NOT_FX - set(scene_style.CAPCUT_SCENE_FX))
    assert not missing, f"캡컷이 싣는 법이 없는 완성본 효과: {missing} — scene_style.CAPCUT_SCENE_FX 에 정하라"


def test_needs_bake_follows_table():
    assert scene_style._needs_bake({"masks": [{"fx": "blur"}]}, {})
    assert not scene_style._needs_bake({"masks": [{"fx": "fill"}]}, {})
    assert scene_style._needs_bake({"highlight": {"cx": .5, "on": True}}, {})
    assert not scene_style._needs_bake({"highlight": {"cx": .5, "on": False}}, {})   # 꺼 둔 강조(실측 job 607562e55ddf 33장면)
    assert scene_style._needs_bake({}, {"camera": [{"zoom": 1}, {"zoom": 1.2}]})
    assert not scene_style._needs_bake({"zoom": 1.3, "shock": True}, {"camera": [{"zoom": 1}]})


def test_dim_spans_lays_black_outside_media_box(tmp_path):
    from PIL import Image
    scenes = [{"start": 0.0, "end": 1.0}, {"start": 1.0, "end": 2.0}]
    layers = [{"media": {"top": 35, "height": 65}, "file": "a.png"}, {"media": {"top": 0, "height": 100}, "file": "b.png"}]
    out = scene_style.dim_spans(scenes, {"mode": "story", "presetId": "t11", "sceneIndex": 0, "effects": {}}, layers, tmp_path)
    assert [(o["start"], o["end"]) for o in out] == [(0.0, 1.0)]          # 칸이 화면 전체인 장면엔 깔지 않는다
    img = Image.open(out[0]["path"])
    assert img.getpixel((10, 10))[3] == 255 and img.getpixel((10, 1900))[3] == 0
