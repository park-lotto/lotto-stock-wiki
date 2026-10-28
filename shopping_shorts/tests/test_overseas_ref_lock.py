# -*- coding: utf-8 -*-
"""2026-10-09 사이트 전면 멈춤: ig_add 동시 저장 → UNIQUE 오류 → 쓰기 트랜잭션 연 채 연결이 남아 DB 쓰기 전체가 막혔다."""
import sqlite3
import threading

from shopping_shorts import config, overseas_ref as o


def _items():
    return [{"user": "acme_shop", "code": "ABC", "likes": 5, "caption": "nice chair #chair", "q": "chair"}]


def test_concurrent_add_does_not_fail_or_lock(tmp_path, monkeypatch):
    db = tmp_path / "r.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    errs = []
    def go():
        try:
            o.add_instagram("cat", _items())
        except Exception as e:      # noqa: BLE001
            errs.append(e)
    ts = [threading.Thread(target=go) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs
    c = sqlite3.connect(db, timeout=0.5)       # 아무도 쓰기 잠금을 쥐고 있지 않아야 즉시 쓸 수 있다
    c.execute("CREATE TABLE IF NOT EXISTS z(x)"); c.execute("INSERT INTO z VALUES(1)"); c.commit()
    assert c.execute("SELECT COUNT(*) FROM overseas_ref_channel").fetchone()[0] == 1


def test_error_mid_save_releases_lock(tmp_path, monkeypatch):
    db = tmp_path / "r.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    o.add_instagram("cat", _items())
    def boom(*a, **k):
        raise RuntimeError("x")
    real = o._save
    def half(c, *a, **k):
        c.execute("UPDATE overseas_ref_channel SET subs=1")    # 쓰기 트랜잭션 열린 상태에서
        boom()
    monkeypatch.setattr(o, "_save", half)
    try:
        o.add_instagram("cat", _items())
    except RuntimeError:
        pass
    c = sqlite3.connect(db, timeout=0.5)
    c.execute("UPDATE overseas_ref_channel SET subs=2"); c.commit()   # 잠겨 있으면 database is locked
