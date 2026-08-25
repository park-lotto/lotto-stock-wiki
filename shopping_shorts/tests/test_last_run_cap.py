# -*- coding: utf-8 -*-
"""마지막 수집 결과에 상한이 걸려 있는지 (2026-08-24).

★왜 필요한가 (라이브 실측)
   '주소로 가져오기'는 새 1건을 앞에 붙이고 나머지를 그대로 둔다 — 지우는 쪽이
   없어서 계속 커졌다. 유튜브가 8,281건(4.47MB)까지 쌓였고,
   /api/reference 한 번에 그걸 다 내려보냈다(실측 974ms).
   관리자 목록 응답에도 통째로 딸려가 6.25MB가 됐던 원인이기도 하다.

   ★2026-08-25: 자르는 **기준**이 틀려 회귀가 났다. 목록은 최신순이 아니라
   수집 순서라, 뒤에서 훑는 채널이 통째로 사라졌다. 이제 자르기 전에 최신순으로
   정렬한다(_newest_first). 아래 test_newest_by_age_survives가 그 규칙을 지킨다.
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
    store.save_last_run_platform("youtube", _items(Store.LAST_RUN_MAX_ITEMS + 500), "2026-08-24")
    got, _at = store.load_last_run_platform("youtube")
    assert len(got) == Store.LAST_RUN_MAX_ITEMS


def test_instagram_save_is_capped_the_same(store):
    """★두 경로가 다른 상한을 쓰면 어긋난다(0순위-B)."""
    store.save_last_run(_items(Store.LAST_RUN_MAX_ITEMS + 500), "2026-08-24")
    got, _at = store.load_last_run()
    assert len(got) == Store.LAST_RUN_MAX_ITEMS


def test_newest_survives_the_cut(store):
    """★자르는 쪽은 **뒤(오래된 것)**여야 한다. 앞을 자르면 방금 등록한 게 사라진다."""
    store.save_last_run_platform("youtube", _items(Store.LAST_RUN_MAX_ITEMS + 500), "2026-08-24")
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


def test_newest_by_age_survives(store):
    """★회귀 방지(2026-08-25): 수집 순서가 뒤죽박죽이어도 **최신이 남고 오래된 것이 잘린다**.

    정렬 없이 자르면 '뒤에서 수집됐다'는 이유만으로 채널이 통째로 사라진다
    (실측: 8,580건 중 5,580건이 잘려 썰쇼핑 채널이 화면에서 없어졌다)."""
    n = Store.LAST_RUN_MAX_ITEMS
    old = [{"shortcode": "old%d" % i, "age_hours": 300.0} for i in range(n)]
    fresh = [{"shortcode": "fresh%d" % i, "age_hours": 1.0} for i in range(500)]
    store.save_last_run_platform("youtube", old + fresh, "2026-08-25")   # 최신이 뒤에 있다
    got, _at = store.load_last_run_platform("youtube")
    kept = {g["shortcode"] for g in got}
    assert all(("fresh%d" % i) in kept for i in range(500)), "최신 500건이 잘려나갔다"
    assert len(got) == n
