"""인스타 다운로드는 무료 경로 우선, Apify는 폴백(2026-07-31 실사고).

증상: 담은 영상 2개 모두 "대본을 아직 분석하지 못했어요".
원인: 대본 분석(Gemini) 전에 mp4를 받아야 하는데 그 다운로드가 Apify 전용이었고
      크레딧이 말라(17/17 소진) 파일을 못 받았다 → Gemini는 호출도 못 됐다.
"""
from pathlib import Path

import pytest

from shopping_shorts import media_download as md


def test_free_path_used_first(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(md, "resolve_media_url",
                        lambda p, c: calls.append(("resolve", p, c)) or "https://cdn/x.mp4")

    def _no_apify(*a, **kw):
        raise AssertionError("무료 경로가 됐는데 Apify를 불렀다(유료 낭비)")

    monkeypatch.setattr("shopping_shorts.apify_client.fetch_single_reel", _no_apify)
    monkeypatch.setattr("shopping_shorts.frame_extract.download_video",
                        lambda url, d: Path(d) / "v.mp4")
    path, cap = md._download_instagram("https://www.instagram.com/p/DbUuORBJ1h1/", str(tmp_path))
    assert path.endswith("v.mp4") and cap == ""
    assert calls == [("resolve", "instagram", "DbUuORBJ1h1")]


def test_falls_back_to_apify_when_free_path_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(md, "resolve_media_url", lambda p, c: "")     # 무료 경로 실패
    monkeypatch.setattr("shopping_shorts.apify_client.fetch_single_reel",
                        lambda url: {"videoUrl": "https://cdn/y.mp4", "caption": "캡션"})
    monkeypatch.setattr("shopping_shorts.frame_extract.download_video",
                        lambda url, d: Path(d) / "y.mp4")
    path, cap = md._download_instagram("https://www.instagram.com/reel/ABC123/", str(tmp_path))
    assert path.endswith("y.mp4") and cap == "캡션"


def test_error_mentions_both_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(md, "resolve_media_url", lambda p, c: "")
    monkeypatch.setattr("shopping_shorts.apify_client.fetch_single_reel",
                        lambda url: (_ for _ in ()).throw(RuntimeError("apify 소진")))
    with pytest.raises(RuntimeError) as e:
        md._download_instagram("https://www.instagram.com/p/ZZZ/", str(tmp_path))
    assert "무료" in str(e.value) and "apify 소진" in str(e.value)
