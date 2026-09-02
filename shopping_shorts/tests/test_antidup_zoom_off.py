# -*- coding: utf-8 -*-
"""반중복 자동확대는 꺼져 있다 (2026-09-02 사장님 "그 확대를 꺼").

왜 껐나: 사장님이 요청한 기능이 아니었다(2026-07-14 커밋 424974989에서 "말 안 해도
항상 적용"으로 넣은 자동 효과). 원본 구도가 늘 잘렸고, 5단계 자막제거 화면의
BEFORE(원본)/AFTER(조립본) 배율이 달라져 "자막제거를 하면 확대된다"로 보였다.
"""
import importlib

from shopping_shorts import video_assemble as va


def test_기본은_확대_없음():
    assert va._BASE_ZOOM == 1.0
    assert va._KENBURNS_ZOOM == 1.0


def test_일반비트는_자르지_않는다():
    vf = va._base_zoom_vf(None)
    assert "scale=1080:1920" in vf, vf          # 1080*1.04=1123 이면 확대가 남은 것
    assert "crop=1080:1920" in vf and vf.count(":") < 8


def test_훅비트도_켄번즈를_돌지_않는다():
    """zoom_end=1이면 1.3배 늘렸다 줄이는 헛일이라 화질만 손해다."""
    assert "zoompan" not in va._kenburns_vf(3.0)
    assert va._kenburns_vf(3.0) == va._base_zoom_vf(None)


def test_사장님이_지정한_확대는_그대로_산다():
    """6단계에서 직접 맞춘 구도는 자동확대와 별개다 — 같이 꺼지면 안 된다."""
    vf = va._base_zoom_vf({"scene_zoom": 1.5})
    assert "scale=1620:2880" in vf, vf
    assert "crop=1080:1920:270:480" in vf, vf


def test_환경변수로_되돌릴_수_있다(monkeypatch):
    monkeypatch.setenv("SHORTS_ANTIDUP_ZOOM", "1")
    m = importlib.reload(va)
    try:
        assert m._BASE_ZOOM == 1.04 and m._KENBURNS_ZOOM == 1.10
        assert "zoompan" in m._kenburns_vf(3.0)
    finally:
        monkeypatch.delenv("SHORTS_ANTIDUP_ZOOM", raising=False)
        importlib.reload(va)


def test_정지구간_줌은_같이_꺼지지_않는다():
    """대사가 소스보다 길어 마지막 프레임을 정지로 늘릴 때의 줌은 **반중복과 목적이 다르다**.
    "뚝 멈춰 어색하다"는 사장님 육안 피드백(2026-07-19)으로 넣은 것이라 살아 있어야 한다.
    (반중복 확대를 끄면서 이것까지 죽여 test_freeze_motion이 깨졌던 것을 고정한다)"""
    assert va._FREEZE_ZOOM > 1.0
    vf = va._kenburns_vf(2.0, zoom_end=va._FREEZE_ZOOM)
    assert "zoompan" in vf and "*on" in vf
