from shopping_shorts import vmake_client as vc


def test_sign_deterministic():
    a = vc._sign("appkey", "secret", "1700000000", "nonce123")
    b = vc._sign("appkey", "secret", "1700000000", "nonce123")
    assert a == b
    assert isinstance(a, str) and len(a) >= 16


def test_sign_changes_with_input():
    base = vc._sign("appkey", "secret", "1700000000", "n1")
    assert base != vc._sign("appkey", "secret", "1700000000", "n2")
    assert base != vc._sign("appkey", "secret", "1700000001", "n1")
    assert base != vc._sign("appkey", "other", "1700000000", "n1")


def test_auth_headers_shape():
    h = vc._auth_headers("appkey", "secret", timestamp="1700000000", nonce="n1")
    assert h["X-App-Key"] == "appkey"
    assert h["X-Timestamp"] == "1700000000"
    assert h["X-Nonce"] == "n1"
    assert "X-Sign" in h and h["X-Sign"]


import pytest


def test_remove_subtitles_orchestration(tmp_path, monkeypatch):
    calls = {}
    monkeypatch.setattr(vc, "_submit", lambda video, key: calls.setdefault("job", "JOB1") or "JOB1")
    monkeypatch.setattr(vc, "_poll", lambda job, key, timeout: "http://x/result.mp4")
    def fake_dl(url, dest):
        calls["dl"] = (url, str(dest))
        open(dest, "wb").write(b"clean")
        return str(dest)
    monkeypatch.setattr(vc, "_download", fake_dl)

    out = tmp_path / "clean.mp4"
    result = vc.remove_subtitles(str(tmp_path / "in.mp4"), "key:secret", out_path=str(out))
    assert result == str(out)
    assert calls["job"] == "JOB1"
    assert calls["dl"][0] == "http://x/result.mp4"
    assert out.read_bytes() == b"clean"


def test_remove_subtitles_no_key_raises(tmp_path):
    with pytest.raises(ValueError, match="API 키"):
        vc.remove_subtitles(str(tmp_path / "in.mp4"), "", out_path=str(tmp_path / "o.mp4"))


def test_poll_timeout_raises(monkeypatch):
    monkeypatch.setattr(vc, "_request", lambda *a, **k: {"status": "pending"})
    with pytest.raises(TimeoutError):
        vc._poll("JOB1", "key:secret", timeout=0)
