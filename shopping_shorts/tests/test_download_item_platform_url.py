# -*- coding: utf-8 -*-
"""수집항목 → 영상 다운로드 시 **플랫폼에 맞는 주소**를 쓴다 (2026-09-06).

_find_collected_item으로 유튜브 항목이 찾히게 되면서 이 함수에 유튜브 item이
처음으로 들어오게 됐다. 그런데 여기엔 인스타 전제가 하나 박혀 있었다:

    page = (item.get("url") or "").strip()
    if not page and item.get("shortcode"):
        page = f"https://www.instagram.com/reel/{item['shortcode']}/"   # ← 무조건 인스타

url이 빈 유튜브 항목이 오면 `instagram.com/reel/7ONI6JjXvMw/`라는 **존재하지 않는
주소**를 받으러 간다 — 실패 사유가 "인스타 다운로드 실패"로 뭉개져 원인 추적이
어려워진다(메모리: ★오류표본·뭉갠사유).

라이브 실측(2026-09-06): 유튜브 스냅샷 8,524건은 url을 갖고 있어 정상 경로를 타지만,
플랫폼이 늘어나는 중이라 전제를 남겨두면 언젠가 밟는다(0순위-B).
"""
import pytest

from shopping_shorts import app as app_mod


@pytest.fixture
def 받은주소(monkeypatch):
    """download_any가 실제로 어떤 주소를 받으러 갔는지 기록한다."""
    got = {}

    def _fake_download_any(page, work_dir):
        got["page"] = page
        return "/tmp/fake.mp4", ""

    monkeypatch.setattr(app_mod, "download_any", _fake_download_any)
    return got


def test_url이_있으면_그대로_쓴다_유튜브(받은주소):
    item = {"shortcode": "7ONI6JjXvMw", "platform": "youtube",
            "url": "https://www.youtube.com/watch?v=7ONI6JjXvMw"}
    app_mod._download_item_video(item, "/tmp/wd")
    assert 받은주소["page"] == "https://www.youtube.com/watch?v=7ONI6JjXvMw"


def test_url이_있으면_그대로_쓴다_인스타(받은주소):
    item = {"shortcode": "DcAAA111",
            "url": "https://www.instagram.com/reel/DcAAA111/"}
    app_mod._download_item_video(item, "/tmp/wd")
    assert 받은주소["page"] == "https://www.instagram.com/reel/DcAAA111/"


def test_url이_없는_인스타는_릴스주소를_조립한다(받은주소):
    """종전 동작 유지 — 인스타 항목은 shortcode로 릴스 주소를 만들어 받는다."""
    item = {"shortcode": "DcAAA111"}          # platform 없음 = 인스타(종전 기본)
    app_mod._download_item_video(item, "/tmp/wd")
    assert 받은주소["page"] == "https://www.instagram.com/reel/DcAAA111/"


def test_url이_없는_유튜브는_인스타주소를_만들지_않는다():
    """★핵심. 유튜브 항목에 instagram.com 주소를 조립해 던지면 안 된다.

    받을 주소가 없으면 **명확한 사유로 실패**해야 원인 추적이 된다.
    """
    item = {"shortcode": "7ONI6JjXvMw", "platform": "youtube"}   # url 없음
    with pytest.raises(RuntimeError) as e:
        app_mod._download_item_video(item, "/tmp/wd")
    assert "instagram" not in str(e.value).lower(), "인스타 주소를 만들면 안 된다"


@pytest.mark.parametrize("platform", ["tiktok", "threads", "naverclip",
                                      "pinterest", "xiaohongshu", "douyin"])
def test_url이_없는_타플랫폼도_마찬가지(platform):
    item = {"shortcode": "CODE1", "platform": platform}
    with pytest.raises(RuntimeError):
        app_mod._download_item_video(item, "/tmp/wd")


def test_주소가_아예_없으면_사유가_분명하다():
    with pytest.raises(RuntimeError) as e:
        app_mod._download_item_video({}, "/tmp/wd")
    assert "재수집" in str(e.value)
