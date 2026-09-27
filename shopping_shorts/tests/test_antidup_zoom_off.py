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


def test_정지구간_확대도_없다_미리보기와_같은_정지(monkeypatch):
    """정지 구간 켄번즈도 뺐다(2026-09-27 사장님 결정). 편집 화면 미리보기는 정지 컷을 그냥 정지로 보여주므로
    완성본도 같아야 한다(30 job 대조 "정지컷만 밀림" 17칸의 유일한 원인). 정지 구간 ffmpeg 필터에 zoompan 이 없어야 한다."""
    assert va._FREEZE_ZOOM == 1.0
    assert "zoompan" not in va._kenburns_vf(2.0, zoom_end=va._FREEZE_ZOOM)
    calls = []
    monkeypatch.setattr(va, "_run_ffmpeg", lambda cmd, *a, **k: calls.append(cmd))
    va._extend_with_frozen_motion("in.mp4", play_out=1.0, freeze=1.0, out_path="out.mp4", frames=60)
    vf = calls[0][calls[0].index("-vf") + 1]
    assert "tpad=stop_mode=clone" in vf and "zoompan" not in vf, vf
    assert calls[0][calls[0].index("-frames:v") + 1] == "60"
