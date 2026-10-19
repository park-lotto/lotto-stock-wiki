# -*- coding: utf-8 -*-
"""현재 채널 — 엔진 모듈이 `from . import spec`으로 보는 값은 여기 등록된 채널 spec으로 위임된다.

왜 프록시인가: 엔진 20모듈이 79개 상수를 `spec.X`로 읽는다(2026-09-25 실측). 함수마다 spec을 넘기면
전부 고쳐야 하고, 채널을 바꾸는 자리는 pipeline.run_step 하나면 된다.
★숨은 전역 상태다 — 바꾸는 곳은 `use()` 하나뿐이어야 한다(0순위-B). 테스트는 fixture로 되돌린다.
"""
import importlib

DEFAULT = "brainbulb"
_current = None


def use(name):
    """채널 spec 모듈을 현재 채널로. → 모듈"""
    global _current
    _current = importlib.import_module(f"shopping_shorts.channel_presets.{name}.spec")
    return _current


def current():
    if _current is None:
        use(DEFAULT)
    return _current


def name():
    return current().__name__.split(".")[-2]
