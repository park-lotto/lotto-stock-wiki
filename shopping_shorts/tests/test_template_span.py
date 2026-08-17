"""span('full'|'first') → dur(초) 변환. 화면의 말과 렌더의 말을 잇는 유일한 지점."""
from shopping_shorts import mix_pipeline as mp


def test_full_span_has_no_dur():
    out = mp._template_layer({"id": "tpl_01", "span": "full"}, first_beat_dur=3.2)
    assert out is not None
    assert "dur" not in out or out["dur"] is None


def test_first_span_uses_first_beat_duration():
    out = mp._template_layer({"id": "tpl_01", "span": "first"}, first_beat_dur=3.2)
    assert out["dur"] == 3.2


def test_first_span_without_beat_falls_back_to_full():
    """비트 길이를 모르면 '첫 장면만'을 흉내내다 0초로 사라지느니 전체로 둔다."""
    out = mp._template_layer({"id": "tpl_01", "span": "first"}, first_beat_dur=0)
    assert "dur" not in out or out["dur"] is None


def test_unknown_template_id_returns_none():
    assert mp._template_layer({"id": "tpl_99", "span": "full"}, first_beat_dur=3) is None


def test_no_template_returns_none():
    assert mp._template_layer(None, first_beat_dur=3) is None
    assert mp._template_layer({}, first_beat_dur=3) is None


def test_abspath_points_at_real_file():
    """경로만 만들고 파일이 없으면 ffmpeg가 통째로 죽는다 — 실재를 확인한다."""
    import os
    out = mp._template_layer({"id": "tpl_01", "span": "full"}, first_beat_dur=3)
    assert os.path.exists(out["_abspath"])


def test_malformed_span_defaults_to_full():
    """모르는 span 값이 오면 전체로 — 조용히 사라지는 것보다 낫다."""
    out = mp._template_layer({"id": "tpl_01", "span": "쓰레기"}, first_beat_dur=3.2)
    assert "dur" not in out or out["dur"] is None
