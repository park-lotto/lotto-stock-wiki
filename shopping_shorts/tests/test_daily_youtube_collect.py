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
    # 2026-07-29: seed_only는 구현돼 있으나 아직 켜지 않는다.
    # 미등록 우량 채널을 시드에 먼저 넣기 전에 켜면 수집량이 급감한다(설계 §T3 → §T4 순서).
    # register_good_youtube_channels.py 실행 후 True로 바꾸고 이 단언도 True로 뒤집는다.
    assert calls["seed_only"] is False


def test_main_survives_exception(monkeypatch):
    def boom(platform, seed_only=False):
        raise RuntimeError("api down")
    monkeypatch.setattr(dyc.service, "collect", boom)
    assert dyc.main() == 1                   # 예외 삼키고 비정상 종료코드만
