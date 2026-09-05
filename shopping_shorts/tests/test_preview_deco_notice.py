"""미리보기가 꾸미기를 뺀다는 사실을 화면이 **미리** 알리는지.

2026-09-02 실측: 6단계에서 자막색을 검정(#000000)으로 바꾸고 3단계 미리보기를 보면
자막이 **흰색 그대로**다. 버그가 아니라 설계다 —
`mix_pipeline.run_preview`가 assemble에 `caption_style=None, deco={}`를 넘긴다
("스펙 §9: 꾸미기 제외"). 최종 렌더(run_render)는 정상적으로 넘긴다.

문제는 **그 사실이 화면에 없다**는 것. 고객 눈엔 "바꿨는데 반영 안 됨"이고,
진짜 저장 버그(자막 컨트롤이 저장을 안 부르던 것)와 증상이 완전히 똑같아 구별이 안 된다.

이 테스트는 코드(꾸미기 제외)와 안내(화면 문구)가 **짝으로** 유지되는지 본다.
한쪽만 바뀌면 빨개진다.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENE_LAB = ROOT / "static" / "scene_lab.html"
MIX_PIPELINE = ROOT / "mix_pipeline.py"


def test_preview_really_excludes_deco():
    """전제 확인 — 미리보기가 정말 꾸미기를 빼는가(빼지 않게 바뀌면 안내가 거짓이 된다)."""
    src = MIX_PIPELINE.read_text(encoding="utf-8")
    i = src.index("out_path = work / \"preview.mp4\"")
    body = src[i:i + 1600]
    assert "deco={}" in body, "미리보기가 더는 꾸미기를 빼지 않는다 — 안내 문구를 고쳐야 한다"
    assert "caption_style" not in body.split("assemble(")[1][:400], (
        "미리보기가 caption_style을 넘기기 시작했다 — 안내 문구를 고쳐야 한다")


def test_notice_is_shown_before_playing():
    """재생 전 안내(#playerIdle)에 '꾸미기는 빠져 있다'가 보여야 한다."""
    html = SCENE_LAB.read_text(encoding="utf-8")
    i = html.index('id="playerIdle"')
    idle = html[i:html.index('id="player"', i)]
    assert "꾸미기" in idle, "미리보기 안내에 꾸미기 얘기가 없다"
    assert re.search(r"빠져\s*있", idle), "'빠져 있다'는 사실이 안 적혀 있다"
    assert "완성본" in idle, "어디서 확인하면 되는지(완성본 만들기)를 안 알려준다"


def test_notice_mentions_caption_color():
    """실제로 사장님이 겪은 항목(자막 색)을 콕 집어 말해야 한다 — 막연하면 안 읽힌다."""
    html = SCENE_LAB.read_text(encoding="utf-8")
    i = html.index('id="playerIdle"')
    idle = html[i:html.index('id="player"', i)]
    assert "자막" in idle and ("색" in idle or "헤드카피" in idle), (
        "무엇이 빠지는지 구체적으로 안 적혀 있다")
