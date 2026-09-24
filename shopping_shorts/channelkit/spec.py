# -*- coding: utf-8 -*-
"""spec 프록시 — `spec.X`를 현재 채널(registry.current())의 X로 넘긴다. 상수는 channel_presets/<이름>/spec.py에.

PEP 562 모듈 __getattr__. `getattr(spec, "X", None)`도 그대로 된다(안쪽 AttributeError가 기본값으로 떨어짐).
"""
from . import registry


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return getattr(registry.current(), name)


def __dir__():
    return sorted(set(dir(registry.current())))
