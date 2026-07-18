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


def test_burn_captions_t0가_caption_drawtexts로_그대로_전달된다(tmp_path, monkeypatch):
    """캐릭터라이제이션: _burn_captions가 _beat_timeline의 t0를
    _caption_drawtexts에 순서대로 위치인자(5번째)로 넘기는지 고정한다.
    이 경계가 깨지면 자막·모션(전환) 배치가 어긋난다."""
    import shopping_shorts.video_assemble as va

    font = tmp_path / "f.ttf"
    font.write_bytes(b"\x00")
    base = tmp_path / "base.mp4"
    base.write_bytes(b"\x00")

    monkeypatch.setattr(va, "_run_ffmpeg", lambda cmd, **k: None)
    monkeypatch.setattr(va, "_resolve_font", lambda: str(font))
    monkeypatch.setattr(va.shutil, "copy", lambda *a, **k: None)

    captured_t0 = []

    def fake_drawtexts(narration, dur, work, idx, t0=0.0, style=None, real_durs=None, cap_offset=0.0):
        captured_t0.append(t0)
        return []

    monkeypatch.setattr(va, "_caption_drawtexts", fake_drawtexts)

    tts = {0: "a.mp3", 1: "b.mp3", 2: "c.mp3"}
    with patch("shopping_shorts.video_assemble._probe_duration", side_effect=[3.0, 4.0, 2.0]):
        va._burn_captions(str(base), _plan(), tts, str(tmp_path / "out.mp4"), tmp_path, None, None, None)

    assert captured_t0 == [0.0, 3.0, 7.0]
