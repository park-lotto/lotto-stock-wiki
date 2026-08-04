"""내부검색 제품명 직접검색(2026-08-04 2차) — 순환 구멍 봉인 계약.

잠그는 것: 태그 겹침이 0이라도 **판독된 제품명이 같으면** 결과에 나온다.
종전 구조는 태그 겹침 후보 안에서만 같은 제품을 찾아서, 태그가 어긋난 영상은
제품명이 캐시돼 있어도 영영 안 나왔다(사장님 제보 "있는 것 중에서 못 잡는다").
"""
from unittest.mock import patch

import pytest

from shopping_shorts import app as ap
from shopping_shorts.store import Store


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "t.db")
    store = Store(path)
    with store._conn() as c:
        for sc, user, tags in [
            ("QRY", "chan_a", '["살림꿀팁","주방용품"]'),
            ("SAME", "chan_b", '["인테리어","분위기"]'),      # 겹침 0 — 태그로는 절대 못 만남
            ("NEAR", "chan_c", '["살림꿀팁","정리"]'),          # 겹침 1 — 종전에도 후보
        ]:
            c.execute("INSERT INTO channel_archive(username, shortcode, url, thumbnail, "
                      " views, likes, comments, posted_at) VALUES(?,?,?,?,1,1,1,'2026-01-01')",
                      (user, sc, "u", "t"))
            c.execute("INSERT INTO vision_tags(shortcode, subject, keywords_json, created_at) "
                      "VALUES(?, '', ?, datetime('now'))", (sc, tags))
    store.save_product("SAME", "스텐 채칼")   # 이미 판독돼 있던 같은 제품
    store.save_product("NEAR", "극세사 걸레")
    return path


def _call(db_path, **kw):
    with patch.object(ap, "DB_PATH", db_path), \
         patch.object(ap, "_require_admin", lambda req: None), \
         patch("shopping_shorts.product_name.identify_many",
               lambda items, dbp: {"QRY": "전동 채칼"}):
        return ap.api_archive_similar(request=None, shortcode="QRY", **kw)


def test_same_product_surfaces_even_with_zero_tag_overlap(db):
    out = _call(db)
    codes = [i["shortcode"] for i in out["items"]]
    assert "SAME" in codes, "겹침0이어도 제품명이 같으면 나와야 한다 — 순환 구멍 회귀"
    same = next(i for i in out["items"] if i["shortcode"] == "SAME")
    assert same["same_product"] is True
    assert codes[0] == "SAME", "같은 제품이 최상단"


def test_different_product_not_marked_same(db):
    out = _call(db)
    near = next(i for i in out["items"] if i["shortcode"] == "NEAR")
    assert near["same_product"] is False   # 극세사 걸레 ≠ 전동 채칼
