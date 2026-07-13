import tempfile
from pathlib import Path
from shopping_shorts import audio_post


def test_no_op_returns_input_untouched(monkeypatch):
    """tempo=1.0 + silence off면 ffmpeg 호출 없이 입력경로 그대로 반환."""
    called = {"n": 0}
    monkeypatch.setattr(audio_post.subprocess, "run", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    p = Path(tempfile.mkdtemp()) / "in.mp3"
    p.write_bytes(b"ID3")
    out = audio_post.post_process(str(p), str(p), tempo=1.0, silence_trim="off")
    assert out == str(p)
    assert called["n"] == 0


def test_builds_filter_chain(monkeypatch):
    cmd = {}
    def fake_run(c, **k):
        cmd["c"] = c
        Path(c[-1]).write_bytes(b"ID3out")
        class R: returncode = 0
        return R()
    monkeypatch.setattr(audio_post.subprocess, "run", fake_run)

    src = Path(tempfile.mkdtemp()) / "in.mp3"; src.write_bytes(b"ID3")
    dst = Path(tempfile.mkdtemp()) / "out.mp3"
    audio_post.post_process(str(src), str(dst), tempo=1.25, silence_trim="mid")
    af = cmd["c"][cmd["c"].index("-af") + 1]
    assert "atempo=1.25" in af
    assert "silenceremove" in af


def test_inplace_same_path_uses_tempfile(monkeypatch):
    """in==out이면 ffmpeg 출력이 입력과 다른 임시파일이어야(같으면 ffmpeg 실패)."""
    cmd = {}
    def fake_run(c, **k):
        cmd["c"] = c
        Path(c[-1]).write_bytes(b"ID3out")
        class R: returncode = 0
        return R()
    monkeypatch.setattr(audio_post.subprocess, "run", fake_run)

    p = Path(tempfile.mkdtemp()) / "same.mp3"; p.write_bytes(b"ID3-original")
    out = audio_post.post_process(str(p), str(p), tempo=1.25, silence_trim="off")
    assert out == str(p)
    # ffmpeg에 넘긴 출력경로(마지막 인자)는 입력과 달라야 한다
    assert cmd["c"][-1] != str(p)
    assert cmd["c"][cmd["c"].index("-i") + 1] == str(p)
    # 교체 결과가 out_path에 반영됨
    assert p.read_bytes() == b"ID3out"


def test_silence_level_params():
    assert audio_post._silence_filter("off") is None
    assert "stop_threshold" in audio_post._silence_filter("weak")
    import re
    def dur(level):
        return float(re.search(r"stop_duration=([\d.]+)", audio_post._silence_filter(level)).group(1))
    assert dur("strong") < dur("mid") < dur("weak")
