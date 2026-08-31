"""API 관측판의 데이터층 — 모든 외부 API 호출의 성공·실패를 한 깔때기로 기록한다.

왜 만들었나 (2026-09-01, 사장님 "오늘 계속 사고가 발생했어. 제미니 api 때문에"):
  08-31 하루 제미니 429가 워커에서만 2,524건(실측)이었는데 그걸 셀 수 있는 곳이
  journald grep뿐이었다. gemini_usage(usage_meter)는 **성공 콜만** 기록하고,
  기존 키 현황 API(/api/refs/api_usage)는 08-27 상태파일 포맷 변경을 못 따라가
  exhausted_today가 항상 0으로 깨져 있었다. 즉 "지금 무슨 일이 나고 있나"를
  물어볼 데가 없었다 — 그래서 사고마다 두더지잡기가 됐다.

무엇을 기록하나:
  api_events  — 외부 API 1콜 1행(성공 포함). 서비스·풀·키(마스킹)·기능(op)·분류(outcome).
  api_heartbeats — 프로세스(웹/워커N)가 키풀 합류를 언제 했고 몇 개였나.

설계 원칙 (usage_meter와 동일):
  - **관측이 본작업을 죽이면 안 된다.** 모든 기록 실패는 삼키고 log.warning만 남긴다.
  - 판정(classify)은 여기 **한 곳**에만 있다(0순위-B). key_vault의 기존 판정 함수를
    재사용하고, 호출부마다 에러 분류를 새로 적지 않는다.
  - 키는 원문을 저장하지 않는다 — 끝 6자(key_tail)만. 인덱스는 참고용으로만 싣는다
    (회원 합류로 목록이 변하면 인덱스는 어긋난다 — memory: apify 인덱스 함정과 동일 계보).

끄기: API_HEALTH=0 (usage_meter의 USAGE_METER=0과 같은 킬스위치).
⚠️ 관측판이 "기록 0건"이면 사용 0이 아니라 이 킬스위치·배선 누락부터 의심하라.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent / "data" / "reference.db"
_init_lock = threading.Lock()
_initialized = False

# 이벤트 분류(outcome) — 화면·판정이 이 어휘만 안다. 새 값을 더할 땐 화면 범례도 같이.
OUT_OK = "ok"                      # 정상 응답
OUT_RPM = "rpm"                    # 분당 한도 429 — 기다리면 풀린다
OUT_RPD = "rpd"                    # 일일 한도 429 — 오늘은 안 풀린다(구글 리셋까지)
OUT_AUTH = "auth_dead"             # 401/403 계정·키 사망 — 영구, 키 제거 대상
OUT_QUOTA = "quota"                # 429인데 분당/일일 확정 불가
OUT_SERVER = "server"              # 5xx/overloaded — 상대 서버 문제
OUT_TIMEOUT = "timeout"
OUT_NETWORK = "network"
OUT_EMPTY = "empty"                # 200인데 내용 없음(빈 응답)
OUT_SILENT = "silent_fallback"     # ★키 없음 → 무음 mp3로 조용히 내려앉음(고객은 무음 영상)
OUT_LOCK = "lock"                  # 로테이션이 키를 잠금(소진 마킹)
OUT_REVIVE = "revive"              # 프로브가 키를 되살림
OUT_ERROR = "error"                # 그 외

# 요청이 실제로 상대 API에 나간 outcome — RPD 예산 계산은 이것만 센다.
_REQUEST_OUTCOMES = (OUT_OK, OUT_RPM, OUT_RPD, OUT_AUTH, OUT_QUOTA,
                     OUT_SERVER, OUT_TIMEOUT, OUT_EMPTY, OUT_ERROR)
# 사람이 "사고"로 보는 outcome — 판정·피드 기본 필터.
FAIL_OUTCOMES = (OUT_RPM, OUT_RPD, OUT_AUTH, OUT_QUOTA, OUT_SERVER,
                 OUT_TIMEOUT, OUT_NETWORK, OUT_EMPTY, OUT_SILENT, OUT_ERROR)

_KST = timezone(timedelta(hours=9))
# 구글 무료티어 RPD는 태평양시 자정에 리셋된다(실측 08-27: 오전 429 키가 오후 200).
# PT는 서머타임이 있어 고정 오프셋이 아니다 — 근사로 UTC-7(PDT)을 쓰되, 겨울(-8)엔
# 리셋 시각이 1시간 어긋날 수 있음을 화면 '읽는 법'에 명시한다(예산은 어차피 추세치).
_PT_OFFSET_H = -7


def _utcnow():
    return datetime.now(timezone.utc)


def _kst_day(dt=None):
    return (dt or _utcnow()).astimezone(_KST).strftime("%Y-%m-%d")


def pt_day_start_utc(dt=None):
    """지금이 속한 '구글 하루'(태평양시 기준)의 시작 시각(UTC). RPD 예산 창."""
    now = (dt or _utcnow()).astimezone(timezone(timedelta(hours=_PT_OFFSET_H)))
    start_pt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_pt.astimezone(timezone.utc)


def _enabled():
    return os.environ.get("API_HEALTH", "1") == "1"


def _proc_kind():
    """이 프로세스가 무엇인가 — web/worker/bulk/cron/기타. 이벤트의 '어디서' 축."""
    try:
        if os.environ.get("SHORTS_BULK_MODE") == "1":
            return "bulk"
        import sys
        argv = " ".join(sys.argv)
        if "shopping_shorts.worker" in argv:
            return "worker"
        if "uvicorn" in argv or "shopping_shorts.app" in argv:
            return "web"
        if "capacity_watch" in argv:
            return "cron"
        mod = Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else ""
        return mod or "etc"
    except Exception:                     # noqa: BLE001 — 관측이 본작업을 죽이면 안 된다
        return "etc"


def _ensure_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT    NOT NULL,          -- UTC ISO
            day       TEXT    NOT NULL,          -- KST 날짜(사람이 보는 축)
            service   TEXT    NOT NULL,          -- gemini/elevenlabs/typecast/vmake/serpapi/youtube/apify/...
            pool      TEXT,                      -- gemini: shorts | vault-general | ... 그 외 NULL
            key_tail  TEXT,                      -- 키 끝 6자(마스킹 식별자) — 원문 저장 금지
            key_idx   INTEGER,                   -- 기록 시점 인덱스(참고용)
            owner     TEXT,                      -- owner|member|NULL
            op        TEXT,                      -- 기능(대본생성/태깅/…) — usage_meter와 같은 축
            model     TEXT,
            job_id    TEXT,
            customer_id TEXT,
            outcome   TEXT    NOT NULL,
            http      INTEGER,
            detail    TEXT,                      -- 에러 원문 앞부분(500자) — 뭉갠 문구 금지의 근거
            dur_ms    INTEGER,
            proc      TEXT                       -- web|worker|bulk|cron|etc
        )""")
    for stmt in (
        "CREATE INDEX IF NOT EXISTS ix_ae_ts ON api_events(ts)",
        "CREATE INDEX IF NOT EXISTS ix_ae_day_svc ON api_events(day, service)",
        "CREATE INDEX IF NOT EXISTS ix_ae_outcome ON api_events(outcome, ts)",
        "CREATE INDEX IF NOT EXISTS ix_ae_key ON api_events(service, key_tail, ts)",
    ):
        conn.execute(stmt)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_heartbeats (
            proc   TEXT NOT NULL,               -- web|worker|bulk|...
            pid    INTEGER NOT NULL,
            ts     TEXT NOT NULL,               -- UTC ISO — 마지막 합류/생존 신고
            detail TEXT,                        -- JSON: 풀별 사장님/회원 키 수
            PRIMARY KEY (proc, pid)
        )""")
    conn.commit()


def _connect(timeout=10):
    global _initialized
    conn = sqlite3.connect(str(_DB_PATH), timeout=timeout)
    if not _initialized:
        with _init_lock:
            if not _initialized:
                _ensure_schema(conn)
                _initialized = True
    return conn


def key_tail(key) -> str | None:
    """키 마스킹 식별자 — 끝 6자만. 원문을 어디에도 싣지 않기 위한 유일한 변환."""
    if not key:
        return None
    s = str(key)
    return s[-6:] if len(s) >= 6 else s


# ── 에러 분류 — 판단은 여기 한 곳 ─────────────────────────────────────────

def classify(exc_or_msg, http=None) -> str:
    """예외/메시지 → outcome. key_vault의 기존 판정을 재사용한다(0순위-B).

    ⚠️ "A 또는 B"로 뭉개지 않는다 — 원문은 detail로 따로 싣고, 여기선 하나만 고른다.
    분류 우선순위: 계정사망 > 일일소진 > 분당 > 기타429 > 5xx > 타임아웃 > 네트워크.
    """
    m = str(exc_or_msg or "")
    try:
        from pipeline.atoms import key_vault as _kv
        if _kv.is_account_disabled_error(Exception(m)):
            return OUT_AUTH
        daily = _kv.is_daily_exhausted_error(Exception(m))
        quota = _kv.is_quota_error(Exception(m))
    except Exception:                     # noqa: BLE001 — atoms가 없어도 자체 판정으로 돈다
        daily = ("429" in m or "RESOURCE_EXHAUSTED" in m) and ("PerDay" in m or "limit: 500" in m)
        quota = "429" in m or "RESOURCE_EXHAUSTED" in m
        if ("UNAUTHENTICATED" in m or "PERMISSION_DENIED" in m
                or "ACCOUNT_STATE_INVALID" in m or "service account is deleted" in m):
            return OUT_AUTH
    if http in (401, 403) and not quota:
        return OUT_AUTH
    if daily or "run out of searches" in m:   # serpapi 월간 소진 — 오늘 안 풀린다
        return OUT_RPD
    if quota:
        low = m.lower()
        if "per minute" in low or "perminute" in low or "requests per minute" in low:
            return OUT_RPM
        # 서버가 초 단위 재시도 시각을 줬으면 분당 계열로 본다(retry_delay_seconds와 같은 근거)
        if "retry in" in low:
            return OUT_RPM
        return OUT_QUOTA
    if http in (429,):
        return OUT_QUOTA
    if any(c in m for c in ("503", "UNAVAILABLE", "overloaded", "500 ", "502", "504")):
        return OUT_SERVER
    if http and 500 <= int(http) < 600:
        return OUT_SERVER
    if any(c in m for c in ("timed out", "timeout", "Timeout", "DEADLINE")):
        return OUT_TIMEOUT
    if any(c in m for c in ("Connection", "connection", "Network", "getaddrinfo", "SSL", "RemoteDisconnected")):
        return OUT_NETWORK
    return OUT_ERROR


# ── 기록 ──────────────────────────────────────────────────────────────────

def record(service, outcome, *, pool=None, key=None, key_idx=None, owner=None,
           op=None, model=None, job_id=None, customer_id=None,
           http=None, detail=None, dur_ms=None):
    """1이벤트 기록. 실패해도 예외를 올리지 않는다(관측이 본작업을 죽이면 안 된다)."""
    if not _enabled():
        return
    if os.environ.get("PYTEST_CURRENT_TEST") and str(_DB_PATH).endswith("reference.db"):
        # ★테스트가 라이브 DB를 오염시키지 않게(ops_alert 2026-08-14 실사고와 같은 이유).
        #   테스트는 set_db_path()로 임시 DB를 지정해서 검증한다.
        return
    try:
        now = _utcnow()
        # op이 비면 usage_meter의 스택 유도 판정을 그대로 빌린다(판단처 하나).
        if not op:
            try:
                from shopping_shorts import usage_meter as _um
                ctx = _um.current_context()
                op = ctx.get("op") or _um._op_from_stack()
                job_id = job_id or ctx.get("job_id")
                customer_id = customer_id if customer_id is not None else ctx.get("customer_id")
            except Exception as e:        # noqa: BLE001 — 문맥 없이도 기록은 간다
                log.debug("api_health: op 문맥 유도 실패(무해) %r", e)
        # ★2초만 기다린다(리뷰 3): 429 폭풍+쓰기 경합 때 기록 한 줄이 예외 전파를
        #   10초씩 붙잡으면 호출부의 retry_delay 페이싱이 밀린다. 못 쓰면 버리고 경고.
        conn = _connect(timeout=2)
        try:
            conn.execute(
                "INSERT INTO api_events(ts,day,service,pool,key_tail,key_idx,owner,"
                "op,model,job_id,customer_id,outcome,http,detail,dur_ms,proc) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (now.isoformat(), _kst_day(now), service, pool,
                 key_tail(key), key_idx, owner, op, model, job_id,
                 None if customer_id is None else str(customer_id),
                 outcome, http, (str(detail)[:500] if detail else None),
                 dur_ms, _proc_kind()))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:                # noqa: BLE001
        log.warning("api_health: 기록 실패(무시하고 진행) %s", e)
    # 키 사망은 즉시 사람에게 — ops_alert가 쿨다운(30분)으로 도배를 막는다.
    if outcome == OUT_AUTH:
        try:
            from shopping_shorts import ops_alert
            # 제미니·유튜브는 회사 풀 키, 나머지는 회원 등록(BYOK) 키가 대부분이다 —
            # 처방을 갈라 보낸다(리뷰 8: 회원 키에 ".env에서 제거"는 틀린 처방).
            # kind도 서비스별로 — 한 쿨다운에 서로 다른 서비스 사망이 묻히지 않게.
            if service in ("gemini", "youtube"):
                cure = " — /apiwatch에서 확인, env에서 제거 필요"
            else:
                cure = " — 회원 등록 키(BYOK)일 수 있음: /apiwatch 피드에서 고객 확인"
            ops_alert.raise_alert(
                f"api_key_dead_{service}",
                f"[API] {service} 키 사망 감지({'…' + (key_tail(key) or '?')})",
                f"{detail or ''}"[:300] + cure)
        except Exception as e:            # noqa: BLE001 — 경보 실패가 기록을 막으면 안 된다
            log.warning("api_health: 키사망 경보 실패(무시) %r", e)


def record_failure(service, exc, **kw):
    """예외 → 분류 + 기록 한 줄짜리 헬퍼. 배선부는 이것만 부르면 된다."""
    try:
        outcome = classify(exc, http=kw.get("http"))
        kw.setdefault("detail", str(exc))
        record(service, outcome, **kw)
        return outcome
    except Exception:                     # noqa: BLE001
        return OUT_ERROR


def heartbeat(detail=None, proc=None):
    """프로세스 생존/키풀 합류 신고. keypool.resync_pools와 워커 루프가 부른다.
    같은 (proc,pid)는 덮어쓴다 — 행이 늘지 않는다."""
    if not _enabled():
        return
    if os.environ.get("PYTEST_CURRENT_TEST") and str(_DB_PATH).endswith("reference.db"):
        return
    try:
        conn = _connect(timeout=2)               # 하트비트도 핫패스 — 경합 시 버린다
        try:
            conn.execute(
                "INSERT INTO api_heartbeats(proc,pid,ts,detail) VALUES(?,?,?,?) "
                "ON CONFLICT(proc,pid) DO UPDATE SET ts=excluded.ts, detail=excluded.detail",
                (proc or _proc_kind(), os.getpid(), _utcnow().isoformat(),
                 json.dumps(detail, ensure_ascii=False) if detail else None))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:                # noqa: BLE001
        log.warning("api_health: heartbeat 실패(무시) %s", e)


_last_purge_day = {"d": None}


def purge(days=30):
    """오래된 이벤트 정리 — **하루 한 번만** 실제로 돈다(2026-09-01 리뷰 확정: 게이트
    없이는 30초 자동갱신마다 DELETE가 나가고, 오래 안 열다 열면 대량 DELETE 한 방이
    쓰기락을 점유해 12워커 record가 줄줄이 기다린다)."""
    if os.environ.get("PYTEST_CURRENT_TEST") and str(_DB_PATH).endswith("reference.db"):
        return                                   # 테스트가 라이브 DB를 지우면 안 된다
    today = _kst_day()
    if _last_purge_day["d"] == today:
        return
    _last_purge_day["d"] = today
    try:
        conn = _connect()
        try:
            cut = (_utcnow() - timedelta(days=days)).isoformat()
            conn.execute("DELETE FROM api_events WHERE ts < ?", (cut,))
            # 웹은 기동·키 등록 때만 신고한다 — 3일이면 멀쩡한 웹의 신고가 지워져
            # '합류 안 함'으로 오독된다(리뷰 15). 7일 보존.
            stale = (_utcnow() - timedelta(days=7)).isoformat()
            conn.execute("DELETE FROM api_heartbeats WHERE ts < ?", (stale,))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:                # noqa: BLE001 — 정리 실패는 다음 조회가 다시 시도한다
        log.warning("api_health: purge 실패(무시) %r", e)


def set_db_path(p):
    """테스트 전용 — 임시 DB로 바꾼다."""
    global _DB_PATH, _initialized
    _DB_PATH = Path(p)
    _initialized = False


# ── 스냅샷 — 지금 키풀이 어떻게 생겼나 ─────────────────────────────────────

def _shorts_pool_snapshot():
    """SHORTS 풀(태깅·댓글·EDL 차용) — config+comment_gen이 진실."""
    out = {"name": "제미니 · 쇼핑쇼츠 풀(SHORTS_GEMINI_KEY*)", "pool": "shorts",
           "env_src": "systemd(/etc/shopping-shorts.env) + 회원 DB 합류"}
    try:
        from shopping_shorts import config
        from shopping_shorts import comment_gen
        keys = list(config.SHORTS_GEMINI_KEYS)
        n_owner = len(getattr(config, "_OWNER_GEMINI_KEYS", []) or [])
        locked = comment_gen._live_exhausted()          # {idx: 만료ts} — 만료분 자동 제외
        state = comment_gen._load_state()
        burned = sorted(state.get("revived_once") or [])
        now = time.time()
        out.update({
            "total": len(keys), "owner": n_owner, "member": max(0, len(keys) - n_owner),
            "locked": [{"idx": i, "left_s": max(0, int(t - now)),
                        "tail": key_tail(keys[i]) if i < len(keys) else None}
                       for i, t in sorted(locked.items())],
            "live": len(keys) - len([i for i in locked if i < len(keys)]),
            "revived_once": burned,
            "keys": [{"idx": i, "tail": key_tail(k),
                      "owner": "owner" if i < n_owner else "member",
                      "state": ("locked" if i in locked else "live")}
                     for i, k in enumerate(keys)],
        })
    except Exception as e:                # noqa: BLE001
        out["error"] = str(e)[:200]
    return out


def _vault_pool_snapshot():
    """vault 풀(제작소 대본·위키 공용) — pipeline/atoms/key_vault가 진실.
    ⚠️vault 소진기록은 TTL이 없다(당일 내내) — 화면에 그 사실 자체를 표시한다."""
    out = {"name": "제미니 · vault 풀(GEMINI_API_KEY* 4그룹)", "pool": "vault",
           "env_src": ".env(파일 직접 읽음) + 회원 합류", "groups": {}, "ttl": "없음(당일 낙인)"}
    try:
        from pipeline.atoms import key_vault as kv
        for g in ("general", "ingest", "embed", "briefing"):
            keys = kv.get_keys(g)
            live = kv.get_live_keys(g)
            out["groups"][g] = {
                "total": len(keys), "live": len(live),
                "keys": [{"idx": i, "tail": key_tail(k),
                          "state": ("live" if k in live else "locked")}
                         for i, k in enumerate(keys)],
            }
        try:
            st = json.loads(Path(kv._STATE_PATH).read_text(encoding="utf-8"))
            out["state_date"] = st.get("date")
        except Exception:                 # noqa: BLE001
            out["state_date"] = None
    except Exception as e:                # noqa: BLE001
        out["error"] = str(e)[:200]
    return out


def _other_services_snapshot():
    """제미니 외 서비스 — 키 개수와 정책(개인전용/공용풀)만. 잔량은 아는 것만 정직하게."""
    rows = []
    try:
        from shopping_shorts import config
        env = os.environ

        def _count(prefix, first_no_suffix=True, cap=50):
            n = 0
            for i in range(1, cap + 1):
                name = prefix if (i == 1 and first_no_suffix) else f"{prefix}_{i}"
                if env.get(name):
                    n += 1
            return n

        rows.append({"service": "youtube", "label": "유튜브 Data API",
                     "owner": _count("YOUTUBE_API_KEY"), "policy": "공용풀(회원 합류)",
                     "note": "쿼터 %는 코드가 모름 — 403/429 반응형 로테이션만"})
        rows.append({"service": "elevenlabs", "label": "일레븐랩스 TTS",
                     "owner": 1 if getattr(config, "ELEVENLABS_API_KEY", "") else 0,
                     "policy": "개인전용(회원키·폴백없음)",
                     "note": "★키 없으면 무음 mp3로 조용히 내려앉음 — silent_fallback 이벤트로 감시"})
        rows.append({"service": "typecast", "label": "타입캐스트 TTS",
                     "owner": 1 if env.get("TYPECAST_API_KEY") else 0,
                     "policy": "개인전용", "note": "ssfm-* 프리셋만 이쪽"})
        rows.append({"service": "vmake", "label": "VMake 자막제거",
                     "owner": _count("VMAKE_API_KEY"), "policy": "개인전용",
                     "note": "60002(크레딧 소진)만 로테이션"})
        rows.append({"service": "serpapi", "label": "SerpAPI 렌즈",
                     "owner": _count("SERPAPI_KEY"), "policy": "개인전용",
                     "note": "월 250/키 — 잔량은 account.json 실조회"})
        rows.append({"service": "apify", "label": "Apify 수집",
                     "owner": _count("APIFY_TOKEN"), "policy": "회사",
                     "note": "월 $5/토큰 — 402/403 로테이션, 인덱스 파일 영속"})
        rows.append({"service": "proxy", "label": "Webshare 프록시",
                     "owner": 1 if env.get("WEBSHARE_USER") else 0, "policy": "회사",
                     "note": "★잔액 조회 API 토큰 없음 — 실패 이벤트로만 감시(과거 '계정 전멸' 오진의 뿌리)"})
    except Exception as e:                # noqa: BLE001
        rows.append({"service": "error", "label": str(e)[:200]})
    return rows


def _collector_units_snapshot():
    """수집 systemd 유닛 상태 — 인스타 수집이 failed로 죽어 있어도 아무도 모르는 사각을 화면에.
    sudo 없이 읽기만. 서버가 아니면(로컬 개발) 조용히 빈 목록."""
    units = ["shopping-shorts-instagram-collect.service",
             "shopping-shorts-instagram-discover.service"]
    out = []
    try:
        import subprocess
        r = subprocess.run(["systemctl", "is-failed", *units],
                           capture_output=True, text=True, timeout=3)
        states = (r.stdout or "").split()
        for u, s in zip(units, states):
            out.append({"unit": u.replace("shopping-shorts-", "").replace(".service", ""),
                        "failed": s == "failed", "state": s})
    except Exception as e:                # noqa: BLE001 — 서버가 아니면(로컬) 없는 게 정상
        log.debug("api_health: systemd 유닛 조회 불가(무해) %r", e)
    return out


def snapshot():
    return {
        "gemini": [_shorts_pool_snapshot(), _vault_pool_snapshot()],
        "others": _other_services_snapshot(),
        "collectors": _collector_units_snapshot(),
    }


# ── 집계 ──────────────────────────────────────────────────────────────────

def aggregates(hours=24):
    """서비스·기능(op)·outcome별 집계 + 키별 오늘 사용량 + 최근 사고 피드."""
    out = {"by_service": [], "by_op": [], "recent_fails": [], "keys_today": [],
           "hourly": [], "heartbeats": []}
    try:
        conn = _connect()
        conn.row_factory = sqlite3.Row
        try:
            since = (_utcnow() - timedelta(hours=hours)).isoformat()
            pt_start = pt_day_start_utc().isoformat()
            fail_in = ",".join("?" * len(FAIL_OUTCOMES))

            out["by_service"] = [dict(r) for r in conn.execute(
                f"SELECT service, outcome, COUNT(*) n FROM api_events "
                f"WHERE ts >= ? GROUP BY service, outcome", (since,))]

            out["by_op"] = [dict(r) for r in conn.execute(
                "SELECT COALESCE(op,'(미상)') op, service, outcome, COUNT(*) n "
                "FROM api_events WHERE ts >= ? GROUP BY op, service, outcome "
                "ORDER BY n DESC LIMIT 200", (since,))]

            out["recent_fails"] = [dict(r) for r in conn.execute(
                f"SELECT ts, service, pool, key_tail, key_idx, op, model, outcome, "
                f"http, detail, job_id, customer_id, proc FROM api_events "
                f"WHERE outcome IN ({fail_in}) ORDER BY id DESC LIMIT 80",
                FAIL_OUTCOMES)]

            # 키별 '구글 하루'(PT 자정 이후) 사용/429 — RPD 예산의 근거.
            # ★total은 _REQUEST_OUTCOMES만 센다(2026-09-01 리뷰 확정): lock 이벤트도
            #   키를 싣고 기록되므로 COUNT(*)면 일일소진 429 1건이 실패+잠금 2행으로
            #   잡혀 사고날일수록 예산이 부풀었다 — 관측판이 답할 질문을 스스로 왜곡.
            req_in = ",".join("?" * len(_REQUEST_OUTCOMES))
            out["keys_today"] = [dict(r) for r in conn.execute(
                f"SELECT service, pool, key_tail, "
                f"SUM(CASE WHEN outcome='ok' THEN 1 ELSE 0 END) ok, "
                f"SUM(CASE WHEN outcome IN ('rpm','quota') THEN 1 ELSE 0 END) rpm, "
                f"SUM(CASE WHEN outcome='rpd' THEN 1 ELSE 0 END) rpd, "
                f"SUM(CASE WHEN outcome='auth_dead' THEN 1 ELSE 0 END) dead, "
                f"SUM(CASE WHEN outcome IN ({req_in}) THEN 1 ELSE 0 END) total "
                f"FROM api_events WHERE ts >= ? AND key_tail IS NOT NULL "
                f"GROUP BY service, pool, key_tail ORDER BY total DESC LIMIT 300",
                (*_REQUEST_OUTCOMES, pt_start))]

            out["hourly"] = [dict(r) for r in conn.execute(
                f"SELECT substr(ts, 1, 13) hour_utc, "
                f"SUM(CASE WHEN outcome='ok' THEN 1 ELSE 0 END) ok, "
                f"SUM(CASE WHEN outcome IN ({fail_in}) THEN 1 ELSE 0 END) fail "
                f"FROM api_events WHERE ts >= ? GROUP BY hour_utc ORDER BY hour_utc",
                (*FAIL_OUTCOMES, since))]

            out["heartbeats"] = [dict(r) for r in conn.execute(
                "SELECT proc, pid, ts, detail FROM api_heartbeats ORDER BY proc, pid")]
        finally:
            conn.close()
    except Exception as e:                # noqa: BLE001
        out["error"] = str(e)[:300]
    return out


# ── 판정 — 맨 위 한 줄 (ops.html 철학: 답 먼저, 근거는 아래) ─────────────────

def verdict(snap=None, agg=None):
    """지금 상태 한 줄 + 처방. danger가 새로 켜지면 ops_alert로 사람에게 민다."""
    if not _enabled():                           # 기록을 껐으면 묵은 이벤트로 경보하지 않는다(리뷰 13)
        return {"level": "ok", "msg": "관측이 꺼져 있습니다(API_HEALTH=0) — 판정 없음",
                "problems": [], "warns": []}
    snap = snap or snapshot()
    agg = agg or aggregates(hours=1)
    problems, warns = [], []
    try:
        # ① 최근 1시간 실패 비율(서비스별) — silent_fallback은 1건이라도 danger
        fails = {}
        oks = {}
        for row in agg.get("by_service", []):
            svc = row.get("service")
            if row.get("outcome") == OUT_OK:
                oks[svc] = oks.get(svc, 0) + row.get("n", 0)
            elif row.get("outcome") in FAIL_OUTCOMES:
                fails[svc] = fails.get(svc, 0) + row.get("n", 0)
            if row.get("outcome") == OUT_SILENT and row.get("n", 0) > 0:
                problems.append(f"{svc}: 무음 폴백 {row['n']}건 — 고객이 무음 영상을 받았다")
            if row.get("outcome") == OUT_AUTH and row.get("n", 0) > 0:
                problems.append(f"{svc}: 죽은 키 호출 {row['n']}건 — .env에서 제거 필요")
        for svc, f in fails.items():
            tot = f + oks.get(svc, 0)
            if tot >= 10 and f / tot > 0.5:
                problems.append(f"{svc}: 최근 1시간 실패율 {round(100 * f / tot)}% ({f}/{tot}건)")
            elif tot >= 10 and f / tot > 0.2:
                warns.append(f"{svc}: 최근 1시간 실패율 {round(100 * f / tot)}%")

        # ② 제미니 풀 잔량
        for pool in snap.get("gemini", []):
            if pool.get("error"):
                warns.append(f"{pool.get('name', '?')}: 스냅샷 실패({pool['error'][:60]})")
                continue
            if pool.get("pool") == "shorts":
                total, live = pool.get("total", 0), pool.get("live", 0)
                if total and live == 0:
                    problems.append("쇼핑쇼츠 제미니 풀 전멸(살아있는 키 0개)")
                elif total and live / total < 0.3:
                    warns.append(f"쇼핑쇼츠 제미니 풀 잔여 {live}/{total}개")
            else:
                for g, d in (pool.get("groups") or {}).items():
                    if d.get("total") and d.get("live") == 0:
                        warns.append(f"vault {g} 그룹 전멸(0/{d['total']}) — TTL 없어 내일까지 잠김")

        # ③ 수집 유닛
        for c in snap.get("collectors", []):
            if c.get("failed"):
                warns.append(f"수집 유닛 죽음: {c['unit']}")
    except Exception as e:                # noqa: BLE001
        warns.append(f"판정 일부 실패: {str(e)[:80]}")

    if problems:
        level, msg = "danger", " / ".join(problems[:3])
    elif warns:
        level, msg = "warn", " / ".join(warns[:3])
    else:
        level, msg = "ok", "모든 API가 정상 동작 중입니다."

    if level == "danger":
        try:
            from shopping_shorts import ops_alert
            ops_alert.raise_alert("api_health_danger", "[API관측판] " + problems[0],
                                  " / ".join(problems)[:500])
        except Exception as e:            # noqa: BLE001 — 경보 실패가 판정을 막으면 안 된다
            log.warning("api_health: danger 경보 실패(무시) %r", e)
    return {"level": level, "msg": msg, "problems": problems, "warns": warns}


# ── RPD 예산 — "모자라지 않은가"에 숫자로 답한다 ───────────────────────────

# 무료티어 키당 일일 요청 수. 모델·티어가 바뀌면 여기만 고쳐라(0순위-B).
RPD_PER_KEY = int(os.environ.get("GEMINI_RPD_PER_KEY", "500"))


def budget(snap=None, agg=None):
    """제미니: 오늘(구글 하루) 태운 요청 vs 키 수 × RPD. 소진 예상 시각까지."""
    snap = snap or snapshot()
    agg = agg or aggregates()
    try:
        # ★키 수는 풀 합산이 아니라 tail 전역 dedup(2026-09-01 리뷰 확정): 회원 키는
        #   refresh가 SHORTS·vault 양쪽에 합류시켜 합산하면 같은 물리 키가 2번 세어져
        #   cap이 부풀고(회원 44키면 +22,000건) 소진 임박이 '여유'로 보인다.
        #   구글 RPD는 키(프로젝트) 단위 — 두 풀에 있어도 500은 한 번뿐이다.
        tails = set()
        for pool in snap.get("gemini", []):
            if pool.get("pool") == "shorts":
                for k in (pool.get("keys") or []):
                    tails.add(k.get("tail"))
            else:
                for d in (pool.get("groups") or {}).values():
                    for k in (d.get("keys") or []):
                        tails.add(k.get("tail"))
        tails.discard(None)
        n_keys = len(tails)
        cap = n_keys * RPD_PER_KEY
        used = sum(r.get("total", 0) for r in agg.get("keys_today", [])
                   if r.get("service") == "gemini")
        start = pt_day_start_utc()
        elapsed_h = max(0.25, (_utcnow() - start).total_seconds() / 3600)
        rate = used / elapsed_h
        left_h = ((cap - used) / rate) if (rate > 0 and cap > used) else None
        return {
            "keys": n_keys, "cap": cap, "used": used,
            "used_pct": round(100 * used / cap, 1) if cap else None,
            "rate_per_h": round(rate, 1),
            "exhaust_in_h": round(left_h, 1) if left_h is not None else None,
            "keys_needed_for_today": (max(0, -(-int(rate * 24) // RPD_PER_KEY) - n_keys)
                                      if rate > 0 else 0),
            "window_start_utc": start.isoformat(),
        }
    except Exception as e:                # noqa: BLE001
        return {"error": str(e)[:200]}
