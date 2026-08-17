# -*- coding: utf-8 -*-
"""역대 히트작 문턱 버튼을 '구간'으로 끊는다(2026-08-17).

왜: 문턱만 낮추는 구조라 1만+/3천+/1천+ 세 버튼이 **같은 400건**을 줬다.
댓글 내림차순 상위 400을 자르니 문턱을 낮춰도 얼굴이 그대로였다
(실측: 셋 다 400건, 1위 _miso.home 132,424) → 눌러도 화면이 안 바뀌었다.
"""
import sqlite3

import pytest

from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    with s._conn() as c:
        for n in (50000, 12000, 9999, 5000, 3000, 2999, 1500, 1000, 999):
            c.execute(
                "INSERT INTO channel_archive(username, shortcode, url, thumbnail,"
                " views, likes, comments, posted_at, first_seen, last_seen)"
                " VALUES('u',?,'','t',0,0,?,'2026-07-01',datetime('now'),datetime('now'))",
                (f"s{n}", n))
    return s


def _c(rows):
    return sorted(r["comments"] for r in rows)


def test_1만은_상한_없이_전부(store):
    assert _c(store.archive_hits(min_comments=10000)) == [12000, 50000]


def test_3천대는_1만_이상을_안_보여준다(store):
    got = _c(store.archive_hits(min_comments=3000, max_comments=9999))
    assert got == [3000, 5000, 9999]
    assert 12000 not in got and 50000 not in got


def test_1천대는_3천대와도_안_겹친다(store):
    got = _c(store.archive_hits(min_comments=1000, max_comments=2999))
    assert got == [1000, 1500, 2999]


def test_세_구간이_서로_하나도_안_겹친다(store):
    a = set(_c(store.archive_hits(min_comments=10000)))
    b = set(_c(store.archive_hits(min_comments=3000, max_comments=9999)))
    c = set(_c(store.archive_hits(min_comments=1000, max_comments=2999)))
    assert not (a & b) and not (b & c) and not (a & c)


def test_상한_0이면_예전처럼_문턱_이상_전부(store):
    """기존 호출부(상한 없이 부르던 곳)가 그대로 동작해야 한다."""
    assert _c(store.archive_hits(min_comments=1000, max_comments=0)) == \
        [1000, 1500, 2999, 3000, 5000, 9999, 12000, 50000]
