"""나머지 작업 과금 + 일일 상한 — 키가 있어도 상한은 걸린다.

두 축이 **따로** 돈다는 것이 이 파일의 요점이다:
  · 일일 상한(check_and_count) = 서버 보호. 사용자 키가 있어도 걸린다.
  · 포인트 차감(_charge_or_402) = 비용 회수. 사용자 키가 있으면 안 걸린다.
"""
import importlib
import re

import pytest

from shopping_shorts import keycrypt, keyroute, points, pricing
from shopping_shorts.store import Store

_KEY = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 유효한 Fernet 키(44자). 테스트 전용


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _KEY)
    importlib.reload(keycrypt)
    return Store(str(tmp_path / "t.db"))


# ── 과금 여부 판단은 keyroute가 정한다(0순위-B) ──────────────────────

def test_lens_charges_when_owner_key(store, monkeypatch):
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    points.add(store, 4, 1000)
    assert keyroute.should_charge(store, 4, keyroute.SVC_GEMINI) is True


def test_script_free_with_user_key(store, monkeypatch):
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    store.add_customer_key(4, keyroute.SVC_GEMINI, "내키")
    assert keyroute.should_charge(store, 4, keyroute.SVC_GEMINI) is False


# ── 일일 상한 기본값 (사장님 지시 2026-08-17) ─────────────────────────

def test_daily_limit_defaults_are_ten(store):
    """★사장님 지시: 본인 키가 있어도 영상제작·렌즈검색은 하루 10회."""
    from shopping_shorts.app import _CREDIT_DEFAULTS, _CREDIT_PRO_DEFAULTS
    assert _CREDIT_DEFAULTS["lens"] == 10
    assert _CREDIT_DEFAULTS["render"] == 10
    assert _CREDIT_PRO_DEFAULTS["lens"] == 10
    assert _CREDIT_PRO_DEFAULTS["render"] == 10


def test_script_limits_unchanged(store):
    """script는 지시 대상이 아니다 — 건드리지 않았음을 못박는다."""
    from shopping_shorts.app import _CREDIT_DEFAULTS, _CREDIT_PRO_DEFAULTS
    assert _CREDIT_DEFAULTS["script"] == 10
    assert _CREDIT_PRO_DEFAULTS["script"] == 200


def test_daily_limit_applies_even_with_user_key(store, monkeypatch, tmp_path):
    """★핵심: 사용자 키를 등록해도 일일 상한은 그대로 걸린다.

    상한은 서버 보호 목적이라 포인트(비용 회수)와 축이 다르다. 사용자 키가
    있으면 상한까지 풀린다고 착각하면 렌더 서버가 통째로 잠긴다."""
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "limit.db"))
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    st = Store(str(tmp_path / "limit.db"))
    st.add_customer_key(7, keyroute.SVC_GEMINI, "내키")
    # 무료 등급 render 상한 = 10회
    allowed = sum(1 for _ in range(12) if app_mod.check_and_count(7, "render"))
    assert allowed == 10, "사용자 키가 있어도 render 하루 10회에서 막혀야 한다"


# ── _charge_or_402 — 세 갈래 ────────────────────────────────────────

@pytest.fixture
def charge(tmp_path, monkeypatch):
    """_charge_or_402를 격리 DB로 부를 수 있게 묶어 준다."""
    from shopping_shorts import app as app_mod
    db = str(tmp_path / "charge.db")
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    return app_mod._charge_or_402, Store(db)


def test_charge_returns_none_when_balance_enough(charge):
    _charge_or_402, st = charge
    points.add(st, 4, 1000)
    assert _charge_or_402(4, pricing.OP_LENS, keyroute.SVC_GEMINI) is None


def test_charge_actually_deducts(charge):
    """★차감이 실제로 일어나는지 — 잔액 변화를 직접 본다."""
    _charge_or_402, st = charge
    points.add(st, 4, 1000)
    before = points.balance(st, 4)
    assert _charge_or_402(4, pricing.OP_MIX, keyroute.SVC_GEMINI) is None
    after = points.balance(st, 4)
    assert before - after == pricing.cost(st, pricing.OP_MIX)
    assert after == 1000 - pricing.cost(st, pricing.OP_MIX)


def test_charge_deducts_each_call(charge):
    """두 번 부르면 두 번 깎인다 — 한 번만 깎고 마는 캐시 함정 방지."""
    _charge_or_402, st = charge
    points.add(st, 4, 1000)
    unit = pricing.cost(st, pricing.OP_MIX)
    for n in (1, 2, 3):
        assert _charge_or_402(4, pricing.OP_MIX, keyroute.SVC_GEMINI) is None
        assert points.balance(st, 4) == 1000 - unit * n


def test_charge_402_when_insufficient(charge):
    """잔액이 모자라면 402 + 아무것도 안 깎는다."""
    from starlette.responses import JSONResponse
    _charge_or_402, st = charge
    points.add(st, 4, 5)                       # OP_MIX(300)보다 적다
    resp = _charge_or_402(4, pricing.OP_MIX, keyroute.SVC_GEMINI)
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 402
    assert points.balance(st, 4) == 5, "실패했는데 잔액이 줄면 안 된다"


def test_402_body_has_need_and_have(charge):
    """402 body에 필요·보유 포인트가 화면 단위로 들어간다."""
    _charge_or_402, st = charge
    points.add(st, 4, 5)
    body = _charge_or_402(4, pricing.OP_MIX, keyroute.SVC_GEMINI).body.decode()
    assert '"ok":false' in body.replace(" ", "")
    need = pricing.to_display(pricing.cost(st, pricing.OP_MIX))
    assert f"필요 {need}P" in body
    assert f"보유 {pricing.to_display(5)}P" in body


def test_charge_free_with_user_key(charge):
    """★사용자 키가 있으면 None이고 잔액도 그대로다(잔액 0이어도 통과)."""
    _charge_or_402, st = charge
    st.add_customer_key(4, keyroute.SVC_GEMINI, "내키")
    assert points.balance(st, 4) == 0
    assert _charge_or_402(4, pricing.OP_LENS, keyroute.SVC_GEMINI) is None
    assert points.balance(st, 4) == 0, "내 키를 쓰는데 포인트가 깎이면 안 된다"


def test_charge_owner_cid_zero_not_charged(charge):
    """cid 0 = 사장님 본인. keyroute가 개인키 조회를 건너뛰고 사장님 키를 준다.

    ★_charge_clean(mix_pipeline)은 cid 0을 아예 과금 대상에서 뺀다 — 자기 키로
      자기한테 청구하는 꼴이기 때문. 여기도 같은 결과여야 한다."""
    _charge_or_402, st = charge
    assert points.balance(st, 0) == 0
    assert _charge_or_402(0, pricing.OP_MIX, keyroute.SVC_GEMINI) is None
    assert points.balance(st, 0) == 0


def test_charge_cid_string_normalized(charge):
    """cid가 문자열 "4"로 와도 같은 사람이다(2026-07-30 실사고 계열)."""
    _charge_or_402, st = charge
    st.add_customer_key(4, keyroute.SVC_GEMINI, "내키")
    assert _charge_or_402("4", pricing.OP_LENS, keyroute.SVC_GEMINI) is None
    assert points.balance(st, 4) == 0


def test_charge_uses_admin_price_setting(charge):
    """단가는 admin 설정을 따른다 — pricing.cost를 우회해 하드코딩하지 않았음."""
    _charge_or_402, st = charge
    st.set_setting("point_cost_lens", "250")
    points.add(st, 4, 1000)
    assert _charge_or_402(4, pricing.OP_LENS, keyroute.SVC_GEMINI) is None
    assert points.balance(st, 4) == 750


# ── 환불 — 실패한 작업은 포인트를 돌려준다 ──────────────────────────

@pytest.fixture
def refund(tmp_path, monkeypatch):
    from shopping_shorts import app as app_mod
    db = str(tmp_path / "refund.db")
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    monkeypatch.setattr(keyroute, "_owner_keys", lambda svc: ["사장님키"])
    return app_mod._charge_or_402, app_mod._refund_points, Store(db)


def test_refund_restores_points(refund):
    """★깎았다가 실패하면 원래 잔액으로 돌아온다 — 크레딧 환불과 대칭."""
    _charge, _refund_points, st = refund
    points.add(st, 4, 1000)
    assert _charge(4, pricing.OP_SCRIPT, keyroute.SVC_GEMINI) is None
    assert points.balance(st, 4) < 1000
    _refund_points(4, pricing.OP_SCRIPT, keyroute.SVC_GEMINI)
    assert points.balance(st, 4) == 1000


def test_refund_noop_for_user_key(refund):
    """★안 깎은 사람에게 돈이 생기면 안 된다 — 사용자 키는 환불도 없다."""
    _charge, _refund_points, st = refund
    st.add_customer_key(4, keyroute.SVC_GEMINI, "내키")
    assert _charge(4, pricing.OP_LENS, keyroute.SVC_GEMINI) is None
    _refund_points(4, pricing.OP_LENS, keyroute.SVC_GEMINI)
    assert points.balance(st, 4) == 0


def test_refund_noop_for_owner(refund):
    """cid 0(사장님)은 안 깎았으니 환불도 없다."""
    _charge, _refund_points, st = refund
    _refund_points(0, pricing.OP_MIX, keyroute.SVC_GEMINI)
    assert points.balance(st, 0) == 0


def test_refund_survives_db_error(refund, monkeypatch):
    """finally에서 불리므로 자체 예외를 삼켜야 한다 — 원래 응답을 가리면 안 된다."""
    _charge, _refund_points, st = refund
    monkeypatch.setattr(points, "refund",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("DB 락")))
    points.add(st, 4, 1000)
    _refund_points(4, pricing.OP_SCRIPT, keyroute.SVC_GEMINI)   # 안 터져야 한다


def test_refund_wired_wherever_credit_refunded():
    """★크레딧을 돌려주는 곳은 포인트도 돌려줘야 한다 — 한쪽만 있으면 잔액이 갉힌다."""
    src = _app_src()
    assert src.count("refund_credit(cid,") == src.count("_refund_points(cid,"), (
        "refund_credit 지점 수와 _refund_points 지점 수가 다르다")


# ── 배선 — 8곳이 실제로 코드에 박혔는가 ──────────────────────────────

def _app_src():
    from pathlib import Path
    from shopping_shorts import app as app_mod
    return Path(app_mod.__file__).read_text(encoding="utf-8")


def test_all_eight_sites_wired():
    """★check_and_count 지점마다 과금이 붙었는지 — 하나라도 빠지면 공짜 구멍."""
    src = _app_src()
    calls = [m for m in re.finditer(r"check_and_count\(", src)]
    # 정의 1개 + 호출 8개
    assert len(calls) == 9, f"check_and_count 등장 횟수가 9가 아니다: {len(calls)}"
    assert src.count("_charge_or_402(") == 9, (
        "_charge_or_402 정의 1 + 호출 8 = 9가 아니다: " f"{src.count('_charge_or_402(')}")


def test_wiring_uses_constants_not_literals():
    """★상수를 써야 한다 — 문자열 오타는 조용히 무료가 된다."""
    src = _app_src()
    for lit in ('_charge_or_402(cid, "', "_charge_or_402(cid, '"):
        assert lit not in src, f"과금 호출에 문자열 리터럴이 들어갔다: {lit}"
    assert src.count("pricing.OP_") >= 8
    assert src.count("keyroute.SVC_GEMINI") >= 8


def test_autoload_failed_points_status_is_terminal():
    """autoload는 항목 루프라 402를 return하면 안 된다 — 그 항목만 접는다.

    ★status를 failed_로 시작하게 지은 이유: 프론트가 /^failed_/로 실패를 모으고
      (produce.html:4022), skipped_cap일 때만 다음 배치를 부른다(:4035). 다른 이름을
      쓰면 실패 목록에서 빠지거나 무한 재시도가 된다."""
    src = _app_src()
    body = src[src.index("def api_produce_autoload"):]
    body = body[:body.index("\n@app.")]              # 이 라우트 함수 안만 본다
    assert '"status": "failed_points"' in body
    # ★402를 그대로 return하면 남은 항목까지 죽는다 — 루프 안에선 continue여야 한다.
    assert "return _denied" not in body
    assert "_charge_or_402(cid, pricing.OP_SCRIPT" in body


def test_prewarm_not_charged():
    """★예열은 사장님 배치다 — 사용자에게 과금하면 안 된다."""
    from pathlib import Path
    from shopping_shorts import prewarm
    assert "_charge_or_402" not in Path(prewarm.__file__).read_text(encoding="utf-8")
