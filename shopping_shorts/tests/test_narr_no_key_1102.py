"""스피치매틱스 키가 없어도 줄별 받아쓰기가 위스퍼로 돈다(11-02 회원 계획 실패)."""
from tools.calcopy.engine import asr_local, check_line_sync, narr_verify as NV


def test_no_key_falls_back_to_whisper(monkeypatch, tmp_path):
    f = tmp_path / "v.wav"
    f.write_bytes(b"x")
    monkeypatch.setattr(NV, "CACHE", tmp_path / "c")
    monkeypatch.setattr(asr_local, "speechmatics_key", lambda: "")
    monkeypatch.setattr(check_line_sync, "asr_segments", lambda p: [(0.1, 0.5, "안녕")])
    assert NV.heard_words(f) == [{"s": 0.1, "e": 0.5, "w": "안녕", "conf": 1.0}]
