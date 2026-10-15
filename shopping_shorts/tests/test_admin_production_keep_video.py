# -*- coding: utf-8 -*-
"""오늘 제작 현황 — 자동 갱신이 목록을 통째로 다시 그리지 않는다(관제 167, 2026-10-09 사장님 "영상을 보다가 끊긴다").

결과물 검사는 tools/admin_production_check.py(라이브에서 영상을 재생해 갱신 뒤에도 같은 요소·재생 이어짐). 이 파일은
그 구조가 되돌아가지 않게 지키는 가드다."""
import pathlib
import re

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "admin_production.html").read_text(encoding="utf-8")


def test_목록을_통째로_다시_그리지_않는다():
    assert not re.search(r"getElementById\('grid'\)\.innerHTML\s*=", HTML)      # 통째로 쓰면 <video> 가 전부 새로 만들어진다
    assert "syncGrid(rows);" in HTML
    body = HTML[HTML.index("function syncGrid("):HTML.index("function load(")]
    assert "el.dataset.id = id" in body                                          # 카드는 작업 번호로 짝을 맞춘다
    assert "el._media !== p.media" in body and "el._body !== p.body" in body    # 달라진 칸만 고쳐 쓴다
    assert "if (el === cursor) cursor = cursor.nextElementSibling;" in body      # 순서가 맞는 카드는 옮기지 않는다(옮겨도 재생이 끊긴다)
