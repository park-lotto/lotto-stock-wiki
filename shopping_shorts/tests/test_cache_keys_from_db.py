# -*- coding: utf-8 -*-
"""캐시 키는 URL 추론이 아니라 **DB에 적힌 shortcode**를 먼저 읽는다 (2026-08-17).

★왜 이 테스트가 있나 — 실사고:
  `_cache_keys_for_url`이 정규식(인스타·유튜브·틱톡)으로만 키를 만들어서
  **도우인·샤오홍슈는 키가 0개**였다. 그래서 고독스 C100의 쿠팡 재료를
  상세4·리뷰8까지 다 긁어 `product_facts_grab_douyin_b26e5b24ee36`에 저장해뒀는데도
  대본 생성이 **한 번도 못 찾았다**(조용한 실패 — 화면엔 그냥 '재료 없음').

  근본 원인은 저장과 조회가 서로 다른 규칙을 쓴 것이다(CLAUDE.md 0순위-B):
    저장 → DB의 shortcode 그대로 (`grab_douyin_…`)
    조회 → URL에서 정규식 추론   (`grab_` 접두사는 URL에 없다 → 영원히 불발)

  실측(라이브 DB 394건): 수정 전 캐시 적중 130건 → 수정 후 248건(+118), 회귀 0.
  도우인·샤오홍슈뿐 아니라 인스타 46·유튜브 29·틱톡 26건도 새로 적중했다 —
  정규식이 있는 플랫폼조차 `grab_`·짧은해시 키로 저장된 건 못 찾고 있었다.

이 테스트가 지키는 것: **플랫폼이 늘어도 정규식을 안 고쳐도 된다.**
정규식에 없는 URL이라도 DB에 기록이 있으면 반드시 찾아내야 한다.
"""
import sqlite3

from shopping_shorts import mix_pipeline
from shopping_shorts.store import Store


def _store(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    return st


def test_douyin_url_finds_shortcode_from_db(tmp_path):
    """정규식에 없는 플랫폼(도우인)도 DB에 담겨 있으면 캐시 키가 나온다."""
    st = _store(tmp_path)
    url = "https://www.douyin.com/video/7657533491349086970"
    st.mix_basket_add("grab_douyin_b26e5b24ee36", url=url)

    # ★추론으로는 못 만드는 키다 — 이게 0개인 것이 사고의 원인이었다.
    assert _regex_only(url) == []

    assert st.shortcodes_for_url(url) == ["grab_douyin_b26e5b24ee36"]
    assert "grab_douyin_b26e5b24ee36" in _keys_with_db(mix_pipeline, tmp_path, url)


def test_unknown_url_returns_empty_not_crash(tmp_path):
    """기록도 없고 정규식도 안 맞으면 빈 리스트 — 죽지 않는다(종전대로 재추출)."""
    st = _store(tmp_path)
    assert st.shortcodes_for_url("https://example.com/no/such/video") == []
    assert st.shortcodes_for_url("") == []
    assert st.shortcodes_for_url(None) == []


def test_regex_fallback_still_works(tmp_path):
    """DB에 기록이 없어도 인스타 URL은 종전대로 맞힌다(회귀 방지)."""
    url = "https://www.instagram.com/reel/Db_2V-mzT44/"
    keys = _regex_only(url)
    assert "Db_2V-mzT44" in keys
    assert "lens_instagram_Db_2V-mzT44" in keys


def test_db_key_comes_before_guess(tmp_path):
    """DB 키가 추론 키보다 앞에 온다 — 적힌 것이 짐작보다 정확하다."""
    st = _store(tmp_path)
    url = "https://www.tiktok.com/@x/video/7458060642738605355"
    st.mix_basket_add("lens_tiktok_1jw6i6i", url=url)   # 짧은해시 = 추론 불가 키
    got = st.shortcodes_for_url(url)
    assert got == ["lens_tiktok_1jw6i6i"]


def test_script_wiki_source_url_also_searched(tmp_path):
    """담기 기록이 없어도 위키에 남은 source_url로 찾는다."""
    st = _store(tmp_path)
    url = "https://www.rednote.com/search_result/6834528c0000000023010908"
    with sqlite3.connect(str(tmp_path / "t.db")) as c:
        c.execute("INSERT INTO script_wiki(customer_id, shortcode, source_url) "
                  "VALUES(?,?,?)", (0, "grab_xhs_abc123", url))
    assert st.shortcodes_for_url(url) == ["grab_xhs_abc123"]


# --- helpers -------------------------------------------------------------

def _regex_only(url):
    """DB를 빼고 정규식만 돌린 결과 — 수정 전 동작과 같다."""
    keys = []
    for rx, plat in zip(mix_pipeline._SHORTCODE_RES, mix_pipeline._SHORTCODE_PLATFORMS):
        m = rx.search(url or "")
        if m:
            keys.append(m.group(1))
            keys.append("lens_%s_%s" % (plat, m.group(1)))
            break
    return keys


def _keys_with_db(mp, tmp_path, url):
    """`_cache_keys_for_url`이 보는 DB를 테스트용으로 바꿔 실행한다."""
    import shopping_shorts.config as cfg
    old = cfg.DB_PATH
    cfg.DB_PATH = str(tmp_path / "t.db")
    try:
        return mp._cache_keys_for_url(url)
    finally:
        cfg.DB_PATH = old
