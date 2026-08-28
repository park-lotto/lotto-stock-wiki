# -*- coding: utf-8 -*-
"""고객 상세 시트(2026-08-29) — 시간 정규화·AI 원가 귀속·시트 계산.

★이 테스트가 지키는 것은 '화면이 예쁜가'가 아니라 **숫자가 거짓말을 안 하는가**다.
  - 시간 형식이 4가지라 하나만 잘못 읽어도 하루가 통째로 밀린다.
  - AI 원가는 주인이 안 적히면 0으로 보이는데, 그건 '안 썼다'가 아니다.
  - 결제 금액이 0인데 원가율을 0%로 내면 "공짜로 잘 벌고 있다"는 정반대 결론이 난다.
"""
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shopping_shorts import usage_meter  # noqa: E402
from shopping_shorts.store import Store  # noqa: E402


# ── 시간 정규화 ──────────────────────────────────────────────────────────
def _kst_day(value):
    from shopping_shorts.app import _kst_day as f
    return f(value)


def test_kst_day_reads_every_format():
    """테이블마다 다른 4가지 형식을 전부 같은 KST 날짜 축으로 읽는다."""
    # epoch초(customer_activity.at, payments.paid_at)
    ts = int(datetime(2026, 8, 28, 5, 0, tzinfo=timezone.utc).timestamp())
    assert _kst_day(ts) == "2026-08-28"
    # ISO8601 UTC(mix_jobs.created_at) — 16:12 UTC는 KST로 다음 날이다
    assert _kst_day("2026-08-28T16:12:21.716064+00:00") == "2026-08-29"
    assert _kst_day("2026-08-28T05:00:00+00:00") == "2026-08-28"
    # datetime('now') 공백형(points_ledger.created_at) — tz가 없으니 UTC로 읽어야 한다
    assert _kst_day("2026-08-25 11:45:27") == "2026-08-25"
    # YYYY-MM-DD(usage.day, customer_access.day) — 이미 날짜라 그대로
    assert _kst_day("2026-08-28") == "2026-08-28"


def test_kst_day_returns_none_for_unusable():
    """읽을 수 없는 값은 None — 지어내지 않는다."""
    for bad in (None, "", "trial", "그냥글자"):
        assert _kst_day(bad) is None


def test_naive_timestamp_is_read_as_utc_not_local():
    """★공백형에 타임존이 없다고 로컬시간으로 읽으면 9시간이 밀린다.

    2026-08-28 20:00 UTC는 KST로 이미 다음 날 05:00이다. 로컬(KST)로 잘못 읽으면
    같은 날로 남아 하루가 어긋난다.
    """
    assert _kst_day("2026-08-28 20:00:00") == "2026-08-29"


# ── AI 원가 귀속 ─────────────────────────────────────────────────────────
@pytest.fixture()
def meter_db(tmp_path, monkeypatch):
    db = tmp_path / "reference.db"
    monkeypatch.setattr(usage_meter, "_DB_PATH", db)
    monkeypatch.setattr(usage_meter, "_initialized", False)
    return db


def _rows(db):
    return sqlite3.connect(str(db)).execute(
        "SELECT customer_id, op, krw FROM gemini_usage ORDER BY id").fetchall()


def test_keyctx_owner_is_attributed_without_explicit_track(meter_db):
    """★이 테스트가 이번 작업의 핵심이다.

    라이브 실측(2026-08-29): 28,314건 중 27,079건(96%·86,580원)이 customer_id NULL.
    track(customer_id=)를 넘기는 곳이 mix_pipeline 하나뿐이라, 대본·렌즈·태깅이
    전부 '누가 썼는지 모르는 비용'으로 쌓였다. keyctx는 이미 주인을 알고 있었다.
    """
    from shopping_shorts import keyctx
    with keyctx.owner(57):
        usage_meter.record("gemini-3.1-flash-lite", 1000, 500)
    assert _rows(meter_db)[0][0] == "57"


def test_explicit_customer_id_beats_keyctx(meter_db):
    """워커가 job 주인을 아는 경우가 더 정확하므로 명시값이 이긴다."""
    from shopping_shorts import keyctx
    with keyctx.owner(57):
        with usage_meter.track(op="제작", customer_id=99):
            usage_meter.record("gemini-3.5-flash", 100, 100)
    cid, op, _ = _rows(meter_db)[0]
    assert (cid, op) == ("99", "제작")


def test_customer_id_is_stored_as_text(meter_db):
    """컬럼이 TEXT인데 int를 넣으면 '57'과 57이 서로 안 잡힌다 → 쓸 때 통일한다."""
    with usage_meter.track(customer_id=7):
        usage_meter.record("gemini-3.1-flash-lite", 10, 10)
    assert isinstance(_rows(meter_db)[0][0], str)


def test_owner_zero_is_recorded_not_dropped(meter_db):
    """사장님(0) 몫도 원가다 — 빼면 전체 합이 안 맞는다."""
    from shopping_shorts import keyctx
    with keyctx.owner(0):
        usage_meter.record("gemini-3.1-flash-lite", 10, 10)
    assert _rows(meter_db)[0][0] == "0"


def test_op_falls_back_to_calling_module(meter_db):
    """op를 25개 호출부마다 적으면 반드시 빠뜨린다 → 호출 스택에서 유도한다."""
    src = "def call(rec):\n    rec('gemini-3.1-flash-lite', 10, 10)\n"
    fake = Path(usage_meter.__file__).with_name("script_generate.py")
    ns = {}
    exec(compile(src, str(fake), "exec"), ns)
    ns["call"](usage_meter.record)
    assert _rows(meter_db)[0][1] == "대본생성"


def test_unknown_module_keeps_its_name(meter_db):
    """표에 없는 새 모듈은 '(미지정)'으로 뭉개지 않고 이름을 남긴다."""
    src = "def call(rec):\n    rec('gemini-3.1-flash-lite', 10, 10)\n"
    fake = Path(usage_meter.__file__).with_name("brand_new_thing.py")
    ns = {}
    exec(compile(src, str(fake), "exec"), ns)
    ns["call"](usage_meter.record)
    assert _rows(meter_db)[0][1] == "brand_new_thing"


def test_metering_failure_never_breaks_the_call(meter_db, monkeypatch):
    """계측이 본작업을 죽이면 안 된다 — DB가 막혀도 원화값은 돌아온다."""
    def boom():
        raise RuntimeError("DB 죽음")
    monkeypatch.setattr(usage_meter, "_connect", boom)
    assert usage_meter.record("gemini-3.1-flash-lite", 1000, 1000) > 0


# ── store 조회 ───────────────────────────────────────────────────────────
@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "s.db"))


def test_ai_cost_matches_both_text_and_int_customer_id(store):
    """옛 행은 정수로, 새 행은 문자열로 저장돼 있다 — 한쪽만 보면 반쪽만 잡힌다."""
    with store._conn() as c:
        usage_meter._ensure_schema(c)
        c.executemany(
            "INSERT INTO gemini_usage(ts,day,op,customer_id,model,in_tokens,out_tokens,krw)"
            " VALUES(?,?,?,?,?,?,?,?)",
            [("2026-08-29T00:00:00+00:00", "2026-08-29", "제작", "57", "m", 10, 10, 100.0),
             ("2026-08-29T00:00:00+00:00", "2026-08-29", "대본생성", 57, "m", 10, 10, 50.0)])
    assert store.customer_ai_cost(57)["total"]["krw"] == 150.0


def test_unattributed_cost_is_reported(store):
    """미상 원가를 화면이 밝힐 수 있어야 한다 — 안 보이면 합이 안 맞는 이유를 모른다."""
    with store._conn() as c:
        usage_meter._ensure_schema(c)
        c.executemany(
            "INSERT INTO gemini_usage(ts,day,customer_id,model,in_tokens,out_tokens,krw)"
            " VALUES(?,?,?,?,?,?,?)",
            [("2026-08-01T00:00:00+00:00", "2026-08-01", None, "m", 10, 10, 80.0),
             ("2026-08-01T00:00:00+00:00", "2026-08-01", "", "m", 10, 10, 20.0),
             ("2026-08-01T00:00:00+00:00", "2026-08-01", "57", "m", 10, 10, 5.0)])
    assert store.ai_cost_unattributed() == {"calls": 2, "krw": 100.0}


def test_usage_days_keeps_trial_bucket(store):
    """체험 render는 day가 날짜가 아니라 'trial' 리터럴이다 — 날짜필터에 지워지면 안 된다."""
    store.usage_incr(5, "render", "trial")
    store.usage_incr(5, "lens", "2026-08-28")
    days = store.customer_usage_days(5, since_day="2026-08-01")
    assert {d["day"] for d in days} == {"trial", "2026-08-28"}


def test_usage_days_excludes_global_bucket(store):
    """customer_id=-1은 전역 집계 버킷이라 개인 시트에 섞이면 안 된다."""
    store.usage_incr(-1, "lens", "2026-08-28")
    store.usage_incr(5, "lens", "2026-08-28")
    assert [d["count"] for d in store.customer_usage_days(5)] == [1]


def test_customer_jobs_reports_made_by_video_path(store):
    """'완성'의 진실은 status가 아니라 video_path다 — 접수만 하고 못 만든 건 제외."""
    now = datetime.now(timezone.utc).isoformat()
    with store._conn() as c:
        c.executemany(
            "INSERT INTO mix_jobs(job_id,customer_id,status,created_at,updated_at,"
            "video_path,urls_json,target_seconds,structure) VALUES(?,?,?,?,?,?,?,?,?)",
            [("a", 5, "done", now, now, "/x/a.mp4", '["u1","u2"]', 30, ""),
             ("b", 5, "failed", now, now, "", '["u1"]', 30, "")])
    got = {j["job_id"]: (j["made"], j["sources"]) for j in store.customer_jobs(5)}
    assert got == {"a": (True, 2), "b": (False, 1)}


def test_access_rows_returns_raw_not_just_counts(store):
    """요약(개수)만으론 '언제 어느 IP로' 들어왔는지 알 수 없다."""
    store.record_access(5, "1.1.1.1", "UA-A", "2026-08-28")
    store.record_access(5, "2.2.2.2", "UA-B", "2026-08-28")
    rows = store.customer_access_rows(5)
    assert {r["ip"] for r in rows} == {"1.1.1.1", "2.2.2.2"}


# ── 관리자 목록 성능 최적화가 결과를 바꾸지 않는가 ────────────────────────
# ★일괄 경로를 새로 만들면 낱개 경로와 언젠가 어긋난다(0순위-B). 어긋나면
#   "화면은 pro 200회라는데 게이트는 10회에서 막는" 사고가 그대로 재발한다.
#   그래서 **두 경로의 출력이 같은지** 테스트가 대조한다.
def _make_customers(store):
    """실제 생성 경로로 만든다 — INSERT를 직접 쓰면 NOT NULL 컬럼을 빠뜨린다."""
    ids = {}
    for uname, plan in (("a@x.com", "pro"), ("b@x.com", "free"), ("c@x.com", "trial")):
        cid = store.create_customer(uname, "pw", email=uname, approved=True)
        store.set_plan(cid, plan)
        ids[plan] = cid
    return ids


def test_effective_limits_all_matches_single(store):
    from shopping_shorts.app import _effective_limits, _effective_limits_all
    ids = _make_customers(store)
    store.set_setting("limit_lens_pro", "50")
    store.set_setting("limit_render", "7")
    store.set_setting("limit_script_pro", "")        # 빈칸 → fallback=True 경로도 탄다
    customers = [{"id": cid, "plan": plan} for plan, cid in ids.items()]
    bulk = _effective_limits_all(store, customers)
    for cu in customers:
        assert bulk[cu["id"]] == _effective_limits(store, cu["id"]), \
            f"cid {cu['id']}에서 일괄/낱개 한도가 어긋났다"


def test_access_level_with_passed_cust_matches_db_lookup(store, monkeypatch):
    """cust를 넘긴 경로와 DB를 읽는 경로가 같은 답을 내야 한다."""
    import shopping_shorts.app as A
    ids = _make_customers(store)
    pend = store.create_customer("d@x.com", "pw", email="d@x.com", approved=False)
    monkeypatch.setattr(A, "DB_PATH", store.path if hasattr(store, "path") else A.DB_PATH)
    monkeypatch.setattr(A, "Store", lambda *_a, **_k: store)
    for cid in list(ids.values()) + [pend]:
        cust = store.get_customer(cid)
        assert A.access_level(cid, cust=cust) == A.access_level(cid), f"cid {cid}"


def test_limit_gate_never_uses_the_cache(store, monkeypatch):
    """★막는 쪽은 항상 지금 값을 본다.

    캐시를 게이트에 물렸다가 렌즈 한도 테스트 10건이 깨졌다(2026-08-29). 라이브로
    나갔다면 키를 등록·삭제한 고객이 20초간 **옛 한도**로 막히거나 통과했을 것이다.
    """
    import shopping_shorts.app as A
    A._LENSKEY_CACHE.clear()
    calls = []

    def fake_keys_for(_st, cid, _svc):
        calls.append(cid)
        return (["k"] * len(calls), True)      # 부를 때마다 개수가 늘어난다

    monkeypatch.setattr(A.keyroute, "keys_for", fake_keys_for)
    monkeypatch.setattr(A, "Store", lambda *_a, **_k: store)

    # 기본(캐시 끔) — 부를 때마다 실제 값을 다시 본다
    assert A._lens_key_count(1) == 1
    assert A._lens_key_count(1) == 2, "게이트 경로가 캐시를 썼다 — 옛 한도가 걸린다"

    # 목록 경로(캐시 켬) — 두 번째는 캐시를 쓴다
    n1 = A._lens_key_count(1, cache=True)
    assert A._lens_key_count(1, cache=True) == n1
    A._LENSKEY_CACHE.clear()


def test_tiny_cost_ratio_is_not_rounded_to_zero():
    """★0.0%는 '원가가 안 든다'로 읽힌다 — 실측 cid260은 38.66원/770,000원이었다."""
    from shopping_shorts.app import _ratio_pct
    assert _ratio_pct(38.66, 770000) == 0.005      # 0.0으로 뭉개지면 안 된다
    assert _ratio_pct(323.68, 770000) == 0.04
    assert _ratio_pct(100000, 770000) == 13.0      # 큰 값은 소수 1자리로 충분


def test_points_ledger_rows_are_listed(store):
    """잔액 합계만 있고 내역 목록이 없었다 — 무엇 때문에 깎였는지 봐야 한다."""
    store.points_add(5, 10000, "pro_grant")
    store.points_add(5, -500, "vmake")
    led = store.customer_points_ledger(5)
    assert [(r["delta"], r["reason"]) for r in led] == [(-500, "vmake"), (10000, "pro_grant")]
