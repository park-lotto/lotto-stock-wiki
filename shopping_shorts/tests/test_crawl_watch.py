# -*- coding: utf-8 -*-
"""🕸 크롤링 관측판 — 매일 도는 크롤이 어떤 상태인지 화면으로 본다(2026-09-01 사장님).

★왜 필요한가: 채널별 결과(LAST_VERDICTS)와 집계(LAST_TALLY)는 **메모리에만** 있고
  프로세스가 끝나면 사라진다. 그래서 "어제 뭐가 죽었나"를 journalctl로만 알 수 있었다
  (실측 2026-08-31: 발굴 0건을 화면으로는 알 수 없었다 — 핸드오프 '남은 잔업').
"""
import json

import pytest

from shopping_shorts import crawl_watch as cw


@pytest.fixture()
def db(tmp_path):
    return str(tmp_path / "t.db")


def test_record_run_then_latest(db):
    """한 회차를 남기면 그대로 되읽힌다."""
    cw.record_run(db, "instagram_collect",
                  tally={"ok": 144, "login_wall": 0, "unknown": 3, "error": 0},
                  verdicts=[("a", "ok", ""), ("b", "unknown", "https://x")],
                  items=164, seconds=2094.1)
    got = cw.latest(db, "instagram_collect")
    assert got["tally"]["ok"] == 144
    assert got["items"] == 164
    assert got["total"] == 2          # 채널 2개
    assert got["failed"] == 1         # ok가 아닌 것 1개


def test_latest_none_when_empty(db):
    assert cw.latest(db, "instagram_collect") is None


def test_history_orders_newest_first(db):
    for n in (1, 2, 3):
        cw.record_run(db, "instagram_collect", tally={"ok": n}, verdicts=[], items=n)
    rows = cw.history(db, "instagram_collect", days=30)
    assert [r["items"] for r in rows[:3]] == [3, 2, 1]


def test_dead_channels_lists_repeated_failures(db):
    """★대역폭을 아끼는 핵심 — 계속 실패하는 채널을 골라낸다.

    죽은 채널도 살아있는 채널과 똑같이 프록시 대역폭을 먹는다(하루 3.34GB의 일부).
    2회 이상 연속 실패한 채널은 크롤에서 빼야 낭비가 멈춘다.
    """
    cw.record_run(db, "instagram_collect", tally={}, verdicts=[
        ("dead1", "unknown", ""), ("alive", "ok", ""), ("dead2", "login_wall", "")], items=0)
    cw.record_run(db, "instagram_collect", tally={}, verdicts=[
        ("dead1", "unknown", ""), ("alive", "ok", ""), ("dead2", "login_wall", "")], items=0)
    dead = cw.dead_channels(db, "instagram_collect", min_fails=2)
    names = {d["username"] for d in dead}
    assert "dead1" in names and "dead2" in names
    assert "alive" not in names          # 살아있는 채널을 빼면 수집이 준다


def test_dead_channels_resets_on_success(db):
    """한 번이라도 살아나면 죽은 채널이 아니다(되살아난 채널을 영구 제외하면 손해)."""
    cw.record_run(db, "instagram_collect", tally={}, verdicts=[("x", "unknown", "")], items=0)
    cw.record_run(db, "instagram_collect", tally={}, verdicts=[("x", "unknown", "")], items=0)
    cw.record_run(db, "instagram_collect", tally={}, verdicts=[("x", "ok", "")], items=1)
    assert [d for d in cw.dead_channels(db, "instagram_collect", min_fails=2)
            if d["username"] == "x"] == []


def test_verdict_says_nothing_ran(db):
    """한 번도 안 돌았으면 '모름'이지 '정상'이 아니다(조용한 실패를 정상으로 읽으면 안 된다)."""
    v = cw.verdict(db)
    assert v["level"] in ("unknown", "danger")
    assert "instagram_collect" in json.dumps(v, ensure_ascii=False)


def test_verdict_flags_all_channels_failed(db):
    """채널 전부 실패는 빨강 — 2026-08-31에 153채널이 그랬다."""
    cw.record_run(db, "instagram_collect", tally={"ok": 0, "unknown": 153},
                  verdicts=[(f"c{i}", "unknown", "") for i in range(153)], items=0)
    assert cw.verdict(db)["level"] == "danger"


def test_verdict_flags_zero_collect_even_when_channels_ok(db):
    """★채널은 다 살아있는데 **수집이 0건**인 경우도 빨강이다.

    '전부 실패'와 다른 병이다 — 긁기는 됐는데 저장이 0이면 파서가 깨졌거나 필터가
    다 걸러낸 것이다. 채널 판정만 보면 초록으로 보여 조용히 넘어간다.
    """
    cw.record_run(db, "instagram_collect", tally={"ok": 3},
                  verdicts=[("a", "ok", ""), ("b", "ok", ""), ("c", "ok", "")], items=0)
    assert cw.verdict(db)["level"] == "danger"


# ── API 엔드포인트 — **실제로 호출하는** 테스트(모듈 import만으로는 NameError를 못 잡는다) ──
def test_api_crawl_returns_shape(tmp_path, monkeypatch):
    """/api/admin/crawl이 실제 응답을 준다. 기록이 없어도 200이어야 한다."""
    from shopping_shorts import app as appmod
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "_require_admin", lambda r: None)

    out = appmod._api_crawl(request=None, days=14)
    assert out["ok"] is True
    assert set(out["jobs"]) == set(cw.JOBS)
    assert out["dead"] == []
    assert out["verdict"]["level"] in ("ok", "warn", "danger", "unknown")


def test_api_crawl_reflects_recorded_run(tmp_path, monkeypatch):
    """기록한 회차가 API 응답에 그대로 나온다(배선이 살아있다는 증거)."""
    from shopping_shorts import app as appmod
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "_require_admin", lambda r: None)

    cw.record_run(db, "instagram_collect", tally={"ok": 1, "unknown": 2},
                  verdicts=[("a", "ok", ""), ("b", "unknown", ""), ("c", "unknown", "")],
                  items=5, seconds=12.5)
    out = appmod._api_crawl(request=None, days=14)
    latest = out["jobs"]["instagram_collect"]["latest"]
    assert latest["items"] == 5 and latest["total"] == 3 and latest["failed"] == 2
    assert out["verdict"]["level"] == "warn"      # 절반 이상 실패


def test_dead_channels_counts_recent_streak_not_all_history(db):
    """★옛날에 한 번 살았다고 빼면 안 된다(2026-09-01 자체 실측으로 잡은 버그).

    실패2 → 성공1 → 실패2 인 채널은 **지금 죽어 있다**. 그런데 '과거에 성공한 적
    있으면 제외'로 짰더니 목록에서 통째로 사라져, 정작 빼야 할 채널이 계속 대역폭을
    먹었다. 기준은 '지금 연속으로 죽어 있나'다.
    """
    for v in ("unknown", "unknown", "ok", "unknown", "unknown"):
        cw.record_run(db, "instagram_collect", tally={}, verdicts=[("x", v, "")], items=0)
    dead = cw.dead_channels(db, "instagram_collect", min_fails=2)
    assert [d["username"] for d in dead] == ["x"]
    assert dead[0]["fails"] == 2      # 최근 연속 2회. 옛 실패까지 더해 4가 되면 안 된다


def test_admin_page_links_to_crawl_dashboard():
    """★화면을 만들었으면 **가는 길**도 만들어야 한다(2026-09-01 실측 사고).

    /crawl을 배포하고 라우트·API·테스트까지 다 통과했는데 사장님은 "안 열림"이었다.
    원인은 버그가 아니라 **어디에도 링크가 없어서** 주소를 외워 쳐야 했던 것.
    admin.html 주석에 이미 같은 사고가 적혀 있었다("관측판 /ops는 어디에도 링크가 없었다").
    같은 실수를 두 번 했으므로 테스트로 막는다.
    """
    import pathlib
    html = (pathlib.Path(__file__).resolve().parents[1]
            / "static" / "admin.html").read_text(encoding="utf-8")
    assert 'href="/crawl"' in html, "관리자 화면에 크롤링 관측판 링크가 없다"
    assert 'href="/ops"' in html, "기존 관측판 링크까지 사라지면 안 된다"


# ══════════════════════════════════════════════════════════════════════
# 살아 움직이는 관측판 — "물어봐서 아는" 게 아니라 스스로 신호를 낸다
# (2026-09-01 사장님 "살아있는것처럼 계속움직이는 관측판이 되야한다")
# ══════════════════════════════════════════════════════════════════════

def test_stale_job_is_danger_even_with_old_success(db):
    """★가장 위험한 구멍 — 어제 성공 기록이 있으면 오늘 안 돌아도 초록이었다.

    타이머가 통째로 죽으면 화면은 영원히 '정상'이라 아무도 모른다.
    예정 시각이 지났는데 오늘 기록이 없으면 **빨강**이어야 한다.
    """
    cw.record_run(db, "instagram_collect", tally={"ok": 100},
                  verdicts=[(f"c{i}", "ok", "") for i in range(100)],
                  items=120, ran_at="2026-08-31 00:16:00")     # 어제(UTC)
    v = cw.verdict(db, now="2026-09-01 05:00:00")              # 오늘 14:00 KST
    assert v["level"] == "danger"
    assert "소식" in v["msg"] or "안 돌" in v["msg"]


def test_fresh_run_today_is_ok(db):
    """오늘 예정대로 돌았으면 초록."""
    cw.record_run(db, "instagram_collect", tally={"ok": 100},
                  verdicts=[(f"c{i}", "ok", "") for i in range(100)],
                  items=120, ran_at="2026-09-01 00:16:00")
    for j in ("instagram_discover", "youtube_collect"):
        cw.record_run(db, j, tally={"found": 5}, verdicts=[], items=5,
                      ran_at="2026-09-01 00:16:00")
    assert cw.verdict(db, now="2026-09-01 05:00:00")["level"] == "ok"


def test_before_due_time_is_not_stale(db):
    """예정 시각 전이면 아직 안 돈 게 정상 — 빨강이면 매일 새벽마다 거짓 경보."""
    cw.record_run(db, "instagram_collect", tally={"ok": 1}, verdicts=[("a", "ok", "")],
                  items=1, ran_at="2026-08-31 00:16:00")
    # 09-01 05:00 KST = 08-31 20:00 UTC. 아직 오늘 09:00 KST 전이다.
    v = cw.verdict(db, now="2026-08-31 20:00:00")
    assert v["level"] != "danger"


def test_running_run_is_visible_while_it_works(db):
    """★심박 — 도는 중에도 화면이 움직인다(끝나야만 보이면 '정지된 표'다)."""
    rid = cw.start_run(db, "instagram_collect", total=147)
    cw.beat(db, rid, done=30, items=42)
    cur = cw.latest(db, "instagram_collect")
    assert cur["state"] == "running"
    assert cur["done"] == 30 and cur["items"] == 42


def test_finished_run_is_not_running(db):
    rid = cw.start_run(db, "instagram_collect", total=3)
    cw.finish_run(db, rid, tally={"ok": 3},
                  verdicts=[("a", "ok", ""), ("b", "ok", ""), ("c", "ok", "")], items=9)
    cur = cw.latest(db, "instagram_collect")
    assert cur["state"] == "done" and cur["items"] == 9


def test_crashed_run_is_danger(db):
    """시작만 하고 심박이 끊기면 '돌다가 죽은 것' — 이걸 못 잡으면 조용히 사라진다."""
    rid = cw.start_run(db, "instagram_collect", total=147)
    cw.beat(db, rid, done=10, items=5, at="2026-09-01 00:00:00")
    v = cw.verdict(db, now="2026-09-01 02:00:00")      # 2시간째 심박 없음
    assert v["level"] == "danger"
    assert "멈춘" in v["msg"] or "죽" in v["msg"]


def test_alert_fires_once_for_same_problem(db, monkeypatch):
    """★알림은 화면을 안 봐도 오게 한다. 단 같은 사고로 도배하면 안 된다."""
    sent = []
    monkeypatch.setattr(cw, "_send_alert", lambda kind, title, detail: sent.append(kind) or True)
    cw.record_run(db, "instagram_collect", tally={"ok": 0, "unknown": 3},
                  verdicts=[(f"d{i}", "unknown", "") for i in range(3)], items=0,
                  ran_at="2026-09-01 00:16:00")
    cw.check_and_alert(db, now="2026-09-01 01:00:00")
    cw.check_and_alert(db, now="2026-09-01 01:10:00")
    assert len(sent) == 1, f"같은 사고로 {len(sent)}번 알림 — 도배"


def test_alert_not_sent_when_healthy(db, monkeypatch):
    sent = []
    monkeypatch.setattr(cw, "_send_alert", lambda kind, title, detail: sent.append(kind) or True)
    for j in cw.JOBS:
        cw.record_run(db, j, tally={"ok": 5},
                      verdicts=[(f"c{i}", "ok", "") for i in range(5)], items=10,
                      ran_at="2026-09-01 00:16:00")
    cw.check_and_alert(db, now="2026-09-01 01:00:00")
    assert sent == []


def test_api_exposes_live_fields(tmp_path, monkeypatch):
    """★화면이 '움직이려면' API가 진행 상태를 줘야 한다(state/done/beat_at/server_now).

    이 필드가 빠지면 화면은 끝난 회차만 보여주는 '정지된 표'로 되돌아간다.
    """
    from shopping_shorts import app as appmod
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "_require_admin", lambda r: None)

    rid = cw.start_run(db, "instagram_collect", total=147)
    cw.beat(db, rid, done=30, items=42)
    out = appmod._api_crawl(request=None, days=14)

    live = out["jobs"]["instagram_collect"]["latest"]
    assert live["state"] == "running"
    assert live["done"] == 30 and live["total"] == 147 and live["items"] == 42
    assert live["beat_at"]                      # 심박 시각이 있어야 '멈춤'을 잴 수 있다
    assert out.get("server_now")                # 화면이 '몇 분 전'을 서버 시계로 계산한다
