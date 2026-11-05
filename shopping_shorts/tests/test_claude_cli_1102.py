"""엔진 PATH 에 claude 가 없어도 렌더가 죽지 않는다(11-02 회원 FileNotFoundError)."""
from tools.calcopy.engine import claude_cli as CC


def test_no_claude_returns_error_not_raise(monkeypatch):
    monkeypatch.setattr(CC, "claude_exe", lambda: None)
    assert CC.ask([], "x", tag="t", model="m") == (None, "claude 실행 파일 없음")


def test_finds_local_bin_when_not_on_path(monkeypatch, tmp_path):
    (tmp_path / ".local/bin").mkdir(parents=True)
    (tmp_path / ".local/bin/claude.exe").write_bytes(b"x")
    monkeypatch.setattr(CC.shutil, "which", lambda n: None)
    monkeypatch.setattr(CC.Path, "home", lambda: tmp_path)
    assert CC.claude_exe().endswith("claude.exe")
