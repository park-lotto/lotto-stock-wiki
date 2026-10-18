"""'클로드형' 서버 포털 — 고객 PC(로컬 MCP)가 부르는 REST 와 고객 페이지(/claude)의 판단 주인(관제 234, 숏템MCP).

설계: docs/superpowers/specs/2026-10-18-숏템MCP-design.md(§2-3·§5·§7·§8·§9) · 계약: 2026-10-18-숏템MCP-api.md.
서버는 **보여주기·설정·내려주기·라이선스 확인·이상 행동 탐지**만 한다. 제작(대본·TTS·렌더·검사) 호출은 0건.

판단 주인(각 하나 — 라우트는 부르기만, 0순위-C):
  issue_license / verify_license  라이선스 키 발급·검증(SHORTEM-L1.<cid>.<exp>.<kv>.<sig>, 서버는 키 해시만)
  license                         기기 지문 2대·회수·정지·엔진 버전
  lease                           cid 당 활성 작업 1개(TTL 180초, 하트비트 60초, 다른 기기 거절, 강제 해제)
  assets_for                      이번 작업이 **참조하는 자산만** 서명 URL(6h) — 통째로 안 준다
  pack                            그 job 의 발급 목록 안 자산만 재발급
  preview                         견본(preview/ 접두사)만, Range 거부, 10분 토큰 — 원본(assets/)과 저장소 접두사가 다르다
  anomaly_check                   §7-9 A1~A10 탐지 → allow/throttle/deny/alert
  asset_url                       원본 서명 URL 만들기 — 객체 저장소(R2)로 바꿀 때 **이 함수 하나만** 바뀐다

★DB 는 숏템메이커 sqlite 하나(Store 연결 방식 그대로). 표는 여기서 CREATE TABLE IF NOT EXISTS — store.py 는 안 고친다.
★키·토큰 원문은 로그·DB 어디에도 안 남긴다(해시·앞 12자만).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote

from shopping_shorts import channel_profile

log = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# 고정 단계 이름(9) — PC 진행 표시·lease step_name 공용(api.md §8)
STEP_NAMES = ("소재", "분석", "대본", "장면 계획", "음성", "렌더", "검사", "확인", "완료")
LICENSE_DAYS = 365
LEASE_TTL = 180
HEARTBEAT_EVERY = 60
ASSET_URL_TTL = 6 * 3600
PREVIEW_TOKEN_TTL = 600
DEVICES_MAX = 2
PROFILES_MAX = 10
ASSET_KINDS = ("font", "sfx", "bgm", "template", "meme")
# 견본 종류 → 허용 확장자(앞이 우선). 원본 kind 와 별개로 목소리·통과작도 견본만 있다.
PREVIEW_KINDS = {"font": ("png",), "sfx": ("mp3",), "bgm": ("mp3",), "template": ("jpg", "png"),
                 "meme": ("jpg",), "voice": ("mp3",), "result": ("mp4",)}
PREVIEW_MEDIA = {"png": "image/png", "jpg": "image/jpeg", "mp3": "audio/mpeg", "mp4": "video/mp4"}
# 노출 검사 공용 목록(api.md §9) — 페이지 응답(/api/claude/me/*)에 이 키가 있으면 안 된다
PAGE_FORBIDDEN_KEYS = ("bench", "strengths", "frame", "path", "commit", "evidence", "slug_bench")

# 탐지 임계값 초기안(설계 §7-9, 개정 4 D 확정) — 설정 키 claude_anomaly_thresholds(JSON)로 배포 없이 덮어쓴다
ANOMALY_DEFAULTS = {
    "a1_countries": 2,          # 24h 안 서로 다른 국가 수
    "a2_warn": 5, "a2_suspend": 10,          # 24h 동시 실행 시도
    "a3_per_day": 200, "a3_ratio": 3.0, "a3_min_calls": 10, "a3_throttle_per_min": 10,
    "a4_per_min": 60, "a4_per_hour": 600, "a4_repeat": 3, "a4_suspend_sec": 3600,
    "a5_suspend": 10,           # 하루 목록 밖 자산 요청
    "a6_alert": 3,              # 24h 회수된 키 사용
    "a7_per_day": 3, "a7_days": 7,
    "a9_warn": 3, "a9_alert": 5,             # 30일 기기 교체
    "a10_per_day": 500, "a10_full_min": 10, "a10_bad_per_day": 10, "a10_repeat": 3,
    "suspend_sec": 30 * 86400,  # 사람이 풀 때까지(관리자 경보 '해제')
}

RULE_TITLE = {
    "A1": "키 공유 의심(다른 국가·등록 안 된 기기)", "A2": "동시 실행 시도", "A3": "자산 긁어가기 의심",
    "A4": "짧은 시간 대량 요청", "A5": "고른 프리셋 밖 자산 요청", "A6": "회수된 키 사용",
    "A7": "하트비트 없이 끊긴 작업 반복", "A8": "엔진 버전 낮음·위조", "A9": "기기 교체 잦음", "A10": "견본 긁어가기 의심",
}

_HTTP = {"no_key": 401, "bad_key": 401, "expired": 401, "revoked": 403, "suspended": 403, "device_unknown": 403,
         "device_limit": 403, "engine_old": 403, "not_in_plan": 403, "not_entitled": 403,
         "busy_other_device": 409, "lease_lost": 409, "rate_limited": 429, "disabled": 503, "bad_request": 400}

_FP_RE = re.compile(r"^[0-9a-f]{64}$")
_JOB_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_PID_RE = re.compile(r"^[\w\-.가-힣]{1,80}$")
_SEMVER = re.compile(r"^(\d{1,4})\.(\d{1,4})\.(\d{1,6})$")


class PortalError(Exception):
    """고객용 실패 하나 — {"ok": false, "code", "msg", "retry_after"?} 로 나간다."""

    def __init__(self, code, msg, retry_after=None):
        super().__init__(msg)
        self.code, self.msg, self.retry_after = code, msg, retry_after
        self.status = _HTTP.get(code, 400)

    def body(self):
        b = {"ok": False, "code": self.code, "msg": self.msg}
        if self.retry_after is not None:
            b["retry_after"] = int(self.retry_after)
        return b


def call(fn, *a, **kw):
    """라우트 공용 — (HTTP 상태, 본문). 라우트는 이것만 부르고 판단하지 않는다."""
    try:
        return 200, fn(*a, **kw)
    except PortalError as e:
        return e.status, e.body()


def _now():
    return int(time.time())


def store_dir() -> Path:
    return Path(os.environ.get("CLAUDE_STORE_DIR") or (HERE / "data" / "claude_store"))


def channel_root() -> Path:
    """장부(channel/브랜드.json…)와 프리셋 틀(channel/<slug>/preset/**)이 있는 저장소 뿌리."""
    return Path(os.environ.get("CLAUDE_CHANNEL_ROOT") or ROOT)


# ── 비밀값 ──────────────────────────────────────────────────────────────
def _base_secret() -> bytes:
    """CLAUDE_LICENSE_SECRET 이 있으면 그것, 없으면 세션 서명키(DASH_SECRET)에서 파생. 소스에 기본값을 박지 않는다."""
    env = (os.environ.get("CLAUDE_LICENSE_SECRET") or "").strip()
    if env:
        return env.encode()
    import sys
    app = sys.modules.get("shopping_shorts.app")
    dash = getattr(app, "DASH_SECRET", "") if app else ""
    dash = dash or (os.environ.get("DASH_SECRET") or "").strip()
    if not dash:
        try:
            from shopping_shorts.config import DB_PATH
            dash = (Path(DB_PATH).parent / ".session_secret").read_text(encoding="utf-8").strip()
        except OSError:
            dash = ""
    if not dash:
        raise PortalError("disabled", "서버 준비가 끝나지 않았습니다(비밀값 없음)")
    return hmac.new(dash.encode(), b"shortem-claude-license-v1", hashlib.sha256).digest()


def _k(label: str) -> bytes:
    return hmac.new(_base_secret(), label.encode(), hashlib.sha256).digest()


def _mac(label, msg) -> str:
    return hmac.new(_k(label), msg.encode(), hashlib.sha256).hexdigest()


# ── DB ──────────────────────────────────────────────────────────────────
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS claude_licenses (
        cid INTEGER PRIMARY KEY, kv INTEGER NOT NULL DEFAULT 0, gkv INTEGER NOT NULL DEFAULT 0,
        key_hash TEXT, issued INTEGER, expires INTEGER, plan TEXT DEFAULT 'claude', entitled_json TEXT,
        revoked INTEGER NOT NULL DEFAULT 0, suspended_until INTEGER NOT NULL DEFAULT 0, suspend_rule TEXT)""",
    """CREATE TABLE IF NOT EXISTS claude_devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cid INTEGER NOT NULL, fp_hash TEXT NOT NULL, dev_id TEXT NOT NULL,
        name TEXT, slot INTEGER, created INTEGER, last_seen INTEGER, removed INTEGER NOT NULL DEFAULT 0)""",
    "CREATE INDEX IF NOT EXISTS idx_claude_devices_cid ON claude_devices(cid, removed)",
    """CREATE TABLE IF NOT EXISTS claude_leases (
        cid INTEGER PRIMARY KEY, lease_id TEXT NOT NULL, fp_hash TEXT NOT NULL, device_name TEXT,
        job_id TEXT NOT NULL, step_name TEXT, acquired INTEGER, expires INTEGER)""",
    """CREATE TABLE IF NOT EXISTS claude_license_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, cid INTEGER, device_hash TEXT, ip TEXT,
        country TEXT, route TEXT, kind TEXT, asset_ids TEXT, detail TEXT)""",
    "CREATE INDEX IF NOT EXISTS idx_claude_llog ON claude_license_log(cid, kind, ts)",
    """CREATE TABLE IF NOT EXISTS claude_lease_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, cid INTEGER, device_hash TEXT, action TEXT,
        job_id TEXT, lease_id TEXT, step_name TEXT, result TEXT)""",
    "CREATE INDEX IF NOT EXISTS idx_claude_lslog ON claude_lease_log(cid, ts)",
    """CREATE TABLE IF NOT EXISTS claude_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, cid INTEGER, rule TEXT, level TEXT,
        count INTEGER, detail TEXT, notified INTEGER DEFAULT 0, resolved INTEGER NOT NULL DEFAULT 0, resolved_at INTEGER)""",
    "CREATE INDEX IF NOT EXISTS idx_claude_alerts ON claude_alerts(cid, rule, ts)",
    """CREATE TABLE IF NOT EXISTS claude_profiles (
        id TEXT PRIMARY KEY, customer_id INTEGER NOT NULL, name TEXT, preset_id TEXT, options_json TEXT,
        version INTEGER NOT NULL DEFAULT 1, created INTEGER, updated INTEGER)""",
    "CREATE INDEX IF NOT EXISTS idx_claude_profiles_cid ON claude_profiles(customer_id)",
    """CREATE TABLE IF NOT EXISTS claude_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, cid INTEGER, kind TEXT, text TEXT, job_id TEXT)""",
    """CREATE TABLE IF NOT EXISTS claude_assets (
        id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT, sha256 TEXT NOT NULL, size INTEGER,
        preview_id TEXT, grp TEXT, meta_json TEXT, updated INTEGER)""",
    """CREATE TABLE IF NOT EXISTS claude_job_assets (
        cid INTEGER NOT NULL, job_id TEXT NOT NULL, asset_id TEXT NOT NULL, issued INTEGER,
        profile_id TEXT, profile_version INTEGER, PRIMARY KEY (cid, job_id, asset_id))""",
)
_schema_ready: set = set()
_schema_lock = threading.Lock()


def _store(store=None):
    if store is not None:
        return store
    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    return Store(DB_PATH)


def ensure_schema(store):
    key = str(Path(store.db_path).resolve())
    if key in _schema_ready:
        return
    with _schema_lock:
        if key in _schema_ready:
            return
        with _tx(store) as c:
            for sql in _SCHEMA:
                c.execute(sql)
        _schema_ready.add(key)


@contextmanager
def _tx(store, write=False):
    c = store._conn()
    shared = getattr(getattr(store, "_reuse_tl", None), "conn", None) is c
    try:
        if write and not c.in_transaction:
            c.execute("BEGIN IMMEDIATE")      # lease 처럼 읽고-쓰기가 겹치면 안 되는 곳 — 쓰기 순서를 하나로
        yield c
        c.commit()
    except BaseException:
        c.rollback()
        raise
    finally:
        if not shared:
            c.close()


def _rows(c, sql, args=()):
    cur = c.execute(sql, args)
    cols = [d[0] for d in cur.description or ()]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _row(c, sql, args=()):
    r = _rows(c, sql, args)
    return r[0] if r else None


def _setting(store, key, default=""):
    try:
        v = store.get_setting(key, None)
    except Exception:      # noqa: BLE001 — 설정 조회 실패는 기본값(로그는 남긴다)
        log.warning("claude_portal: 설정 %s 조회 실패", key, exc_info=True)
        return default
    return default if v in (None, "") else v


def _thresholds(store) -> dict:
    t = dict(ANOMALY_DEFAULTS)
    raw = _setting(store, "claude_anomaly_thresholds", "")
    if raw:
        try:
            t.update({k: v for k, v in json.loads(raw).items() if k in ANOMALY_DEFAULTS})
        except (ValueError, AttributeError):
            log.warning("claude_portal: claude_anomaly_thresholds JSON 이 깨져 기본값을 쓴다")
    return t


def _gate(store, key, cid) -> bool:
    """스위치 판정은 app._setting_gate 하나(""끔·"admin"·"11,42"·"1")."""
    from shopping_shorts import app as _app
    return bool(_app._setting_gate(store, key, cid))


def _assets_on(store, cid) -> bool:
    """claude_assets_enabled 는 **킬스위치** — 비어 있으면 켬(포털 스위치를 따른다), "0/off" 면 끔, 그 밖은 _setting_gate."""
    v = str(_setting(store, "claude_assets_enabled", "")).strip().lower()
    if v == "":
        return True
    if v in ("0", "off", "false"):
        return False
    return _gate(store, "claude_assets_enabled", cid)


# ── 라이선스 키 ──────────────────────────────────────────────────────────
def _sig(cid, exp, kv) -> str:
    return _mac("license", f"{cid}|{exp}|{kv}")[:32]


def _key_hash(key: str) -> str:
    return _mac("keyhash", key)


def _gkv(store) -> int:
    try:
        return int(str(_setting(store, "license_kv", "0")).strip() or 0)
    except ValueError:
        return 0


def issue_license(cid, store=None) -> dict:
    """새 키 발급(kv+1 — 옛 키 즉시 무효). 키 원문은 반환값에만 있고 DB 엔 해시만 남는다."""
    store = _store(store)
    ensure_schema(store)
    cid = int(cid)
    now = _now()
    exp = now + LICENSE_DAYS * 86400
    with _tx(store, write=True) as c:
        row = _row(c, "SELECT kv FROM claude_licenses WHERE cid=?", (cid,))
        kv = (row["kv"] if row else 0) + 1
        key = f"SHORTEM-L1.{cid}.{exp}.{kv}.{_sig(cid, exp, kv)}"
        if row:
            c.execute("UPDATE claude_licenses SET kv=?, gkv=?, key_hash=?, issued=?, expires=?, revoked=0 WHERE cid=?",
                      (kv, _gkv(store), _key_hash(key), now, exp, cid))
        else:
            c.execute("INSERT INTO claude_licenses(cid, kv, gkv, key_hash, issued, expires) VALUES(?,?,?,?,?,?)",
                      (cid, kv, _gkv(store), _key_hash(key), now, exp))
    return {"key": key, "kv": kv, "issued": now, "expires": exp}


def _parse_key(key):
    if not key:
        raise PortalError("no_key", "라이선스 키가 없습니다 — 숏템메이커 '클로드형' 페이지에서 키를 발급하세요")
    parts = key.strip().split(".")
    if len(parts) != 5 or parts[0] != "SHORTEM-L1" or not all(p.isdigit() for p in parts[1:4]):
        raise PortalError("bad_key", "라이선스 키 형식이 올바르지 않습니다")
    cid, exp, kv = int(parts[1]), int(parts[2]), int(parts[3])
    if not hmac.compare_digest(parts[4], _sig(cid, exp, kv)):
        raise PortalError("bad_key", "라이선스 키가 올바르지 않습니다")
    return cid, exp, kv


def verify_license(key, store=None) -> dict:
    """키 → {"cid","exp","kv","issued","row"}. 위조 bad_key · 만료 expired · 옛 kv·회수·전역 kv 변경 revoked."""
    store = _store(store)
    ensure_schema(store)
    cid, exp, kv = _parse_key(key)
    with _tx(store) as c:
        row = _row(c, "SELECT * FROM claude_licenses WHERE cid=?", (cid,))
    if (not row or row["kv"] != kv or not hmac.compare_digest(row["key_hash"] or "", _key_hash(key.strip()))
            or int(row["gkv"] or 0) != _gkv(store) or row["revoked"]):
        raise PortalError("revoked", "이 라이선스 키는 더 이상 쓸 수 없습니다 — 페이지에서 새 키를 발급하세요")
    if exp < _now():
        raise PortalError("expired", "라이선스 기간이 끝났습니다")
    return {"cid": cid, "exp": exp, "kv": kv, "issued": row["issued"], "row": row}


def ctx_from_request(request, ip="") -> dict:
    """라우트 → 판단 함수로 넘기는 요청 정보(헤더만). 쿠키·본문은 안 읽는다."""
    h = request.headers
    auth = h.get("authorization") or ""
    return {"key": auth[7:].strip() if auth.lower().startswith("bearer ") else "",
            "device": (h.get("x-shortem-device") or "").strip().lower(),
            # ★HTTP 헤더는 ASCII 만 실린다 — PC 는 이름을 UTF-8 퍼센트 인코딩해 보낸다(한글 기기명)
            "device_name": re.sub(r"[\x00-\x1f<>]", "", unquote(h.get("x-shortem-device-name") or "")).strip()[:40],
            "engine": (h.get("x-shortem-engine") or "").strip(),
            "ip": ip, "country": (h.get("cf-ipcountry") or h.get("x-geo-country") or "").strip().upper()[:4],
            "referer": h.get("referer") or "", "host": h.get("host") or "", "range": h.get("range") or ""}


def _fp_hash(fp) -> str:
    return hashlib.sha256(("shortem-dev|" + fp).encode()).hexdigest()


def _semver(v):
    m = _SEMVER.match(v or "")
    return tuple(int(x) for x in m.groups()) if m else None


def _front(store, ctx, route, need_device=True):
    """PC 라우트 공통 관문: 키 → 스위치 → 탐지(속도·정지) → 지문 → 엔진 → 등록 기기. (cid, info, device_row)"""
    try:
        info = verify_license(ctx.get("key"), store)
    except PortalError as e:
        if e.code == "revoked":
            try:
                cid, _, _ = _parse_key(ctx.get("key"))
                anomaly_check(cid, {"type": "revoked_key", "route": route, **_ev(ctx)}, store=store)
            except PortalError:
                pass
        raise
    cid = info["cid"]
    if not _gate(store, "claude_portal_enabled", cid):
        raise PortalError("disabled", "클로드형 서비스가 지금 꺼져 있습니다")
    _raise_on(anomaly_check(cid, {"type": "request", "route": route, **_ev(ctx)}, store=store))
    fp = ctx.get("device") or ""
    if not _FP_RE.match(fp):
        raise PortalError("bad_request", "기기 지문이 올바르지 않습니다 — 설치팩을 다시 확인하세요")
    want = _semver(str(_setting(store, "claude_min_engine", "1.0.0")))
    have = _semver(ctx.get("engine"))
    if have is None or (want and have < want):
        anomaly_check(cid, {"type": "engine_old", "route": route, **_ev(ctx)}, store=store)
        raise PortalError("engine_old", "숏템 엔진이 오래됐습니다 — 설치팩을 새로 받아 주세요")
    dev = None
    if need_device:
        with _tx(store) as c:
            dev = _row(c, "SELECT * FROM claude_devices WHERE cid=? AND fp_hash=? AND removed=0", (cid, _fp_hash(fp)))
        if not dev:
            raise PortalError("device_unknown", "이 기기는 등록되지 않았습니다 — 먼저 '숏템 준비 점검'으로 기기를 등록하세요")
    return cid, info, dev


def _ev(ctx):
    return {"ip": ctx.get("ip", ""), "country": ctx.get("country", ""),
            "device": _fp_hash(ctx["device"])[:12] if ctx.get("device") else ""}


def _raise_on(res):
    if res["action"] in ("deny", "throttle"):
        raise PortalError(res["code"], res["msg"], res.get("retry_after"))


# ── 프리셋·장부 ──────────────────────────────────────────────────────────
def _public_preset_id(internal: str) -> str:
    """고객에게 보이는 프리셋 id — 내부 경로(벤치 채널 slug 가 들어 있다)를 그대로 안 내보낸다(§7-4 slug 비노출)."""
    return "p_" + hashlib.sha256(("preset|" + internal).encode()).hexdigest()[:10]


def presets(store=None, include_off=False) -> list:
    """channel/<slug>/preset/**/frame.json(+manifest.json) 전부. 스위치 claude_presets_off(쉼표 목록)로 끈 것은 뺀다."""
    base = channel_root() / "channel"
    off = set()
    if store is not None:
        off = {x.strip() for x in str(_setting(store, "claude_presets_off", "")).split(",") if x.strip()}
    out = []
    for fp in sorted(base.glob("*/preset/**/frame.json")):
        d = fp.parent
        if not (d / "manifest.json").exists():
            continue
        rel = d.relative_to(base).as_posix()           # sseolpulda/preset/A_흰바탕창/창아래_검정
        slug, _, style = rel.partition("/preset/")
        internal = f"{slug}/{style}"
        pid = _public_preset_id(internal)
        if not include_off and (pid in off or internal in off):
            continue
        out.append({"id": pid, "internal": internal, "slug": slug, "style": style, "dir": d})
    return out


def _preset_by_id(store, pid):
    return next((p for p in presets(store) if p["id"] == pid), None)


def _style_label(style: str) -> str:
    """'A_흰바탕창/창아래_검정' → '흰바탕창 · 창아래 검정' (틀 설명 문장 — 수치·좌표 없음)."""
    parts = []
    for seg in style.split("/"):
        seg = re.sub(r"^[A-Z]_", "", seg)
        parts.append(seg.replace("_", " "))
    return " · ".join(p for p in parts if p)


def _ledgers():
    from shopping_shorts import calcopy_board
    return calcopy_board.preset_home(channel_root())


def _entitled(store, cid, row=None) -> list:
    """구매한 프리셋 목록. 아직 결제 연동 전이라 entitled_json 이 비면 켜져 있는 프리셋 전부."""
    allp = [p["id"] for p in presets(store)]
    raw = (row or {}).get("entitled_json")
    if raw:
        try:
            want = set(json.loads(raw))
            return [p for p in allp if p in want]
        except ValueError:
            log.warning("claude_portal: cid %s entitled_json 이 깨졌다", cid)
    return allp


# ── 자산 카탈로그·저장소 ──────────────────────────────────────────────────
def put_blob(path: Path) -> tuple:
    """원본 파일 → assets/<sha256>(내용주소). (sha256, size). 같은 내용은 한 번만 저장."""
    data = Path(path).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    dst = store_dir() / "assets" / sha
    if not dst.exists() or dst.stat().st_size != len(data):
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, dst)
    return sha, len(data)


def upsert_asset(store, aid, kind, name, sha, size, grp="", preview_id=None, meta=None):
    ensure_schema(store)
    with _tx(store, write=True) as c:
        c.execute("INSERT INTO claude_assets(id, kind, name, sha256, size, preview_id, grp, meta_json, updated) "
                  "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, name=excluded.name, "
                  "sha256=excluded.sha256, size=excluded.size, preview_id=excluded.preview_id, grp=excluded.grp, "
                  "meta_json=excluded.meta_json, updated=excluded.updated",
                  (aid, kind, name, sha, size, preview_id, grp, json.dumps(meta or {}, ensure_ascii=False), _now()))


def _assets(store, kind=None) -> list:
    ensure_schema(store)
    with _tx(store) as c:
        if kind:
            return _rows(c, "SELECT * FROM claude_assets WHERE kind=? ORDER BY id", (kind,))
        return _rows(c, "SELECT * FROM claude_assets ORDER BY kind, id")


def _voices() -> list:
    try:
        return json.loads((HERE / "assets" / "voice_presets.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.warning("claude_portal: voice_presets.json 을 못 읽었다", exc_info=True)
        return []


def catalog(store) -> dict:
    """옵션 검증용 id 집합 — 서버 자산 id 만 옵션 값이 된다."""
    rows = _assets(store)
    cat = {"font": set(), "sfx_pack": set(), "bgm": set(), "template": set(), "meme_kind": set(),
           "voice": {v.get("preset_id") for v in _voices() if v.get("preset_id")}}
    for r in rows:
        k, rest = r["id"].split(":", 1)
        if k == "font":
            cat["font"].add(rest)
        elif k == "sfx" and r.get("grp"):
            cat["sfx_pack"].add(r["grp"])
        elif k == "bgm":
            cat["bgm"].add(rest)
        elif k == "template":
            cat["template"].add(rest)
        elif k == "meme" and r.get("grp"):
            cat["meme_kind"].add(r["grp"])
    return cat


def asset_url(asset: dict, cid, job_id, now=None) -> tuple:
    """원본 서명 URL — **이 함수 하나**가 정한다. 지금은 서버 디스크 + /api/claude/blob/<토큰>(HMAC, 6h, 1 URL 1 파일).
    객체 저장소(R2/S3)를 붙이면 여기만 그 서명 URL 로 바꾼다. (url, 만료)"""
    exp = (now or _now()) + ASSET_URL_TTL
    payload = json.dumps({"s": asset["sha256"], "a": asset["id"], "c": int(cid), "j": job_id, "e": exp},
                         separators=(",", ":"), ensure_ascii=False).encode()
    b = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"/api/claude/blob/{b}.{_mac('blob', b)[:32]}", exp


def blob(token: str) -> dict:
    """서명 URL → 원본 파일. 위조·만료면 403. Range 허용(원본 다운로드 경로 — 견본과 다른 길)."""
    try:
        b, sig = token.rsplit(".", 1)
    except ValueError:
        raise PortalError("bad_request", "주소가 올바르지 않습니다") from None
    if not hmac.compare_digest(sig, _mac("blob", b)[:32]):
        raise PortalError("not_in_plan", "주소가 올바르지 않습니다")
    try:
        d = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)))
    except ValueError:
        raise PortalError("bad_request", "주소가 올바르지 않습니다") from None
    if int(d.get("e") or 0) < _now():
        raise PortalError("expired", "주소 유효 시간이 지났습니다 — 다시 받아 주세요")
    sha = str(d.get("s") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise PortalError("bad_request", "주소가 올바르지 않습니다")
    f = store_dir() / "assets" / sha
    if not f.exists():
        raise PortalError("not_in_plan", "자산 파일이 서버에 없습니다")
    return {"file": f, "name": str(d.get("a") or sha).split(":")[-1].split("/")[-1], "media_type": "application/octet-stream"}


def _refs_of(merged: dict, store) -> list:
    """합본이 **실제로 참조하는** 자산 id(순서 유지·중복 없음) — 글꼴(틀이 그리는 것)·효과음 팩 파일·곡·템플릿."""
    opts = merged.get("options") or {}
    refs = [f"font:{f}" for f in channel_profile.fonts_of(merged.get("frame"))]
    pack = opts.get("sfx_pack")
    if pack:
        refs += [r["id"] for r in _assets(store, "sfx") if r.get("grp") == pack]
    tr = (opts.get("bgm") or {}).get("track")
    if tr and tr != "none":
        refs.append(f"bgm:{tr}")
    tpl = opts.get("template")
    if tpl and tpl != "none":
        refs.append(f"template:{tpl}")
    return list(dict.fromkeys(refs))


def _strip_internal(x):
    """규칙에서 근거·측정 원값·경로를 뺀다(고객 PC 로는 계산에 쓰는 값만)."""
    drop = {"why", "evidence", "bench", "sources", "source", "variable_stats", "strengths", "measured_at", "notes",
            "unknown", "from", "path", "commit", "made_by", "tool", "rules_path", "nearest_template"}
    if isinstance(x, dict):
        return {k: _strip_internal(v) for k, v in x.items() if k not in drop}
    if isinstance(x, list):
        return [_strip_internal(v) for v in x]
    return x


def _rules_of(pdir: Path, man: dict) -> dict:
    # 공식 문장(man["rules"])은 PC 가 쓰지 않는다 — 노하우 최소 노출(설계 §7-4)이라 보내지 않는다. 칸 역할·고정값만 간다.
    rules = {"roles": man.get("roles") or [],
             "fixed": {k: (v or {}).get("value") for k, v in (man.get("fixed") or {}).items() if isinstance(v, dict)}}
    rp = man.get("rules_path")
    if isinstance(rp, str) and rp.startswith("channel/") and ".." not in rp:
        f = channel_root() / rp
        try:
            rules["script"] = _strip_internal(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass       # 대본 규칙표가 없는 틀도 있다(틀 규칙만 간다)
    return rules


# ── license ─────────────────────────────────────────────────────────────
def license(ctx: dict, store=None) -> dict:
    """GET /api/claude/license — 확인 + 이 기기 등록(빈 칸이 있으면 자동, 2대 차면 거절·자동 교체 없음)."""
    store = _store(store)
    ensure_schema(store)
    cid, info, _ = _front(store, ctx, "license", need_device=False)
    fp = ctx["device"]
    name = ctx.get("device_name") or "이름 없는 기기"
    now = _now()
    fh = _fp_hash(fp)
    registered_now = False
    with _tx(store, write=True) as c:
        dev = _row(c, "SELECT * FROM claude_devices WHERE cid=? AND fp_hash=? AND removed=0", (cid, fh))
        live = _rows(c, "SELECT slot FROM claude_devices WHERE cid=? AND removed=0", (cid,))
        if dev:
            c.execute("UPDATE claude_devices SET last_seen=?, name=? WHERE id=?", (now, name, dev["id"]))
        elif len(live) < DEVICES_MAX:
            used = {r["slot"] for r in live}
            slot = next(s for s in range(1, DEVICES_MAX + 1) if s not in used)
            c.execute("INSERT INTO claude_devices(cid, fp_hash, dev_id, name, slot, created, last_seen) VALUES(?,?,?,?,?,?,?)",
                      (cid, fh, fp[:12], name, slot, now, now))
            dev = {"slot": slot, "name": name}
            registered_now = True
            live.append({"slot": slot})
    if not dev:
        _raise_on(anomaly_check(cid, {"type": "device_limit", "route": "license", **_ev(ctx)}, store=store))
        raise PortalError("device_limit", "기기 2대가 이미 등록돼 있습니다 — 마이페이지에서 기기 교체 후 다시 시도하세요")
    _raise_on(anomaly_check(cid, {"type": "license", "route": "license", **_ev(ctx)}, store=store))
    row = info["row"]
    return {"ok": True, "cid": cid, "plan": row.get("plan") or "claude", "expires": info["exp"],
            "device": {"id": fp[:12], "name": name, "slot": dev["slot"], "registered_now": registered_now},
            "devices_used": len(live), "devices_max": DEVICES_MAX,
            "entitled_presets": _entitled(store, cid, row),
            "profiles": [{"profile_id": p["profile_id"], "name": p["name"], "preset_id": p["preset_id"],
                          "version": p["version"]} for p in list_profiles(cid, store)],
            "min_engine": str(_setting(store, "claude_min_engine", "1.0.0")),
            "min_installer": str(_setting(store, "claude_min_installer", "1.0.0")), "server_time": _now()}


# ── lease ───────────────────────────────────────────────────────────────
def _lease_log(c, cid, fh, action, job_id, lease_id, step, result):
    c.execute("INSERT INTO claude_lease_log(ts, cid, device_hash, action, job_id, lease_id, step_name, result) "
              "VALUES(?,?,?,?,?,?,?,?)", (_now(), cid, (fh or "")[:12], action, job_id, lease_id, step, result))


def lease(ctx: dict, body: dict, store=None) -> dict:
    """POST /api/claude/lease — cid 당 활성 1개. acquire(멱등)·heartbeat·release(멱등)."""
    store = _store(store)
    ensure_schema(store)
    body = body if isinstance(body, dict) else {}
    action = body.get("action")
    job_id = str(body.get("job_id") or "")
    lease_id = str(body.get("lease_id") or "")
    step = body.get("step_name")
    if action not in ("acquire", "heartbeat", "release"):
        raise PortalError("bad_request", "action 은 acquire·heartbeat·release 중 하나입니다")
    if step is not None and step not in STEP_NAMES:
        raise PortalError("bad_request", "단계 이름이 목록에 없습니다")
    if action == "acquire" and not _JOB_RE.match(job_id):
        raise PortalError("bad_request", "job_id 가 올바르지 않습니다")
    cid, _, dev = _front(store, ctx, "lease")
    fh = dev["fp_hash"]
    now = _now()
    busy = None
    expired_old = False
    with _tx(store, write=True) as c:
        cur = _row(c, "SELECT * FROM claude_leases WHERE cid=?", (cid,))
        if cur and cur["expires"] <= now:
            _lease_log(c, cid, cur["fp_hash"], "expired", cur["job_id"], cur["lease_id"], cur["step_name"], "expired")
            c.execute("DELETE FROM claude_leases WHERE cid=?", (cid,))
            expired_old, cur = True, None
        if action == "acquire":
            if cur and cur["fp_hash"] == fh and cur["job_id"] == job_id:
                c.execute("UPDATE claude_leases SET expires=?, step_name=COALESCE(?, step_name) WHERE cid=?",
                          (now + LEASE_TTL, step, cid))
                _lease_log(c, cid, fh, "acquire", job_id, cur["lease_id"], step, "renew")
                out = {"ok": True, "lease_id": cur["lease_id"], "ttl": LEASE_TTL, "heartbeat_every": HEARTBEAT_EVERY}
            elif cur:
                busy = cur
                _lease_log(c, cid, fh, "acquire", job_id, None, step, "busy")
            else:
                lid = "ls_" + secrets.token_hex(8)
                c.execute("INSERT INTO claude_leases(cid, lease_id, fp_hash, device_name, job_id, step_name, acquired, expires) "
                          "VALUES(?,?,?,?,?,?,?,?)", (cid, lid, fh, dev.get("name"), job_id, step, now, now + LEASE_TTL))
                _lease_log(c, cid, fh, "acquire", job_id, lid, step, "ok")
                out = {"ok": True, "lease_id": lid, "ttl": LEASE_TTL, "heartbeat_every": HEARTBEAT_EVERY}
        elif action == "heartbeat":
            if cur and cur["lease_id"] == lease_id and cur["fp_hash"] == fh:
                c.execute("UPDATE claude_leases SET expires=?, step_name=COALESCE(?, step_name) WHERE cid=?",
                          (now + LEASE_TTL, step, cid))
                _lease_log(c, cid, fh, "heartbeat", cur["job_id"], lease_id, step, "ok")
                out = {"ok": True, "ttl": LEASE_TTL}
            else:
                _lease_log(c, cid, fh, "heartbeat", job_id or None, lease_id, step, "lost")
                out = None
        else:
            if cur and cur["lease_id"] == lease_id and cur["fp_hash"] == fh:
                c.execute("DELETE FROM claude_leases WHERE cid=?", (cid,))
            _lease_log(c, cid, fh, "release", job_id or (cur or {}).get("job_id"), lease_id, step, "ok")
            out = {"ok": True}
    if expired_old:
        anomaly_check(cid, {"type": "lease_expired", "route": "lease", **_ev(ctx)}, store=store)
    if busy is not None:
        _raise_on(anomaly_check(cid, {"type": "busy", "route": "lease", **_ev(ctx)}, store=store))
        wait = max(1, busy["expires"] - now)
        if busy["fp_hash"] == fh:
            raise PortalError("busy_other_device", "이 기기에서 다른 작업이 진행 중입니다 — 끝나거나 3분 뒤 다시 시도하세요", wait)
        raise PortalError("busy_other_device",
                          f"다른 기기({busy.get('device_name') or '다른 기기'})에서 작업 중입니다 — 끝나거나 3분 뒤 다시 시도하세요", wait)
    if out is None:
        raise PortalError("lease_lost", "작업 권한이 끊겼습니다(다른 곳에서 해제됐거나 3분 넘게 연락이 없었습니다) — 다시 시작하면 이어집니다")
    if action == "release":
        anomaly_check(cid, {"type": "released", "route": "lease", **_ev(ctx)}, store=store)
    return out


def force_release(cid, store=None) -> dict:
    """마이페이지 '강제 해제' — 앞 기기는 다음 하트비트에서 lease_lost 를 받는다."""
    store = _store(store)
    ensure_schema(store)
    with _tx(store, write=True) as c:
        cur = _row(c, "SELECT * FROM claude_leases WHERE cid=?", (int(cid),))
        if cur:
            c.execute("DELETE FROM claude_leases WHERE cid=?", (int(cid),))
            _lease_log(c, int(cid), cur["fp_hash"], "force_release", cur["job_id"], cur["lease_id"], cur["step_name"], "ok")
    return {"ok": True, "released": bool(cur)}


def _active_lease(c, cid):
    cur = _row(c, "SELECT * FROM claude_leases WHERE cid=?", (cid,))
    return cur if cur and cur["expires"] > _now() else None


# ── assets_for · pack ───────────────────────────────────────────────────
def _profile_row(c, cid, profile_id):
    return _row(c, "SELECT * FROM claude_profiles WHERE id=? AND customer_id=?", (profile_id, int(cid)))


def assets_for(cid, profile_id, job_request: dict, store=None) -> dict:
    """이번 작업에 필요한 것만 — 합본(channel_profile.merge) → 합본이 참조하는 자산만 서명 URL(6h).

    job_request = {"job_id", "lease_id"?, "extra"?, "device_hash"}. 유효 lease(job 일치) 필수."""
    store = _store(store)
    ensure_schema(store)
    cid = int(cid)
    job_id = str(job_request.get("job_id") or "")
    if not _JOB_RE.match(job_id):
        raise PortalError("bad_request", "job_id 가 올바르지 않습니다")
    if not _assets_on(store, cid):
        raise PortalError("disabled", "자산 내려받기가 지금 꺼져 있습니다")
    with _tx(store) as c:
        cur = _active_lease(c, cid)
        prof = _profile_row(c, cid, profile_id)
        lic = _row(c, "SELECT * FROM claude_licenses WHERE cid=?", (cid,))
    if (not cur or cur["job_id"] != job_id or cur["fp_hash"] != job_request.get("device_hash")
            or (job_request.get("lease_id") and cur["lease_id"] != job_request.get("lease_id"))):
        raise PortalError("lease_lost", "작업 권한이 없습니다 — 작업을 다시 시작하세요")
    if not prof:
        raise PortalError("bad_request", "채널 프로필을 찾을 수 없습니다 — 페이지에서 프로필을 저장하세요")
    if prof["preset_id"] not in _entitled(store, cid, lic):
        raise PortalError("not_entitled", "이 프리셋은 지금 쓸 수 없습니다")
    p = _preset_by_id(store, prof["preset_id"])
    if not p:
        raise PortalError("not_entitled", "이 프리셋은 지금 쓸 수 없습니다")
    try:
        frame = json.loads((p["dir"] / "frame.json").read_text(encoding="utf-8"))
        man = json.loads((p["dir"] / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.error("claude_portal: 프리셋 %s 틀을 못 읽었다", p["internal"], exc_info=True)
        raise PortalError("not_entitled", "이 프리셋을 지금 준비할 수 없습니다") from None
    options = json.loads(prof["options_json"] or "{}")
    merged = channel_profile.merge({"frame": frame}, channel_profile.DEFAULT_PACK, options)
    refs = _refs_of(merged, store)
    # 대본 신호어가 고른 구체 짤·효과음 — 프로필이 허용한 풀 안만
    extra = job_request.get("extra") or ""
    eff = merged["options"]
    by_id = {a["id"]: a for a in _assets(store)}
    for it in [x.strip() for x in str(extra).split(",") if x.strip()][:40]:
        a = by_id.get(it)
        ok = bool(a) and ((a["kind"] == "meme" and a.get("grp") in ((eff.get("meme_pool") or {}).get("kinds") or []))
                          or (a["kind"] == "sfx" and a.get("grp") == eff.get("sfx_pack")))
        if not ok:
            anomaly_check(cid, {"type": "out_of_plan", "route": "assets", "asset": it}, store=store)
            raise PortalError("not_in_plan", "고른 프로필 밖 자산입니다")
        if it not in refs:
            refs.append(it)
    now = _now()
    assets, missing = [], []
    for aid in refs:
        a = by_id.get(aid)
        if not a:
            missing.append(aid)
            continue
        url, _ = asset_url(a, cid, job_id, now)
        assets.append({"id": a["id"], "kind": a["kind"], "sha256": a["sha256"], "size": a["size"], "name": a["name"], "url": url})
    if missing:
        log.warning("claude_portal: cid %s job %s 참조 자산이 등록 안 됨 %s — sync_assets 를 돌려라", cid, job_id, missing)
    with _tx(store, write=True) as c:
        for a in assets:
            c.execute("INSERT OR REPLACE INTO claude_job_assets(cid, job_id, asset_id, issued, profile_id, profile_version) "
                      "VALUES(?,?,?,?,?,?)", (cid, job_id, a["id"], now, profile_id, prof["version"]))
    _raise_on(anomaly_check(cid, {"type": "assets_issued", "route": "assets", "n": len(assets)}, store=store))
    issued = int((lic or {}).get("issued") or 0)
    bundle = {"preset_id": prof["preset_id"], "profile_version": prof["version"],
              "license": {"cid": cid, "issued": issued, "mark": _mac("mark", f"{cid}|{issued}|{job_id}")[:12]},
              "frame": merged["frame"], "rules": _rules_of(p["dir"], man), "options": eff, "per_video": merged["per_video"]}
    return {"ok": True, "job": job_id, "profile_version": prof["version"], "expires": now + ASSET_URL_TTL,
            "bundle": bundle, "assets": assets, "missing": missing}


def assets(ctx: dict, profile_id, job_id, lease_id=None, extra=None, store=None) -> dict:
    """GET /api/claude/assets — 관문 뒤 assets_for."""
    store = _store(store)
    ensure_schema(store)
    cid, _, dev = _front(store, ctx, "assets")
    return assets_for(cid, profile_id, {"job_id": job_id, "lease_id": lease_id, "extra": extra,
                                        "device_hash": dev["fp_hash"]}, store=store)


def pack(cid, asset_id, job, store=None) -> dict:
    """그 job 의 발급 목록 안 자산만 서명 URL 재발급. 목록 밖 = not_in_plan(A5)."""
    store = _store(store)
    ensure_schema(store)
    with _tx(store) as c:
        hit = _row(c, "SELECT 1 FROM claude_job_assets WHERE cid=? AND job_id=? AND asset_id=?", (int(cid), str(job), str(asset_id)))
        a = _row(c, "SELECT * FROM claude_assets WHERE id=?", (str(asset_id),)) if hit else None
    if not a:
        _raise_on(anomaly_check(int(cid), {"type": "out_of_plan", "route": "pack", "asset": str(asset_id)}, store=store))
        raise PortalError("not_in_plan", "이번 작업 목록에 없는 자산입니다")
    url, _ = asset_url(a, cid, job)
    return {"ok": True, "asset": {"id": a["id"], "kind": a["kind"], "sha256": a["sha256"], "size": a["size"], "name": a["name"], "url": url}}


def pack_route(ctx: dict, asset_id, job, store=None) -> dict:
    store = _store(store)
    ensure_schema(store)
    cid, _, _ = _front(store, ctx, "pack")
    return pack(cid, asset_id, job, store=store)


def feedback(ctx: dict, body: dict, store=None) -> dict:
    store = _store(store)
    ensure_schema(store)
    cid, _, _ = _front(store, ctx, "feedback")
    body = body if isinstance(body, dict) else {}
    kind, text = body.get("kind"), body.get("text")
    if kind not in ("request", "bug") or not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise PortalError("bad_request", "kind 는 request·bug, text 는 1~2000자입니다")
    job = str(body.get("job_id") or "")[:64] or None
    with _tx(store, write=True) as c:
        cur = c.execute("INSERT INTO claude_feedback(ts, cid, kind, text, job_id) VALUES(?,?,?,?,?)", (_now(), cid, kind, text.strip(), job))
        fid = cur.lastrowid
    return {"ok": True, "id": fid}


# ── 견본(preview) ───────────────────────────────────────────────────────
def preview_token(cid) -> dict:
    exp = _now() + PREVIEW_TOKEN_TTL
    return {"t": f"{int(cid)}.{exp}.{_mac('preview', f'{int(cid)}|{exp}')[:24]}", "exp": exp}


def _preview_file(kind, pid):
    for ext in PREVIEW_KINDS.get(kind, ()):
        f = store_dir() / "preview" / kind / f"{pid}.{ext}"
        if f.exists():
            return f, ext
    return None, None


def _preview_total(kind) -> int:
    d = store_dir() / "preview" / kind
    exts = PREVIEW_KINDS.get(kind, ())
    return sum(1 for f in d.glob("*") if f.suffix.lstrip(".") in exts) if d.exists() else 0


def preview(cid, kind, pid, token, headers: dict, store=None) -> dict:
    """견본만(STORE/preview/<kind>/<id>.<ext>). 세션 cid·10분 토큰 둘 다, Range 거부, 다른 사이트 Referer 거부."""
    store = _store(store)
    ensure_schema(store)
    cid = int(cid)
    h = {str(k).lower(): v for k, v in (headers or {}).items()}
    if kind not in PREVIEW_KINDS or not _PID_RE.match(str(pid or "")) or ".." in str(pid):
        raise PortalError("bad_request", "견본 주소가 올바르지 않습니다")
    bad = None
    # ★브라우저 <audio>/<video> 는 첫 요청에 늘 "Range: bytes=0-"(처음부터 끝까지)를 싣는다(2026-10-18 헤드리스 크롬 실측 403).
    #   그건 통째 요청이라 받아 주고(라우트가 206 아닌 200 통째로 보낸다) — 중간부터·조각 요청만 거부한다.
    rng = str(h.get("range") or "").replace(" ", "").lower()
    if rng and rng != "bytes=0-":
        bad = "range"
    ref = h.get("referer") or ""
    if ref and h.get("host"):
        m = re.match(r"^https?://([^/]+)", ref)
        if not m or m.group(1).lower() != str(h["host"]).lower():
            bad = "referer"
    if bad:
        _raise_on(anomaly_check(cid, {"type": "preview_bad", "route": "preview", "detail": bad}, store=store))
        raise PortalError("not_in_plan", "견본은 페이지 안에서만 볼 수 있습니다")
    try:
        tc, texp, tsig = str(token or "").split(".")
        good = (int(tc) == cid and int(texp) >= _now()
                and hmac.compare_digest(tsig, _mac("preview", f"{cid}|{int(texp)}")[:24]))
    except ValueError:
        good = False
    if not good:
        raise PortalError("expired", "견본 보기 시간이 지났습니다 — 페이지를 새로 고쳐 주세요")
    _raise_on(anomaly_check(cid, {"type": "request", "route": "preview", "kind": kind, "asset": f"{kind}:{pid}"}, store=store))
    f, ext = _preview_file(kind, pid)
    if not f:
        raise PortalError("bad_request", "아직 준비되지 않은 견본입니다")
    return {"file": f, "media_type": PREVIEW_MEDIA[ext],
            "headers": {"Content-Disposition": "inline", "Cache-Control": "private, max-age=600", "Accept-Ranges": "none"}}


# ── 이상 행동 탐지(§7-9) ─────────────────────────────────────────────────
def _count(c, cid, kind, since, route=None):
    if route:
        return c.execute("SELECT COUNT(*) FROM claude_license_log WHERE cid=? AND kind=? AND route=? AND ts>=?",
                         (cid, kind, route, since)).fetchone()[0]
    return c.execute("SELECT COUNT(*) FROM claude_license_log WHERE cid=? AND kind=? AND ts>=?", (cid, kind, since)).fetchone()[0]


def _alerts_since(c, cid, rule, since, level=None):
    if level:
        return c.execute("SELECT COUNT(*) FROM claude_alerts WHERE cid=? AND rule=? AND level=? AND ts>=?",
                         (cid, rule, level, since)).fetchone()[0]
    return c.execute("SELECT COUNT(*) FROM claude_alerts WHERE cid=? AND rule=? AND ts>=?", (cid, rule, since)).fetchone()[0]


def _raise_alert(c, cid, rule, level, count, detail):
    cur = c.execute("INSERT INTO claude_alerts(ts, cid, rule, level, count, detail) VALUES(?,?,?,?,?,?)",
                    (_now(), cid, rule, level, count, detail))
    return {"id": cur.lastrowid, "cid": cid, "rule": rule, "level": level, "count": count, "detail": detail}


def _suspend(c, cid, seconds, rule):
    until = _now() + int(seconds)
    c.execute("UPDATE claude_licenses SET suspended_until=MAX(suspended_until, ?), suspend_rule=? WHERE cid=?", (until, rule, cid))


def _notify(alerts):
    """텔레그램 경보 — 요청을 기다리게 하지 않는다(뒤 줄). 실패는 삼키지 않고 로그로 남긴다."""
    if not alerts or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    lines = [f"🛡 [클로드형 경보] {a['rule']} {RULE_TITLE.get(a['rule'], '')} · cid {a['cid']} · {a['level']} · {a['count']}회 · {a['detail']}"
             for a in alerts]

    def _send():
        try:
            from shopping_shorts import notify
            if not notify.send_telegram("\n".join(lines) + "\n→ /admin '클로드형 경보'에서 확인"):
                log.warning("claude_portal: 텔레그램 경보 전송 실패(키 없음·네트워크) — DB 경보는 남아 있다: %s", lines)
        except Exception:      # noqa: BLE001 — 경보 실패가 요청을 깨면 안 된다. 대신 로그
            log.exception("claude_portal: 텔레그램 경보 전송 중 예외")
    threading.Thread(target=_send, daemon=True).start()


_prune_state = {"day": None}


def anomaly_check(cid, event: dict, store=None) -> dict:
    """판정 주인(§7-9): 이벤트를 기록하고 A1~A10 규칙으로 판정 → {"action": allow|throttle|deny|alert, code, msg, retry_after}.

    event.type: request(모든 라우트·미리보기) · license · device_limit · busy · assets_issued · out_of_plan · revoked_key ·
                lease_expired · released · engine_old · device_removed · preview_bad"""
    store = _store(store)
    ensure_schema(store)
    cid = int(cid)
    t = _thresholds(store)
    now = _now()
    typ = event.get("type") or "request"
    route = event.get("route") or typ
    res = {"action": "allow", "code": None, "msg": None}
    alerts = []

    def _deny(code, msg, retry=None, action="deny"):
        res.update({"action": action, "code": code, "msg": msg})
        if retry is not None:
            res["retry_after"] = int(retry)

    with _tx(store, write=True) as c:
        c.execute("INSERT INTO claude_license_log(ts, cid, device_hash, ip, country, route, kind, asset_ids, detail) VALUES(?,?,?,?,?,?,?,?,?)",
                  (now, cid, event.get("device", ""), event.get("ip", ""), event.get("country", ""), route, typ,
                   event.get("asset") or (str(event["n"]) if "n" in event else None), event.get("detail")))
        lic = _row(c, "SELECT suspended_until, suspend_rule FROM claude_licenses WHERE cid=?", (cid,))
        suspended = bool(lic and (lic["suspended_until"] or 0) > now)

        def _hit_suspend(rule, seconds, detail, count):
            _suspend(c, cid, seconds, rule)
            alerts.append(_raise_alert(c, cid, rule, "suspend", count, detail))
            _deny("suspended", "이상 사용이 감지돼 잠시 멈췄습니다 — 관리자 확인 뒤 풀립니다", seconds)

        if typ == "request":
            if suspended:
                _deny("suspended", "이상 사용이 감지돼 잠시 멈췄습니다 — 관리자 확인 뒤 풀립니다", lic["suspended_until"] - now)
            else:
                m1 = _count(c, cid, "request", now - 59)
                h1 = _count(c, cid, "request", now - 3599)
                if m1 > t["a4_per_min"] or h1 > t["a4_per_hour"]:
                    if not _alerts_since(c, cid, "A4", now - 60):
                        alerts.append(_raise_alert(c, cid, "A4", "throttle", m1 if m1 > t["a4_per_min"] else h1,
                                                   f"분당 {m1} · 시간당 {h1}"))
                    if _alerts_since(c, cid, "A4", now - 3600, "throttle") >= t["a4_repeat"]:
                        _hit_suspend("A4", t["a4_suspend_sec"], "속도 제한 반복", m1)
                    else:
                        _deny("rate_limited", "요청이 너무 많습니다 — 잠시 뒤 다시 시도하세요", 60, "throttle")
                elif route == "assets" and _alerts_since(c, cid, "A3", now - 86400) and \
                        _count(c, cid, "request", now - 59, "assets") > t["a3_throttle_per_min"]:
                    _deny("rate_limited", "자산 요청이 너무 많습니다 — 잠시 뒤 다시 시도하세요", 60, "throttle")
                elif route == "preview":
                    d1 = _count(c, cid, "request", now - 86400, "preview")
                    kind = event.get("kind")
                    total = _preview_total(kind) if kind else 0
                    seen = c.execute("SELECT COUNT(DISTINCT asset_ids) FROM claude_license_log WHERE cid=? AND kind='request' "
                                     "AND route='preview' AND ts>=? AND asset_ids LIKE ?", (cid, now - 86400, f"{kind}:%")).fetchone()[0] if kind else 0
                    # 전수 순차 = 짤·BGM·효과음만(설계 §8-1). 글꼴·템플릿은 고르는 화면이 한 번에 여러 장 보여 준다
                    full = kind in ("meme", "bgm", "sfx") and total >= t["a10_full_min"] and seen >= total
                    if d1 > t["a10_per_day"] or full:
                        if not _alerts_since(c, cid, "A10", now - 600):
                            alerts.append(_raise_alert(c, cid, "A10", "throttle", d1,
                                                       "24h 견본 %d개" % d1 + (f" · {kind} 전부 차례로" if full else "")))
                        if _alerts_since(c, cid, "A10", now - 86400, "throttle") >= t["a10_repeat"]:
                            _hit_suspend("A10", t["suspend_sec"], "견본 긁기 지속", d1)
                        else:
                            _deny("rate_limited", "견본을 너무 많이 열었습니다 — 내일 다시 보거나 고른 것만 보세요", 3600, "throttle")
        elif typ in ("license", "device_limit"):
            hit, detail = False, ""
            if typ == "device_limit":
                hit, detail = True, "등록 안 된 기기에서 키 사용(기기 2대 찬 상태)"
            else:
                n = c.execute("SELECT COUNT(DISTINCT country) FROM claude_license_log WHERE cid=? AND kind='request' AND route='license' "
                              "AND ts>=? AND country<>''", (cid, now - 86400)).fetchone()[0]
                if n >= t["a1_countries"]:
                    hit, detail = True, f"24h 국가 {n}곳"
            if hit:
                prior = _alerts_since(c, cid, "A1", now - 86400)
                if prior == 0:
                    alerts.append(_raise_alert(c, cid, "A1", "warn", 1, detail))
                    res["action"] = "alert"
                else:
                    _hit_suspend("A1", t["suspend_sec"], detail, prior + 1)
        elif typ == "busy":
            n = _count(c, cid, "busy", now - 86400)
            if n >= t["a2_suspend"]:
                _hit_suspend("A2", t["suspend_sec"], f"24h 동시 실행 시도 {n}회", n)
            elif n == t["a2_warn"]:
                alerts.append(_raise_alert(c, cid, "A2", "warn", n, f"24h 동시 실행 시도 {n}회"))
                res["action"] = "alert"
        elif typ == "assets_issued":
            day = c.execute("SELECT COALESCE(SUM(CAST(asset_ids AS INTEGER)),0) FROM claude_license_log WHERE cid=? AND kind='assets_issued' AND ts>=?",
                            (cid, now - 86400)).fetchone()[0]
            calls = _count(c, cid, "assets_issued", now - 7 * 86400)
            done = _count(c, cid, "released", now - 7 * 86400)
            ratio = calls / max(1, done)
            if day > t["a3_per_day"] or (calls >= t["a3_min_calls"] and ratio > t["a3_ratio"]):
                first = _row(c, "SELECT MIN(ts) AS ts FROM claude_alerts WHERE cid=? AND rule='A3' AND resolved=0", (cid,))
                if first and first["ts"] and first["ts"] <= now - 86400:
                    _hit_suspend("A3", t["suspend_sec"], f"하루 자산 {day}개 · 7일 요청/완료 {ratio:.1f}", day)
                elif not _alerts_since(c, cid, "A3", now - 86400):
                    alerts.append(_raise_alert(c, cid, "A3", "throttle", day, f"하루 자산 {day}개 · 7일 요청/완료 {ratio:.1f}"))
                    res["action"] = "alert"
        elif typ == "out_of_plan":
            n = _count(c, cid, "out_of_plan", now - 86400)
            if n >= t["a5_suspend"]:
                _hit_suspend("A5", t["suspend_sec"], f"하루 목록 밖 요청 {n}회", n)
            else:
                _deny("not_in_plan", "이번 작업 목록에 없는 자산입니다")
        elif typ == "revoked_key":
            n = _count(c, cid, "revoked_key", now - 86400)
            if n >= t["a6_alert"] and not _alerts_since(c, cid, "A6", now - 86400):
                alerts.append(_raise_alert(c, cid, "A6", "alert", n, f"24h 회수된 키 {n}회"))
            res["action"] = "deny" if n < t["a6_alert"] else "alert"
        elif typ == "lease_expired":
            n = _count(c, cid, "lease_expired", now - 86400)
            if n >= t["a7_per_day"] and not _alerts_since(c, cid, "A7", now - 86400):
                days = sum(1 for d in range(t["a7_days"])
                           if c.execute("SELECT COUNT(*) FROM claude_license_log WHERE cid=? AND kind='lease_expired' AND ts>=? AND ts<?",
                                        (cid, now - (d + 1) * 86400, now - d * 86400)).fetchone()[0] >= t["a7_per_day"])
                level = "alert" if days >= t["a7_days"] else "warn"
                alerts.append(_raise_alert(c, cid, "A7", level, n, f"하루 {n}회 끊김 · {days}일째"))
                res["action"] = "alert"
        elif typ == "engine_old":
            if not _alerts_since(c, cid, "A8", now - 86400):
                alerts.append(_raise_alert(c, cid, "A8", "warn", 1, "엔진 버전 낮음·알 수 없음"))
            res["action"] = "deny"
        elif typ == "device_removed":
            n = _count(c, cid, "device_removed", now - 30 * 86400)
            if n > t["a9_alert"]:
                _deny("suspended", "기기 교체가 너무 잦습니다 — 관리자 확인 뒤 교체됩니다")
                c.execute("DELETE FROM claude_license_log WHERE id=(SELECT MAX(id) FROM claude_license_log WHERE cid=? AND kind='device_removed')", (cid,))
                if not _alerts_since(c, cid, "A9", now - 86400, "alert"):
                    alerts.append(_raise_alert(c, cid, "A9", "alert", n, f"30일 기기 교체 {n - 1}회 + 막힌 시도"))
            elif n == t["a9_alert"]:
                alerts.append(_raise_alert(c, cid, "A9", "alert", n, f"30일 기기 교체 {n}회"))
                res["action"] = "alert"
            elif n == t["a9_warn"]:
                alerts.append(_raise_alert(c, cid, "A9", "warn", n, f"30일 기기 교체 {n}회"))
                res["action"] = "alert"
        elif typ == "preview_bad":
            n = _count(c, cid, "preview_bad", now - 86400)
            if n >= t["a10_bad_per_day"]:
                _hit_suspend("A10", t["suspend_sec"], f"하루 Range·다른 사이트 견본 요청 {n}회", n)
            else:
                _deny("not_in_plan", "견본은 페이지 안에서만 볼 수 있습니다")
    _notify([a for a in alerts if a["level"] != "throttle" or a["rule"] in ("A3", "A10")])
    res["alerts"] = alerts
    day = time.strftime("%Y-%m-%d")
    if _prune_state["day"] != day:
        _prune_state["day"] = day
        try:
            prune_logs(store)
        except sqlite3.Error:
            log.warning("claude_portal: 로그 정리 실패", exc_info=True)
    return res


def prune_logs(store=None, keep_days=365) -> dict:
    """claude_license_log·claude_lease_log 1년 보관(설계 §7-7) — 그보다 오래된 행 삭제."""
    store = _store(store)
    ensure_schema(store)
    cut = _now() - int(keep_days) * 86400
    with _tx(store, write=True) as c:
        a = c.execute("DELETE FROM claude_license_log WHERE ts<?", (cut,)).rowcount
        b = c.execute("DELETE FROM claude_lease_log WHERE ts<?", (cut,)).rowcount
    return {"license_log": a, "lease_log": b}


# ── 관리자 경보 ─────────────────────────────────────────────────────────
def list_alerts(store=None, include_resolved=False, limit=200) -> list:
    store = _store(store)
    ensure_schema(store)
    with _tx(store) as c:
        sql = "SELECT * FROM claude_alerts" + ("" if include_resolved else " WHERE resolved=0") + " ORDER BY id DESC LIMIT ?"
        rows = _rows(c, sql, (int(limit),))
    for r in rows:
        r["title"] = RULE_TITLE.get(r["rule"], r["rule"])
    return rows


def resolve_alert(alert_id, store=None) -> dict:
    """경보 해제 — 정지(suspend) 경보면 그 고객 정지도 같이 푼다(정지는 사람이 푼다)."""
    store = _store(store)
    ensure_schema(store)
    with _tx(store, write=True) as c:
        a = _row(c, "SELECT * FROM claude_alerts WHERE id=?", (int(alert_id),))
        if not a:
            return {"ok": True, "closed": 0}
        c.execute("UPDATE claude_alerts SET resolved=1, resolved_at=? WHERE id=?", (_now(), a["id"]))
        if a["level"] == "suspend":
            c.execute("UPDATE claude_licenses SET suspended_until=0, suspend_rule=NULL WHERE cid=?", (a["cid"],))
    return {"ok": True, "closed": 1, "unsuspended": a["level"] == "suspend"}


def set_revoked(cid, revoked=True, store=None) -> dict:
    store = _store(store)
    ensure_schema(store)
    with _tx(store, write=True) as c:
        n = c.execute("UPDATE claude_licenses SET revoked=? WHERE cid=?", (1 if revoked else 0, int(cid))).rowcount
    return {"ok": True, "changed": n}


# ── 프로필·고객 페이지 ───────────────────────────────────────────────────
def list_profiles(cid, store=None) -> list:
    store = _store(store)
    ensure_schema(store)
    with _tx(store) as c:
        rows = _rows(c, "SELECT * FROM claude_profiles WHERE customer_id=? ORDER BY updated DESC", (int(cid),))
    return [{"profile_id": r["id"], "name": r["name"], "preset_id": r["preset_id"], "version": r["version"],
             "options": json.loads(r["options_json"] or "{}"), "updated": r["updated"]} for r in rows]


def save_profile(cid, body: dict, store=None) -> dict:
    """POST /api/claude/me/profile — 옵션 검증(자산 id 만·모르는 키 거절) 뒤 저장, version+1."""
    store = _store(store)
    ensure_schema(store)
    cid = int(cid)
    body = body if isinstance(body, dict) else {}
    name = str(body.get("name") or "").strip()
    if not name or len(name) > 30:
        raise PortalError("bad_request", "프로필 이름은 1~30자입니다")
    pid = body.get("preset_id")
    with _tx(store) as c:
        lic = _row(c, "SELECT * FROM claude_licenses WHERE cid=?", (cid,))
    if pid not in _entitled(store, cid, lic):
        raise PortalError("not_entitled", "고를 수 없는 프리셋입니다")
    try:
        opts = channel_profile.validate(body.get("options") or {}, catalog(store))
    except channel_profile.OptionError as e:
        raise PortalError("bad_request", str(e)) from None
    now = _now()
    prof_id = body.get("profile_id")
    with _tx(store, write=True) as c:
        if prof_id:
            cur = _profile_row(c, cid, prof_id)
            if not cur:
                raise PortalError("bad_request", "프로필을 찾을 수 없습니다")
            ver = cur["version"] + 1
            c.execute("UPDATE claude_profiles SET name=?, preset_id=?, options_json=?, version=?, updated=? WHERE id=?",
                      (name, pid, json.dumps(opts, ensure_ascii=False), ver, now, prof_id))
        else:
            n = c.execute("SELECT COUNT(*) FROM claude_profiles WHERE customer_id=?", (cid,)).fetchone()[0]
            if n >= PROFILES_MAX:
                raise PortalError("bad_request", f"프로필은 {PROFILES_MAX}개까지 만들 수 있습니다")
            prof_id, ver = "cp_" + secrets.token_hex(6), 1
            c.execute("INSERT INTO claude_profiles(id, customer_id, name, preset_id, options_json, version, created, updated) "
                      "VALUES(?,?,?,?,?,?,?,?)", (prof_id, cid, name, pid, json.dumps(opts, ensure_ascii=False), ver, now, now))
    return {"ok": True, "profile_id": prof_id, "version": ver, "options": opts}


def remove_device(cid, device_id, store=None) -> dict:
    """마이페이지 기기 교체(빼기). 자동 교체는 없다 — 빼야 새 기기가 들어온다. 잦으면 A9."""
    store = _store(store)
    ensure_schema(store)
    cid = int(cid)
    with _tx(store) as c:
        dev = _row(c, "SELECT * FROM claude_devices WHERE cid=? AND dev_id=? AND removed=0", (cid, str(device_id or "")))
    if not dev:
        raise PortalError("bad_request", "기기를 찾을 수 없습니다")
    _raise_on(anomaly_check(cid, {"type": "device_removed", "route": "me/device/remove"}, store=store))
    with _tx(store, write=True) as c:
        c.execute("UPDATE claude_devices SET removed=1 WHERE id=?", (dev["id"],))
        cur = _row(c, "SELECT * FROM claude_leases WHERE cid=?", (cid,))
        if cur and cur["fp_hash"] == dev["fp_hash"]:
            c.execute("DELETE FROM claude_leases WHERE cid=?", (cid,))
    return {"ok": True}


def _installers() -> list:
    mf = store_dir() / "installers" / "manifest.json"
    try:
        d = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for it in d.get("items") or []:
        if not isinstance(it, dict) or it.get("os") not in ("win-x64", "mac-arm64", "mac-x64"):
            continue
        f = store_dir() / "installers" / Path(str(it.get("file") or "")).name
        out.append({"os": it["os"], "version": it.get("version"), "sha256": it.get("sha256"), "size": it.get("size"),
                    "ready": f.is_file(), "download": f"/api/claude/me/installer/{it['os']}" if f.is_file() else None})
    return out


def installer_file(os_id) -> dict:
    for it in json.loads((store_dir() / "installers" / "manifest.json").read_text(encoding="utf-8")).get("items") or []:
        if it.get("os") == os_id:
            f = store_dir() / "installers" / Path(str(it.get("file") or "")).name
            if f.is_file():
                return {"file": f, "name": f.name}
    raise PortalError("bad_request", "아직 준비되지 않은 설치팩입니다")


def _caption_packs() -> list:
    """자막팩 이름·설명 — static/caption-motions.js 의 /*PACKS*/ 묶음 하나가 주인(여기는 읽기만)."""
    try:
        js = (HERE / "static" / "caption-motions.js").read_text(encoding="utf-8")
        d = json.loads(js.split("/*PACKS*/")[1])
    except (OSError, IndexError, ValueError):
        log.warning("claude_portal: caption-motions.js 자막팩을 못 읽었다", exc_info=True)
        return []
    return [{"id": k, "label": v.get("label") or k, "desc": v.get("desc") or ""} for k, v in d.items()
            if k in channel_profile.CAPTION_PACKS]


def _clean_example(v):
    return re.sub(r"\s*\([^)]*\)", "", str(v or "")).strip() or None


def home(cid, store=None) -> dict:
    """GET /api/claude/me/home — 프리셋 카드(브랜드 이름만)·팩 목록(견본 id 만)·내 프로필·라이선스·기기·설치팩.
    ★페이지 응답 — PAGE_FORBIDDEN_KEYS(bench·strengths·frame·path·commit·evidence·slug_bench)·원본 서명 URL 0개."""
    store = _store(store)
    ensure_schema(store)
    cid = int(cid)
    led = _ledgers()
    brand_of = {b["slug"]: b["brand"] for b in led.get("brands") or []}

    def _pv(kind, pid):
        return str(pid) if pid is not None and _preview_file(kind, pid)[0] else None

    passed = [r for r in led.get("results") or [] if r.get("state") == "통과"]
    results = [{"n": r.get("n"), "brand": r.get("brand"), "style": r.get("style"), "seconds": r.get("seconds"),
                "date": r.get("date"), "preview": _pv("result", r.get("n"))} for r in passed]
    plist = []
    for p in presets(store):
        mine = [r["n"] for r in passed if r.get("channel") == p["slug"]]
        plist.append({"id": p["id"], "brand": brand_of.get(p["slug"]) or "숏템 프리셋", "label": _style_label(p["style"]),
                      "results": mine})
    styles = [{"name": s["name"], "desc": s.get("desc") or "", "example": _clean_example(s.get("example")),
               "audio_kinds": s.get("audio_kinds") or []} for s in led.get("styles") or []]
    rows = _assets(store)
    fonts_json = {}
    try:
        for f in json.loads((HERE / "static" / "fonts.json").read_text(encoding="utf-8")):
            fonts_json[Path(f.get("file") or "").stem.lower()] = f.get("name")
    except (OSError, ValueError):
        pass
    fonts, sfx, bgm, tpls, memes = [], {}, [], [], {}
    font_seen = set()
    for r in rows:
        meta = json.loads(r.get("meta_json") or "{}")
        k, rest = r["id"].split(":", 1)
        if k == "font":
            # 같은 파일을 가리키는 이름 둘(렌더러 이름·Cc 이름)은 한 칸만 — 고객에겐 같은 글꼴이다
            if r["sha256"] in font_seen:
                continue
            font_seen.add(r["sha256"])
            stem = Path(r["name"] or "").stem
            label = (meta.get("label") or fonts_json.get(stem.lower())
                     or re.sub(r"^\d+_", "", stem).replace("_", " ").replace("-", " ") or rest)
            fonts.append({"id": rest, "name": label, "preview": _pv("font", rest)})
        elif k == "sfx":
            g = sfx.setdefault(r["grp"], {"id": r["grp"], "files": [], "preview": _pv("sfx", r["grp"])})
            g["files"].append(meta.get("slot") or r["name"])
        elif k == "bgm":
            bgm.append({"id": rest, "title": meta.get("title") or rest, "artist": meta.get("artist") or "", "preview": _pv("bgm", rest)})
        elif k == "template":
            tpls.append({"id": rest, "name": meta.get("label") or rest, "preview": _pv("template", rest)})
        elif k == "meme":
            memes.setdefault(r["grp"], {"kind": r["grp"], "count": 0})["count"] += 1
    for m in memes.values():
        d = store_dir() / "preview" / "meme"
        m["sprites"] = sorted(f.stem for f in d.glob("*.jpg") if f.stem.startswith(f"sprite_{m['kind']}_")) if d.exists() else []
    voices = [{"id": v["preset_id"], "name": v.get("name"), "desc": v.get("one_liner") or "", "variant": v.get("variant"),
               "preview": _pv("voice", v["preset_id"])} for v in _voices() if v.get("preset_id")]
    with _tx(store) as c:
        lic = _row(c, "SELECT kv, issued, expires, revoked, suspended_until FROM claude_licenses WHERE cid=?", (cid,))
        devs = _rows(c, "SELECT dev_id, name, slot, created, last_seen FROM claude_devices WHERE cid=? AND removed=0 ORDER BY slot", (cid,))
        cur = _active_lease(c, cid)
        notes = _rows(c, "SELECT rule, level, ts FROM claude_alerts WHERE cid=? AND resolved=0 AND level IN ('warn','suspend') ORDER BY id DESC LIMIT 5", (cid,))
    lic_out = {"has_key": bool(lic and lic["kv"]), "issued": (lic or {}).get("issued"), "expires": (lic or {}).get("expires"),
               "revoked": bool(lic and lic["revoked"]), "suspended": bool(lic and (lic["suspended_until"] or 0) > _now())}
    return {"ok": True, "presets": plist, "styles": styles, "results": results,
            "packs": {"fonts": fonts, "sfx": sorted(sfx.values(), key=lambda g: g["id"]), "bgm": bgm, "templates": tpls,
                      "voices": voices, "memes": sorted(memes.values(), key=lambda m: -m["count"]),
                      "caption_packs": _caption_packs(), "caption_motions": list(channel_profile.CAPTION_MOTIONS),
                      "caption_modes": list(channel_profile.CAPTION_MODES)},
            "profiles": list_profiles(cid, store), "license": lic_out,
            "devices": [{"id": d["dev_id"], "name": d["name"], "slot": d["slot"], "last_seen": d["last_seen"]} for d in devs],
            "devices_max": DEVICES_MAX,
            "lease": ({"device": cur["device_name"], "step": cur["step_name"], "since": cur["acquired"]} if cur else None),
            "notices": [{"title": RULE_TITLE.get(n["rule"], n["rule"]), "level": n["level"], "ts": n["ts"]} for n in notes],
            "installers": _installers(), "steps": list(STEP_NAMES),
            # 그림 안내(설치→키→첫 편) — 설치팩 쪽이 static/claude_guide.html 로 넣으면 링크가 열린다
            "guide": "/static/claude_guide.html" if (HERE / "static" / "claude_guide.html").is_file() else None}


def forbidden_hits(obj, keys=PAGE_FORBIDDEN_KEYS) -> list:
    """노출 검사 — obj 안 금지 키 경로 + 원본 서명 URL 문자열. 빈 목록이어야 통과."""
    hits = []

    def walk(x, at):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in keys:
                    hits.append(f"{at}.{k}")
                walk(v, f"{at}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{at}[{i}]")
        elif isinstance(x, str) and "/api/claude/blob/" in x:
            hits.append(f"{at}=<blob url>")
    walk(obj, "$")
    return hits
