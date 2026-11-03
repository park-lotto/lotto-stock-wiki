"""#1533 이만수 — 쿠팡 검색에 같은·비슷한 제품이 없으면 다섯 자리가 각자 NO_SIMILAR 로 멈춰 '비슷한 제품도 못 찾음 → 편 종료'.
주인 flow._no_similar — 끝내지 않고 회원 Claude 가 웹 검색으로 상품 주소를 찾는다(_link_ask, 검색 막힘과 같은 길). 한도를 넘으면 회원에게 묻는 멈춤."""
from tools.calcopy.hybrid import flow as F


def _st(phase):
    return {"version": "썰템쇼판", "fmt": "쇼핑형", "phase": phase, "tries": {}, "log": [], "read": {"product_words": ["접이식 빨래 건조대"]},
            "_wide": True, "coupang_qs": ["접이식 빨래 건조대"]}


def test_best_none_asks_link():
    st = _st("best_rated")
    out = F.step(st, {"coupang": {"items": []}}, {}, {})
    assert out["status"] == "review" and out["review"][0]["id"] == "product_link" and st["phase"] == "link_got", out
    assert F.LINK_NONE in out["review"][0]["ask"] and "막혔다" not in out["review"][0]["ask"]


def test_shop_none_asks_link():
    st = _st("s_cands")
    st["bench"] = {}
    out = F.step(st, {"coupang": {"items": []}}, {}, {})
    assert out["status"] == "review" and out["review"][0]["id"] == "product_link", out


def test_link_limit_then_member_stop():
    st = _st("best_rated")
    st["tries"]["product_link"] = F.LINK_MAX
    out = F.step(st, {"coupang": {"items": []}}, {}, {})
    assert out["status"] == "stop" and "다시 시도" in out["fix"], out
