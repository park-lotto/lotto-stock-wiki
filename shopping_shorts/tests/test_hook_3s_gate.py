# -*- coding: utf-8 -*-
"""훅 3초 게이트 — **라이브 스파인의 실제 도입 문장**으로 검증한다(2026-08-19).

★오탐이 미탐보다 나쁘다(2026-08-15 CTA 사고와 같은 유형: 옳게 쓴 대본을 FAIL로
  잡으면 재작성 루프가 스타일을 망가뜨린다). 그래서 '진짜 대본이 통과하는가'를
  먼저 못 박는다.
"""
from shopping_shorts import script_gate as sg

# 라이브 spine 55(유튜브 「이건 바로 OO」)·56(유튜브 「원래 이렇게 쓰는 거 아닌데」)의 실제 templates 첫 항목.
REAL_BAIT = "최근 딱 봤을 때는 도저히 용도를 알기 힘든 이 제품이"
REAL_ORIGIN = "이게 원래는 의류 태그 부착용으로 개발된 제품이었음"

CONCEAL = {"hook_3s": True, "hook_conceal": True, "chars_per_30s": 270}
PLAIN = {"hook_3s": True, "chars_per_30s": 270}


def _ok(checks):
    return all(c["ok"] for c in checks)


def test_실제_은폐형_도입은_통과한다():
    full = REAL_BAIT + " 이걸 개발한 독일의 천재가 돈방석에 앉았다는데 이건 바로 마늘다지기"
    cs = sg.hook_checks(CONCEAL, full, product="마늘다지기")
    assert cs, "hook_3s를 선언했는데 검사 항목이 안 생겼다"
    assert _ok(cs), [c for c in cs if not c["ok"]]


def test_실제_오용형_도입은_통과한다():
    full = REAL_ORIGIN + " 그런데 사람들은 옷감이 손상되지 않는 점을 눈치채고"
    assert _ok(sg.hook_checks(PLAIN, full, product="옷수선 태그건"))


def test_서론으로_시작하면_잡는다():
    full = "안녕하세요 여러분 오늘은 정말 좋은 제품 하나 소개해드릴게요"
    cs = sg.hook_checks(PLAIN, full)
    assert not _ok(cs)
    assert "서론" in " ".join(c["name"] for c in cs if not c["ok"])


def test_은폐형이_3초에_정체를_밝히면_잡는다():
    full = "이건 바로 마늘다지기인데요 최근에 나온 제품입니다 진짜 편해요"
    cs = sg.hook_checks(CONCEAL, full, product="마늘다지기")
    assert not _ok(cs)
    assert "은폐" in " ".join(c["name"] for c in cs if not c["ok"])


def test_은폐를_선언안하면_정체노출은_안_잡는다():
    """오용형은 정체를 처음부터 밝힌다 — 은폐 검사를 걸면 멀쩡한 대본이 죽는다."""
    full = "이건 바로 마늘다지기인데 이게 원래는 다른 용도로 개발된 제품이었음"
    assert _ok(sg.hook_checks(PLAIN, full, product="마늘다지기"))


def test_선언안한_스타일은_검사자체가_없다():
    """회귀 0 — 기존 스타일은 항목이 안 생기니 재작성 지시문도 안 바뀐다."""
    assert sg.hook_checks({"chars_per_30s": 270}, "안녕하세요 오늘은") == []


def test_창은_말속도_상수를_빌려쓴다():
    """★초 계산 상수를 여기 또 박으면 화면·편성과 다른 수를 말하게 된다(0순위-B)."""
    win = sg.hook_window({}, "가" * 200)
    assert len(win) == int(sg._speech_cps() * 3)


def test_check가_훅항목을_싣는다():
    """게이트 본체에 배선됐는지 — 함수만 있고 아무도 안 부르면 없는 것과 같다."""
    style = dict(CONCEAL, beat_roles=["bait"], templates={})
    checks, _full = sg.check(style, [{"role": "bait", "text": REAL_BAIT}], product="마늘다지기")
    assert any(c["name"].startswith("훅 3초") for c in checks)


def test_DB에서_게이트까지_플래그가_실린다(tmp_path):
    """★함수만 있고 플래그가 안 실리면 라이브에서만 죽는다(2026-08-19 실제로 겪었다).
    DB에 켠 값이 list_spines dict를 거쳐 게이트까지 도달하는지 끝까지 본다."""
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "t.db"))
    sid = st.add_spine("유튜브 「이건 바로 OO」", status="approved")
    st.set_spine_style(sid, beat_roles=["bait"], templates={},
                       chars_per_30s=270, hook_3s=True, hook_conceal=True)
    sp = [x for x in st.list_spines(status="approved") if x["id"] == sid][0]
    assert sp["hook_3s"] is True and sp["hook_conceal"] is True
    assert sg.hook_checks(sp, "안녕하세요 오늘은 소개해드릴게요"), "게이트가 안 켜졌다"


# ── 한 낱말 제품명 회귀 방지 (2026-09-09) ──────────────────────────────────
# ★2026-09-08에 "낱말 2개 이상 겹칠 때만 유출"로 완화했다가(선풍기 틈새 청소 솔의
#   '청소' 한 낱말로 멀쩡한 훅이 반려된 탓) **제품명 자체가 한 낱말인 경우**를 놓쳤다.
#   "마늘다지기"를 훅에 그대로 써도 통과해 은폐형의 생명이 죽었다. 둘 다 지킨다.

def test_한낱말_제품명은_한번만_나와도_잡는다():
    """제품명이 한 낱말이면 그 한 낱말이 곧 정체다."""
    cs = sg.hook_checks(CONCEAL, "이건 바로 마늘다지기인데 최근 화제라는데", product="마늘다지기")
    assert not _ok(cs), "한 낱말 제품명이 훅에 나왔는데 통과했다"
    assert "은폐" in " ".join(c["name"] for c in cs if not c["ok"])


def test_여러낱말_제품의_한낱말_스침은_통과한다():
    """'선풍기 틈새 청소 솔'의 '청소'처럼 카테고리어가 스치는 건 유출이 아니다."""
    full = "최근 딱 봤을 때는 도저히 용도를 알기 힘든 이 청소 도구가"
    assert _ok(sg.hook_checks(CONCEAL, full, product="선풍기 틈새 청소 솔")), "멀쩡한 훅을 반려했다"


def test_여러낱말_제품이_두낱말_겹치면_잡는다():
    full = "이건 바로 틈새 청소 솔인데 진짜 편하다는 거"
    assert not _ok(sg.hook_checks(CONCEAL, full, product="선풍기 틈새 청소 솔"))
