"""썸네일 캐시 키·포맷 변환 (2026-08-17 실사고).

★사고: 캐시 키를 항상 'URL 경로의 파일명'으로 잡았는데, 구글 렌즈 썸네일은
  `encrypted-tbn0.gstatic.com/images?q=tbn:...` 처럼 경로가 전부 `/images`다.
  → 렌즈 결과의 **모든 썸네일이 같은 키**가 되어 처음 저장된 그림 하나가 전 카드에
  재사용됐다(사장님 실측: 유튜브 카드 3장이 전부 같은 강아지 사진, 영상은 정상).
"""
from shopping_shorts import app as appmod


_GSTATIC = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9Gc"


def test_gstatic_thumbs_get_different_cache_keys():
    """★핵심 회귀 — 쿼리로만 구분되는 URL이 같은 파일에 캐시되면 안 된다."""
    a = appmod._thumb_cache_path(_GSTATIC + "AAAA")
    b = appmod._thumb_cache_path(_GSTATIC + "BBBB")
    assert a is not None and b is not None
    assert a != b, "쿼리가 다른데 캐시 키가 같다 — 카드마다 남의 썸네일이 뜬다"


def test_same_url_is_stable():
    """같은 URL은 항상 같은 파일(캐시가 실제로 히트해야 한다)."""
    u = _GSTATIC + "CCCC"
    assert appmod._thumb_cache_path(u) == appmod._thumb_cache_path(u)


def test_instagram_keeps_filename_key_across_signature_change():
    """인스타는 **파일명** 키를 유지한다 — 서명(oe=)만 바뀐 만료 URL이 와도 캐시가
    히트해야 `_thumb_via_oembed` 자가복구(2026-08-09)가 의미를 갖는다."""
    base = "https://scontent-ssn1-1.cdninstagram.com/v/t51.2885-15/123_n.jpg"
    a = appmod._thumb_cache_path(base + "?oe=OLD&_nc_ht=x")
    b = appmod._thumb_cache_path(base + "?oe=NEW&_nc_ht=y")
    assert a == b, "인스타 만료 URL이 캐시를 못 쓰면 oembed 복구가 매번 다시 돈다"


def test_instagram_and_gstatic_do_not_collide():
    ig = appmod._thumb_cache_path(
        "https://scontent.cdninstagram.com/v/t51/abc_n.jpg?oe=1")
    gs = appmod._thumb_cache_path(_GSTATIC + "abc_n.jpg")
    assert ig != gs


def test_no_filename_still_cacheable_for_query_hosts():
    """경로에 파일명이 없어도(gstatic의 `/images`) 캐시를 포기하지 않는다."""
    assert appmod._thumb_cache_path(_GSTATIC + "DDDD") is not None


# ── HEIC → JPEG 변환 ────────────────────────────────────────────

def test_non_heic_passes_through_untouched():
    body = b"\xff\xd8\xff\xe0jpegbytes"
    out, ctype = appmod._thumb_to_web_format(body, "image/jpeg")
    assert out is body and ctype == "image/jpeg"


def test_heic_without_library_returns_original(monkeypatch):
    """pillow-heif가 없으면 **원본 그대로** — 썸네일 하나 때문에 카드를 죽이지 않는다
    (지금까지와 같은 동작 = 안 나빠진다)."""
    monkeypatch.setattr(appmod, "_HEIF_READY", False)
    body = b"heicbytes"
    out, ctype = appmod._thumb_to_web_format(body, "image/heic")
    assert out == body and ctype == "image/heic"


def test_heic_is_converted_when_library_present():
    """설치돼 있으면 실제로 JPEG로 바뀐다. 없으면 이 테스트는 건너뛴다
    (서버엔 설치했지만 로컬·CI엔 없을 수 있다 — 가짜 green을 만들지 않는다)."""
    import pytest
    pytest.importorskip("pillow_heif")
    import io
    from PIL import Image
    import pillow_heif

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 200, 30)).save(buf, "JPEG")
    heif = pillow_heif.from_pillow(Image.open(io.BytesIO(buf.getvalue())))
    heic_bytes = heif.to_bytes() if hasattr(heif, "to_bytes") else None
    if not heic_bytes:
        out = io.BytesIO()
        heif.save(out, format="HEIF")
        heic_bytes = out.getvalue()

    appmod._HEIF_READY = None          # 감지 로직도 함께 태운다
    body, ctype = appmod._thumb_to_web_format(heic_bytes, "image/heic")
    assert ctype == "image/jpeg"
    assert body[:2] == b"\xff\xd8", "JPEG 매직바이트가 아니다"


# ── mp4 프록시 허용 호스트 ──────────────────────────────────────

def test_video_proxy_allows_tiktok_and_douyin():
    """렌즈 인라인 재생이 프록시를 타므로 이 호스트들이 열려 있어야 한다."""
    allowed = appmod._ALLOWED_VIDEO_HOSTS
    for host in ("tiktokcdn.com", "douyinvod.com"):
        assert any(host in h for h in allowed), host


def test_video_proxy_still_rejects_unknown_and_internal_hosts():
    """열어주는 만큼 SSRF 가드가 살아 있어야 한다."""
    allowed = appmod._ALLOWED_VIDEO_HOSTS
    for bad in ("https://evil.com/a.mp4",
                "https://tiktokcdn.com.evil.com/a.mp4",
                "http://169.254.169.254/latest/meta-data/",
                "http://127.0.0.1:8849/x.mp4"):
        assert appmod._reject_cdn_proxy(bad, allowed), bad
