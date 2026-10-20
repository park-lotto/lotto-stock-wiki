# -*- coding: utf-8 -*-
"""구글 일시 과부하(503)면 다음 키로 넘어간다(관제 247).

종전: seo_generate·thumb_title·product_name 이 503을 받으면 첫 키에서 바로 None —
과부하 시간대(10-19 23시~10-20 01시) 제목·태그 생성이 66번 실패했다."""
import json

import pytest

from shopping_shorts import seo_generate, thumb_title, product_name


class _Resp:
    def __init__(self, text):
        self.text = text


def _fake_clients(monkeypatch, mod_vault, payload):
    calls = {"n": 0}

    class _Models:
        def generate_content(self, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
            return _Resp(json.dumps(payload))

    class _Client:
        models = _Models()

    monkeypatch.setattr(mod_vault, "get_client_for_key", lambda k: _Client(), raising=False)
    monkeypatch.setattr(mod_vault, "pick_paced_key", lambda pool: pool[0] if pool else None)
    return calls


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)


def test_seo_503_다음키로(monkeypatch):
    monkeypatch.setattr(seo_generate.keyroute, "gemini_keys", lambda g: ["k1", "k2"])
    monkeypatch.setattr(seo_generate, "_build_prompt", lambda *a, **k: "p")
    calls = _fake_clients(monkeypatch, seo_generate.key_vault, {"title": "t"})
    assert seo_generate.generate({}) == {"title": "t"}
    assert calls["n"] == 2


def test_thumb_title_503_다음키로(monkeypatch):
    monkeypatch.setattr(thumb_title.keyroute, "gemini_keys", lambda g: ["k1", "k2"])
    monkeypatch.setattr(thumb_title, "_build_prompt", lambda *a, **k: "p")
    calls = _fake_clients(monkeypatch, thumb_title.key_vault, {"titles": [{"text": "제목"}]})
    out = thumb_title.generate({"given_script": "x"})
    assert out and out[0]["text"]
    assert calls["n"] == 2


def test_seo_503_계속이면_포기(monkeypatch):
    """끝없이 기다리지 않는다 — 일시 장애 재시도는 3번까지."""
    monkeypatch.setattr(seo_generate.keyroute, "gemini_keys", lambda g: ["k%d" % i for i in range(10)])
    monkeypatch.setattr(seo_generate, "_build_prompt", lambda *a, **k: "p")
    n = {"c": 0}

    class _M:
        def generate_content(self, **kw):
            n["c"] += 1
            raise RuntimeError("503 UNAVAILABLE")

    class _C:
        models = _M()

    monkeypatch.setattr(seo_generate.key_vault, "get_client_for_key", lambda k: _C())
    monkeypatch.setattr(seo_generate.key_vault, "pick_paced_key", lambda pool: pool[0] if pool else None)
    assert seo_generate.generate({}) is None
    assert n["c"] == 4
