# -*- coding: utf-8 -*-
"""channelkit.registry — 엔진 모듈이 보는 `spec`은 현재 채널 spec으로 위임되는 프록시다."""
import importlib
import sys
import types

import pytest

from shopping_shorts.channelkit import registry, spec


def _fake_channel(name, **consts):
    """테스트용 채널 spec 모듈을 sys.modules에 심는다."""
    mod = types.ModuleType(f"shopping_shorts.channel_presets.{name}.spec")
    for k, v in consts.items():
        setattr(mod, k, v)
    pkg = types.ModuleType(f"shopping_shorts.channel_presets.{name}")
    pkg.__path__ = []
    sys.modules[f"shopping_shorts.channel_presets.{name}"] = pkg
    sys.modules[f"shopping_shorts.channel_presets.{name}.spec"] = mod
    return mod


@pytest.fixture(autouse=True)
def _restore():
    yield
    registry.use(registry.DEFAULT)


def test_default_is_brainbulb():
    registry.use(registry.DEFAULT)
    assert registry.current().__name__ == "shopping_shorts.channel_presets.brainbulb.spec"
    assert spec.CANVAS_W == 1080 and spec.CANVAS_H == 1920


def test_use_switches_proxy():
    _fake_channel("fakech", CANVAS_W=720, CANVAS_H=1280)
    registry.use("fakech")
    assert spec.CANVAS_W == 720
    registry.use(registry.DEFAULT)
    assert spec.CANVAS_W == 1080


def test_missing_attr_raises_and_getattr_default_works():
    _fake_channel("fakech2", CANVAS_W=1)
    registry.use("fakech2")
    with pytest.raises(AttributeError):
        spec.NO_SUCH_CONSTANT
    assert getattr(spec, "FACE_MODEL", None) is None


def test_fonts_dir_moved_with_channel():
    registry.use(registry.DEFAULT)
    import os
    assert os.path.isfile(os.path.join(spec.FONTS_DIR, "SBAggroB.ttf"))
    assert "channel_presets" in spec.FONTS_DIR.replace("\\", "/")
