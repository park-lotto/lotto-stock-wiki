"""원클릭 담기(북마클릿/유저스크립트 → /api/grab → 모음집) 테스트 (2026-07-18)."""
import base64
import re
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def test_mix_basket_add_is_idempotent(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert s.mix_basket_add("grab_x", url="u", customer_id=0) is True
    assert s.mix_basket_add("grab_x", url="u", customer_id=0) is False   # 중복=안 빠지고 유지
    assert "grab_x" in s.mix_basket_shortcodes(customer_id=0)


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", False)   # 인증 off → cid=0(legacy)로 담김
    return TestClient(appmod.app)


def test_grab_adds_xiaohongshu_to_basket(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/grab", params={"url": "https://www.xiaohongshu.com/discovery/item/abc",
                                   "title": "발광 물총", "thumbnail": "t.jpg"})
    assert r.status_code == 200 and "담겼어요" in r.text
    scs = Store(str(tmp_path / "t.db")).mix_basket_shortcodes(customer_id=0)
    assert any(x.startswith("grab_xiaohongshu_") for x in scs)


def test_grab_accepts_rednote_search_result(tmp_path, monkeypatch):
    """카드별 담기(v1.2.0)가 보내는 rednote.com/search_result URL을 담아야 한다.
    한국 로그인 도메인이 rednote.com이라 www.xiaohongshu.com은 게스트벽이고 카드는 rednote에서 뜬다."""
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/grab", params={"url": "https://www.rednote.com/search_result/6884d27e0000000012",
                                   "title": "香蕉鸡蛋饼", "thumbnail": "t.jpg"})
    assert r.status_code == 200 and "담겼어요" in r.text
    scs = Store(str(tmp_path / "t.db")).mix_basket_shortcodes(customer_id=0)
    assert any(x.startswith("grab_xiaohongshu_") for x in scs)   # rednote=샤오홍슈 플랫폼


def test_grab_userscript_is_thin_loader(tmp_path, monkeypatch):
    """grab.user.js는 로직을 서버에서 불러오는 '로더'여야 한다(재설치 없이 업데이트되게)."""
    c = _client(tmp_path, monkeypatch)
    r = c.get("/grab.user.js")
    assert r.status_code == 200
    assert "GM_xmlhttpRequest" in r.text and "/grab_logic.js" in r.text


def test_grab_logic_served_with_card_logic(tmp_path, monkeypatch):
    """/grab_logic.js는 실제 담기 로직(카드별 버튼 포함)을 서빙한다."""
    c = _client(tmp_path, monkeypatch)
    r = c.get("/grab_logic.js")
    assert r.status_code == 200
    assert "addCardBtns" in r.text and "section.note-item" in r.text


def test_grab_logic_clears_card_btns_in_single_post_viewer(tmp_path, monkeypatch):
    """★2026-08-03 틱톡 실사고: SPA 전환으로 그리드에 붙인 카드버튼이 단일 영상 뷰어에
    남아 8개씩 떠다녔다. 뷰어(isSinglePost)에선 clearCardBtns로 걷어내는 배선을 못 박는다.
    ★2026-08-03 후속: 걷어내기는 틱톡 전용(tk)이어야 한다 — 전역 적용했더니 인스타
    검색 그리드에서 담기 버튼이 통째로 사라졌다(모달 뷰어 + img 지연로딩)."""
    c = _client(tmp_path, monkeypatch)
    t = c.get("/grab_logic.js").text
    assert "clearCardBtns" in t
    assert "if (tk) clearCardBtns();" in t
    assert "if (isSinglePost())" in t
    # data-ssgrab 표식도 같이 지워야 그리드로 돌아갔을 때 버튼이 다시 붙는다.
    assert 'removeAttribute("data-ssgrab")' in t


def test_grab_rejects_unknown_platform(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/grab", params={"url": "https://example.com/whatever"})
    assert r.status_code == 200 and "담을 수 없는" in r.text
    assert Store(str(tmp_path / "t.db")).mix_basket_shortcodes(customer_id=0) == set() \
        or not Store(str(tmp_path / "t.db")).mix_basket_shortcodes(customer_id=0)


def test_grab_requires_login_when_auth_on(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)     # 인증 on + 쿠키 없음 → 로그인 안내
    c = TestClient(appmod.app)
    r = c.get("/api/grab", params={"url": "https://www.tiktok.com/@x/video/1"})
    assert r.status_code == 200 and "로그인" in r.text


def test_grab_setup_page_bookmarklet_points_to_api(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.get("/grab")
    assert r.status_code == 200 and "북마크바로 드래그" in r.text
    m = re.search(r'atob\("([^"]+)"\)', r.text)
    decoded = base64.b64decode(m.group(1)).decode()
    assert decoded.startswith("javascript:") and "/api/grab?url=" in decoded


def test_mix_basket_meta_roundtrip(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.mix_basket_add("grab_yt_1", url="u", customer_id=0)
    s.mix_basket_set_meta("grab_yt_1", customer_id=0, thumbnail="cover.jpg", name="제목",
                          meta={"views": 12000, "likes": 340, "duration": 45, "channel": "채널A"})
    item = [i for i in s.mix_basket_list(customer_id=0) if i["shortcode"] == "grab_yt_1"][0]
    assert item["thumbnail"] == "cover.jpg" and item["name"] == "제목"
    assert item["meta"]["views"] == 12000 and item["meta"]["channel"] == "채널A"


def test_set_meta_does_not_overwrite_existing_name(tmp_path):
    """유저스크립트가 이미 준 name/thumbnail은 보강이 덮지 않는다."""
    s = Store(str(tmp_path / "t.db"))
    s.mix_basket_add("grab_yt_2", url="u", thumbnail="orig.jpg", name="원제목", customer_id=0)
    s.mix_basket_set_meta("grab_yt_2", customer_id=0, thumbnail="new.jpg", name="새제목")
    item = [i for i in s.mix_basket_list(customer_id=0) if i["shortcode"] == "grab_yt_2"][0]
    assert item["thumbnail"] == "orig.jpg" and item["name"] == "원제목"


def test_set_meta_merges_not_overwrites(tmp_path):
    """재보강이 간헐 실패로 일부 필드만 와도 기존 값을 안 잃고 병합한다."""
    s = Store(str(tmp_path / "t.db"))
    s.mix_basket_add("grab_tk_1", url="u", customer_id=0)
    s.mix_basket_set_meta("grab_tk_1", customer_id=0, meta={"views": 676000, "comments": 715})
    s.mix_basket_set_meta("grab_tk_1", customer_id=0, meta={"channel": "오늘식탁"})  # views 없이 옴
    m = [i for i in s.mix_basket_list(customer_id=0) if i["shortcode"] == "grab_tk_1"][0]["meta"]
    assert m["views"] == 676000 and m["comments"] == 715 and m["channel"] == "오늘식탁"
