# -*- coding: utf-8 -*-
"""api_health(API 관측판 데이터층) — 분류·기록·집계·배선이 실제로 닿는지.

★배선 테스트는 '함수가 있다'가 아니라 **이벤트 행이 실제로 박히는지**를 본다
  (판정만 맞고 실전 0건이던 vmake 전례 — memory: 마크업테스트_문자열검색_무용지물)."""

import json
import os
import sqlite3

import pytest

from shopping_shorts import api_health


# ── 분류 — 실제 사고 원문으로 검증한다 (지어낸 문구 금지) ──────────────────

# 2026-08-31 편집안RPM대기 실사고 원문
_RPM_MSG = ("429 RESOURCE_EXHAUSTED. Quota exceeded for quota metric "
            "'Generate Content API requests per minute' ... Please retry in 22.5s")
# 2026-08-09 태거 실측 원문(분당 한도)
_RPM_MSG2 = "429 RESOURCE_EXHAUSTED ... limit: 5, model: gemini-3.5-flash / Please retry in 45.5s"
# 일일 소진(PerDay)
_RPD_MSG = ("429 RESOURCE_EXHAUSTED. Quota exceeded for quota metric ... "
            "GenerateRequestsPerDayPerProjectPerModel, limit: 500")
# 2026-08-31 죽은 키 원문
_AUTH_MSG = "401 UNAUTHENTICATED. The bound service account is deleted or disabled."
# 2026-08-10 무더기 비활성화 원문
_AUTH_MSG2 = "403 PERMISSION_DENIED ..."


@pytest.mark.parametrize("msg,http,want", [
    (_RPM_MSG, None, api_health.OUT_RPM),
    (_RPM_MSG2, None, api_health.OUT_RPM),
    (_RPD_MSG, None, api_health.OUT_RPD),
    (_AUTH_MSG, None, api_health.OUT_AUTH),
    (_AUTH_MSG2, None, api_health.OUT_AUTH),
    ("503 UNAVAILABLE: The model is overloaded", None, api_health.OUT_SERVER),
    ("HTTPSConnectionPool ... Read timed out", None, api_health.OUT_TIMEOUT),
    ("RemoteDisconnected('Remote end closed')", None, api_health.OUT_NETWORK),
    ("이상한 미지의 오류", None, api_health.OUT_ERROR),
    ("Too Many Requests", 429, api_health.OUT_QUOTA),
    ("Your account has run out of searches.", None, api_health.OUT_RPD),  # serpapi 월간 소진
    ("Unauthorized", 401, api_health.OUT_AUTH),
])
def test_classify(msg, http, want):
    assert api_health.classify(msg, http=http) == want


def test_classify_priority_auth_over_quota():
    """계정사망 문구에 429가 섞여도 사망이 이긴다 — 영구 제외 대상이 분당 대기로 오분류되면
    죽은 키를 계속 때린다(2026-08-10 사고의 재발 모양)."""
    assert api_health.classify(
        "429 ... UNAUTHENTICATED service account is deleted or disabled") == api_health.OUT_AUTH


# ── 기록·집계 라운드트립 ───────────────────────────────────────────────────

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    p = tmp_path / "api_health_test.db"     # 이름이 reference.db가 아니라 pytest 가드를 안 탄다
    api_health.set_db_path(p)
    yield p
    api_health.set_db_path(
        os.path.join(os.path.dirname(api_health.__file__), "data", "reference.db"))


def test_record_and_aggregate_roundtrip(tmp_db):
    api_health.record("gemini", api_health.OUT_OK, pool="shorts",
                      key="A" * 20 + "TAIL01", op="태깅", model="gemini-3.1-flash-lite")
    api_health.record("gemini", api_health.OUT_RPM, pool="shorts",
                      key="A" * 20 + "TAIL01", op="태깅", detail=_RPM_MSG)
    api_health.record("elevenlabs", api_health.OUT_SILENT, customer_id=57)

    agg = api_health.aggregates(hours=1)
    by = {(r["service"], r["outcome"]): r["n"] for r in agg["by_service"]}
    assert by[("gemini", "ok")] == 1
    assert by[("gemini", "rpm")] == 1
    assert by[("elevenlabs", "silent_fallback")] == 1
    # 사고 피드에 성공은 없고 실패만 온다 + 원문이 실려 있다(뭉갠 문구 금지의 근거)
    feeds = agg["recent_fails"]
    assert all(f["outcome"] != "ok" for f in feeds)
    assert any("per minute" in (f["detail"] or "") for f in feeds)


def test_key_is_masked_in_db(tmp_db):
    """★키 원문은 DB 어디에도 저장되면 안 된다 — 끝 6자만."""
    secret = "AIzaSyFAKEFAKEFAKEFAKE-SECRET9"
    api_health.record("gemini", api_health.OUT_OK, key=secret)
    conn = sqlite3.connect(tmp_db)
    rows = conn.execute("SELECT key_tail FROM api_events").fetchall()
    blob = json.dumps(conn.execute("SELECT * FROM api_events").fetchall(),
                      ensure_ascii=False, default=str)
    conn.close()
    assert rows[0][0] == secret[-6:]
    assert secret not in blob


def test_record_skips_live_db_under_pytest(tmp_path):
    """pytest 중엔 라이브 reference.db에 안 쓴다(ops_alert 2026-08-14 오염사고와 같은 가드)."""
    live_like = tmp_path / "reference.db"
    api_health.set_db_path(live_like)
    try:
        api_health.record("gemini", api_health.OUT_OK)
        assert not live_like.exists() or sqlite3.connect(live_like).execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='api_events'").fetchone()[0] == 0
    finally:
        api_health.set_db_path(
            os.path.join(os.path.dirname(api_health.__file__), "data", "reference.db"))


def test_heartbeat_upserts_one_row_per_process(tmp_db):
    api_health.heartbeat({"gemini": {"owner": 1, "member": 58}}, proc="worker")
    api_health.heartbeat({"gemini": {"owner": 1, "member": 59}}, proc="worker")
    agg = api_health.aggregates()
    hbs = [h for h in agg["heartbeats"] if h["proc"] == "worker"]
    assert len(hbs) == 1                       # 같은 (proc,pid)는 덮어쓴다
    assert "59" in (hbs[0]["detail"] or "")


# ── 판정 ──────────────────────────────────────────────────────────────────

def test_verdict_silent_fallback_is_danger(tmp_db):
    """무음 폴백은 1건이라도 danger — 고객이 무음 영상을 받은 것이다."""
    api_health.record("elevenlabs", api_health.OUT_SILENT)
    v = api_health.verdict(snap={"gemini": [], "others": [], "collectors": []},
                           agg=api_health.aggregates(hours=1))
    assert v["level"] == "danger"
    assert any("무음" in p for p in v["problems"])


def test_verdict_ok_when_quiet(tmp_db):
    v = api_health.verdict(snap={"gemini": [], "others": [], "collectors": []},
                           agg=api_health.aggregates(hours=1))
    assert v["level"] == "ok"


def test_verdict_auth_dead_is_danger(tmp_db):
    api_health.record("gemini", api_health.OUT_AUTH, detail=_AUTH_MSG)
    v = api_health.verdict(snap={"gemini": [], "others": [], "collectors": []},
                           agg=api_health.aggregates(hours=1))
    assert v["level"] == "danger"


def test_verdict_counts_dead_keys_not_calls(tmp_db):
    """★죽은 키 1개를 12번 때린 것을 "12개 사망"으로 읽으면 안 된다(2026-09-01 사장님 지적).

    실사고: crawling_bot이 옛 키 목록을 메모리에 들고 34분간 12번 401을 맞았는데
    피드가 12줄로 펼쳐져 무더기 사망으로 보였다. 판정 단위는 **키 개수**다."""
    for _ in range(12):
        api_health.record("gemini", api_health.OUT_AUTH, pool="vault",
                          key="X" * 20 + "VRgKpw", detail=_AUTH_MSG)
    agg = api_health.aggregates(hours=1)
    assert len(agg["dead_keys"]) == 1                  # 키는 하나
    assert agg["dead_keys"][0]["hits"] == 12           # 헛호출은 12번
    v = api_health.verdict(snap={"gemini": [], "others": [], "collectors": []}, agg=agg)
    msg = " ".join(v["problems"])
    assert "죽은 키 1개" in msg and "12번" in msg      # 개수와 횟수를 갈라서 말한다


# ── 배선 — MeteredClient 실패가 api_events에 실제로 닿는가 ─────────────────

class _BoomModels:
    def generate_content(self, *a, **kw):
        raise RuntimeError(_RPM_MSG)


class _OkModels:
    def generate_content(self, *a, **kw):
        class R:                                # usage_metadata 없는 성공 응답
            text = "{}"
        return R()


class _FakeClient:
    def __init__(self, models):
        self.models = models


def test_metered_client_failure_reaches_api_events(tmp_db, monkeypatch):
    monkeypatch.setenv("USAGE_METER", "1")
    from shopping_shorts import usage_meter
    cl = usage_meter.wrap(_FakeClient(_BoomModels()), pool="shorts", key="K" * 30)
    with pytest.raises(RuntimeError):
        cl.models.generate_content(model="gemini-3.1-flash-lite", contents="hi")
    agg = api_health.aggregates(hours=1)
    by = {(r["service"], r["outcome"]): r["n"] for r in agg["by_service"]}
    assert by.get(("gemini", "rpm")) == 1      # ★예외가 분류돼 기록되고
    conn = sqlite3.connect(tmp_db)
    pool, tail, dur = conn.execute(
        "SELECT pool, key_tail, dur_ms FROM api_events").fetchone()
    conn.close()
    assert pool == "shorts" and tail == "K" * 6      # ★풀·키 귀속이 실려 있다
    assert dur is not None


def test_metered_client_success_recorded(tmp_db, monkeypatch):
    monkeypatch.setenv("USAGE_METER", "1")
    from shopping_shorts import usage_meter
    cl = usage_meter.wrap(_FakeClient(_OkModels()), pool="vault", key="V" * 30)
    cl.models.generate_content(model="gemini-3.5-flash", contents="hi")
    agg = api_health.aggregates(hours=1)
    by = {(r["service"], r["outcome"]): r["n"] for r in agg["by_service"]}
    assert by.get(("gemini", "ok")) == 1


def test_comment_gen_lock_event_wired(tmp_db, monkeypatch):
    """_mark_key_exhausted가 잠금 이벤트를 남기는가 — 상태파일은 임시로 돌린다."""
    from shopping_shorts import comment_gen
    monkeypatch.setattr(comment_gen, "_STATE_PATH",
                        tmp_db.parent / "state_test.json")
    comment_gen._mark_key_exhausted(3, retry_after=120)
    agg = api_health.aggregates(hours=1)
    locks = [r for r in agg["by_service"]
             if r["service"] == "gemini" and r["outcome"] == "lock"]
    assert locks and locks[0]["n"] == 1
    conn = sqlite3.connect(tmp_db)
    idx, detail = conn.execute(
        "SELECT key_idx, detail FROM api_events WHERE outcome='lock'").fetchone()
    conn.close()
    assert idx == 3 and "ttl=120" in detail


def test_tts_silent_event_wired(tmp_db):
    from shopping_shorts import tts
    tts._record_tts_event("elevenlabs", None, silent=True, customer_id=7)
    agg = api_health.aggregates(hours=1)
    by = {(r["service"], r["outcome"]): r["n"] for r in agg["by_service"]}
    assert by.get(("elevenlabs", "silent_fallback")) == 1


# ── 예산 ──────────────────────────────────────────────────────────────────

def test_budget_counts_requests_in_pt_window(tmp_db):
    for _ in range(10):
        api_health.record("gemini", api_health.OUT_OK, pool="shorts", key="B" * 20)
    snap = {"gemini": [{"pool": "shorts", "total": 2, "owner": 1, "member": 1,
                        "live": 2, "locked": [], "keys": [
                            {"idx": 0, "tail": "TAIL_A", "owner": "owner", "state": "live"},
                            {"idx": 1, "tail": "TAIL_B", "owner": "member", "state": "live"}]}]}
    b = api_health.budget(snap=snap, agg=api_health.aggregates())
    assert b["keys"] == 2                      # 키 수는 tail 전역 dedup(리뷰 수리 후 방식)
    assert b["cap"] == 2 * api_health.RPD_PER_KEY
    assert b["used"] == 10
    assert b["used_pct"] == pytest.approx(100 * 10 / (2 * api_health.RPD_PER_KEY), abs=0.11)


# ── 기존 관측 버그의 재발 방지 ─────────────────────────────────────────────

def test_live_exhausted_returns_int_keys_for_admin_api(tmp_path, monkeypatch):
    """/api/refs/api_usage가 소진 수를 셀 때 쓰는 _live_exhausted가 dict 상태(08-27 포맷)
    에서 int 키를 돌려주는지 — 옛 코드는 str 키를 int와 비교하다 TypeError로 죽어
    exhausted_today가 항상 0으로 보였다(2026-09-01 수리의 회귀 가드)."""
    import time as _t
    from shopping_shorts import comment_gen
    sp = tmp_path / "state.json"
    sp.write_text(json.dumps({
        "date": comment_gen._today_str(),
        "exhausted": {"2": _t.time() + 999, "5": _t.time() - 10},   # 5번은 만료됨
        "revived_once": []}), encoding="utf-8")
    monkeypatch.setattr(comment_gen, "_STATE_PATH", sp)
    live = comment_gen._live_exhausted()
    assert set(live.keys()) == {2}             # int 키 + 만료 자동 해제
    # 수리된 app.py 코드 모양 그대로 — int 비교가 죽지 않아야 한다
    assert len([i for i in live if i < 10]) == 1


# ── 엔드포인트 — 실제로 호출되는 테스트 1개 (memory: 모듈import 런타임NameError) ──

class _FakeReq:
    class _S:
        customer_id = 0                        # cid 0 = 사장님(관리자)
    state = _S()
    headers = {}
    cookies = {}


def test_apiwatch_endpoint_executes_end_to_end(tmp_db):
    """라우트 함수가 스냅샷→집계→판정→예산→계약까지 실제로 돈다 — NameError류를 여기서 잡는다."""
    from shopping_shorts import app as appmod
    out = appmod._api_apiwatch(_FakeReq(), hours=24)
    assert out.get("ok") is True, out
    assert "snapshot" in out and "verdict" in out and "budget" in out
    c = out["contract"]
    assert "gemini" in (c.get("pooled") or [])
    assert isinstance(c.get("rpm_per_key"), int)


def test_apiwatch_endpoint_denies_non_admin(tmp_db):
    from shopping_shorts import app as appmod

    class R(_FakeReq):
        class _S:
            customer_id = 777                  # 일반 회원
        state = _S()
    out = appmod._api_apiwatch(R(), hours=24)
    assert not isinstance(out, dict) or out.get("ok") is not True


# ── 2026-09-01 적대 리뷰 확정 결함의 회귀 가드 ─────────────────────────────

def test_budget_excludes_lock_events(tmp_db):
    """잠금(lock) 이벤트는 실제 요청이 아니다 — used에 세면 429 1건이 2건으로 부푼다."""
    api_health.record("gemini", api_health.OUT_RPD, pool="shorts", key="C" * 20)
    api_health.record("gemini", api_health.OUT_LOCK, pool="shorts", key="C" * 20,
                      key_idx=0, detail="ttl=1800s")
    snap = {"gemini": [{"pool": "shorts", "total": 1, "owner": 1, "member": 0,
                        "live": 1, "locked": [], "keys": [{"idx": 0, "tail": "C" * 6,
                        "owner": "owner", "state": "live"}]}]}
    b = api_health.budget(snap=snap, agg=api_health.aggregates())
    assert b["used"] == 1                      # rpd 1건만 — lock은 요청이 아니다


def test_budget_dedups_member_keys_across_pools(tmp_db):
    """회원 키는 SHORTS·vault 양쪽에 합류한다 — cap이 두 번 세면 소진 임박이 '여유'로 보인다."""
    shared = {"idx": 0, "tail": "SAME99", "owner": "member", "state": "live"}
    snap = {"gemini": [
        {"pool": "shorts", "total": 1, "owner": 0, "member": 1, "live": 1,
         "locked": [], "keys": [dict(shared)]},
        {"pool": "vault", "groups": {"general": {"total": 1, "live": 1,
         "keys": [dict(shared)]}}},
    ]}
    b = api_health.budget(snap=snap, agg=api_health.aggregates())
    assert b["keys"] == 1                      # 같은 물리 키는 한 번만
    assert b["cap"] == api_health.RPD_PER_KEY


def test_verdict_respects_kill_switch(tmp_db, monkeypatch):
    """API_HEALTH=0이면 판정도 쉰다 — 기록을 껐는데 묵은 이벤트로 경보하면 안 된다."""
    api_health.record("elevenlabs", api_health.OUT_SILENT)   # danger급 이벤트를 심고
    monkeypatch.setenv("API_HEALTH", "0")
    v = api_health.verdict()
    assert v["level"] == "ok" and "꺼져" in v["msg"]


# ── 2026-09-01: 경보 정확성 (사장님 지적 2건) ──────────────────────────

def test_rpm_alone_is_not_danger(tmp_db):
    """★분당 한도는 기다리면 풀린다 — 사고가 아니다.

    실측(09-01 06:40 서버): 아침 크론 시간대에 rpm 66 / ok 56이 나와
    "실패율 56% danger" 경보가 떴는데, 실제로는 56건이 정상 처리되고 있었다.
    매일 아침 울리는 경보는 진짜 사고를 가린다."""
    for _ in range(66):
        api_health.record("gemini", api_health.OUT_RPM, pool="shorts", key="A" * 20)
    for _ in range(56):
        api_health.record("gemini", api_health.OUT_OK, pool="shorts", key="A" * 20)
    v = api_health.verdict(snap={"gemini": [], "others": [], "collectors": []},
                           agg=api_health.aggregates(hours=1))
    assert v["level"] != "danger"                    # ★핵심
    assert any("분산" in w for w in v["warns"])       # 처방까지 말해준다


def test_rpd_still_raises_danger(tmp_db):
    """일일 소진은 오늘 안 풀린다 — 이건 여전히 사고다(rpm과 처방이 다르다)."""
    for _ in range(30):
        api_health.record("gemini", api_health.OUT_RPD, pool="shorts", key="B" * 20)
    v = api_health.verdict(snap={"gemini": [], "others": [], "collectors": []},
                           agg=api_health.aggregates(hours=1))
    assert v["level"] == "danger"


def test_verdict_carries_time(tmp_db):
    """★언제 기준인지 없으면 이미 고친 일을 지금 사고로 읽는다
    (09-01: 04:11에 뺀 키를 04:08 경보로 다시 쫓았다)."""
    v = api_health.verdict(snap={"gemini": [], "others": [], "collectors": []},
                           agg=api_health.aggregates(hours=1))
    assert v.get("checked_at")                        # 판정 시각
    assert v.get("window")                            # 어느 창을 봤나


def test_dead_key_problem_includes_last_seen(tmp_db):
    """죽은 키 문구에 '마지막 언제'가 붙어야 끝난 일인지 알 수 있다."""
    api_health.record("gemini", api_health.OUT_AUTH, pool="vault", key="C" * 20)
    v = api_health.verdict(snap={"gemini": [], "others": [], "collectors": []},
                           agg=api_health.aggregates(hours=1))
    msg = " ".join(v["problems"])
    assert "마지막" in msg and ("방금" in msg or "분 전" in msg or "시간" in msg)
