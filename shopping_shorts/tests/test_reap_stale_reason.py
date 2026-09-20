"""배경작업 중단을 '고장'으로 세지 않는다 — 2026-08-19 사장님 총점검 지시.

실측(라이브): job_queue failed 45건 중 **43건이 '워커가 중단됐습니다'**였고
그게 오류표 1위였다. 그런데 갈라보니:
  · durfill  done 248 / '중단' 33  → 길이 캐시는 24시간에 732건이 채워지는 중
  · auto_deploy.sh는 durfill·prewarm을 **일부러 안 기다리고** 죽인다
    (스크립트 주석: "재시작으로 죽어도 다음 크론이 다시 큐에 넣으므로 잃는 게 없다")
즉 이 중단은 **정상 동작**인데 고장과 같은 문구로 적혀, 진짜 고장(EDL 13건)을 가렸다.
"""
import tempfile, os
import pytest
from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def _stale(store, task):
    with store._conn() as c:
        c.execute("INSERT INTO job_queue(task,args_json,state,heartbeat_at,created_at) "
                  "VALUES(?,'{}','running',datetime('now','-10 minutes'),datetime('now'))",
                  (task,))


def _err(store, task):
    with store._conn() as c:
        return c.execute("SELECT error FROM job_queue WHERE task=?", (task,)).fetchone()[0]


def test_배경작업은_고장이_아니라고_적는다(store):
    # prewarm은 2026-09-04부터 failed가 아니라 **다시 큐에 들어간다**(아래 테스트).
    for t in ("durfill", "overseas"):
        _stale(store, t)
    store.reap_stale(minutes=2)
    for t in ("durfill", "overseas"):
        assert "고장 아님" in _err(store, t), f"{t}가 고장으로 집계된다"


def _state(store, task):
    with store._conn() as c:
        return c.execute("SELECT state, args_json, claimed_at FROM job_queue WHERE task=?",
                         (task,)).fetchone()


def test_끊긴_담기는_다시_큐에_들어간다(store):
    """2026-09-04 실사고: 문구만 '자동 재시도 대상'이고 재시도 코드가 없어 고객이 다시 담아야 했다."""
    _stale(store, "prewarm")
    assert store.reap_stale(minutes=2) == 1
    st, args, claimed = _state(store, "prewarm")
    assert st == "queued" and claimed is None
    assert '"_restart_retry": 1' in args
    assert "다시 시작" in _err(store, "prewarm")


def test_담기_재시도는_상한이_있다(store):
    """영원히 되살리면 배포가 끝나도 좀비가 큐를 돈다 — 상한에 닿으면 종전대로 failed."""
    import json
    with store._conn() as c:
        c.execute("INSERT INTO job_queue(task,args_json,state,heartbeat_at,created_at) "
                  "VALUES('prewarm',?,'running',datetime('now','-10 minutes'),datetime('now'))",
                  (json.dumps({"_restart_retry": Store.PREWARM_RESTART_RETRIES}),))
    store.reap_stale(minutes=2)
    st, _, _ = _state(store, "prewarm")
    assert st == "failed"
    assert "고장 아님" in _err(store, "prewarm")


def test_재큐된_담기는_고객작업_전파를_안_건드린다(store):
    """prewarm은 mix_jobs 상태칸이 없다 — 재큐가 다른 job 상태를 바꾸면 안 된다."""
    _stale(store, "prewarm")
    _stale(store, "mix")
    store.reap_stale(minutes=2)
    assert _state(store, "prewarm")[0] == "queued"
    assert _err(store, "mix") == "워커가 중단됐습니다"


def test_고객작업은_종전대로_실패로_적는다(store):
    """고객 영상이 죽은 건 진짜 사고다 — 여기까지 뭉뚱그리면 안 된다."""
    for t in ("mix", "render"):
        _stale(store, t)
    store.reap_stale(minutes=2)
    for t in ("mix", "render"):
        assert _err(store, t) == "워커가 중단됐습니다", f"{t} 문구가 바뀌면 안 된다"


def test_두_문구가_서로_다르다(store):
    """같은 문구면 집계에서 못 가른다 — 이 구분이 이 수정의 목적이다."""
    _stale(store, "durfill")
    _stale(store, "mix")
    store.reap_stale(minutes=2)
    assert _err(store, "durfill") != _err(store, "mix")


def test_살아있는_작업은_안_건드린다(store):
    """하트비트가 뛰는 중이면 정리 대상이 아니다(정상 진행 중인 걸 죽이면 큰 사고)."""
    with store._conn() as c:
        c.execute("INSERT INTO job_queue(task,args_json,state,heartbeat_at,created_at) "
                  "VALUES('mix','{}','running',datetime('now'),datetime('now'))")
    assert store.reap_stale(minutes=2) == 0
    with store._conn() as c:
        assert c.execute("SELECT state FROM job_queue").fetchone()[0] == "running"


def test_정리건수를_그대로_반환한다(store):
    for t in ("durfill", "mix", "prewarm"):
        _stale(store, t)
    assert store.reap_stale(minutes=2) == 3
