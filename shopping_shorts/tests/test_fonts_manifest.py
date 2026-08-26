# -*- coding: utf-8 -*-
"""폰트 목록의 정본은 fonts.json 하나다 — 화면들이 그것과 어긋나면 실패시킨다.

★왜 (0순위-B)
   종전엔 폰트 목록이 세 벌(produce.html의 @font-face·HC_FONTS, produce_intro.html의
   @font-face)이라 하나만 빠뜨려도 **오류 없이 조용히** 그 폰트가 기본체로 나왔다.
   이제 tools/sync_fonts.py 가 fonts.json에서 셋을 다시 써 넣고, 이 테스트가
   "실행하는 걸 잊었나"를 잡는다.

★실제 사고 예방 (test_caption_space_glyph.py, 2026-08-24 고객 제보)
   공백 글리프가 없는 폰트는 ffmpeg drawtext가 띄어쓰기를 ⊠로 그린다.
   손글씨·디자인 폰트일수록 흔하다 → 새 폰트가 늘 때마다 여기서 함께 훑는다.
"""
import json
import pathlib
import re
import subprocess
import sys

import pytest

BASE = pathlib.Path(__file__).resolve().parent.parent.parent
STATIC = BASE / "shopping_shorts" / "static"
FONTS_JSON = STATIC / "fonts.json"
FONT_DIR = STATIC / "fonts"


def _manifest():
    return json.loads(FONTS_JSON.read_text(encoding="utf-8"))


def _css_pairs(name):
    t = (STATIC / name).read_text(encoding="utf-8")
    return set(re.findall(r"font-family:'([^']+)';src:url\('/fonts/([^']+)'\)", t))


def test_정본_파일이_있고_비어있지_않다():
    fonts = _manifest()
    assert fonts, "fonts.json 이 비었다"


def test_목록의_폰트_파일이_전부_실제로_있다():
    """목록에만 있고 파일이 없으면 화면에서 조용히 기본체로 나온다."""
    missing = [f["file"] for f in _manifest()
               if not (FONT_DIR / f["file"]).exists()]
    assert not missing, f"static/fonts/ 에 없는 폰트: {missing}"


def test_css_이름과_파일명이_중복되지_않는다():
    """css 이름이 겹치면 뒤 폰트가 앞 폰트를 덮어써 엉뚱한 글꼴이 나온다."""
    fonts = _manifest()
    css = [f["css"] for f in fonts]
    files = [f["file"] for f in fonts]
    assert len(css) == len(set(css)), "css 이름 중복"
    assert len(files) == len(set(files)), "file 중복"


def test_css_이름이_css_식별자다():
    """따옴표·공백이 섞이면 스타일 블록이 통째로 깨진다."""
    for f in _manifest():
        assert re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", f["css"]), f["css"]


@pytest.mark.parametrize("page", ["produce.html", "produce_intro.html"])
def test_화면의_font_face가_정본과_일치한다(page):
    want = {(f["css"], f["file"]) for f in _manifest()}
    got = _css_pairs(page)
    missing, extra = want - got, got - want
    assert not missing and not extra, (
        f"{page} 가 fonts.json 과 어긋났다 — py tools/sync_fonts.py 를 실행해라.\n"
        f"  빠짐: {sorted(missing)}\n  잉여: {sorted(extra)}")


def test_HC_FONTS_배열이_정본과_일치한다():
    t = (STATIC / "produce.html").read_text(encoding="utf-8")
    m = re.search(r"const HC_FONTS=\[(.*?)\n\];", t, re.S)
    assert m, "produce.html 에서 HC_FONTS 를 못 찾았다"
    got = re.findall(r"\{name:'([^']*)',\s*file:'([^']*)',\s*css:'([^']*)'\}", m.group(1))
    want = [(("⭐ " + f["name"]) if f.get("star") else f["name"], f["file"], f["css"])
            for f in _manifest()]
    assert got == want, "HC_FONTS 가 fonts.json 과 어긋났다 — py tools/sync_fonts.py 실행"


def test_sync_fonts_check가_통과한다():
    """도구 스스로 '최신'이라고 말하는지 — 위 검사들의 상호 확인."""
    r = subprocess.run(
        [sys.executable, str(BASE / "tools" / "sync_fonts.py"), "--check"],
        capture_output=True, cwd=str(BASE))
    assert r.returncode == 0, r.stdout.decode("utf-8", "replace")


def test_공백_글리프_없는_폰트를_목록이_알고_있다():
    """빙그레·리디바탕처럼 U+0020 글리프가 없는 폰트는 자막에서 ⊠가 된다.
    video_assemble 이 어절을 따로 그려 우회하므로 **막지는 않되**, 새 폰트가
    들어올 때 눈에 띄게 목록으로 남긴다(회귀 감시)."""
    ImageFont = pytest.importorskip("PIL.ImageFont", reason="Pillow 필요")
    from shopping_shorts import video_assemble as va

    lacking = []
    for f in _manifest():
        p = FONT_DIR / f["file"]
        if not p.exists():
            continue
        try:
            font = ImageFont.truetype(str(p), 70)
        except Exception:
            continue
        if va._lacks_space_glyph(font):
            lacking.append(f["file"])
    # 알려진 2종. 늘어나면 이 테스트가 알려준다 — 우회 로직이 그 폰트도 타는지 확인하라.
    assert set(lacking) <= {"Binggrae-Bold.otf", "RIDIBatang.otf"}, (
        f"공백 글리프 없는 폰트가 새로 늘었다: {lacking}\n"
        f"  자막 띄어쓰기가 ⊠로 나올 수 있다(2026-08-24 고객 제보와 같은 증상).\n"
        f"  video_assemble._lacks_space_glyph 우회가 적용되는지 확인하고 목록에 추가하라.")
