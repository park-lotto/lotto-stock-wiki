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


def test_sidebar_logo_is_prominent():
    """메인 로고는 크고 눈에 띄게(사장님 2026-07-21) — .ss-nav h1 폰트가 커야 한다."""
    import re
    js = (STATIC / "sidebar.js").read_text(encoding="utf-8")
    m = re.search(r"\.ss-nav h1\{[^}]*font-size:\s*(\d+)px", js)
    assert m, ".ss-nav h1 font-size를 못 찾음(구조 변경?)"
    assert int(m.group(1)) >= 24, f"메인 로고가 작다({m.group(1)}px) — 크게 강조해야 함"


def test_sidebar_logo_click_goes_home():
    """로고를 누르면 홈(/)으로 — '새로고침' 지시(사장님 2026-07-21)."""
    import re
    js = (STATIC / "sidebar.js").read_text(encoding="utf-8")
    assert re.search(r"<h1[^>]*onclick", js), "로고 h1에 클릭 핸들러가 없다"
    assert "location.href='/'" in js, "로고 클릭이 홈(/)으로 안 간다"


def test_sidebar_menu_items_are_larger():
    """카테고리 메뉴를 크게 — ss-item 폰트 15px 이상(사장님 2026-07-21)."""
    import re
    js = (STATIC / "sidebar.js").read_text(encoding="utf-8")
    m = re.search(r"\.ss-item\{[^}]*font-size:\s*(\d+)px", js)
    assert m and int(m.group(1)) >= 15, f"메뉴 항목이 작다 — {m and m.group(1)}px"


def test_sidebar_groups_are_boxed():
    """카테고리를 박스로 시각 구분 — ss-group에 테두리/배경(사장님 2026-07-21)."""
    import re
    js = (STATIC / "sidebar.js").read_text(encoding="utf-8")
    m = re.search(r'"\.ss-group\{[^}]*\}"', js)
    assert m, ".ss-group 스타일을 못 찾음"
    block = m.group(0)
    assert "border" in block or "background" in block, "그룹이 박스(테두리/배경)가 아니다"


def test_page_titles_use_shottembox_not_old_brand():
    for name in _TITLE_PAGES:
        html = (STATIC / name).read_text(encoding="utf-8")
        head = html[:html.find("</head>")] if "</head>" in html else html
        assert "쇼핑쇼츠" not in head, f"{name} 탭 제목에 옛 브랜드 '쇼핑쇼츠'가 남아있다"
        assert "숏템박스" in head, f"{name} 탭 제목에 숏템박스가 없다"
