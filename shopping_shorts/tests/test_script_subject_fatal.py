"""★소재가 다른 대본은 화면에 내보내지 않는다 (2026-09-09 사장님 재발 제보).

실측(work f2547fc3a753, cid 109 '레트로 모니터'):
  재료 product = 'Mac Mini용 레트로 매킨토시 스타일 케이스'
  그런데 A안이 **채칼·도마·칼날** 대본으로 나왔다.
  게이트는 `소재 일치 False`로 **정확히 잡고 있었다** — 그런데도 화면에 실렸다.

뿌리: generate_one_style은 재시도 뒤에도 통과 못 하면 **길이(밀도)가 가장 가까운 안을
그대로 내보낸다**(fail-open). 밀도·순서가 어설픈 건 고쳐 쓰면 되지만, 소재가 다르면
그 대본은 통째로 남의 제품 이야기다.
(09-07엔 프롬프트 가드만 넣었다 — "프롬프트가 말해도 아무도 막지 않으면 안 지켜진다")
"""
from shopping_shorts import script_gate

_채칼_대본 = [
    {"role": "hook", "text": "와, 저희 언니가 이거 쓰고 요리 시간 반으로 줄었다고 난리 치더라고요."},
    {"role": "story", "text": "매번 퇴근하고 저녁 준비할 때마다 재료 손질하느라 1시간씩 서 있는 게 정말 고역이었거든요."},
    {"role": "benefit", "text": "근데 이게 채소 크기랑 모양을 딱 맞춰서 한 번에 싹 썰어주니까 도마 앞에서 씨름할 일이 없더라고요."},
    {"role": "cta", "text": "댓글에 '도구' 남겨주시면 제가 쓰는 제품 정보 바로 알려드릴게요."},
]
_우리제품 = "Mac Mini용 레트로 매킨토시 스타일 케이스"


def test_gate_catches_wrong_subject():
    """게이트가 소재 이탈을 잡는지 — 이게 깨지면 아래 방어가 통째로 무의미하다."""
    checks, _full = script_gate.check({}, _채칼_대본, product=_우리제품, seconds=30)
    names = {c["name"]: c["ok"] for c in checks}
    assert "소재 일치" in names, names
    assert names["소재 일치"] is False, "재료와 다른 제품인데 통과했다"


def test_subject_mismatch_is_fatal():
    """소재 이탈은 '고쳐서라도 내보낸다'가 안 되는 치명 실패여야 한다."""
    checks, _ = script_gate.check({}, _채칼_대본, product=_우리제품, seconds=30)
    assert script_gate.fatal_fail(checks) == "소재 일치"


def test_other_failures_are_not_fatal():
    """길이·순서 같은 실패까지 치명으로 다루면 생성이 통째로 막힌다(회귀 방지)."""
    checks = [{"name": "말 밀도(155~222자)", "ok": False},
              {"name": "구간 순서", "ok": False},
              {"name": "소재 일치", "ok": True}]
    assert script_gate.fatal_fail(checks) == ""


def test_generate_one_style_drops_subject_leak(monkeypatch):
    """모델이 끝까지 다른 소재를 내면 generate_one_style은 **버린다**(None)."""
    from shopping_shorts import script_generate as sg

    # ★호출부 형태 그대로 흉내낸다(짐작 금지): generate_one_style은
    #   `_call_json(prompt, schema, note=note)` 가 돌려주는 dict의 "beats"를 쓰고,
    #   그 앞에서 `bank_assemble.style_block(...)`이 비면 곧장 None을 돌려준다.
    # style_block은 함수 안에서 `from shopping_shorts import bank_assemble`로 늦게 불러온다
    # → 모듈 자체를 갈아야 한다(sg.bank_assemble 속성은 없다).
    from shopping_shorts import bank_assemble
    monkeypatch.setattr(bank_assemble, "style_block",
                        lambda *a, **k: "[스타일 예시] 테스트용 블록")
    monkeypatch.setattr(sg, "_call_json",
                        lambda *a, **k: {"beats": [dict(b) for b in _채칼_대본]})
    note = {}
    out = sg.generate_one_style(
        [{"full_text": "레트로 매킨토시 케이스에 맥미니를 넣는 제품", "product": _우리제품}],
        {"id": 1, "name": "테스트"}, 30, note=note)
    assert out is None, "소재가 틀린 안이 그대로 나갔다"
    assert note.get("reason") == "소재이탈", note
