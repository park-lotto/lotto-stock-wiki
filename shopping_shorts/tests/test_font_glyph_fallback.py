# -*- coding: utf-8 -*-
"""폰트에 없는 글자를 그리려다 두부(□·네모X)로 나가는 것을 막는다.

★실사고 (2026-08-26 사장님 제보 — "최종렌더하니 네모에 x로 나온다")
   목록의 '옥 말랑'(OkMallangW.ttf)은 OKFont가 낸 **영문 전용** 폰트다
   (글리프 81개 = 영문·숫자·기호, 한글 0자). 파일 자체는 멀쩡한 TTF라
   브라우저도 ffmpeg도 **아무 오류 없이 로드**했고, 그 폰트로 만든 영상은
   한글이 전부 네모X로 나갔다. "static/fonts에 파일이 있는가"만 보던
   종전 규칙으로는 영영 못 잡는 종류의 사고다.

   그래서 두 겹으로 막는다:
     ① tools/sync_fonts.py — 한글 글리프 없는 폰트를 목록에 넣으면 거기서 막힌다
                              (영문 전용은 "latin": true 로 명시)
     ② video_assemble._font_ref — 렌더 직전, 그 폰트가 **그 문구를** 못 그리면
                              기본 자막폰트로 되돌린다(두부 대신 다른 글꼴)

⚠️폰트 이름·파일크기로 판정하지 마라 — 그런 목록은 반드시 썩는다.
  글리프를 직접 본다(_lacks_space_glyph 와 같은 원칙).
"""
import json
import pathlib

import pytest

BASE = pathlib.Path(__file__).resolve().parent.parent.parent
STATIC = BASE / "shopping_shorts" / "static"
FONT_DIR = STATIC / "fonts"
FONTS_JSON = STATIC / "fonts.json"

pytest.importorskip("PIL.ImageFont", reason="Pillow 필요")


def _va():
    from shopping_shorts import video_assemble
    return video_assemble


def _manifest():
    return json.loads(FONTS_JSON.read_text(encoding="utf-8"))


def test_없는_글자를_찾아낸다():
    """판정기 자체가 맞는가 — 옥말랑은 한글을 못 그리고 영문은 그린다(실측)."""
    va = _va()
    p = FONT_DIR / "OkMallangW.ttf"
    if not p.exists():
        pytest.skip("OkMallangW.ttf 없음")
    assert va._missing_glyphs(p, "한글 자막입니다") == "한글자막입니다"
    assert va._missing_glyphs(p, "SALE 2026") == ""
    assert va._missing_glyphs(FONT_DIR / "BMJUA.ttf", "한글 자막입니다") == ""


def test_공백은_없는_글자로_치지_않는다():
    """빙그레·리디바탕은 U+0020 글리프가 없지만 어절을 따로 그려 이미 우회한다.
    여기서 폴백시켜 버리면 사장님이 고른 글꼴이 통째로 바뀐다(회귀)."""
    va = _va()
    for f in ("Binggrae-Bold.otf", "RIDIBatang.otf"):
        p = FONT_DIR / f
        if p.exists():
            assert va._missing_glyphs(p, "공백 있는 문장") == "", f


def test_못_그리는_폰트는_기본폰트로_되돌린다(tmp_path):
    """_font_ref = 폰트 해석의 단일 출구. 네 갈래를 한 번에 본다."""
    va = _va()
    (tmp_path / "font.ttf").write_bytes((FONT_DIR / "BMJUA.ttf").read_bytes())
    ref = lambda f, t: va._font_ref(f, tmp_path, "k", t)  # noqa: E731
    assert ref("OkMallangW.ttf", "한글 자막") == "font.ttf", "두부인데 폴백 안 했다"
    assert ref("OkMallangW.ttf", "SALE 2026") == "font_k.ttf", "영문은 그대로 써야 한다"
    assert ref("BMJUA.ttf", "한글 자막") == "font_k.ttf", "멀쩡한 폰트를 버렸다"
    assert ref("없는파일.ttf", "한글 자막") == "font.ttf"
    assert ref(None, "한글 자막") == "font.ttf"


def test_자막과_헤드카피_두_경로가_모두_폴백한다(tmp_path):
    """호출부 형태 그대로 부른다 — 함수만 고치고 호출부가 옛 형태면 소용없다."""
    va = _va()
    (tmp_path / "font.ttf").write_bytes((FONT_DIR / "BMJUA.ttf").read_bytes())

    seg_ref, _ = va._resolve_seg_font({"font": "OkMallangW.ttf"}, tmp_path, "seg", "한글 자막")
    assert seg_ref == "font.ttf", "자막(세그먼트) 경로가 두부로 나간다"
    ok_ref, _ = va._resolve_seg_font({"font": "BMJUA.ttf"}, tmp_path, "seg", "한글 자막")
    assert ok_ref == "font_seg.ttf"

    got = va._fixed_drawtext({"font": "OkMallangW.ttf", "text": "한글 헤드카피"}, tmp_path, "hc")
    line = got if isinstance(got, str) else ":".join(got or [])
    assert "fontfile=font.ttf:" in line, "헤드카피 경로가 두부로 나간다"
    got2 = va._fixed_drawtext({"font": "BMJUA.ttf", "text": "한글 헤드카피"}, tmp_path, "hc2")
    line2 = got2 if isinstance(got2, str) else ":".join(got2 or [])
    assert "fontfile=font_hc2.ttf:" in line2


def test_한글폰트라면_한글_글리프가_있다():
    """목록 전체 훑기. 영문 전용은 latin:true 로 **명시**해야 통과한다.
    새 폰트를 넣을 때 여기서 걸리면 sync_fonts.py 가 시키는 대로 하면 된다."""
    va = _va()
    bad = []
    for f in _manifest():
        p = FONT_DIR / f["file"]
        if f.get("latin") or not p.exists():
            continue
        miss = va._missing_glyphs(p, "가한글씨")
        if miss:
            bad.append(f"{f['file']}({f['name']}) 없는글자={miss}")
    assert not bad, (
        "한글 글리프가 없는 폰트가 한글 목록에 있다 — 최종렌더에서 네모X가 된다:\n  "
        + "\n  ".join(bad)
        + '\n영문 전용 폰트라면 fonts.json 항목에 "latin": true 를 넣어라.')


def test_영문전용_폰트는_이름으로도_드러난다():
    """사장님이 목록에서 고르기 전에 알아야 한다 — 렌더 폴백은 최후의 방어선일 뿐."""
    for f in _manifest():
        if f.get("latin"):
            assert "영문" in f["name"], (
                f"{f['file']} 은 영문 전용인데 이름에 표시가 없다: {f['name']}\n"
                f"  화면 목록에서 한글 폰트처럼 보여 또 고르게 된다.")
