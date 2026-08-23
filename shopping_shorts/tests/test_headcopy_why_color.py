"""헤드카피 후보 = 썸네일 제목 추천과 같은 모양(두 줄 + 이유문) + 카드별 색 고르개.

사장님 지시(2026-08-24): "헤드카피도 템플릿 안에 들어가는 거니 흡수해서 구현" /
"헤드카피 쓰는 폰트나 팩톤은 썸네일에 배치된 것 활용하고 색상변경만 추가로 넣어줘".

★why는 **왜 이 문구가 먹히는지**를 한 줄로 말한다(썸네일 thumb_title.py와 같은 계약).
  없으면 사장님이 4개 중 무엇을 고를 근거가 없어 그냥 첫 번째를 누르게 된다.
"""
import pathlib

import pytest

from shopping_shorts import headcopy_gen

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


# ── 백엔드: why를 실어 나른다 ────────────────────────────────
def _fake_call(payload):
    def _f(prompt, schema):
        return payload
    return _f


def test_suggest_carries_why(monkeypatch):
    """AI가 준 why가 그대로 카드까지 간다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", _fake_call(
        {"copies": [{"label": "반전형", "text": "축 처진 머리 이제 안 해요",
                     "why": "상식과 반대되는 결과를 제시해 궁금증을 유발했습니다"}]}))
    out = headcopy_gen.suggest("아무 대본")
    assert out[0]["why"] == "상식과 반대되는 결과를 제시해 궁금증을 유발했습니다"


def test_why_missing_is_empty_not_crash(monkeypatch):
    """★why가 없어도 죽지 않는다 — 옛 캐시·구버전 응답이 그대로 올 수 있다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", _fake_call(
        {"copies": [{"label": "훅형", "text": "네일샵 10만원 아끼는 꿀팁"}]}))
    out = headcopy_gen.suggest("아무 대본")
    assert out and out[0]["why"] == ""


def test_why_is_in_schema():
    """스키마에 why가 없으면 Gemini가 아예 안 만들어준다(조용히 빈칸)."""
    props = headcopy_gen._SCHEMA["properties"]["copies"]["items"]["properties"]
    assert "why" in props


def test_prompt_asks_for_why():
    assert "why" in headcopy_gen._PROMPT


def test_why_too_long_is_trimmed(monkeypatch):
    """이유문이 문단이 되면 카드가 무너진다 — 길이를 잠근다."""
    monkeypatch.setattr(headcopy_gen, "_call_json", _fake_call(
        {"copies": [{"label": "x", "text": "짧은 훅 두 줄", "why": "가" * 500}]}))
    out = headcopy_gen.suggest("아무 대본")
    assert len(out[0]["why"]) <= headcopy_gen._WHY_LEN


def test_still_two_lines_with_why(monkeypatch):
    """why를 붙였다고 두 줄 고정이 풀리면 안 된다(기존 계약)."""
    monkeypatch.setattr(headcopy_gen, "_call_json", _fake_call(
        {"copies": [{"label": "x", "text": "축 처진 머리 이제 안 해요", "why": "이유"}]}))
    out = headcopy_gen.suggest("아무 대본")
    assert out[0]["text"].count("\n") == 1


# ── 화면: 썸네일 카드와 같은 모양 + 색 고르개 ──────────────────
def _card_body():
    i = HTML.index("async function loadHeadcopySuggest")
    j = HTML.index("function useHeadcopy", i)
    return HTML[i:j]


def test_card_shows_two_lines_like_thumb():
    """★썸네일 카드처럼 줄바꿈을 <br>로 보여준다 — '\n'을 그대로 두면 한 줄로 붙어 보인다."""
    assert "<br>" in _card_body()


def test_card_shows_why():
    assert "c.why" in _card_body()


def test_card_has_color_picker():
    """카드마다 색 고르개 — 누르면 그 색으로 들어간다(사장님: '색상변경만 추가')."""
    body = _card_body()
    assert "type=\"color\"" in body or "type='color'" in body
    assert "useHeadcopyColor" in body


def test_color_pick_does_not_swallow_card_click():
    """★색 고르개를 누를 때 카드까지 눌리면 문구가 멋대로 바뀐다 — 클릭 전파를 막는다."""
    assert "stopPropagation" in _card_body()


def test_use_headcopy_color_sets_hcColor():
    """값의 주인은 hcColor 하나(0순위-B) — STATE를 직접 만지지 않는다."""
    i = HTML.index("function useHeadcopyColor")
    body = HTML[i:i + 700]
    assert "hcColor" in body and "updateHC()" in body


# ── 삭제: 강조 단어 칸 + 프리셋 줄(사장님 "이건 삭제해도 되고") ──
def test_highlight_rule_ui_removed():
    """수동 입력 UI는 화면에서 뺀다."""
    assert 'id="highlightRuleList"' not in HTML
    assert "+ 강조 단어 추가" not in HTML


def test_hc_preset_row_removed():
    assert 'id="hcPresets"' not in HTML


def test_highlight_rules_data_path_survives():
    """★UI만 뺀다 — 데이터 경로는 살아 있어야 한다.

    틀(applyHeadcopySet)이 2줄째 색(color2)을 highlight_rules로 넣고 렌더가 그걸 읽는다.
    여기까지 지우면 '흰→노랑' 투톤이 통째로 죽는다.
    """
    assert "_fromFrame" in HTML
    assert "STATE.deco.highlight_rules" in HTML


def test_render_highlight_rules_is_null_safe():
    """자리가 없어졌으니 그리는 함수는 조용히 돌아가야 한다."""
    i = HTML.index("function renderHighlightRules")
    assert "if(!box) return" in HTML[i:i + 300]
