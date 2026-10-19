"""호환 shim — 옛 경로 `shopping_shorts.brainbulb.<모듈>`을 `shopping_shorts.channelkit`으로 넘긴다.

brainbulb는 2026-09-25에 채널 엔진(channelkit) + 채널 spec (channels/brainbulb)으로 쪼개졌다.
brainbulb_api.py·static/brainbulb.html·옛 테스트가 이 경로를 쓴다. 새 코드는 channelkit을 직접 import.
"""
import importlib
import sys

_KIT = "shopping_shorts.channelkit"
_NAMES = ["pipeline", "spec", "lint", "layout", "ass_gen", "render", "review", "frames", "measure",
          "timing", "voice", "sfx", "prompt", "providers", "make"]
# 뇌전구 전용 모듈은 2026-09-25에 channel_presets/brainbulb/로 옮겼다
_CH = "shopping_shorts.channel_presets.brainbulb"
_CH_NAMES = ["images", "photos", "photocheck", "community", "steps"]


def __getattr__(name):
    if name in _NAMES:
        mod = importlib.import_module(f"{_KIT}.{name}")
        sys.modules[f"{__name__}.{name}"] = mod
        return mod
    if name in _CH_NAMES:
        mod = importlib.import_module(f"{_CH}.{name}")
        sys.modules[f"{__name__}.{name}"] = mod
        return mod
    raise AttributeError(name)


# `from shopping_shorts.brainbulb import X` 는 위 __getattr__로 되지만
# `import shopping_shorts.brainbulb.providers` (서브모듈 import 문법)은 sys.modules에 미리 있어야 한다.
for _n in _NAMES:
    try:
        sys.modules[f"{__name__}.{_n}"] = importlib.import_module(f"{_KIT}.{_n}")
    except ImportError:
        pass
for _n in _CH_NAMES:
    try:
        sys.modules[f"{__name__}.{_n}"] = importlib.import_module(f"{_CH}.{_n}")
    except ImportError:
        pass
