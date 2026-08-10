"""yt-dlp 채널목록은 간헐적으로 빈 응답을 준다(2026-07-24 실측: --playlist-end 1에서 entries=None,
3건은 정상). 한 번 비었다고 그 채널을 버리면 랭킹에 구멍이 나므로 재시도한다."""
from shopping_shorts import tiktok_client as tc


def test_retries_on_empty_then_succeeds(monkeypatch):
    calls = {"n": 0}
    def fake_run(*a, **k):
        calls["n"] += 1
        class R:
            returncode = 0
            stdout = '{"entries": []}' if calls["n"] == 1 else '{"entries": [{"id": "x"}]}'
            stderr = ""
        return R()
    monkeypatch.setattr(tc.subprocess, "run", fake_run)
    monkeypatch.setattr(tc.time, "sleep", lambda s: None)
    out = tc.fetch_account_videos("@a")
    assert calls["n"] == 2            # 첫 빈 응답 → 재시도
    assert len(out) == 1


def test_gives_up_after_retries_returns_empty(monkeypatch):
    calls = {"n": 0}
    def fake_run(*a, **k):
        calls["n"] += 1
        class R:
            returncode = 0
            stdout = '{"entries": []}'
            stderr = ""
        return R()
    monkeypatch.setattr(tc.subprocess, "run", fake_run)
    monkeypatch.setattr(tc.time, "sleep", lambda s: None)
    out = tc.fetch_account_videos("@a")
    assert out == []                  # 끝내 비면 빈 리스트(그 채널만 스킵, 전체는 계속)
    assert calls["n"] <= 3            # 무한 재시도 금지
