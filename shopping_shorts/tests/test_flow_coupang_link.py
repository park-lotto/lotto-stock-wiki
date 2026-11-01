"""10-30 사장님 "쿠팡은 고객 API 먼저, 없으면 크롬 웹 — 막히면 상품 링크 받기 · 크롬은 한 번만".
설치본 시험(C:/t/inst_ep1): 크롬 'Access Denied' → 다시 시도만 돌다 15.4분 뒤 멈춤. 이제 그 자리에서 회원 Claude 가 상품 주소를 찾아 회원 확인 → 그 상품으로."""
import json

from tools.calcopy.hybrid import flow as F, runner_ops as R


def _st():
    return {"version": "썰템쇼판", "fmt": "쇼핑형", "phase": "given_same", "given": "무스 메이플버터", "tries": {}, "log": [], "read": {"product_words": ["메이플버터"]}}


def test_search_blocked_asks_link_not_retry():
    st = _st()
    out = F.step(st, {"coupang": {"items": [], "search_failed": True}}, {}, {})
    assert out["status"] == "review" and out["review"][0]["id"] == "product_link" and st["phase"] == "link_got"
    assert "무스 메이플버터" in out["review"][0]["ask"]


def test_link_answer_sets_product_and_goes_on(monkeypatch):
    st = _st()
    F.step(st, {"coupang": {"search_failed": True}}, {}, {})
    seen = {}
    monkeypatch.setattr(F, "ph_reviews", lambda st_, m, rp, u: seen.setdefault("reviews", True) and {"do": [{"id": "reviews", "cmd": "x"}], "then": "reviews_got"})
    monkeypatch.setitem(F.PHASES, "reviews", F.ph_reviews)
    out = F.step(st, {}, {"product_link": {"url": "https://www.coupang.com/vp/products/7123456789?itemId=1", "name": "무스 메이플 버터 150g",
                                           "same": True, "category": "식품", "image": "https://thumbnail.coupangcdn.com/a.jpg"}}, {})
    assert st["product"]["product_id"] == "7123456789" and st["product"]["mode"] == "exact" and st["product"]["image"].endswith("a.jpg")
    assert seen.get("reviews") and out["do"][0]["id"] == "reviews"


def test_link_limit_stops_with_member_fix():
    st = _st()
    st["tries"]["product_link"] = F.LINK_MAX
    out = F.step(st, {"coupang": {"search_failed": True}}, {}, {})
    assert out["status"] == "stop" and "파트너스" in json.dumps(out, ensure_ascii=False)


def test_blocked_page_title():
    assert R.blocked_page("Access Denied") and not R.blocked_page("쿠팡! | 무스 메이플버터")


def test_retry_after_watch_stop_goes_back_to_asker():
    """감독 멈춤 뒤 다시 시도 = 옛 감독 답을 되풀이하지 말고 그 일을 시킨 단계부터(10-30 설치본 시험: 같은 '반복됐어요'만 3번)."""
    st = _st()
    st.update(phase="watch_got", _watch_from="given", watch_keys={"k": 2})
    out = F.step(st, {}, {}, {})
    assert "watch_keys" not in st or not st["watch_keys"].get("k")
    assert any("감독 멈춤 뒤 다시 시도 → given" in x for x in st["log"])
