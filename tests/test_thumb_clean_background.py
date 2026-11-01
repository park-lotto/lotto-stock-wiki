"""덧지우기 실패·재청소 중에도 썸네일 배경은 이미 있는 청소본을 쓴다(관제 299)."""
import pytest
from shopping_shorts import app as A
from shopping_shorts import mix_pipeline as M


@pytest.mark.parametrize("status", ["failed", "cleaning", "ready"])
def test_청소본이_있으면_상태와_무관(tmp_path, monkeypatch, status):
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    monkeypatch.setattr(M, "clean_base_for", lambda job, work: None)
    work = tmp_path / "j1"
    work.mkdir()
    f = work / "final_clean_abc.mp4"
    f.write_bytes(b"x" * 2048)
    job = {"clean_status": status, "subtitle_removal": 1}
    assert A._thumb_clean_background("j1", job) == str(f)


def test_자막제거를_안_켠_작업은_청소본을_안_쓴다(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    work = tmp_path / "j2"
    work.mkdir()
    (work / "final_clean_abc.mp4").write_bytes(b"x" * 2048)
    assert A._thumb_clean_background("j2", {"clean_status": "", "subtitle_removal": 0}) == ""
