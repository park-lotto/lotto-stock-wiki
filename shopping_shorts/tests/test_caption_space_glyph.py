# -*- coding: utf-8 -*-
"""공백 글리프 없는 폰트에서 자막 띄어쓰기가 ⊠로 나오던 것 — 2026-08-24 고객 제보.

실측: 고객이 받은 영상에 "진짜⊠이렇게", "이거⊠한스푼만⊠넣고⊠볶으라는거에요".
대본·자막 텍스트 파일은 전부 깨끗한 U+0020이었고, 원인은 **폰트에 U+0020 글리프가
없어서** ffmpeg drawtext가 .notdef(네모)를 그린 것이었다.
서버 폰트 22종 중 빙그레체·리디바탕 2종이 해당(공백 마스크 높이 70px, 정상은 0).

고친 방식: 그런 폰트에서는 **띄어쓰기를 drawtext에 넘기지 않고** 어절을 따로 그린 뒤
사이를 좌표로 벌린다. 정상 폰트는 종전대로 한 번에 그린다(회귀 0).
"""
import pathlib

import pytest

from shopping_shorts import video_assemble as va

ImageFont = pytest.importorskip("PIL.ImageFont", reason="Pillow 필요")

FONT_DIR = pathlib.Path(va.__file__).parent / "static" / "fonts"
NO_SPACE = ["Binggrae-Bold.otf", "RIDIBatang.otf"]
OK_FONT = "Pretendard-Bold.otf"


def _font(name, size=70):
    p = FONT_DIR / name
    if not p.exists():
        pytest.skip("폰트 없음: %s" % name)
    return ImageFont.truetype(str(p), size)


@pytest.mark.parametrize("name", NO_SPACE)
def test_공백_글리프_없는_폰트를_찾아낸다(name):
    assert va._lacks_space_glyph(_font(name)) is True


def test_정상_폰트는_공백_있음으로_본다():
    assert va._lacks_space_glyph(_font(OK_FONT)) is False


def test_공백없는_폰트의_한칸_폭은_네모폭이_아니라_적당한_값이다():
    """폰트가 돌려주는 advance는 ⊠ 네모 폭(≈1em)이라 그대로 쓰면 어절이 과하게 벌어진다."""
    f = _font(NO_SPACE[0])
    assert va._space_px(f, 70) == pytest.approx(70 * 0.28)
    assert va._space_px(f, 70) < f.getlength(" ") / 2


def test_정상_폰트의_폭_계산은_종전과_같다():
    f = _font(OK_FONT)
    t = "이거 한스푼만 넣고"
    assert va._text_px(f, t, 70) == f.getlength(t)


def test_공백없는_폰트도_폭이_어절합_기준으로_나온다():
    f = _font(NO_SPACE[0])
    t = "이거 한스푼만 넣고"
    words = t.split(" ")
    expect = sum(f.getlength(w) for w in words) + va._space_px(f, 70) * (len(words) - 1)
    assert va._text_px(f, t, 70) == pytest.approx(expect)


def test_공백없는_폰트는_자막파일에_띄어쓰기를_안_넘긴다(tmp_path):
    """★핵심 회귀 — 여기 공백이 들어가면 그 자리가 그대로 ⊠가 된다."""
    if not (FONT_DIR / NO_SPACE[0]).exists():
        pytest.skip("폰트 없음")
    va._segmented_drawtext("이거 한스푼만 넣고", {"font": NO_SPACE[0], "size": 78},
                           tmp_path, "t", 50, 50, single_line=True)
    files = sorted(tmp_path.glob("txt_*.txt"))
    assert files, "자막 텍스트 파일이 안 만들어졌다"
    for f in files:
        t = f.read_text(encoding="utf-8")
        assert " " not in t, "%s 에 띄어쓰기가 남았다: %r" % (f.name, t)
    assert len(files) == 3, "어절 3개가 각각 그려져야 한다"


def test_정상_폰트는_한번에_그린다(tmp_path):
    """어절을 쪼개면 box 스타일 배경이 끊긴다 — 정상 폰트는 종전 그대로 둔다."""
    if not (FONT_DIR / OK_FONT).exists():
        pytest.skip("폰트 없음")
    va._segmented_drawtext("이거 한스푼만 넣고", {"font": OK_FONT, "size": 78},
                           tmp_path, "t", 50, 50, single_line=True)
    files = sorted(tmp_path.glob("txt_*.txt"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == "이거 한스푼만 넣고"
