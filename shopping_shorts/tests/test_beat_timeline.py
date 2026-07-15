from unittest.mock import patch

from shopping_shorts.video_assemble import _beat_timeline


def _plan():
    return {"beats": [
        {"beat_idx": 0, "role": "hook", "narration": "훅 문장"},
        {"beat_idx": 1, "role": "body", "narration": "본문 문장"},
        {"beat_idx": 2, "role": "cta", "narration": "마무리"},
    ]}


def test_t0_누적으로_비트_경계를_만든다():
    tts = {0: "a.mp3", 1: "b.mp3", 2: "c.mp3"}
    with patch("shopping_shorts.video_assemble._probe_duration", side_effect=[3.0, 4.0, 2.0]):
        tl = _beat_timeline(_plan(), tts)
    assert [x["t0"] for x in tl] == [0.0, 3.0, 7.0]
    assert [x["dur"] for x in tl] == [3.0, 4.0, 2.0]
    assert [x["beat_idx"] for x in tl] == [0, 1, 2]
    assert tl[0]["role"] == "hook"
    assert tl[1]["narration"] == "본문 문장"


def test_tts없는_비트는_건너뛴다():
    tts = {0: "a.mp3", 2: "c.mp3"}          # 비트1 tts 없음
    with patch("shopping_shorts.video_assemble._probe_duration", side_effect=[3.0, 2.0]):
        tl = _beat_timeline(_plan(), tts)
    assert [x["beat_idx"] for x in tl] == [0, 2]
    assert [x["t0"] for x in tl] == [0.0, 3.0]


def test_비트가_없으면_빈리스트():
    assert _beat_timeline({"beats": []}, {}) == []
