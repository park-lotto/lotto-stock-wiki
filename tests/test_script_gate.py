"""대본 스타일 게이트 — 순수함수 검사(실험실에서 실제로 밟은 함정 포함)."""
from shopping_shorts import script_gate


STYLE = {
    "beat_roles": ["hook", "before", "reveal", "after", "cta"],
    "templates": {
        "hook": ["이것 때문에 {가족}한테 욕 바가지로 먹을 뻔했어요",
                 "{장소} 갔다가 진짜 충격 받았어요"],
        "reveal": ["알고 보니 {전문가}가 추천해준 {제품}이라고 하더라구요"],
        "cta": ["댓글에 {단어} 남겨주세요"],
    },
    "chars_per_30s": 300,
}


def _beats(**over):
    base = {
        "hook": "이것 때문에 시어머니한테 욕 바가지로 먹을 뻔했어요. " + "가" * 50,
        "before": "가" * 60,
        "reveal": "알고 보니 살림 전문가가 추천해준 운동화 세제라고 하더라구요. " + "가" * 30,
        "after": "가" * 60,
        "cta": "댓글에 운동화 남겨주세요",
    }
    base.update(over)
    return [{"role": r, "text": base[r]} for r in STYLE["beat_roles"]]


def test_정상_대본은_전부_통과한다():
    checks, full = script_gate.check(STYLE, _beats())
    assert script_gate.passed(checks), [c for c in checks if not c["ok"]]
    assert script_gate.gate_feedback(checks) == ""


def test_조사가_바뀌어도_문장틀로_인정한다():
    """{제품}이라고 → '세제라고' — 받침에 따라 조사가 사라진다. 튕기면 안 된다."""
    assert script_gate.template_matches(
        "알고 보니 살림 유튜버가 추천해준 기름때 세제라고 하더라구요",
        STYLE["templates"]["reveal"])


def test_중괄호_이스케이프_함정_회귀():
    """re.escape를 통째로 걸면 리터럴 점이 돼 절대 안 맞던 버그."""
    assert script_gate.template_matches("댓글에 기름때 남겨주세요",
                                        STYLE["templates"]["cta"])


def test_다른_문장은_문장틀로_인정하지_않는다():
    assert not script_gate.template_matches("제가 직접 써보니 좋더라구요",
                                            STYLE["templates"]["reveal"])
    assert not script_gate.template_matches("아니 이거 저만 몰랐나 봐요",
                                            STYLE["templates"]["hook"])


def test_구간_순서가_어긋나면_잡는다():
    beats = _beats()
    beats[1], beats[2] = beats[2], beats[1]
    checks, _ = script_gate.check(STYLE, beats)
    assert not script_gate.passed(checks)
    assert any(c["name"] == "구간 순서" and not c["ok"] for c in checks)


def test_말_밀도가_모자라면_잡는다():
    """★실측: 목표 300자인데 117자가 나오고도 아무 경고가 없던 것이 이 검사의 이유."""
    short = [{"role": r, "text": "짧게"} for r in STYLE["beat_roles"]]
    short[0]["text"] = "이것 때문에 시어머니한테 욕 바가지로 먹을 뻔했어요"
    short[-1]["text"] = "댓글에 운동화 남겨주세요"
    checks, _ = script_gate.check(STYLE, short)
    assert not script_gate.passed(checks)
    assert any(c["name"].startswith("말 밀도") and not c["ok"] for c in checks)


def test_CTA가_없으면_잡는다():
    checks, _ = script_gate.check(STYLE, _beats(cta="이거 꼭 써보세요"))
    assert any(c["name"] == "CTA 단어유도" and not c["ok"] for c in checks)


def test_실패는_재작성_지시문이_된다():
    checks, _ = script_gate.check(STYLE, _beats(cta="이거 꼭 써보세요"))
    fb = script_gate.gate_feedback(checks)
    assert "재작성 지시" in fb and "CTA 단어유도" in fb


def test_스타일에_밀도가_없으면_일반기준을_쓴다():
    style = dict(STYLE)
    style.pop("chars_per_30s")
    checks, _ = script_gate.check(style, _beats())
    density = [c for c in checks if c["name"].startswith("말 밀도")][0]
    assert "94~189" in density["name"]      # 135자의 70~140%
