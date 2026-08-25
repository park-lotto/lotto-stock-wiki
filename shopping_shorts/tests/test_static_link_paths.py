# -*- coding: utf-8 -*-
"""화면이 가리키는 정적 파일 주소가 **실제로 열리는가** (2026-08-22 실사고).

정적 파일은 **루트에 마운트**돼 있다(`app.mount("/", ...)`, app.py 주석에도 적혀 있다).
그런데 캡컷 안내 링크 3개만 `/static/` 접두사가 붙어 있었다:

    href="/static/capcut_setup.bat"     → 404
    href="/static/capcut_manual.html"   → 404  (×2)

실측(2026-08-22): 서버 내부 curl로 `/static/capcut_setup.bat` = **404**.
그래서 고객은 자동설정 파일도, 그림 매뉴얼도 **한 번도 받지 못했다.**
핸드오프의 "⏭ .bat 실제 더블클릭 동작 확인"이 한 달째 미확인이던 진짜 이유가 이것이다
— 애초에 다운로드 자체가 안 됐다.

★링크는 눈으로 안 보인다. 버튼이 멀쩡히 그려지고 누르면 조용히 404다.
  그래서 검사로 막는다.
"""
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "static"

# 마운트 규약상 존재하지 않는 접두사. 여기 걸리면 그 링크는 404다.
BAD_PREFIX = re.compile(r'(?:href|src)="/static/')


def _html_files():
    return sorted(STATIC.glob("*.html"))


def test_static_접두사를_쓰는_링크가_없다():
    """정적 파일은 루트 마운트다 — `/static/`을 붙이면 404."""
    bad = []
    for f in _html_files():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if BAD_PREFIX.search(line):
                bad.append("%s:%d  %s" % (f.name, i, line.strip()[:90]))
    assert not bad, "루트 마운트인데 /static/ 접두사를 쓴 링크:\n" + "\n".join(bad)


@pytest.mark.parametrize("name", ["capcut_setup.bat", "capcut_manual.html"])
def test_캡컷_안내파일이_실제로_있다(name):
    """링크를 고쳐도 파일이 없으면 여전히 404다 — 둘 다 봐야 한다."""
    assert (STATIC / name).is_file(), "%s 가 static/에 없다" % name


def test_제작소가_캡컷_안내를_루트경로로_가리킨다():
    """★고객이 준비를 시작하는 두 링크다. 여기가 깨지면 캡컷 기능 전체가 죽는다."""
    src = (STATIC / "produce.html").read_text(encoding="utf-8")
    assert 'href="/capcut_setup.bat"' in src
    assert 'href="/capcut_manual.html"' in src


# ── 공개 안내 페이지가 로그인 게이트에 막히지 않는가 (2026-08-25 실사고 3회째) ──
#
# `_AUTH_ALLOW`에 안 넣으면 307 → /login 이다. 페이지는 멀쩡히 배포됐는데 링크만 죽는다.
# 같은 사고가 08-23(가입전 안내 2장) · 08-24(캡컷 안내) · 08-25(capcut_easy) 세 번 났다.
# 주석으로 세 번 적어도 또 났다 → 검사로 막는다.
#
# 여기 넣는 기준: **비회원에게 카톡·단톡방으로 링크를 뿌리는 안내 페이지.**
# 로그인이 필요한 기능 페이지(produce·library 등)는 넣지 마라.
PUBLIC_PAGES = [
    "/setup.html",
    "/capcut_manual.html",
    "/capcut_easy.html",
    "/capcut_setup.bat",
]


def test_공개안내_페이지가_인증허용목록에_있다():
    from shopping_shorts.app import _AUTH_ALLOW

    missing = [p for p in PUBLIC_PAGES if p not in _AUTH_ALLOW]
    assert not missing, (
        "공개 안내인데 _AUTH_ALLOW에 없다 → 307 리다이렉트로 링크가 죽는다: %s" % missing
    )


def test_공개안내_페이지_파일이_실제로_있다():
    """허용목록에만 있고 파일이 없으면 404다."""
    root = STATIC
    missing = []
    for p in PUBLIC_PAGES:
        if not (root / p.lstrip("/")).exists():
            missing.append(p)
    assert not missing, "허용목록에 있는데 파일이 없다: %s" % missing


# ── 한글 페이지에 charset 선언이 있는가 (2026-08-25) ──
#
# 라이브는 FastAPI가 charset 헤더를 붙여줘서 가려지지만, 파일로 저장해 열거나
# charset을 안 붙이는 서버에 올리면 **한글이 통째로 깨진다**.
# 실측: static 28개 중 capcut_easy·capcut_manual 둘만 빠져 있었다.
CHARSET = re.compile(r'<meta\s+charset=', re.I)


def test_모든_html에_meta_charset이_있다():
    bad = [f.name for f in _html_files()
           if not CHARSET.search(f.read_text(encoding="utf-8")[:2000])]
    assert not bad, "meta charset 없음(한글 깨짐 위험): %s" % bad
