from shopping_shorts import service


def test_collect_unimplemented_platform_returns_empty_no_apify_call(monkeypatch, tmp_path):
    """platform="tiktok"(등 인스타/유튜브 외 미구현 플랫폼)은 인스타 Apify
    스크레이프(fetch_reels)로 흘러들면 안 된다 — 실비용 발생 + 라벨 오분류
    (최종리뷰 CRITICAL). collect()는 즉시 빈 리스트만 반환해야 한다."""
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "t.db"))

    def boom(usernames):
        raise AssertionError("fetch_reels 호출됨 — 미구현 플랫폼이 인스타 스크레이프로 흘러듦")
    monkeypatch.setattr(service, "fetch_reels", boom)

    result = service.collect(platform="tiktok")
    assert result == []
