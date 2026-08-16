"""CN 검색 통합 파서 — 폴백·스키마·meta 검증.

★실브라우저·실Apify를 부르지 않는다. 백엔드를 주입해 대체한다
(test_xiaohongshu_playwright.py와 동일 원칙)."""
from shopping_shorts import cn_backends


def test_normalize_fills_all_schema_keys():
    """백엔드가 뭘 빠뜨려도 스키마 키는 전부 채워진다(프론트가 조용히 깨지지 않게)."""
    row = cn_backends.normalize({"url": "https://x.com/1", "title": "t"}, "douyin")
    for key in ("platform", "url", "title", "thumbnail", "play_url",
                "channel", "likes", "views", "duration", "is_short"):
        assert key in row, f"{key} 누락"
    assert row["platform"] == "douyin"
    assert row["likes"] is None          # 없으면 None(0으로 위조하지 않는다)
    assert row["is_short"] is True       # duration 불명 → 숏폼으로 본다


def test_num_survives_infinity_and_nan():
    """★inf는 ValueError가 아니라 OverflowError다. 여기서 예외가 새면
    백엔드 결과가 통째로 죽는다(2026-08-17 코드리뷰 발견)."""
    for bad in ("inf", "-inf", "nan", float("inf"), 1e400):
        row = cn_backends.normalize({"likes": bad, "duration": bad}, "douyin")
        assert row["likes"] is None, f"{bad!r} → likes가 None이어야 한다"
        assert row["duration"] is None
        assert row["is_short"] is True      # duration 불명 → 숏폼 취급


def test_apify_backend_normalizes_and_swallows_errors(monkeypatch):
    """Apify가 터져도 예외가 밖으로 안 나간다(폴백은 cn_search가 판단)."""
    class Boom:
        @staticmethod
        def search(keyword, max_results=10):
            raise RuntimeError("APIFY_TOKEN이 설정되지 않았습니다")

    monkeypatch.setattr(cn_backends, "douyin_search", Boom)
    assert cn_backends.apify_douyin("蒜泥保存", 8) == []


def test_apify_backend_maps_rows(monkeypatch):
    class Ok:
        @staticmethod
        def search(keyword, max_results=10):
            return [{"url": "https://www.douyin.com/video/1", "title": "t",
                     "likes": "12", "duration": 30}]

    monkeypatch.setattr(cn_backends, "douyin_search", Ok)
    rows = cn_backends.apify_douyin("蒜泥保存", 8)
    assert len(rows) == 1
    assert rows[0]["platform"] == "douyin"
    assert rows[0]["likes"] == 12
    assert rows[0]["is_short"] is True


def test_pw_xiaohongshu_builds_absolute_urls():
    """카드가 주는 href는 상대경로(/search_result/…) → 절대 URL로 만들어야 담기가 된다."""
    cards = [{"url": "/search_result/abc?xsec_token=T", "title": "蒜泥",
              "thumb": "https://img/1.jpg", "likes": "12"}]
    rows = cn_backends._pw_xhs_rows(cards)
    assert rows[0]["url"] == "https://www.rednote.com/search_result/abc?xsec_token=T"
    assert rows[0]["platform"] == "xiaohongshu"
    assert rows[0]["thumbnail"] == "https://img/1.jpg"
    assert rows[0]["likes"] == 12


def test_pw_xiaohongshu_drops_cards_without_url():
    """URL 없는 카드는 버린다(담기가 불가능한 카드를 화면에 올리지 않는다)."""
    assert cn_backends._pw_xhs_rows([{"url": None, "title": "x"}]) == []


def test_pw_xiaohongshu_keeps_absolute_urls_unchanged():
    """이미 절대 URL이면 그대로 둔다(BASE를 두 번 붙이지 않는다)."""
    rows = cn_backends._pw_xhs_rows(
        [{"url": "https://www.rednote.com/explore/xyz", "title": "t"}])
    assert rows[0]["url"] == "https://www.rednote.com/explore/xyz"


def test_pw_xiaohongshu_returns_empty_without_session(monkeypatch):
    """세션 파일이 없으면 브라우저를 아예 띄우지 않는다(헛시간 방지)."""
    monkeypatch.setattr(cn_backends.config, "XIAOHONGSHU_SESSION_PATH", "",
                        raising=False)
    assert cn_backends.pw_xiaohongshu("蒜泥保存", 8) == []


def test_pw_douyin_returns_empty_without_session(monkeypatch):
    """세션 파일이 없으면 브라우저를 아예 띄우지 않는다(헛돈·헛시간 방지)."""
    monkeypatch.setattr(cn_backends.config, "DOUYIN_SESSION_PATH", "", raising=False)
    assert cn_backends.pw_douyin("蒜泥保存", 8) == []


def test_douyin_proxy_and_session_decided_together(monkeypatch):
    """계정↔IP가 어긋나지 않게 둘을 한 함수에서 함께 정한다(0순위-B).

    2026-08-09 인스타 실사고: 계정은 로테이션이, 프록시는 다른 코드가 정해
    계정↔IP가 틀어졌고 본인확인 챌린지로 나타났다. 한 함수가 둘 다 돌려주면
    그 사고가 성립하지 않는다."""
    monkeypatch.setenv("WEBSHARE_USER", "u")
    monkeypatch.setenv("WEBSHARE_PASS", "p")
    kw = cn_backends.douyin_context_kw("/tmp/s.json")
    assert kw["storage_state"] == "/tmp/s.json"
    assert kw["proxy"]["server"].startswith("http://")
    assert "-cn-" in kw["proxy"]["username"]     # 도우인은 반드시 중국 출구


def test_douyin_context_without_proxy_creds(monkeypatch):
    """프록시 자격증명이 없으면 proxy 키 없이(직결) 돌려준다 — 크래시하지 않는다."""
    monkeypatch.delenv("WEBSHARE_USER", raising=False)
    monkeypatch.delenv("WEBSHARE_PASS", raising=False)
    kw = cn_backends.douyin_context_kw("/tmp/s.json")
    assert kw["storage_state"] == "/tmp/s.json"
    assert "proxy" not in kw


def test_douyin_rows_dedupes_and_maps():
    """검색 API 응답 → 스키마. 같은 aweme_id는 한 번만."""
    payload = {"data": [
        {"aweme_info": {"aweme_id": "1", "desc": "마늘 보관",
                        "author": {"nickname": "ch"},
                        "statistics": {"digg_count": 12, "play_count": 300}}},
        {"aweme_info": {"aweme_id": "1", "desc": "중복"}},
        {"aweme_info": {"desc": "id 없음"}},
    ]}
    rows = cn_backends._douyin_rows([payload])
    assert len(rows) == 1
    assert rows[0]["url"] == "https://www.douyin.com/video/1"
    assert rows[0]["platform"] == "douyin"
    assert rows[0]["channel"] == "ch"
    assert rows[0]["likes"] == 12
    assert rows[0]["views"] == 300


def test_douyin_rows_survives_garbage():
    """이상한 응답이 와도 예외가 안 난다(계약: 백엔드는 안 던진다)."""
    assert cn_backends._douyin_rows(None) == []
    assert cn_backends._douyin_rows([{}]) == []
    assert cn_backends._douyin_rows([{"data": "not-a-list"}]) == []
    assert cn_backends._douyin_rows([{"data": [None, "x"]}]) == []
