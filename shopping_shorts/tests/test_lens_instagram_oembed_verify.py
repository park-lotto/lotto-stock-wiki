"""렌즈 인스타 카드: 썸네일과 실제 영상이 다르다 (2026-08-18 사장님 제보
"렌즈검색시 중국어 인스타는 썸네일과 영상이 다르다").

원인은 이미 2026-08-03에 **틱톡·유튜브에서 고친 것과 같은 병**이다(lens_discover 주석):
구글 렌즈가 페이지의 **추천영상 썸네일**을 그 페이지 URL과 짝지어 돌려주는 데이터
어긋남. 그래서 `verify_matches`가 oEmbed로 실조회해 제목·썸네일을 실제 값으로
교체한다 — 그런데 **인스타만 대상에서 빠져 있었다**("공개 oEmbed가 없어 대상 외").

실측(2026-08-18 서버): 인스타에는 로그인 없이 되는 oEmbed가 **있다**.
같은 저장소가 이미 `app._thumb_via_oembed`에서 그 엔드포인트를 쓰고 있었다
(`/api/v1/oembed/` + `x-ig-app-id`) — 실제 게시물 3건 전부 200에 진짜 제목·썸네일:
    DawDGT8TJ1J 200 | thumb=YES
    Dat2RByz-DM 200 | thumb=YES   ("시어머니가 알려주신 이 전용세제로…")
    Dasj3_2SHAI 200 | thumb=YES
즉 "인스타는 방법이 없다"는 전제만 낡았고, 배선은 한 줄이면 된다(0순위-B: 같은 판단이
두 군데 — 한쪽만 고쳐져 있었다).
"""
from shopping_shorts import lens_discover as L


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_instagram_has_an_oembed_endpoint():
    """인스타도 엔드포인트를 받아야 한다 — None이면 검증에서 통째로 빠진다."""
    ep = L._oembed_endpoint("instagram", "https://www.instagram.com/p/DawDGT8TJ1J/")
    assert ep, "인스타 oEmbed 엔드포인트가 없다 — 썸네일 교정이 아예 안 돈다"
    assert "instagram.com" in ep and "oembed" in ep


def test_instagram_thumbnail_replaced_with_real_one(monkeypatch):
    """구글이 준 엉뚱한 썸네일이 **실제 게시물 썸네일**로 교체돼야 한다."""
    calls = []

    def fake_get(url, **kw):
        calls.append((url, kw))
        return _Resp(200, {"title": "시어머니가 알려주신 전용세제",
                           "thumbnail_url": "https://scontent.cdninstagram.com/real.jpg"})

    monkeypatch.setattr(L.requests, "get", fake_get)
    items = [{"platform": "instagram",
              "url": "https://www.instagram.com/p/DawDGT8TJ1J/",
              "title": "엉뚱한 추천영상 제목",
              "thumbnail": "https://encrypted-tbn0.gstatic.com/images?q=tbn:WRONG"}]
    L.verify_matches(items, keywords=set())
    assert items[0]["thumbnail"] == "https://scontent.cdninstagram.com/real.jpg", \
        "인스타 썸네일이 실제 값으로 안 바뀌었다"
    assert items[0]["title"] == "시어머니가 알려주신 전용세제"
    assert items[0].get("verified") is True
    assert calls, "oEmbed를 부르지도 않았다"


def test_instagram_oembed_uses_app_id_header(monkeypatch):
    """★x-ig-app-id 헤더가 없으면 인스타가 거절한다(app._thumb_via_oembed와 같은 조건)."""
    seen = {}

    def fake_get(url, **kw):
        seen["headers"] = kw.get("headers") or {}
        return _Resp(200, {"thumbnail_url": "https://cdn/x.jpg"})

    monkeypatch.setattr(L.requests, "get", fake_get)
    L.verify_matches([{"platform": "instagram",
                       "url": "https://www.instagram.com/reel/ABC123/",
                       "title": "t", "thumbnail": "old"}], keywords=set())
    hdr = {k.lower(): v for k, v in seen["headers"].items()}
    assert "x-ig-app-id" in hdr, "app-id 헤더가 빠졌다 — 인스타가 거절한다"


def test_instagram_404_marks_link_dead(monkeypatch):
    """삭제·비공개는 link_ok=False — 틱톡·유튜브와 같은 취급."""
    monkeypatch.setattr(L.requests, "get", lambda url, **kw: _Resp(404, {}))
    items = [{"platform": "instagram", "url": "https://www.instagram.com/p/GONE/",
              "title": "t", "thumbnail": "old"}]
    L.verify_matches(items, keywords=set())
    assert items[0].get("link_ok") is False


def test_failure_keeps_original_item(monkeypatch):
    """검증 실패가 회수율을 깎으면 안 된다 — 원본 유지(no-op)."""
    def boom(url, **kw):
        raise L.requests.RequestException("timeout")

    monkeypatch.setattr(L.requests, "get", boom)
    items = [{"platform": "instagram", "url": "https://www.instagram.com/p/X/",
              "title": "원본제목", "thumbnail": "원본썸네일"}]
    L.verify_matches(items, keywords=set())
    assert items[0]["title"] == "원본제목"
    assert items[0]["thumbnail"] == "원본썸네일"
    assert "link_ok" not in items[0]


def test_tiktok_youtube_unchanged(monkeypatch):
    """기존 두 플랫폼 배선은 그대로여야 한다(회귀 방지)."""
    assert "tiktok.com/oembed" in L._oembed_endpoint("tiktok", "https://x/y")
    assert "youtube.com/oembed" in L._oembed_endpoint("youtube", "https://x/y")
    assert L._oembed_endpoint("xiaohongshu", "https://x/y") is None
    assert L._oembed_endpoint("douyin", "https://x/y") is None
