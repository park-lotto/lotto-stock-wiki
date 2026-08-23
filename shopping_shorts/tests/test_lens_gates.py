# -*- coding: utf-8 -*-
"""렌즈 계열 유료게이트 점검 (2026-08-23).

★왜 생겼나: /api/lens/kw/search 는 docstring에 "유료게이트를 CN과 같은 기준으로
   건다"고 적어놓고 실제로는 과금·상한이 하나도 없었다. 두 경로 모두 Apify(유료)로
   폴백하므로 공짜가 아닌데, 승인된 체험 계정이 무제한으로 태울 수 있었다.

★이 테스트는 "게이트가 붙어 있는가"를 소스에서 확인한다. 실제 호출 검증이 아니라
   회귀 방지용이다 — 누가 게이트를 지우면 여기서 걸린다.
"""
import re
from pathlib import Path

APP = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

# 돈이 나가는 렌즈 경로 — 전부 같은 세 가지를 통과해야 한다.
PAID_LENS_ROUTES = [
    '@app.post("/api/lens/search")',
    '@app.post("/api/lens/cn/search")',
    '@app.post("/api/lens/kw/search")',
]


def _handler_body(marker: str) -> str:
    i = APP.index(marker)
    nxt = APP.find("\n@app.", i + 10)
    return APP[i: nxt if nxt > 0 else i + 4000]


def test_every_paid_lens_route_has_all_three_gates():
    """전역 상한 → 계정별 일일 상한 → 포인트 차감. 하나라도 빠지면 새는 구멍이 된다."""
    missing = []
    for r in PAID_LENS_ROUTES:
        b = _handler_body(r)
        for gate in ("_global_over_cap", "check_and_count", "_charge_or_402"):
            if gate not in b:
                missing.append(f"{r} → {gate} 없음")
    assert not missing, "유료 렌즈 경로에 게이트가 빠졌다: " + "; ".join(missing)


def test_paid_lens_routes_refund_on_failure():
    """★차감했으면 실패 시 되돌려야 한다 — 안 그러면 잔액이 조용히 갉힌다."""
    missing = []
    for r in PAID_LENS_ROUTES:
        b = _handler_body(r)
        if "refund_credit" not in b or "_refund_points" not in b:
            missing.append(r)
    assert not missing, "실패 환불이 없는 유료 렌즈 경로: %s" % missing


def test_lens_gate_uses_constants_not_literals():
    """오타가 조용히 '무료'로 둔갑하지 않게 상수를 쓴다(keyroute·pricing 규칙)."""
    for r in ('@app.post("/api/lens/cn/search")', '@app.post("/api/lens/kw/search")'):
        b = _handler_body(r)
        assert "pricing.OP_LENS" in b, f"{r}: 작업 상수(OP_LENS)를 써야 한다"
        assert re.search(r"keyroute\.SVC_\w+", b), f"{r}: 서비스 상수(SVC_*)를 써야 한다"
