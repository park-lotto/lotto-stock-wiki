"""CTA 없는 스타일 — 유튜브 썰쇼핑 스파인이 항상 FAIL하던 것 (2026-08-19).

왜 필요한가 (실측):
script_gate.check()의 'CTA 단어유도' 검사는 **스타일과 무관하게 무조건** 돈다.
인스타(채이홈)는 CTA가 서명이라 옳은 규칙이었지만, 유튜브 썰쇼핑은 정반대다 —
이븐쇼핑·살림킹왕짱 실측 4편 **전부 CTA가 없고**(댓글률 0.005%, 인스타는 2.35%)
구독 1.46만 채널이 1,047만 조회를 낸다. 완시청이 전부라 댓글을 안 부른다.

그대로 두면 유튜브 스파인은 **아무리 잘 써도 CTA 검사 하나 때문에 영구 FAIL**이고,
재작성 루프가 없는 CTA를 억지로 붙이라고 시켜 스타일을 망가뜨린다.
→ 스타일이 명시적으로 "CTA 없음"을 선언하면 그 검사를 건너뛴다.

★기본값은 기존 동작(검사 O) — 선언 안 한 기존 스파인은 아무것도 안 바뀐다(회귀 0).
"""
from shopping_shorts import script_gate


def _beats(roles_texts):
    return [{"role": r, "text": t} for r, t in roles_texts]


SIWORLD = {
    "beat_roles": ["hook", "cta"],
    "templates": {},
    "chars_per_30s": 300,
}
YT = {
    "beat_roles": ["hook", "twist"],
    "templates": {},
    "chars_per_30s": 270,
    "no_cta": True,          # ← 이 스타일은 CTA를 쓰지 않는다
}


def _named(checks, name):
    return [c for c in checks if c["name"] == name]


def test_기존_스타일은_CTA검사를_그대로_받는다():
    """회귀 방지: no_cta를 선언 안 한 스파인은 지금과 똑같이 동작한다."""
    checks, _ = script_gate.check(SIWORLD, _beats([
        ("hook", "이것 때문에 시어머니한테 욕 바가지로 먹을 뻔했어요"),
        ("cta", "그래서 잘 쓰고 있어요"),          # CTA 없음 → FAIL 이어야 한다
    ]))
    hit = _named(checks, "CTA 단어유도")
    assert hit, "CTA 검사가 사라졌다 — 기존 스타일에는 남아 있어야 한다"
    assert hit[0]["ok"] is False


def test_no_cta_스타일은_CTA검사를_아예_안_받는다():
    """★유튜브 썰쇼핑. CTA가 없는 게 정답이므로 검사 자체가 없어야 한다.

    'ok: True'로 통과시키는 게 아니라 **검사 항목이 없어야** 한다 —
    있으면 재작성 지시문에 CTA 얘기가 섞여 들어간다."""
    checks, _ = script_gate.check(YT, _beats([
        ("hook", "요아정 망하게 한 한국 천재의 발명품"),
        ("twist", "근데 진짜 충격적인 포인트는 스프링으로 질감까지 조절된다는 거"),
    ]))
    assert not _named(checks, "CTA 단어유도"), "no_cta 스타일에 CTA 검사가 돌았다"


def test_no_cta여도_다른_검사는_그대로():
    """CTA만 빼는 것이지 게이트를 무력화하는 게 아니다."""
    checks, _ = script_gate.check(YT, _beats([
        ("twist", "순서가 뒤집혔다"),
        ("hook", "요아정 망하게 한 한국 천재의 발명품"),
    ]))
    order = _named(checks, "구간 순서")
    assert order and order[0]["ok"] is False, "구간 순서 검사는 살아 있어야 한다"


def test_no_cta가_DB왕복에서_살아남는다(tmp_path):
    """★조용한 실패 방지: 게이트가 no_cta를 읽어도 **DB가 실어주지 않으면** 소용없다.

    list_spines()/list_style_spines()가 돌려주는 dict가 그대로 style로 게이트에 들어간다.
    필드를 안 실으면 no_cta는 영영 None이고, 유튜브 스파인은 CTA 검사에 계속 걸린다.
    오류가 안 나서 안 드러나는 종류라 왕복을 테스트로 못박는다."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    sid = st.add_spine(name="유튜브은폐형", beat_chain=["a", "b"],
                       fit_categories=["제품정체형"], status="approved")
    st.set_spine_style(sid, beat_roles=["hook", "twist"], templates={},
                       chars_per_30s=270, no_cta=True)

    got = [s for s in st.list_spines() if s["id"] == sid][0]
    assert got.get("no_cta") is True, "list_spines가 no_cta를 안 실어준다"

    styles = st.list_style_spines(category="제품정체형", status="approved")
    mine = [s for s in styles if s["id"] == sid]
    assert mine and mine[0].get("no_cta") is True, "list_style_spines가 no_cta를 안 실어준다"

    # 그 dict를 그대로 게이트에 넣으면 CTA 검사가 없어야 한다(실사용 경로)
    checks, _ = script_gate.check(mine[0], _beats([
        ("hook", "요아정 망하게 한 한국 천재의 발명품"),
        ("twist", "근데 진짜 충격적인 포인트는 질감까지 조절된다는 거"),
    ]))
    assert not _named(checks, "CTA 단어유도")
