# -*- coding: utf-8 -*-
"""숏템메이커 관리자 화면(/channel_stats)이 부르는 입구 — 관제 281.
수집(collect)·분석(analyze)은 각 모듈이 주인이고, 여기는 '언제 다시 모으나'와 '서버에서 파일이 어디 있나'만 정한다.

서버 파일(전부 shopping_shorts/data/channel_stats/, git 밖):
  buffer_keys.json  — 폴더명 → Buffer 키 (PC ~/.claude/buffer_keys.json 과 같은 내용)
  ledger.json       — 버퍼 예약 장부 사본(없어도 된다 — 파일명 칸만 빈다)
  stats.db          — 스냅샷
갱신: 화면이 데이터를 읽을 때 마지막 수집이 STALE_MIN 분보다 오래면 백그라운드로 한 번 더 모은다(동시에 하나만).
"""
import datetime as dt, json, os, sqlite3, threading, time
from pathlib import Path

from channel_stats import analyze, collect

DIR = Path(os.environ.get("CHSTATS_DIR") or Path(__file__).resolve().parent.parent / "shopping_shorts" / "data" / "channel_stats")
STALE_MIN = 55
_lock = threading.Lock()
_state = {"running": False, "last_error": None, "started": None}


def _load(name, default):
    try:
        return json.loads((DIR / name).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _last_run():
    db = DIR / "stats.db"
    if not db.exists():
        return None
    con = sqlite3.connect(db)
    try:
        r = con.execute("SELECT max(at) FROM runs").fetchone()
        return dt.datetime.fromisoformat(r[0]) if r and r[0] else None
    except sqlite3.OperationalError:
        return None
    finally:
        con.close()


def refresh(log=print):
    """한 번 모은다. 이미 돌고 있으면 건너뛴다."""
    if not _lock.acquire(blocking=False):
        return False
    _state.update(running=True, started=time.time())
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        keys = _load("buffer_keys.json", {})
        if not keys:
            raise RuntimeError(f"Buffer 키 파일이 없다: {DIR / 'buffer_keys.json'}")
        r = collect.collect(str(DIR / "stats.db"), keys=keys, ledger=_load("ledger.json", []), log=log)
        _state["last_error"] = "; ".join(r["errors"]) or None
        return True
    except Exception as e:  # noqa: BLE001 — 실패 사유는 화면 머리(state.error)에 그대로 뜬다
        _state["last_error"] = str(e)
        log(f"[channel_stats] 수집 실패: {e}")
        return False
    finally:
        _state["running"] = False
        _lock.release()


def refresh_async():
    if _state["running"]:
        return False
    threading.Thread(target=refresh, daemon=True, name="channel_stats_refresh").start()
    return True


def data(kick=True):
    """화면용 JSON. 오래됐으면 뒤에서 다시 모으기를 건다(이번 응답은 지금 있는 것)."""
    last = _last_run()
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    stale = last is None or (now - last).total_seconds() > STALE_MIN * 60
    if kick and stale:
        refresh_async()
    out = analyze.build(str(DIR / "stats.db")) if last else {"empty": True}
    out["state"] = {"refreshing": _state["running"], "error": _state["last_error"], "stale": stale,
                    "keys": (DIR / "buffer_keys.json").exists()}
    return out
