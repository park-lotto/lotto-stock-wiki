# -*- coding: utf-8 -*-
"""문장틀을 job마다 다른 순서로 보여준다 — 훅이 매번 같던 것 (2026-08-23 사장님).

## 왜 (실측)

`style_block`은 문장틀을 **항상 같은 순서**로 프롬프트에 실었다. 모델은 앞쪽/특정
문장에 쏠린다 — 다이소 훅 10개로 8회 뽑은 실측:

    1·2·3·8·9·10번 → 0회   (10개 중 6개가 한 번도 안 나온다)
    6번 3회 · 7번 3회 · 4번 1회 · 5번 1회

즉 **틀을 늘려도 순서가 고정이면 소용이 없다**. 조립 경로에는 이미 같은 이유로
`spine_fill._rotate_idx`가 있는데(2026-08-21), 생성기 경로에는 없었다.

★랜덤이 아니라 **job_id 해시**다 — 같은 job을 다시 돌리면 같은 대본이 나온다(재현성).
  role을 섞어 넣어 한 대본 안에서도 칸마다 다른 번호에서 시작한다.
★seed 없이 부르면 종전 순서 그대로 = 회귀 0.
"""
from shopping_shorts import bank_assemble

STYLE = {
    "name": "다이소",
    "beat_roles": ["hook", "cta"],
    "templates": {"hook": ["A1", "A2", "A3", "A4", "A5"], "cta": ["C1", "C2", "C3"]},
    "chars_per_30s": 297,
}


def _order(block, tag):
    """프롬프트에 실린 순서대로 그 칸의 틀을 뽑는다."""
    line = next(l for l in block.split("\n") if '"%s1"' % tag in l or "%s1" % tag in l)
    return [x for x in line.replace('"', " ").split() if x.startswith(tag)]


def test_seed_changes_order():
    """job_id가 다르면 틀 순서가 달라진다."""
    a = _order(bank_assemble.style_block(STYLE, seconds=25, seed="job-aaa"), "A")
    b = _order(bank_assemble.style_block(STYLE, seconds=25, seed="job-bbb"), "A")
    assert set(a) == set(b), "틀이 사라지거나 늘면 안 된다"
    assert a != b, "seed가 달라도 순서가 같다 — 회전이 안 걸렸다"


def test_same_seed_is_reproducible():
    """같은 job_id면 같은 순서 — 다시 돌려도 같은 대본이 나와야 한다."""
    a = _order(bank_assemble.style_block(STYLE, seconds=25, seed="job-aaa"), "A")
    b = _order(bank_assemble.style_block(STYLE, seconds=25, seed="job-aaa"), "A")
    assert a == b, "같은 seed인데 순서가 다르다 — 재현성이 깨진다"


def test_no_seed_keeps_old_order():
    """seed를 안 주면 종전 순서 그대로(회귀 0)."""
    got = _order(bank_assemble.style_block(STYLE, seconds=25), "A")
    assert got == ["A1", "A2", "A3", "A4", "A5"], "seed 없이 순서가 바뀌었다: %s" % got


def test_roles_rotate_independently():
    """한 대본 안에서 칸마다 다른 번호에서 시작한다(전부 1번으로 쏠리지 않게)."""
    blk = bank_assemble.style_block(STYLE, seconds=25, seed="job-xyz")
    assert _order(blk, "A")[0] != "A1" or _order(blk, "C")[0] != "C1", \
        "모든 칸이 1번으로 시작한다 — role이 회전에 안 섞였다"
