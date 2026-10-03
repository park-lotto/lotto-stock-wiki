# -*- coding: utf-8 -*-
"""영상·음성 파일 전송의 주인 _send_media (2026-10-01 관제 062).

스위치(xsendfile_enabled=1) + 아파치 경유(X-Forwarded-*) + 허용 폴더 안 + ASCII 경로 → 본문 없이 X-Sendfile 헤더.
그 외(스위치 꺼짐·직결·폴더 밖·한글 경로)는 종전 파이썬 Range 전송 그대로.
허용 폴더는 tmp(ASCII)로 바꿔 시험한다 — 이 저장소 경로엔 한글이 있어 헤더에 못 싣는다.
"""
import types
from pathlib import Path

from shopping_shorts import app as A
from shopping_shorts.store import Store


def _req(headers=None):
    return types.SimpleNamespace(headers={k.lower(): v for k, v in (headers or {}).items()})


def _setup(tmp_path, monkeypatch, on):
    root = tmp_path / "media"; root.mkdir()
    monkeypatch.setattr(A, "_XSF_ROOTS", (root,))
    db = tmp_path / "t.db"; st = Store(str(db)); st.set_setting("xsendfile_enabled", "1" if on else "")
    monkeypatch.setattr(A, "DB_PATH", str(db)); A._XSF_CACHE["t"] = 0.0
    f = root / "clip.mp4"; f.write_bytes(b"\x00" * 1000)
    return root, f


def test_off_keeps_python_range(tmp_path, monkeypatch):
    _, f = _setup(tmp_path, monkeypatch, False)
    r = A._send_media(str(f), _req({"Range": "bytes=0-9", "X-Forwarded-For": "1.2.3.4"}))
    assert r.status_code == 206 and r.headers["content-range"] == "bytes 0-9/1000"
    assert "x-sendfile" not in r.headers


def test_on_proxied_in_root_gives_xsendfile_header_only(tmp_path, monkeypatch):
    _, f = _setup(tmp_path, monkeypatch, True)
    r = A._send_media(str(f), _req({"Range": "bytes=0-9", "X-Forwarded-For": "1.2.3.4"}))
    assert r.status_code == 200 and r.headers["x-sendfile"] == str(f.resolve())
    assert r.headers["content-type"] == "video/mp4" and r.body == b""
    r2 = A._send_media(str(f), _req({"X-Forwarded-Proto": "https"}), "video/mp4", filename="숏템 영상.mp4")
    assert r2.headers["x-sendfile"] == str(f.resolve()) and "filename*=utf-8''" in r2.headers["content-disposition"]


def test_on_but_direct_or_outside_root_or_korean_path_falls_back(tmp_path, monkeypatch):
    root, f = _setup(tmp_path, monkeypatch, True)
    r = A._send_media(str(f), _req({"Range": "bytes=0-9"}))                       # 아파치를 안 거침(직결)
    assert r.status_code == 206 and "x-sendfile" not in r.headers
    out = tmp_path / "out.mp4"; out.write_bytes(b"\x00" * 100)                    # 허용 폴더 밖
    r = A._send_media(str(out), _req({"Range": "bytes=0-9", "X-Forwarded-For": "1.2.3.4"}))
    assert r.status_code == 206 and "x-sendfile" not in r.headers
    k = root / "한글.mp4"; k.write_bytes(b"\x00" * 100)                            # 헤더에 못 싣는 경로
    r = A._send_media(str(k), _req({"Range": "bytes=0-9", "X-Forwarded-For": "1.2.3.4"}))
    assert r.status_code == 206 and "x-sendfile" not in r.headers


def test_range_media_response_routes_through_owner(tmp_path, monkeypatch):
    _, f = _setup(tmp_path, monkeypatch, True)
    r = A._range_media_response(str(f), _req({"X-Forwarded-For": "1.2.3.4"}), "audio/mpeg")
    assert r.headers.get("x-sendfile") == str(f.resolve()) and r.headers["content-type"] == "audio/mpeg"


def test_unreadable_by_apache_is_chmodded_or_falls_back(tmp_path, monkeypatch):
    """2026-10-02 03:18 사고: 0600 파일에 X-Sendfile 헤더를 줘 아파치가 404(고객 음성 83건). o+r 없으면 0644로 바꾸고, 못 바꾸면 파이썬 전송."""
    _, f = _setup(tmp_path, monkeypatch, True)
    key = str(f.resolve())
    modes = {key: 0o100600}
    class _St:
        def __init__(self, m): self.st_mode = m
    orig = A._xsf_readable
    def ch_ok(p, m): modes[str(p)] = 0o100000 | m
    monkeypatch.setattr(A, "_xsf_readable", lambda rp: orig(rp, chmod=ch_ok, stat=lambda p: _St(modes[str(p)])))
    r = A._send_media(str(f), _req({"X-Forwarded-For": "1.2.3.4"}))
    assert r.headers.get("x-sendfile") == key and modes[key] & 0o004          # 0600 → 0644 → X-Sendfile
    modes[key] = 0o100600
    def ch_fail(p, m): raise OSError("read-only")
    monkeypatch.setattr(A, "_xsf_readable", lambda rp: orig(rp, chmod=ch_fail, stat=lambda p: _St(modes[str(p)])))
    r = A._send_media(str(f), _req({"Range": "bytes=0-9", "X-Forwarded-For": "1.2.3.4"}))
    assert r.status_code == 206 and "x-sendfile" not in r.headers              # 못 바꾸면 파이썬 전송
