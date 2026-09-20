# -*- coding: utf-8 -*-
"""발명품형 4갈래 스파인(2026-09-09) — **실제로 쓸 수 있는 스타일인가**를 본다.

★검사의 핵심은 "등록됐나"가 아니라 **"등록된 게 실제로 도는가"**다.
  - 템플릿이 `spine_fill`이 모르는 슬롯을 쓰면 그 변형은 **통째로 건너뛰어진다**(조용히 죽는다)
  - `hook_3s`를 안 걸면 반말 지시·존댓말 반려가 **한 줄도 안 걸린다**
  - `beat_roles`와 `templates` 키가 어긋나면 그 칸은 문장틀 없이 나간다
  이 셋은 전부 오류 없이 조용히 나빠지는 종류라 테스트가 아니면 못 잡는다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shopping_shorts import bank_assemble, spine_fill   # noqa: E402
from shopping_shorts.store import Store                 # noqa: E402
from tools import seed_spine_invention4 as S            # noqa: E402


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_네갈래가_다_등록된다(tmp_path):
    st = _store(tmp_path)
    for spec in S.SPECS:
        S.upsert(st, spec, apply=True)
    got = {s["name"] for s in st.list_style_spines()}
    for spec in S.SPECS:
        assert spec["name"] in got, "%s가 목록에 없다 — 화면에 카드가 안 뜬다" % spec["name"]


def test_멱등하다_두번_넣어도_안_늘어난다(tmp_path):
    st = _store(tmp_path)
    for spec in S.SPECS:
        S.upsert(st, spec, apply=True)
    before = len(st.list_spines())
    for spec in S.SPECS:
        S.upsert(st, spec, apply=True)
    assert len(st.list_spines()) == before, "두 번 넣었더니 행이 늘었다 — 중복 생성"


def test_템플릿_슬롯이_전부_아는_이름이다():
    """★모르는 슬롯을 쓰면 pick_template이 그 변형을 통째로 건너뛴다(조용히 죽는다)."""
    known = set(spine_fill.SLOT_NAMES)
    for spec in S.SPECS:
        for role, variants in spec["templates"].items():
            for t in variants:
                for slot in spine_fill.slots_in(t):
                    assert slot in known, (
                        "%s / %s: 모르는 슬롯 {%s} — 이 변형은 영영 안 걸린다\n  %s"
                        % (spec["name"], role, slot, t))


def test_beat_roles와_templates_키가_맞는다():
    """칸은 있는데 문장틀이 없으면 그 칸은 맨몸으로 나간다."""
    for spec in S.SPECS:
        roles = set(spec["beat_roles"])
        keys = set(spec["templates"])
        assert keys <= roles, "%s: templates에 없는 칸이 있다 %s" % (spec["name"], keys - roles)
        assert roles == keys, "%s: 문장틀 없는 칸 %s" % (spec["name"], roles - keys)


def test_모든_칸에_문장틀이_두개_이상이다():
    """변형이 하나뿐이면 편마다 같은 문장이 나온다(실측: 훅이 늘 같은 틀로 수렴했다)."""
    for spec in S.SPECS:
        for role, variants in spec["templates"].items():
            assert len(variants) >= 2, "%s / %s: 변형이 %d개뿐" % (spec["name"], role, len(variants))


def test_반말규칙이_걸린다(tmp_path):
    """★hook_3s를 선언해야 프롬프트에 반말 지시가 실린다(2026-08-22 사장님 규칙)."""
    st = _store(tmp_path)
    for spec in S.SPECS:
        S.upsert(st, spec, apply=True)
    for s in st.list_style_spines():
        if not s["name"].startswith("유튜브"):
            continue
        assert s.get("hook_3s"), "%s: hook_3s가 꺼져 있다 — 존댓말이 새도 아무도 안 잡는다" % s["name"]
        blk = bank_assemble.style_block(s, seconds=30)
        assert "반말" in blk, "%s: 프롬프트에 반말 지시가 없다" % s["name"]
        assert "거든요" in blk, "%s: 금지 어미 예시가 없다" % s["name"]


def test_CTA가_전부_꺼져있다(tmp_path):
    """유튜브 썰은 완시청 장사다 — CTA를 쓰지 않는다."""
    st = _store(tmp_path)
    for spec in S.SPECS:
        S.upsert(st, spec, apply=True)
    for s in st.list_style_spines():
        if s["name"].startswith("유튜브"):
            assert s.get("no_cta"), "%s: no_cta가 꺼져 있다" % s["name"]


def test_정체감추는_갈래만_은폐를_건다(tmp_path):
    """①②는 정체를 숨기고 ③④는 처음부터 밝힌다 — 은폐 검사를 잘못 걸면 멀쩡한 대본이 죽는다."""
    st = _store(tmp_path)
    for spec in S.SPECS:
        S.upsert(st, spec, apply=True)
    by = {s["name"]: s for s in st.list_style_spines()}
    assert by[S.S1["name"]].get("hook_conceal"), "① 성과+고조형은 정체를 안 밝힌다"
    assert by[S.S2["name"]].get("hook_conceal"), "② 정체공개형은 중반까지 감춘다"
    assert not by[S.S3["name"]].get("hook_conceal"), "③ 한계중심형은 처음부터 밝힌다"
    assert not by[S.S4["name"]].get("hook_conceal"), "④ 사람이야기형은 처음부터 밝힌다"


def test_길이가_갈래마다_다르다():
    """★기존 3종은 전부 270자로 똑같이 박혀 있었다. 실측은 178~265자로 갈린다."""
    lens = {spec["name"]: spec["chars_per_30s"] for spec in S.SPECS}
    assert len(set(lens.values())) == 4, "길이가 겹친다 — 실측대로 갈라야 한다: %r" % lens
    assert lens[S.S1["name"]] < lens[S.S3["name"]] < lens[S.S2["name"]] < lens[S.S4["name"]], (
        "실측 순서(① 178~190 < ③ 209~217 < ② 194~248 < ④ 228~265)와 다르다: %r" % lens)


def test_정체감추는_갈래는_훅에_제품슬롯이_없다():
    """★①②는 훅에서 이름을 밝히면 안 된다 — {제품}을 쓰면 게이트가 자기 문장을 반려한다."""
    for spec in (S.S1, S.S2):
        for t in spec["templates"]["title"]:
            assert "{제품}" not in t, "%s: 훅에 {제품}이 있다 — 정체가 새고 게이트가 반려한다\n  %s" % (
                spec["name"], t)


def test_첫갈래는_reveal칸이_없다():
    """이 갈래의 정의 자체다 — 끝까지 안 밝힌다."""
    assert "reveal" not in S.S1["beat_roles"], "① 성과+고조형에 reveal이 생겼다"


def test_넷째갈래는_고조가_3단이다():
    """실측 ④는 '미친 포인트' → '심지어' → '진짜 충격' 3단이다(②는 2단)."""
    roles = S.S4["beat_roles"]
    for r in ("benefit", "escalate", "twist"):
        assert r in roles, "④에 %s 칸이 없다 — 3단 고조가 안 선다" % r
