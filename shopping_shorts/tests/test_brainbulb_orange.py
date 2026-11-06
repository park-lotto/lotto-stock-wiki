# -*- coding: utf-8 -*-
"""brainbulb_orange(관제 322) — 원본 뇌전구 규격 + 페이퍼로지·오렌지. 원본 brainbulb 는 안 바뀌어야 한다."""
import pytest

from shopping_shorts.channelkit import registry, spec, measure, ass_gen

ORANGE = "&H000D6CF7"
YELLOW = "&H0000FFFF"


@pytest.fixture(autouse=True)
def _restore():
    yield
    registry.use(registry.DEFAULT)


def _style(name):
    return next(l for l in spec.STYLE_BLOCK.splitlines() if l.startswith(f"Style: {name},"))


def test_orange_fonts_are_paperlogy_and_all_found():
    registry.use("brainbulb_orange")
    fonts = {v[0] for v in spec.STYLE_FONT.values()}
    assert fonts == {"Paperlogy 7 Bold", "Paperlogy 8 ExtraBold", "Paperlogy 9 Black"}
    probe = measure.font_probe(None)                       # 폴백 글꼴과 폭이 달라야 '진짜 잡힘'
    assert probe and all(v["ok"] for v in probe.values()), probe


def test_style_block_and_style_font_agree():
    """줄배치는 STYLE_FONT 로 재고 렌더는 STYLE_BLOCK 으로 그린다 — 둘이 어긋나면 줄이 화면 밖으로 나간다."""
    registry.use("brainbulb_orange")
    for name, (font, _file, size) in spec.STYLE_FONT.items():
        f = _style(name).split(",")
        assert f[1] == font and int(f[2]) == size, (name, f[1:3], font, size)


def test_yellow_slots_are_orange_in_new_preset_only():
    registry.use("brainbulb_orange")
    assert ORANGE in _style("YELLOW") and ORANGE in _style("HL2") and YELLOW not in spec.STYLE_BLOCK
    registry.use("brainbulb")
    assert YELLOW in _style("YELLOW") and YELLOW in _style("HL2")    # 원본은 그대로 노랑


def test_subtitle_built_with_new_preset_uses_paperlogy():
    registry.use("brainbulb_orange")
    tm = {"card_end": 2.0, "total": 4.1, "groups": [
        {"i": 1, "t": 2.0, "d": 2.0, "color": "YELLOW", "role": "NARR", "lines": ["숫자 3개가 나옴"]}]}
    text = ass_gen.build({"h1": "윗줄 제목", "h2": "아랫줄 3개"}, "오프닝 카드 문장임", tm)
    assert "Paperlogy" in text and "에스코어" not in text and "SB 어그로" not in text


def test_output_name_orange_uses_sesangcham_slug():
    """사장님 11-06: 완성본은 렌더할 때 바로 sesangcham_<영어 요약>.mp4 하나만(final.mp4 + 복사본 두 개 금지)."""
    from shopping_shorts.channelkit import render
    registry.use("brainbulb_orange")
    assert render.output_name({"title": {"slug": "Basic-Pension 5yr"}}) == "out/sesangcham_basic-pension-5yr.mp4"
    assert render.output_name({"title": {}}, log=lambda *_: None) == "out/final.mp4"


def test_output_name_original_brainbulb_unchanged():
    from shopping_shorts.channelkit import render
    registry.use("brainbulb")
    assert render.output_name({"title": {"slug": "x"}}) == "out/final.mp4"


def test_meme_start_falls_back_to_zero_when_past_file_end(tmp_path):
    """11-06 태권도 편: 밈 목록 start(원본 기준 4.25초)가 2초짜리 파일 밖이라 고르기는 화면을 못 재고 통과,
    렌더는 0초부터 틀어 초록 배경 고양이가 나왔다. 고르기·렌더가 같은 시작점(render.meme_start)을 써야 한다."""
    import subprocess
    from shopping_shorts.channelkit import render
    from shopping_shorts.channel_presets.brainbulb_orange import memes
    clip = tmp_path / "green2s.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=0x00FF00:s=64x64:d=2", str(clip)],
                   check=True, stdin=subprocess.DEVNULL)
    assert render.meme_start(str(clip), 4.25) == 0.0
    assert render.meme_start(str(clip), 0.5) == 0.5
    assert memes.green_ratio(str(clip), 4.75) is None            # 파일 밖 = 못 잼(예전엔 0 = '초록 아님'으로 통과)
    assert memes.green_ratio(str(clip), render.meme_start(str(clip), 4.25) + 0.2) > memes.GREEN_MAX
