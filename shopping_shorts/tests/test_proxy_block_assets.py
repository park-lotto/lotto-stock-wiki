# -*- coding: utf-8 -*-
"""주거용 프록시 대역폭 절감 — 자산차단이 **프록시를 쓰는 모든 경로**에 걸려 있나.

왜 생겼나(2026-08-17 실사고):
  2026-08-06에 이미지·미디어·폰트 차단을 **아카이브에만** 넣었다(-48% 실측).
  그런데 8/09에 인스타 수집이 계정별 프록시 로테이션으로 바뀌면서 293채널이 전부
  유료 주거용 프록시로 나갔고, 그 경로엔 차단이 없었다.
  → 4일에 25.4GB 소진 · 402 Payment Required · 한 달 예측 192GB(25GB 플랜의 7.7배).

이 테스트가 막는 것: "한 곳만 최적화되고 나머지가 대역폭을 태우는" 재발(0순위-B).
새로 Playwright 컨텍스트를 만들면서 프록시를 쓰는 코드를 추가하면 여기서 걸린다.
"""
import re
from pathlib import Path

import pytest

from shopping_shorts import channel_archive

_SRC = Path(channel_archive.__file__).parent

# 주거용 프록시(Webshare)로 나가면서 새 페이지를 만드는 파일들
_PROXY_FILES = ["channel_archive.py", "instagram_playwright.py", "cn_backends.py"]


def test_차단목록에_stylesheet가_없다():
    """★CSS를 막으면 레이아웃이 안 잡혀 무한스크롤이 죽는다(2026-08-06 실측 372→12건)."""
    assert "stylesheet" not in channel_archive._BLOCKED_RESOURCES
    assert "document" not in channel_archive._BLOCKED_RESOURCES
    assert "xhr" not in channel_archive._BLOCKED_RESOURCES, "데이터가 통째로 날아간다"
    assert "fetch" not in channel_archive._BLOCKED_RESOURCES, "데이터가 통째로 날아간다"


def test_이미지_미디어_폰트는_막는다():
    for r in ("image", "media", "font"):
        assert r in channel_archive._BLOCKED_RESOURCES


def test_route가_이미지를_abort하고_나머지는_통과시킨다():
    aborted, continued = [], []

    class _Req:
        def __init__(self, rt): self.resource_type = rt

    class _Route:
        def __init__(self, rt): self.request = _Req(rt)
        def abort(self): aborted.append(self.request.resource_type)
        def continue_(self): continued.append(self.request.resource_type)

    class _Page:
        def __init__(self): self.fn = None
        def route(self, pat, fn): self.fn = fn

    page = _Page()
    assert channel_archive.block_heavy_assets(page) is True
    for rt in ("image", "media", "font", "xhr", "document", "stylesheet", "script"):
        page.fn(_Route(rt))
    assert set(aborted) == {"image", "media", "font"}
    assert set(continued) == {"xhr", "document", "stylesheet", "script"}


def test_env로_끌_수_있다(monkeypatch):
    """대상 사이트가 렌더를 막아 데이터가 안 나오는 날 대비."""
    class _Page:
        def route(self, *a): raise AssertionError("꺼야 하는데 route를 걸었다")

    monkeypatch.setenv("PROXY_BLOCK_ASSETS", "0")
    assert channel_archive.block_heavy_assets(_Page()) is False


def test_아카이브는_기존_env이름을_유지한다(monkeypatch):
    """서버에 ARCHIVE_BLOCK_ASSETS가 이미 설정돼 있을 수 있다 —
    이름을 바꾸면 조용히 무력화된다."""
    src = (_SRC / "channel_archive.py").read_text(encoding="utf-8")
    assert 'env="ARCHIVE_BLOCK_ASSETS"' in src


@pytest.mark.parametrize("fname", _PROXY_FILES)
def test_프록시_파일의_모든_new_page에_차단이_걸린다(fname):
    """★핵심 회귀 방지: new_page() 뒤 몇 줄 안에 block_heavy_assets가 있어야 한다."""
    src = (_SRC / fname).read_text(encoding="utf-8")
    lines = src.split("\n")
    missing = []
    for i, l in enumerate(lines):
        if re.search(r"\bctx\.new_page\(\)", l):
            window = "\n".join(lines[i:i + 12])
            if "block_heavy_assets" not in window:
                missing.append(i + 1)
    assert not missing, (
        f"{fname}: new_page 뒤에 block_heavy_assets가 없는 줄 {missing} "
        "— 주거용 프록시로 이미지·영상을 받게 된다(2026-08-17 402 사고 재발)")


def test_차단_판단이_한_곳에만_있다():
    """같은 판단이 여러 벌이면 또 한쪽만 최적화된다(0순위-B)."""
    hits = []
    for f in _SRC.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        # route 안에서 resource_type을 보고 abort하는 '판단' 자체
        if re.search(r"resource_type\s+in\s+_BLOCKED_RESOURCES", src):
            hits.append(f.name)
    assert hits == ["channel_archive.py"], f"판단이 여러 곳에 있다: {hits}"
