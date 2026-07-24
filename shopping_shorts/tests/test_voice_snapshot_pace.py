from shopping_shorts import app


def test_snapshot_pace_mode_default_on():
    """UI가 pace_mode를 안 보내도 기본 ON(쇼츠 핵심). preset_id 없으면 store 미접근."""
    snap = app._voice_snapshot(None, {})
    assert snap["pace_mode"] is True


def test_snapshot_pace_mode_respects_off():
    """사장님이 끄면 그대로 False로 스냅샷에 담긴다."""
    snap = app._voice_snapshot(None, {"pace_mode": False})
    assert snap["pace_mode"] is False
