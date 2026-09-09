# -*- coding: utf-8 -*-
"""vault 키 분산 — 키가 많아도 1개만 때리던 것을 막는다(2026-09-01).

## 왜 생겼나 (실측)

최근 6시간 api_events 실측:
    쇼핑쇼츠 web    68개 키로 360콜 → 분당한도(rpm)   0건
    쇼핑쇼츠 worker 39개 키로 202콜 → rpm   1건
    주식위키 server 13개 키로 983콜 → rpm 398건   ← 최다
    report_ingest    1개 키로  64콜 → rpm  64건   (전부 실패)
    post_ingest      1개 키로  38콜 → rpm  37건

같은 회사·같은 시각·같은 구글 한도인데 결과가 정반대였다. 차이는 **나눠 쓰느냐**뿐.
원인은 get_client()가 늘 live[0]을 주던 것 — _active_idx는 rotate()가 항상 0으로
되돌리므로 사실상 고정이고, 429를 맞아야 넘어가는 반응형이라 이미 늦었다.

사장님 질문 "분당한도 걸리는 게 많은데 이건 분배 개선하면 좋아지는 건 아닌가" →
맞다. 키를 더 사는 게 아니라 있는 키를 나눠 쓰는 게 처방이다.
"""
import time

from pipeline.atoms import key_vault as kv


def test_keys_are_spread_evenly(monkeypatch):
    """★100번 호출하면 20개 키에 고루 나뉘어야 한다. 전엔 1개가 100번 다 맞았다."""
    monkeypatch.setattr(kv, "_MIN_GAP_S", 0.0)      # 분포만 본다(대기 제외)
    monkeypatch.setattr(kv, "_KEY_LAST_USED", {})
    monkeypatch.setattr(kv, "_RR_CURSOR", {"i": 0})
    live = [f"KEY{i:02d}" for i in range(20)]
    picks = [kv._pick_key(live) for _ in range(100)]
    used = set(picks)
    assert len(used) == 20, f"키 {len(used)}개만 쓰임 — 분산이 죽었다"
    counts = {k: picks.count(k) for k in used}
    assert max(counts.values()) - min(counts.values()) <= 1   # 균등


def test_pacer_keeps_minimum_gap(monkeypatch):
    """★키가 하나뿐이면 간격을 지켜 **429를 애초에 안 맞는다**.
    이게 없으면 키 1개짜리 크론(report_ingest)이 그대로 전멸한다."""
    monkeypatch.setattr(kv, "_MIN_GAP_S", 0.3)
    monkeypatch.setattr(kv, "_KEY_LAST_USED", {})
    monkeypatch.setattr(kv, "_RR_CURSOR", {"i": 0})
    t0 = time.monotonic()
    for _ in range(3):
        kv._pick_key(["ONLY"])
    assert time.monotonic() - t0 >= 0.55            # 0.3초 × 2회 대기


def test_empty_live_returns_empty(monkeypatch):
    """살아있는 키가 없으면 빈 문자열 — 여기서 예외를 던지면 호출부가 죽는다."""
    monkeypatch.setattr(kv, "_MIN_GAP_S", 0.0)
    assert kv._pick_key([]) == ""


def test_single_key_still_works(monkeypatch):
    """키가 1개뿐이어도 정상적으로 그 키를 준다(분산의 부작용이 없어야 한다)."""
    monkeypatch.setattr(kv, "_MIN_GAP_S", 0.0)
    monkeypatch.setattr(kv, "_KEY_LAST_USED", {})
    assert kv._pick_key(["SOLO"]) == "SOLO"


# ── 목록 회전(rotated) — for문 호출부용 (2026-09-01) ────────────────────

def test_rotated_starts_at_different_key(monkeypatch):
    """★목록의 시작점이 호출마다 넘어가야 한다.

    이게 죽으면 `for key in keys`를 도는 호출부(script_generate·seo_generate·
    thumb_title·pattern_bank·edit_plan)가 전부 keys[0]만 두들기던 2026-08-31
    사고가 그대로 재발한다. 실측: 키 82개 중 최근 5분에 쓰인 건 21개뿐이었다."""
    monkeypatch.setattr(kv, "_RR_CURSOR", {"i": 0})
    live = [f"KEY{i:02d}" for i in range(5)]
    firsts = [kv.rotated(live)[0] for _ in range(5)]
    assert len(set(firsts)) == 5, f"시작 키가 {len(set(firsts))}종뿐 — 회전이 죽었다"


def test_rotated_preserves_all_keys(monkeypatch):
    """순서만 돌리고 원소는 그대로 — 키가 사라지면 후보가 줄어 오히려 악화된다."""
    monkeypatch.setattr(kv, "_RR_CURSOR", {"i": 3})
    live = [f"KEY{i:02d}" for i in range(5)]
    assert sorted(kv.rotated(live)) == sorted(live)
    assert len(kv.rotated(live)) == 5


def test_rotated_is_safe_for_tiny_pools():
    """키 0·1개면 돌릴 게 없다 — 단일키 크론(report_ingest)이 여기서 깨지면 안 된다."""
    assert kv.rotated([]) == []
    assert kv.rotated(["SOLO"]) == ["SOLO"]


def test_cursor_is_seeded_per_process():
    """★워커 12개는 독립 프로세스다 — 커서가 0에서 다 같이 출발하면 전원이 live[0]을 친다.
    PID로 씨딩해 프로세스마다 다른 지점에서 시작한다."""
    import os
    assert kv._RR_CURSOR["i"] != 0 or os.getpid() == 0   # PID가 0인 프로세스는 없다


# ── 소진 낙인 TTL (2026-09-01) ─────────────────────────────────────────

def _tmp_state(tmp_path, payload):
    """상태파일을 임시로 갈아끼운다(라이브 파일을 절대 안 건드린다)."""
    import json
    p = tmp_path / "state.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_old_list_format_gets_ttl(tmp_path, monkeypatch):
    """★배포 즉시 풀려야 한다 — 서버 파일은 옛 형식(list)이다.

    실측(2026-09-01 14:04): 하루 낙인으로 11개가 잠겨 있었는데 구글에 직접 찔러보니
    **8개가 HTTP 200**이었다. 옛 항목에 만료를 안 붙이면 배포해도 그날은 그대로다
    (comment_gen이 2026-08-27에 밟은 함정)."""
    import time
    monkeypatch.setattr(kv, "_STATE_PATH", _tmp_state(tmp_path, {
        "date": "2026-09-01", "exhausted": {"general": [0, 1, 2]}}))
    monkeypatch.setattr(kv, "get_keys", lambda g: [f"K{i}" for i in range(10)])
    locked = kv._live_exhausted("general")
    assert len(locked) == 3
    left = min(locked.values()) - time.time()
    assert 0 < left <= kv._EXHAUST_TTL_S + 5      # 만료시각이 붙었다(영구 낙인 아님)


def test_expired_lock_auto_releases(tmp_path, monkeypatch):
    """만료된 잠금은 조회 시점에 저절로 풀린다 — 이게 '하루 낙인'과의 차이다."""
    import time
    monkeypatch.setattr(kv, "_STATE_PATH", _tmp_state(tmp_path, {
        "date": "x", "exhausted": {"general": {"0": time.time() - 10,
                                               "1": time.time() + 999}}}))
    monkeypatch.setattr(kv, "get_keys", lambda g: [f"K{i}" for i in range(5)])
    assert set(kv._live_exhausted("general")) == {1}      # 만료된 0은 빠진다
    assert "K0" in kv.get_live_keys("general")            # 다시 쓸 수 있다


def test_state_survives_date_change(tmp_path, monkeypatch):
    """★날짜가 달라도 상태를 버리지 않는다 — 만료 판단은 TTL이 한다.
    종전엔 date가 다르면 통째로 버려 '한국 자정에만 해제'가 됐는데, 구글은
    태평양시(한국 오후 4~5시)에 리셋한다."""
    import time
    monkeypatch.setattr(kv, "_STATE_PATH", _tmp_state(tmp_path, {
        "date": "1999-01-01", "exhausted": {"general": {"2": time.time() + 999}}}))
    monkeypatch.setattr(kv, "get_keys", lambda g: [f"K{i}" for i in range(5)])
    assert set(kv._live_exhausted("general")) == {2}      # 옛 날짜여도 유효한 잠금은 산다


def test_retry_after_is_used(tmp_path, monkeypatch):
    """서버가 'Please retry in 45.5s'로 알려주면 그 값을 쓴다(30분을 헛되이 안 잠근다)."""
    import time
    monkeypatch.setattr(kv, "_STATE_PATH", _tmp_state(tmp_path, {"date": "x", "exhausted": {}}))
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "s.lock")
    monkeypatch.setattr(kv, "get_keys", lambda g: ["K0", "K1", "K2"])
    kv.mark_exhausted("general", "K1", 45.5)
    until = kv._live_exhausted("general")[1]
    assert 40 <= until - time.time() <= 50


def test_lock_is_clamped(tmp_path, monkeypatch):
    """★영구 낙인을 만들지 않는다 — 상한 25시간. 아무리 큰 값이 와도 반드시 한 번은 다시 시험한다.

    ★6시간 → 25시간(2026-09-03). 코드 주석에 예고돼 있던 함정이 터졌다: mark_failure가
      retry_delay_seconds를 넘기기 시작했는데, **일일** 소진은 태평양 자정까지 최대 24시간을
      기다려야 한다. 6시간으로 깎으면 그 키가 6시간 뒤 풀려 또 얻어맞는다(comment_gen이
      09-02에 같은 이유로 24시간으로 올렸다)."""
    import time
    monkeypatch.setattr(kv, "_STATE_PATH", _tmp_state(tmp_path, {"date": "x", "exhausted": {}}))
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "s.lock")
    monkeypatch.setattr(kv, "get_keys", lambda g: ["K0", "K1"])
    kv.mark_exhausted("general", "K0", 999999)
    assert kv._live_exhausted("general")[0] - time.time() <= 25 * 3600 + 5
