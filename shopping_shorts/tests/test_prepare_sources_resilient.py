"""매칭 견고화(2026-07-19): 소스 URL 하나가 다운로드 실패해도 배치 전체가 죽지 않고
그 소스만 스킵한다. 렌즈 즐겨찾기로 담긴 불량 URL(instagram.com/popular/{슬러그})이
매칭 단계에서 배치를 통째로 failed로 만들던 실사고의 이중 안전망 —
근본차단은 lens_discover._is_watchable(입구), 여기는 그래도 샌 것에 대한 백스톱.
"""
import pytest

from shopping_shorts import mix_pipeline


def test_prepare_sources_skips_failed_keeps_rest(tmp_path, monkeypatch):
    def fake_download(url, dest):
        if "popular" in url:
            raise RuntimeError(f"인스타 영상 해석 실패: {url}")
        return (f"{dest}/v.mp4", "cap")
    monkeypatch.setattr(mix_pipeline, "download_any", fake_download)

    urls = ["https://insta/reel/a/",
            "https://www.instagram.com/popular/바나나-아침-식사/",  # 불량
            "https://insta/reel/c/"]
    video_paths, captions, skipped = mix_pipeline._prepare_sources(urls, tmp_path)

    # 불량 s1만 빠지고 나머지는 유지(video_id는 인덱스 기준 s{i}라 갭 OK).
    assert set(video_paths) == {"s0", "s2"}
    assert set(captions) == {"s0", "s2"}
    assert len(skipped) == 1 and "popular" in skipped[0][0]


def test_prepare_sources_raises_when_all_fail(tmp_path, monkeypatch):
    def always_fail(url, dest):
        raise RuntimeError("실패")
    monkeypatch.setattr(mix_pipeline, "download_any", always_fail)

    with pytest.raises(RuntimeError):
        mix_pipeline._prepare_sources(["https://x/1", "https://x/2"], tmp_path)
