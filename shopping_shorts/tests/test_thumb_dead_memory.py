# -*- coding: utf-8 -*-
"""썸네일 프록시 죽은 주소 기억(2026-10-01 관제 064): 확정 404/403은 60분, 타임아웃은 5분. 살아있는 건 그대로."""
import time
import types

import requests

from shopping_shorts import app as A


def _dead_url(tag):
    return "https://scontent-nrt1-1.cdninstagram.com/v/t51.82787-15/%s.jpg" % tag


def _call(monkeypatch, exc):
    def _get(url, **kw):
        raise exc
    monkeypatch.setattr(requests, "get", _get)
    monkeypatch.setattr(A, "_thumb_via_oembed", lambda url, sc: None)
    monkeypatch.setattr(A, "_yt_thumb_alternates", lambda url: [])
    monkeypatch.setattr(A, "_thumb_cache_path", lambda url: None)


def test_definitive_404_is_remembered_long(monkeypatch):
    url = _dead_url("dead404"); A._THUMB_NEG.pop(url, None)
    resp = types.SimpleNamespace(status_code=404)
    _call(monkeypatch, requests.HTTPError("404", response=resp))
    r = A.api_thumb(url)
    assert r.status_code == 404
    assert A._THUMB_NEG[url] - time.time() > 3000       # 60분 쪽
    # 기억 중엔 바깥 조회 없이 즉시 404(requests.get 이 불리면 실패)
    monkeypatch.setattr(requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("CDN 재조회")))
    assert A.api_thumb(url).status_code == 404


def test_timeout_is_remembered_short(monkeypatch):
    url = _dead_url("slow"); A._THUMB_NEG.pop(url, None)
    _call(monkeypatch, requests.Timeout("slow"))
    assert A.api_thumb(url).status_code == 404
    left = A._THUMB_NEG[url] - time.time()
    assert 200 < left <= 300


def test_alive_thumb_unchanged(monkeypatch):
    url = _dead_url("alive"); A._THUMB_NEG.pop(url, None)
    class _R:
        status_code = 200; headers = {"Content-Type": "image/jpeg"}; content = b"\xff\xd8\xff\xd9"
        def raise_for_status(self): pass
    monkeypatch.setattr(requests, "get", lambda *a, **k: _R())
    monkeypatch.setattr(A, "_thumb_cache_path", lambda url: None)
    monkeypatch.setattr(A, "_thumb_to_web_format", lambda b, c: (b, c))
    r = A.api_thumb(url)
    assert r.status_code == 200 and url not in A._THUMB_NEG
