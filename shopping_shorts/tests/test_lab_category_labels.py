# -*- coding: utf-8 -*-
"""실험실 팔레트 머리글이 소재 종류에 맞게 나온다 (2026-08-17).

★사장님: "레시피 틀로 고정돼서 재료·반죽 준비 이런 게 들어왔다. 상황에 맞게 몇 개
  만들어놔야 할 듯."
  실측(job 202377f690d9) — 젤펜 영상 4개 전부 `category=기타`인데 화면엔
  '🥣 재료·반죽 준비 · 섞기·짜기'가 떴다. scene_lab.html의 GROUPS가 요리 전용으로
  하드코딩돼 있었다(굽기·반죽·초콜릿·토핑).

고침: 서버가 소재 카테고리를 실어 보내고(api_mix_scene_lab_data → data.category),
화면이 GROUPS_BY_CAT에서 그에 맞는 머리글을 고른다.
★키(완성/after/굽기/마무리/재료/기타)는 **안 바꾼다** — groupOf·useTags·서버
  _ROLE_WANT_SHOTS가 그 키로 돈다. 사람이 읽는 title·hint만 갈아끼운다.

여기서는 **서버가 카테고리를 실제로 넘기는지**를 지킨다(화면 쪽 라벨 표는 JS라
파이썬 테스트로 못 본다 — 대신 값이 안 가면 화면이 영원히 중립 라벨이 된다).
"""
import sqlite3

from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_url로_카테고리를_읽는다(tmp_path):
    st = _store(tmp_path)
    url = "https://www.instagram.com/reel/AAA111/"
    with sqlite3.connect(str(tmp_path / "t.db")) as c:
        c.execute("INSERT INTO script_wiki(customer_id, shortcode, source_url, category) "
                  "VALUES(?,?,?,?)", (0, "AAA111", url, "레시피"))
    assert st.wiki_category_for_url(url) == "레시피"


def test_모르는_url은_None(tmp_path):
    """못 찾으면 None → 서버가 ""로 넘기고 화면은 중립 라벨로 간다(억지 추측 없음)."""
    st = _store(tmp_path)
    assert st.wiki_category_for_url("https://example.com/none") is None
    assert st.wiki_category_for_url("") is None
    assert st.wiki_category_for_url(None) is None


def test_카테고리가_비어있으면_None(tmp_path):
    """빈 문자열은 '모른다'와 같다 — 빈 값으로 레시피 틀을 씌우면 안 된다."""
    st = _store(tmp_path)
    url = "https://www.instagram.com/reel/BBB222/"
    with sqlite3.connect(str(tmp_path / "t.db")) as c:
        c.execute("INSERT INTO script_wiki(customer_id, shortcode, source_url, category) "
                  "VALUES(?,?,?,?)", (0, "BBB222", url, "   "))
    assert st.wiki_category_for_url(url) is None


def test_최신_기록을_쓴다(tmp_path):
    """같은 URL이 재분류됐으면 나중 것 — 옛 분류로 화면이 틀리면 안 된다."""
    st = _store(tmp_path)
    url = "https://www.instagram.com/reel/CCC333/"
    with sqlite3.connect(str(tmp_path / "t.db")) as c:
        c.execute("INSERT INTO script_wiki(customer_id, shortcode, source_url, category) "
                  "VALUES(?,?,?,?)", (0, "CCC333-old", url, "레시피"))
        c.execute("INSERT INTO script_wiki(customer_id, shortcode, source_url, category) "
                  "VALUES(?,?,?,?)", (0, "CCC333-new", url, "홈템"))
    assert st.wiki_category_for_url(url) == "홈템"


def test_라벨_표가_화면에_있다():
    """★JS 표가 통째로 사라지면 젤펜에 '재료·반죽 준비'가 다시 뜬다."""
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "static" / "scene_lab.html").read_text("utf-8")
    assert "GROUPS_BY_CAT" in html
    for cat in ("레시피", "홈템", "뷰티"):
        assert cat in html, "카테고리 %r 라벨이 없다" % cat
    # 키는 그대로여야 한다(groupOf·useTags·서버 _ROLE_WANT_SHOTS와 짝)
    for key in ("'완성'", "'after'", "'굽기'", "'마무리'", "'재료'", "'기타'"):
        assert key in html
