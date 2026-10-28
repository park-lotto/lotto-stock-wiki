"""유튜브 쿠키 계정 돌려쓰기(2026-09-24) — `firefox:yt*`면 yt로 시작하는 프로필을 번갈아 쓴다."""
from shopping_shorts import media_download as md


def _ini(tmp_path, names):
    root = tmp_path / "Mozilla" / "Firefox"
    root.mkdir(parents=True)
    body = "".join(f"[Profile{i}]\nName={n}\nIsRelative=1\nPath=Profiles/x{i}.{n}\n\n"
                   for i, n in enumerate(names))
    (root / "profiles.ini").write_text(body, encoding="utf-8")
    return root


def test_rotates_across_yt_profiles(tmp_path, monkeypatch):
    root = _ini(tmp_path, ["default", "yt2", "yt1", "신규5", "yt3"])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(md.config, "YTDLP_COOKIES_BROWSER_YOUTUBE", "firefox:yt*")
    picks = [md._youtube_browser_cookie_source() for _ in range(6)]
    names = [p.rsplit(".", 1)[-1] for p in picks]
    assert all(p.startswith("firefox:" + str(root)) for p in picks)
    assert set(names) == {"yt1", "yt2", "yt3"}          # yt 아닌 프로필은 안 쓴다
    assert names[:3] != [names[0]] * 3                   # 연속 호출이 다른 계정으로 간다
    assert sorted(names) == ["yt1", "yt1", "yt2", "yt2", "yt3", "yt3"]   # 고르게 나뉜다


def test_plain_value_unchanged(monkeypatch):
    monkeypatch.setattr(md.config, "YTDLP_COOKIES_BROWSER_YOUTUBE", "firefox")
    assert md._youtube_browser_cookie_source() == "firefox"


def test_no_matching_profile_falls_back_to_browser(tmp_path, monkeypatch):
    _ini(tmp_path, ["default"])
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(md.config, "YTDLP_COOKIES_BROWSER_YOUTUBE", "firefox:yt*")
    assert md._youtube_browser_cookie_source() == "firefox"
