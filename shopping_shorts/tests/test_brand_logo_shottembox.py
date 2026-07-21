"""메인 로고·탭 제목 브랜드 = 숏템박스 (사장님 2026-07-21 지시).

마케팅 대문(app.py _BRAND)은 이미 숏템박스인데 내부 툴 페이지의 로고(사이드바)와
브라우저 탭 제목이 옛 '쇼핑쇼츠'로 남아 있었다. 고객 노출 브랜드를 숏템박스로 통일한다.
(내부 명칭 shopping_shorts·딸깍·capcut_setup.bat 창제목은 유지 — 고객 비노출.)
"""
import pathlib

STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"

# 고객이 보는 탭 제목이 있는 페이지들(내부 .bat 제외).
_TITLE_PAGES = ["index.html", "collection.html", "produce.html", "mix.html",
                "library.html", "discover.html", "find.html", "outreach.html"]


def test_sidebar_logo_is_shottembox():
    js = (STATIC / "sidebar.js").read_text(encoding="utf-8")
    assert "숏템박스" in js, "사이드바 메인 로고가 숏템박스가 아니다"
    assert "쇼핑쇼츠" not in js, "사이드바에 옛 브랜드 '쇼핑쇼츠'가 남아있다"


def test_page_titles_use_shottembox_not_old_brand():
    for name in _TITLE_PAGES:
        html = (STATIC / name).read_text(encoding="utf-8")
        head = html[:html.find("</head>")] if "</head>" in html else html
        assert "쇼핑쇼츠" not in head, f"{name} 탭 제목에 옛 브랜드 '쇼핑쇼츠'가 남아있다"
        assert "숏템박스" in head, f"{name} 탭 제목에 숏템박스가 없다"
