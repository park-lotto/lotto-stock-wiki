# -*- coding: utf-8 -*-
"""공용 풀은 꺼둔·죽은 키를 다시 담지 않는다 (2026-09-01).

## 왜 생겼나

`get_pooled_keys`(공용 풀)에 status 필터가 **없었다**. 바로 위 개인 경로
`get_customer_keys_plain`은 2026-08-25(cid 57 실사고)에 `!= 'off'`가 붙었는데
공용 쪽은 안 붙어, 같은 판단이 두 곳에 있고 한쪽만 고쳐진 상태였다(0순위-B).

결과: keypool.resync_pools가 **웹 기동·키 등록·키 삭제·워커 기동마다** 돌면서
꺼둔 키를 풀에 되돌려 놓았다. 키를 격리하거나 죽었다고 표시해도 목록 자체가
매번 되살아나므로, 격리·프로브를 아무리 잘 만들어도 무효가 된다.

## ★제외형이어야 하는 이유

status 기본값이 'unknown'이다(store.py:1114 DEFAULT 'unknown').
포함형(= 'ok')으로 쓰면 **아직 검증 안 된 정상 키가 통째로 사라져** 라이브
용량이 급감한다. 그래서 NOT IN ('off','bad')으로 **나쁜 것만** 뺀다.
"""
import importlib

import pytest

from shopping_shorts import keycrypt, keyroute
from shopping_shorts.store import Store

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 유효한 Fernet 키(44자). 테스트 전용


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    return Store(str(tmp_path / "t.db"))


def _set_status(store, key_id, status):
    with store._conn() as c:
        c.execute("UPDATE customer_keys SET status=? WHERE id=?", (status, key_id))


def test_pool_keeps_ok_unknown_null_and_drops_off_bad(store):
    """★핵심: 나쁜 것만 빠지고 나머지는 전부 남는다."""
    # ★status는 NOT NULL DEFAULT 'unknown'이다(store.py:1114) — NULL은 스키마상
    #   불가능하다. COALESCE는 옛 행 방어용으로 남기되, 검증은 실제 값들로 한다.
    for i, st in enumerate(["ok", "unknown", "empty", "off", "bad"]):
        store.add_customer_key(100 + i, keyroute.SVC_GEMINI, f"KEY-{st}")
        with store._conn() as c:
            kid = c.execute("SELECT MAX(id) FROM customer_keys").fetchone()[0]
        _set_status(store, kid, "" if st == "empty" else st)

    pooled = store.get_pooled_keys(keyroute.SVC_GEMINI)
    assert "KEY-ok" in pooled
    assert "KEY-unknown" in pooled          # ★기본값 — 빠지면 라이브 용량이 급감한다
    assert "KEY-empty" in pooled            # 빈 문자열도 정상 취급(제외형이라 안 걸린다)
    assert "KEY-off" not in pooled          # 사장님이 끈 키
    assert "KEY-bad" not in pooled          # 죽은 키


def test_pool_matches_personal_path_filter(store):
    """★두 경로가 같은 판단을 봐야 한다 — 이 사고의 뿌리가 '한쪽만 고쳐진 것'이다."""
    store.add_customer_key(7, keyroute.SVC_GEMINI, "MINE")
    with store._conn() as c:
        kid = c.execute("SELECT MAX(id) FROM customer_keys").fetchone()[0]
    _set_status(store, kid, "off")
    assert store.get_customer_keys_plain(7, keyroute.SVC_GEMINI) == []   # 개인 경로
    assert "MINE" not in store.get_pooled_keys(keyroute.SVC_GEMINI)      # 공용 풀도 같다


def test_reenabling_key_returns_it_to_pool(store):
    """되살릴 수 있어야 한다 — 오판으로 끈 키를 사장님이 다시 켜면 즉시 풀로 돌아온다."""
    store.add_customer_key(9, keyroute.SVC_GEMINI, "REVIVE")
    with store._conn() as c:
        kid = c.execute("SELECT MAX(id) FROM customer_keys").fetchone()[0]
    _set_status(store, kid, "bad")
    assert "REVIVE" not in store.get_pooled_keys(keyroute.SVC_GEMINI)
    _set_status(store, kid, "ok")
    assert "REVIVE" in store.get_pooled_keys(keyroute.SVC_GEMINI)
