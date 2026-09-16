# -*- coding: utf-8 -*-
"""내부 검사 결과(사실 근거·말 밀도·못 지킨 항목)를 **고객 화면에 띄우지 않는다**를 고정한다.

2026-09-16 사장님: "이런거 자체를 쓰지마. 사람들 봐서 좋을거 없자나."
  · 화면에 뜨던 '⚠️ 말 밀도(129~185자) — 이 스타일에서 벗어났어요' 같은 문구는 우리가 품질을
    조율하려고 만든 내부 지표지 고객 판단용이 아니다. 멀쩡한 대본을 잘못 나온 것처럼 보이게 한다.
  · 09-16 00:42 커밋이 이 파일에 반대 계약("사실검사 폴백 초안이 정상 통과본처럼 보이지 않는지")을
    박아 두었다 — 그날 새벽의 두더지잡기 산물이다. 경로 정리(2단계 검사 단일화)에서 뒤집는다.
  · 검사 자체는 그대로 돈다(script_gate). **표시만** 안 한다. 통과 뱃지(✅ 구조 지킴)는 남긴다.
"""
from pathlib import Path


HTML = (Path(__file__).parents[1] / "static" / "produce.html").read_text(encoding="utf-8")

_INTERNAL_COPY = (
    "사실 근거 확인이 필요한 초안", "사실 근거 확인 필요", "확정 전 빨간 검사 항목",
    "이 스타일에서 벗어났어요", "못 지킨 항목", "장면 근거로 자동 복구",
    "장면에서 확인된 내용만 사용해 자동 복구", "생성에 실패했습니다",
)


def _code_only(s):
    """JS 주석 줄을 뺀다 — "왜 안 띄우는지"를 적은 주석에 그 문구가 인용돼 있다."""
    return "\n".join(ln for ln in s.splitlines() if not ln.strip().startswith("//"))


def _block(start_marker, end_marker):
    start = HTML.index(start_marker)
    end = HTML.index(end_marker, start)
    return _code_only(HTML[start:end])


def test_s2_draft_card_shows_no_internal_check_copy():
    block = _block("function s2DraftHtml(dr,i)", "// ── ✍ 내가 직접 쓰기")
    for copy in _INTERNAL_COPY:
        assert copy not in block, copy
    # 통과 뱃지는 남는다 — 긍정 신호는 고객에게 해가 없다
    assert "✅ 구조 지킴" in block
    # 실패 뱃지 클래스는 더 이상 만들어지지 않는다
    assert 's2-gate fail' not in block


def test_legacy_modal_shows_no_internal_check_copy():
    block = _block("function _pmChecksHtml(dr)", "function pmRenderDrafts")
    for copy in _INTERNAL_COPY:
        assert copy not in block, copy
    assert "구조 지킴" in block


def test_fewer_drafts_notice_is_plain_not_alarming():
    """안이 적게 나왔을 때는 알려야 한다(다시 눌러야 하니까) — 단 '실패' 같은 말 없이 담백하게."""
    start = HTML.index("const _want=s2AnCount();")
    block = _code_only(HTML[start:start + 900])
    assert "안이 만들어졌어요" in block
    assert "다시 만들기" in block
    assert "실패" not in block
    assert "⚠️" not in block
