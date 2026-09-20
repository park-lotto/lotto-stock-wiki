"""가로형 판정에서 '못 잼(None)'이 '세로형(False)'으로 뭉개지지 않는지.

2026-09-02 라이브 실측:
  「🔗 URL 직접 추가」로 담은 인스타 3편이 video_w/video_h = null 이었다.
  (화면 방향 측정이 prewarm.py에만 있어 autoload 경로는 아예 안 쟀다)
  그런데 app.py가 `bool(is_landscape_wh(w,h))`로 감싸 None → False가 되어
  1단계 화면엔 "세로형 확실"과 똑같이 보였다. 가로 영상을 URL로 담으면
  다운로드·추출 비용을 다 쓴 뒤 3단계 믹스에서야 막힌다(08-28 실측 5건).

is_landscape_wh는 "모르면 None"이 설계다(주석에 명시) — 그 뜻을 API가 보존해야
화면이 '모름'과 '세로형'을 구별할 수 있다.
"""
import pytest

from shopping_shorts.mix_pipeline import is_landscape_wh


def test_unknown_stays_none_not_false():
    """못 재면 None — False(세로형 확실)로 바뀌면 안 된다."""
    assert is_landscape_wh(None, None) is None
    assert is_landscape_wh(0, 0) is None
    assert is_landscape_wh(1080, None) is None
    # 진짜 세로/가로는 확정값이어야 한다
    assert is_landscape_wh(1080, 1920) is False
    assert is_landscape_wh(1920, 1080) is True


def test_api_does_not_flatten_none_to_false():
    """source_brief 응답이 None을 그대로 실어야 한다(bool()로 감싸면 실패).

    실제 라우트를 부르면 DB·인증이 필요해 무거우므로, **그 줄의 계약**을
    직접 확인한다: 소스에 `bool(is_landscape_wh(` 가 남아 있으면 뭉개진 것이다.
    """
    import inspect

    from shopping_shorts import app as app_mod

    src = inspect.getsource(app_mod.api_produce_source_brief)
    assert "is_landscape_wh(" in src, "가로형 판정이 사라졌다"
    assert "bool(is_landscape_wh(" not in src, (
        "None(못 잼)이 False(세로형)로 뭉개진다 — '모름'을 화면이 구별할 수 없게 된다")


def test_autoload_measures_dimensions():
    """autoload도 화면 방향을 잰다 — prewarm에만 있으면 URL 직접 추가가 빠진다."""
    import inspect

    from shopping_shorts import app as app_mod

    src = inspect.getsource(app_mod.api_produce_autoload)
    assert "_probe_wh_dur" in src, (
        "autoload가 화면 방향을 안 잰다 — URL로 담은 영상은 video_w/h가 영영 null이라 "
        "1단계에서 '가로형(롱폼)' 경고를 못 띄운다")
    # ★재기만 하고 result에 안 넣으면 저장(storable)에서 그대로 버려진다 —
    #   "쟀다"가 아니라 "실었다"를 봐야 진짜 가드다.
    assert 'result["video_w"]' in src and 'result["video_h"]' in src, (
        "측정값을 result에 안 실었다 — storable()이 저장 순간 버려서 여전히 null이 된다")
