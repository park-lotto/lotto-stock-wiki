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
