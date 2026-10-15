"""관제 209 — 3단계 장면 찾기: 숏템파워 검색어 모드(대본 분석·유료 렌즈 없음) · 담기 창 두 갈래."""
import pathlib
from types import SimpleNamespace

from shopping_shorts import app

INDEX = pathlib.Path(app.__file__).parent / "static" / "index.html"


def test_담기창은_3단계와_즐겨찾기_두_갈래():
    req = SimpleNamespace(query_params={"url": "https://www.youtube.com/shorts/abc", "title": "t", "dest": "x"})
    html = app._grab_choice_html(req, "ed7c92abb6b4").body.decode("utf-8")
    assert "🎬 3단계 작업에 담기" in html and "⭐ 영상 즐겨찾기에 담기" in html
    assert "dest=job" in html and "dest=basket" in html
    assert html.count("dest=") == 2, "옛 dest 는 빼고 새로 붙인다"


def test_검색어모드는_대본분석과_유료렌즈칸을_뺀다():
    src = INDEX.read_text(encoding="utf-8")
    assert "shortcode!=='__single__' && !st.kwOnly" in src
    assert "${st.kwOnly?'':prodBox}" in src and "${st.kwOnly?'':lensBox}" in src
    assert "function openKwFind(" in src and "function lensToJob(" in src
    assert "/yt_search" in src, "검색어 모드 모아보기는 유튜브만"


def test_플랫폼_판별():
    assert app._grab_platform_of("https://youtu.be/x") == "youtube"
    assert app._grab_platform_of("https://www.rednote.com/explore/1") == "xiaohongshu"
    assert app._grab_platform_of("https://www.tiktok.com/@a/video/1") == "tiktok"
