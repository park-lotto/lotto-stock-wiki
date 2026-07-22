from shopping_shorts.video_assemble import _effective_dur, _TRIM_FLOOR, _beat_timeline
import shopping_shorts.video_assemble as va


def test_effective_dur_subtracts_both_edges():
    assert _effective_dur(5.0, head_trim=0.5, tail_trim=1.0) == 3.5


def test_effective_dur_no_trim_returns_probe():
    assert _effective_dur(4.2) == 4.2


def test_effective_dur_floor_guard_blocks_overtrim():
    # 과트림: 남는 길이가 floor 밑이면 floor로 고정(음수/역전 방지)
    assert _effective_dur(1.0, tail_trim=0.9, floor=0.4) == 0.4


def test_effective_dur_negative_trim_treated_as_zero():
    assert _effective_dur(3.0, head_trim=-1.0, tail_trim=-2.0) == 3.0


def test_beat_timeline_applies_tail_trim(monkeypatch):
    # probe를 고정(실 ffprobe 대신) — 각 tts 5.0초로 가정
    monkeypatch.setattr(va, "_probe_duration", lambda p: 5.0)
    plan = {"beats": [
        {"beat_idx": 0, "narration": "가", "tail_trim": 1.0},
        {"beat_idx": 1, "narration": "나"},
    ]}
    tts = {0: "a.mp3", 1: "b.mp3"}
    tl = _beat_timeline(plan, tts)
    assert abs(tl[0]["dur"] - 4.0) < 1e-6          # 5.0 - 1.0 트림
    assert abs(tl[1]["dur"] - 5.0) < 1e-6          # 트림 없음
    assert abs(tl[1]["t0"] - 4.0) < 1e-6           # 다음 비트 t0가 함께 당겨짐
    assert abs(tl[0]["head_trim"] - 0.0) < 1e-6    # 캡컷용 head_trim 노출
