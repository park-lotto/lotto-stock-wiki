from scripts import daily_youtube_collect as dyc


def test_main_collects_youtube_free_path(monkeypatch):
    calls = {}
    def fake_collect(platform, seed_only=False):
        calls["platform"] = platform
        calls["seed_only"] = seed_only
        return [{"shortcode": "a"}]

    monkeypatch.setattr(dyc.service, "collect", fake_collect)
    rc = dyc.main()
    assert rc == 0
    assert calls["platform"] == "youtube"   # 인스타(유료) 아님
    assert calls["seed_only"] is True        # 자동 수집은 키워드 검색 경로를 끈다(2026-07-29)


def test_main_survives_exception(monkeypatch):
    def boom(platform, seed_only=False):
        raise RuntimeError("api down")
    monkeypatch.setattr(dyc.service, "collect", boom)
    assert dyc.main() == 1                   # 예외 삼키고 비정상 종료코드만
