"""담은 적 없는 옛 도서관 픽이 재료로 새어 들어오면 안 된다(2026-08-18 '홈데코랩')."""
import re
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "app.py"


def _body():
    s = SRC.read_text(encoding="utf-8")
    i = s.index("def _load_work_sources(")
    j = s.index("\ndef ", i + 10)
    return s[i:j]


def test_work을_읽었으면_계정전체_픽으로_폴백하지_않는다():
    b = _body()
    assert "work_known = True" in b
    m = re.search(r"if not codes[^\n]*:\n\s+codes = list\(store\.produce_pick_shortcodes", b)
    assert m, "폴백 구문을 못 찾음 — 테스트가 코드를 따라가야 한다"
    assert "not work_known" in m.group(0), "work을 아는데도 폴백하면 남의 픽이 재료가 된다"


def test_codes가_None으로_남지_않는다():
    assert "codes = codes or []" in _body()
