from scripts import daily_youtube_collect as dyc


def test_main_collects_youtube_free_path(monkeypatch):
    calls = {}
    monkeypatch.setattr(dyc.service, "collect",
                        lambda platform: calls.setdefault("platform", platform) or [{"shortcode": "a"}])
    rc = dyc.main()
    assert rc == 0
    assert calls["platform"] == "youtube"   # 인스타(유료) 아님


def test_main_survives_exception(monkeypatch):
    def boom(platform):
        raise RuntimeError("api down")
    monkeypatch.setattr(dyc.service, "collect", boom)
    assert dyc.main() == 1                   # 예외 삼키고 비정상 종료코드만
