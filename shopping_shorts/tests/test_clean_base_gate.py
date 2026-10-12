# -*- coding: utf-8 -*-
"""clean_base_enabled 스위치 — 기본 끔, 판정은 app._setting_gate 하나."""
from shopping_shorts import mix_pipeline as mp


class _S:
    def __init__(self, v): self.v = v
    def get_setting(self, k, d=None): return self.v if k == "clean_base_enabled" else d


def test_default_off():
    assert mp.clean_base_on(_S(""), 42) is False
    assert mp.clean_base_on(_S("0"), 0) is False


def test_all_on():
    assert mp.clean_base_on(_S("1"), 42) is True


def test_admin_only(monkeypatch):
    from shopping_shorts import app as _app
    monkeypatch.setattr(_app, "_is_admin", lambda cid: cid == 0)
    assert mp.clean_base_on(_S("admin"), 0) is True
    assert mp.clean_base_on(_S("admin"), 42) is False


def test_customer_list(monkeypatch):
    from shopping_shorts import app as _app
    monkeypatch.setattr(_app, "_is_admin", lambda cid: False)
    monkeypatch.setattr(_app, "_as_cid", lambda cid: int(cid))
    assert mp.clean_base_on(_S("11,42"), 42) is True
    assert mp.clean_base_on(_S("11,42"), 7) is False


def test_key_is_registered_in_admin_settings():
    from shopping_shorts import app as _app
    import inspect
    assert '"clean_base_enabled"' in inspect.getsource(_app)
