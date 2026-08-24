# -*- coding: utf-8 -*-
"""마지막 수집 결과에 상한이 걸려 있는지 (2026-08-24).

★왜 필요한가 (라이브 실측)
   '주소로 가져오기'는 새 1건을 앞에 붙이고 나머지를 그대로 둔다 — 지우는 쪽이
   없어서 계속 커졌다. 유튜브가 8,281건(4.47MB)까지 쌓였고,
   /api/reference 한 번에 그걸 다 내려보냈다(실측 974ms).
   관리자 목록 응답에도 통째로 딸려가 6.25MB가 됐던 원인이기도 하다.

   랭킹은 최신순이라 뒤쪽 수천 건은 화면에서 볼 일이 없다.
"""
import pytest
from cryptography.fernet import Fernet

from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    return Store(str(tmp_path / "t.db"))


def _items(n):
    return [{"shortcode": "c%d" % i, "pad": "x" * 40} for i in range(n)]


def test_platform_save_is_capped(store):
    store.save_last_run_platform("youtube", _items(5000), "2026-08-24")
    got, _at = store.load_last_run_platform("youtube")
    assert len(got) == Store.LAST_RUN_MAX_ITEMS


def test_instagram_save_is_capped_the_same(store):
    """★두 경로가 다른 상한을 쓰면 어긋난다(0순위-B)."""
    store.save_last_run(_items(5000), "2026-08-24")
    got, _at = store.load_last_run()
    assert len(got) == Store.LAST_RUN_MAX_ITEMS


def test_newest_survives_the_cut(store):
    """★자르는 쪽은 **뒤(오래된 것)**여야 한다. 앞을 자르면 방금 등록한 게 사라진다."""
    store.save_last_run_platform("youtube", _items(5000), "2026-08-24")
    got, _at = store.load_last_run_platform("youtube")
    assert got[0]["shortcode"] == "c0", "맨 앞(최신)이 잘려나갔다"


def test_under_cap_is_untouched(store):
    """상한 아래면 아무것도 바뀌지 않는다 — 기존 동작 그대로."""
    store.save_last_run_platform("threads", _items(10), "2026-08-24")
    got, at = store.load_last_run_platform("threads")
    assert len(got) == 10 and at == "2026-08-24"


def test_empty_is_safe(store):
    store.save_last_run_platform("tiktok", [], "2026-08-24")
    got, _at = store.load_last_run_platform("tiktok")
    assert got == []
