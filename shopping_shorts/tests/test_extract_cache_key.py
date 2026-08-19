# -*- coding: utf-8 -*-
"""추출 캐시 키 (2026-08-06).

★실사고: 캐시 재사용 코드(2026-07-24)가 `store.get_extract(vid)`로 vid="s0"을 넘겨
**한 번도 적중한 적이 없었다**. script_extracts는 shortcode로 저장되는데(담기·AI PICK·
prewarm 전부), 믹스 파이프라인 안에서 소스 이름은 "s0"·"s1"이라 영원히 빗나갔다.

라이브 확인(job ff3921a9ae4c): 저장된 추출 408건, 그 영상의 캐시도 조건 충족
(segments 12개·seg_id 전부·change 필드 있음)인데 매번 Gemini로 재전사 —
작업 118초 중 85초가 다운로드+재추출이었다.
"""
import pytest

from shopping_shorts.mix_pipeline import _cache_key_for_url, _source_video_id


@pytest.mark.parametrize("url,expected", [
    # 인스타 — 실제 라이브에서 캐시가 있는데도 빗나갔던 그 URL
    ("https://www.instagram.com/reel/DbosmpXzCZd/", "DbosmpXzCZd"),
    ("https://www.instagram.com/p/ABC123_x-y/", "ABC123_x-y"),
    ("https://www.instagram.com/reels/XYZ789/", "XYZ789"),
    ("https://www.instagram.com/tv/TV123/", "TV123"),
    # 유튜브
    ("https://youtube.com/shorts/aB3_x-Y", "aB3_x-Y"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=abc12345678", "abc12345678"),
    # 틱톡
    ("https://www.tiktok.com/@user/video/7412345678901234567", "7412345678901234567"),
])
def test_url에서_shortcode를_뽑는다(url, expected):
    assert _cache_key_for_url(url) == expected


@pytest.mark.parametrize("url", ["https://example.com/nothing", "", None, "그냥문자열"])
def test_모르는_URL은_None(url):
    """None이면 호출부가 옛 방식(vid)으로 폴백한다 — 터지면 안 된다."""
    assert _cache_key_for_url(url) is None


def test_소스이름은_캐시키가_아니다():
    """★이 사고의 핵심 — s0/s1은 절대 캐시에 없는 이름이다.

    누군가 다시 get_extract(vid)만 쓰도록 되돌리면 이 테스트가 잡는다."""
    for i in range(3):
        vid = _source_video_id(i)
        assert vid == f"s{i}"
        assert _cache_key_for_url(vid) is None, "s0을 캐시 키로 쓰면 영원히 빗나간다"


def test_호출부가_shortcode로_조회한다():
    """소스에 박아 확인 — 캐시 조회가 URL 기반 키를 쓰는지."""
    import inspect

    from shopping_shorts import mix_pipeline
    src = inspect.getsource(mix_pipeline.run_mix_job)
    assert "_cache_key_for_url" in src, "캐시 조회가 shortcode 키를 써야 한다"
    assert "_url_of" in src, "vid→URL 매핑이 있어야 한다"


# ── 렌즈 접두사 키도 후보에 든다(2026-08-17) ────────────────────────────────
# 같은 영상이 담기 경로에선 `<id>`, 렌즈 경로에선 `lens_<플랫폼>_<id>`로 저장된다.
# 앞 형태만 찾던 탓에 틱톡 소스는 캐시에 재태깅본이 있는데도 한 번도 안 맞았다
# (실측 job 8873eeb48a08: 인스타 1건 적중 / 틱톡 2건 불발 → 고친 뒤 3건 전부 적중).
def test_cache_keys_include_lens_prefixed_form():
    from shopping_shorts.mix_pipeline import _cache_keys_for_url
    ks = _cache_keys_for_url("https://www.tiktok.com/@runnnn_official/video/7458060642738605355")
    assert ks[0] == "7458060642738605355", "담기 경로 키가 먼저 와야 한다"
    assert "lens_tiktok_7458060642738605355" in ks, "렌즈 경로 키가 후보에 없으면 영원히 빗나간다"


def test_cache_keys_cover_every_platform():
    from shopping_shorts.mix_pipeline import (_cache_keys_for_url, _SHORTCODE_RES,
                                              _SHORTCODE_PLATFORMS)
    # 정규식과 플랫폼 이름은 짝으로 움직인다 — 길이가 어긋나면 zip이 조용히 잘라먹는다
    assert len(_SHORTCODE_RES) == len(_SHORTCODE_PLATFORMS)
    for url, plat, code in (
        ("https://www.instagram.com/reel/Db_2V-mzT44/", "instagram", "Db_2V-mzT44"),
        ("https://youtube.com/shorts/abc123XYZ", "youtube", "abc123XYZ"),
    ):
        assert _cache_keys_for_url(url) == [code, f"lens_{plat}_{code}"]


def test_cache_keys_empty_when_unknown():
    from shopping_shorts.mix_pipeline import _cache_keys_for_url
    # 알아볼 수 없는 URL은 빈 목록 — 호출부의 for가 그냥 안 돌고 재추출로 간다
    assert _cache_keys_for_url("https://example.com/whatever") == []
    assert _cache_keys_for_url("s0") == []
    assert _cache_keys_for_url(None) == []
