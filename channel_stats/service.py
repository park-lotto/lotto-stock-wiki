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


def refresh(log=print, force_analytics=False):
    """한 번 모은다(Buffer·유튜브 공개 데이터 → 허용된 채널은 애널리틱스까지). 이미 돌고 있으면 건너뛴다."""
    if not _lock.acquire(blocking=False):
        return False
    _state.update(running=True, started=time.time())
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        keys = _load("buffer_keys.json", {})
        if not keys:
            raise RuntimeError(f"Buffer 키 파일이 없다: {DIR / 'buffer_keys.json'}")
        r = collect.collect(str(DIR / "stats.db"), keys=keys, ledger=_load("ledger.json", []), log=log)
        errs = list(r["errors"])
        if (DIR / "yt_tokens.json").exists():
            from channel_stats import yt_analytics
            con = sqlite3.connect(DIR / "stats.db")
            try:
                recent = {}
                for vid, cid, pub in con.execute("SELECT video_id, channel_id, substr(published,1,10) FROM yt_videos"):
                    recent.setdefault(cid, []).append((vid, pub))
                errs += yt_analytics.collect(str(DIR), con, recent, log=log, force=force_analytics).get("errors", [])
            finally:
                con.close()
        _state["last_error"] = "; ".join(errs) or None
        return True
    except Exception as e:  # noqa: BLE001 — 실패 사유는 화면 머리(state.error)에 그대로 뜬다
        _state["last_error"] = str(e)
        log(f"[channel_stats] 수집 실패: {e}")
        return False
    finally:
        _state["running"] = False
        _lock.release()


def refresh_async(force_analytics=False):
    if _state["running"]:
        return False
    threading.Thread(target=refresh, kwargs={"force_analytics": force_analytics}, daemon=True, name="channel_stats_refresh").start()
    return True


def data(kick=True):
    """화면용 JSON. 오래됐으면 뒤에서 다시 모으기를 건다(이번 응답은 지금 있는 것)."""
    last = _last_run()
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    stale = last is None or (now - last).total_seconds() > STALE_MIN * 60
    if kick and stale:
        refresh_async()
    out = analyze.build(str(DIR / "stats.db")) if last else {"empty": True}
    from channel_stats import yt_analytics
    conn = yt_analytics.connected(str(DIR))
    out["state"] = {"refreshing": _state["running"], "error": _state["last_error"], "stale": stale,
                    "keys": (DIR / "buffer_keys.json").exists(), "oauth_ready": (DIR / "oauth_client.json").exists()}
    out["connections"] = [{"key": c["key"], "name": c["name"], "id": c["id"], "email": ACCOUNT_EMAIL.get(c["key"], ""),
                           "connected": c["id"] in conn, **conn.get(c["id"], {})} for c in out.get("channels", [])]
    return out


# ── 유튜브 애널리틱스 연결(관제 281 2단계) ─────────────────────
# Buffer 폴더 번호 → 그 유튜브 채널을 가진 구글 계정(사장님 10-27). 허용 화면을 그 계정으로 띄우는 힌트일 뿐 — 실제 채널은 콜백이 mine=true 로 확인한다
ACCOUNT_EMAIL = {"950": "parklotto950@gmail.com", "987": "parklotto987@gmail.com", "994": "parklotto994@gmail.com",
                 "995": "parklotto995@gmail.com", "998": "parklotto998@gmail.com", "999": "parklotto999@gmail.com",
                 "숏템07": "shortem07@gmail.com", "21": "parklotto21@gmail.com"}


def oauth_start(key=""):
    from channel_stats import yt_analytics
    return yt_analytics.start_url(str(DIR), ACCOUNT_EMAIL.get(key, ""))


def oauth_finish(code, state):
    from channel_stats import yt_analytics
    title = yt_analytics.finish(str(DIR), code, state)
    refresh_async(force_analytics=True)      # 연결하자마자 시청시간·일별 기록을 채운다
    return title


# ── 매시간 자동 수집(관제 281, 사장님 "한 시간 자동수집으로") ─────────────
# 페이지를 아무도 안 열어도 조회수 점이 매시간 쌓여야 영상별 증가 그래프가 끊기지 않는다.
# 숏템 웹 프로그램이 켜질 때 한 번 부른다(app startup). 서버 웹은 프로세스 1개지만, 혹시 둘이 떠도
# 파일 잠금(flock)으로 한 곳만 모은다. 시험(pytest)·키 파일 없는 곳(트랙·병합 폴더)에선 띄우지 않는다.
CHECK_SEC = 300
START_DELAY = 90               # 기동 직후 몰리는 일(시드·키 합류)과 겹치지 않게
_sched = {"started": False}


def start_scheduler(log=print):
    import sys
    if _sched["started"] or "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if not (DIR / "buffer_keys.json").exists() or os.environ.get("CHSTATS_SCHEDULER", "on") == "off":
        return False
    _sched["started"] = True

    def loop():
        lock = None
        try:
            import fcntl
            lock = open(DIR / ".scheduler.lock", "w")
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            pass                      # 윈도우(로컬 확인) — 잠금 없이 돈다
        except OSError:
            log("[channel_stats] 다른 프로세스가 이미 매시간 수집 중 — 이 프로세스는 쉰다")
            return
        time.sleep(START_DELAY)
        while True:
            try:
                last = _last_run()
                now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
                if last is None or (now - last).total_seconds() > STALE_MIN * 60:
                    refresh(log=log)
            except Exception as e:  # noqa: BLE001 — 한 번 실패해도 다음 회차는 돈다. 사유는 화면 머리(state.error)에도 남는다
                log(f"[channel_stats] 자동 수집 회차 실패: {e}")
            time.sleep(CHECK_SEC)

    threading.Thread(target=loop, daemon=True, name="channel_stats_hourly").start()
    log("[channel_stats] 매시간 자동 수집 시작")
    return True
