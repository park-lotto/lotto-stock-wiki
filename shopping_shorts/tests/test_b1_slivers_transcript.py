# -*- coding: utf-8 -*-
"""1단계 B1 — 끝 조각 합치기·전사 실패 사유(2026-09-05 서버 30편 실측: 끝 0.03초 조각 24편, 전사 0/30인데 사유 몰랐다)."""


def test_끝의_한_프레임_조각은_앞_구간에_합친다():
    from shopping_shorts.frame_script import merge_slivers
    assert merge_slivers([0.0, 3.2, 6.1, 9.97, 10.0]) == [0.0, 3.2, 6.1, 10.0]


def test_첫_조각과_중간_조각도_합치고_0과_끝은_남긴다():
    from shopping_shorts.frame_script import merge_slivers
    assert merge_slivers([0.0, 0.1, 4.0, 4.2, 8.0]) == [0.0, 4.0, 8.0]
    assert merge_slivers([0.0, 0.2]) == [0.0, 0.2]          # 경계 2개면 그대로
    assert merge_slivers([0.0, 5.0, 10.0]) == [0.0, 5.0, 10.0]


def test_기본_경계가_조각을_합친_뒤_긴_구간을_나눈다(monkeypatch):
    from shopping_shorts import frame_script as F, scene_cut, frame_extract
    monkeypatch.setattr(frame_extract, "_probe_duration", lambda p: 10.0)
    monkeypatch.setattr(scene_cut, "detect_cuts", lambda p, threshold=0.3: [(0, 96), (96, 299)])
    monkeypatch.setattr(scene_cut, "video_fps", lambda p: 30.0)
    b = F._default_boundaries("x.mp4")
    assert b[0] == 0.0 and b[-1] == 10.0 and all(y - x >= 0.5 for x, y in zip(b, b[1:]))
    assert 3.2 in b and 9.967 not in b          # 299/30=9.967 끝 조각은 사라진다


def _run(monkeypatch, *, audio, words, groq):
    from shopping_shorts import frame_script as F, config
    monkeypatch.setattr(config, "GROQ_API_KEY", groq)
    monkeypatch.setattr(F, "_default_boundaries", lambda p: [0.0, 2.0, 4.0])
    return F.extract_script_frames(
        "v.mp4", "v", "", get_boundaries=lambda p: [0.0, 2.0, 4.0],
        extract_frame_at=lambda video, t, out: out, extract_audio=lambda v, o: audio,
        transcribe_words=lambda mp3: words,
        tag_frames=lambda groups, caption, segs, brief=None: [{"seg_no": i + 1, "scene_desc": "장면"} for i in range(len(groups))],
        story_brief=lambda *a, **k: {}, translate=lambda t: [])


def test_전사_실패_사유가_결과에_남는다(monkeypatch):
    assert _run(monkeypatch, audio=None, words=None, groq="k")["transcript_status"] == "audio_extract_failed"
    assert _run(monkeypatch, audio="a.mp3", words=None, groq="")["transcript_status"] == "no_groq_key"
    assert _run(monkeypatch, audio="a.mp3", words=None, groq="k")["transcript_status"] == "asr_none"
    assert _run(monkeypatch, audio="a.mp3", words=[], groq="k")["transcript_status"] == "asr_empty"
    assert _run(monkeypatch, audio="a.mp3", words=[{"word": "안녕", "start": 0.1, "end": 0.5}], groq="k")["transcript_status"] == "ok"


def test_전사_HTTP_실패_사유가_남는다(monkeypatch, tmp_path):
    from shopping_shorts import asr_check as A, config

    class _R:
        status_code = 429; text = '{"error":"rate limit"}'

        def json(self):
            return {}
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")
    monkeypatch.setattr(A.requests, "post", lambda *a, **k: _R())
    mp3 = tmp_path / "a.mp3"; mp3.write_bytes(b"x")
    assert A.transcribe_words(str(mp3), language=None) is None
    assert A.last_error().startswith("HTTP 429") and "rate limit" in A.last_error()
