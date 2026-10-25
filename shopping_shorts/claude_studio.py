"""숏템 설정 화면 서버판(관제 266) — 회원이 프리셋을 고르고 화면·자막·소리를 단계별로 바꾸는 /claude/studio 의 판단 주인.

화면 = 회원 PC 설정 화면과 같은 파일(shortem_client/server/ui/index.html). 저장 꼴도 PC settings.json 과 같다
({current, channels: {프리셋id: {pack: 회원이 바꾼 칸만, updated}}}) — PC 가 받아 쓰면 그대로 맞는다.

판단 주인(라우트는 부르기만):
  engine_root   서버에 올린 최신 회원 PC 엔진 묶음(updates/latest.json)을 풀어 둔 곳 — 미리보기 = 고객 PC 와 같은 코드
  _Worker       엔진 preview_request 를 띄워 두고 줄마다 부른다(클릭마다 새로 띄우면 10초, 띄워 두면 0.004초 — 10-25 실측)
  pack_for      엔진 기본 팩 ← 그 프리셋 기본값(원본 영상 기준, 사장님 10-20) ← 회원이 바꾼 칸. PC local_settings.packFor 와 같은 순서
  state·select·save·reset·preview   화면 API
값 검사·미리보기 계산은 엔진(preview_request.check·preview)이 한다 — 여기 새 판단 없음.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

from shopping_shorts import claude_portal as CP

log = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORKER = ROOT / "shortem_client" / "server" / "engine_worker.py"   # 회원 PC engine_bridge 와 같은 파일
UI_FILE = ROOT / "shortem_client" / "server" / "ui" / "index.html"
# 렌더러 정적 파일(화면·글꼴만) — 회원 PC local_ui.STATIC_OK 와 같은 범위
STATIC_OK = __import__("re").compile(r"^(out|shopping_shorts/static)/[0-9A-Za-z가-힣_.\-/]+\.(html|js|css|woff2?|ttf|otf|png|jpe?g|webp|gif|svg|json)$")
_PID_RE = __import__("re").compile(r"^p_[0-9a-f]{10}$")

_SCHEMA = """CREATE TABLE IF NOT EXISTS claude_studio (
    customer_id INTEGER PRIMARY KEY, settings_json TEXT NOT NULL, updated INTEGER)"""
_schema_ok: set = set()


class StudioError(CP.PortalError):
    pass


# ── 엔진 묶음 ────────────────────────────────────────────────────────────
_engine_lock = threading.Lock()


def engine_root() -> Path:
    """미리보기에 쓸 엔진 폴더. 개발은 CLAUDE_STUDIO_ENGINE(엔진 트랙 폴더), 서버는 최신 업데이트 묶음의 engine/ 을 풀어 쓴다."""
    dev = (os.environ.get("CLAUDE_STUDIO_ENGINE") or "").strip()
    if dev:
        return Path(dev)
    up = CP.update_path()
    if not up.is_file():
        raise StudioError("disabled", "회원 PC 엔진 묶음이 서버에 아직 없습니다")
    sha = json.loads(up.read_text(encoding="utf-8"))["sha256"]
    base = CP.store_dir() / "engine"
    dst = base / sha[:12]
    if (dst / ".ok").is_file():
        return dst / "engine"
    with _engine_lock:
        if (dst / ".ok").is_file():
            return dst / "engine"
        z = CP.store_dir() / "assets" / sha
        if not z.is_file():
            raise StudioError("disabled", "회원 PC 엔진 묶음 파일이 없습니다")
        tmp = base / (sha[:12] + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(tmp, [n for n in zf.namelist() if n.startswith("engine/")])
        (tmp / ".ok").write_text(sha, encoding="utf-8")
        shutil.rmtree(dst, ignore_errors=True)
        os.replace(tmp, dst)
        for old in base.iterdir():          # 옛 판은 치운다(판마다 170MB)
            if old.is_dir() and old.name != dst.name:
                shutil.rmtree(old, ignore_errors=True)
        log.info("claude_studio: 엔진 묶음 %s 풀었다", sha[:12])
    return dst / "engine"


class _Worker:
    """엔진 상주 프로세스 하나. 죽거나 엔진 판이 바뀌면 다시 띄운다. 요청은 한 번에 하나(lock)."""

    TIMEOUT = 60

    def __init__(self):
        self.proc, self.root, self.lock = None, None, threading.Lock()

    def _start(self, root: Path):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        self.proc = subprocess.Popen([sys.executable, "-u", str(WORKER), str(root)], cwd=str(root), env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, encoding="utf-8", bufsize=1)
        first = self.proc.stdout.readline()
        if not first or not json.loads(first).get("ready"):
            raise StudioError("disabled", "미리보기 엔진을 띄우지 못했습니다")
        self.root = root

    def call(self, req: dict) -> dict:
        root = engine_root()
        with self.lock:
            for attempt in (1, 2):
                try:
                    if self.proc is None or self.proc.poll() is not None or self.root != root:
                        self._start(root)
                    self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
                    self.proc.stdin.flush()
                    line = self._readline()
                    return json.loads(line)
                except (OSError, ValueError, TimeoutError) as e:
                    log.warning("claude_studio: 엔진 워커 %d번째 실패 — 다시 띄운다: %s", attempt, e)
                    if self.proc:
                        self.proc.kill()
                    self.proc = None
            raise StudioError("disabled", "미리보기 엔진이 응답하지 않습니다")

    def _readline(self) -> str:
        out: list = []
        t = threading.Thread(target=lambda: out.append(self.proc.stdout.readline()), daemon=True)
        t.start()
        t.join(self.TIMEOUT)
        if not out or not out[0]:
            raise TimeoutError("응답 없음")
        return out[0]


WORKER_ONE = _Worker()
_cat_cache: dict = {}


def catalog() -> dict:
    root = str(engine_root())
    if _cat_cache.get("root") != root:
        r = WORKER_ONE.call({"op": "catalog"})
        if r.get("error"):
            raise StudioError("disabled", "고를 수 있는 목록을 못 읽었습니다: " + r["error"])
        _cat_cache.clear()
        _cat_cache.update(root=root, cat=r["catalog"])
    return _cat_cache["cat"]


# ── 저장 ─────────────────────────────────────────────────────────────────
def _ensure(store):
    CP.ensure_schema(store)
    key = str(Path(store.db_path).resolve())
    if key not in _schema_ok:
        with CP._tx(store) as c:
            c.execute(_SCHEMA)
        _schema_ok.add(key)


def _read(store, cid) -> dict:
    _ensure(store)
    with CP._tx(store) as c:
        r = CP._row(c, "SELECT settings_json FROM claude_studio WHERE customer_id=?", (int(cid),))
    try:
        s = json.loads(r["settings_json"]) if r else {}
    except ValueError:
        log.warning("claude_studio: cid %s 설정이 깨졌다 — 빈 설정으로 연다", cid)
        s = {}
    s.setdefault("current", None)
    s.setdefault("current_at", 0)
    s.setdefault("channels", {})
    return s


def _write(store, cid, s: dict):
    _ensure(store)
    with CP._tx(store, write=True) as c:
        c.execute("INSERT INTO claude_studio(customer_id, settings_json, updated) VALUES(?,?,?) "
                  "ON CONFLICT(customer_id) DO UPDATE SET settings_json=excluded.settings_json, updated=excluded.updated",
                  (int(cid), json.dumps(s, ensure_ascii=False), int(time.time())))


def _merge(base, over):
    """PC local_settings.merge 와 같은 깊은 합치기 — 목록·글은 통째로 바뀐다."""
    if isinstance(over, list) or over is None or not isinstance(over, dict):
        return over
    out = dict(base) if isinstance(base, dict) else {}
    for k, v in over.items():
        out[k] = _merge(out.get(k), v)
    return out


def pack_for(cat: dict, pid: str, own: dict) -> dict:
    """엔진 기본 팩 ← 프리셋 기본값(원본 영상) ← 회원이 바꾼 칸(사장님 10-20 '기본값은 모든 프리셋 원본 영상에 맞춘다')."""
    return _merge(_merge(cat["default_pack"], (cat.get("preset_defaults") or {}).get(pid) or {}), own or {})


# ── 프리셋 = 칼카피 영상 스타일(판, 사장님 10-25 '프리셋은 칼카피 영상 스타일') ──────────────
#   판 설정(엔진 tools/calcopy/hybrid/styles/*판.json — 목소리·배경음·효과음·모션·자막팩·짤)이 주인. 여기는 고객용 요약만 만든다.
#   ★벤치 채널 이름은 내보내지 않는다 — 이름·묶음은 이름표(claude_preset_names.json, 채널 slug 기준)·브랜드 장부에서.
def _styles_dir() -> Path | None:
    for d in (Path(os.environ["CLAUDE_STUDIO_STYLES"]) if os.environ.get("CLAUDE_STUDIO_STYLES") else None,
              CP.channel_root() / "tools" / "calcopy" / "hybrid" / "styles"):
        if d and d.is_dir():
            return d
    try:
        d = engine_root() / "tools" / "calcopy" / "hybrid" / "styles"
        return d if d.is_dir() else None
    except CP.PortalError:
        return None


def _preview_index() -> dict:
    try:
        return json.loads((ROOT / "out" / "assets" / "style-previews" / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def style_id(stem: str) -> str:
    import hashlib
    return "s_" + hashlib.sha1(("shortem-style|" + stem).encode()).hexdigest()[:10]


def _voice_engine(vid: str) -> str:
    return "타입캐스트" if str(vid).startswith("tc_") else "일레븐랩스" if str(vid).startswith("kr-") else ""


def style_summary(stem: str, d: dict, names: dict, brands: dict) -> dict:
    """판 하나 → 고객 카드(이름·묶음·뱃지). 뱃지 값은 판 설정을 그대로 읽는다(새 판단 없음)."""
    slug = ((d.get("bench") or {}).get("channel") or "")
    # 판 이름표(_styles, 판 파일 이름 기준)가 먼저 — 없으면 같은 채널 틀의 이름표
    nm = (names.get("_styles") or {}).get(stem) or next((v for k, v in names.items() if isinstance(v, dict) and k.split("/")[0] == slug), {})
    brand = (brands.get(slug) or {}).get("brand")
    packs = d.get("packs") or {}
    v = d.get("voice") or {}
    sfx = packs.get("sfx") or {}
    mo = packs.get("motion") or {}
    bgm = packs.get("bgm") or d.get("bgm") or {}
    badges = []
    if v.get("name"):
        badges.append({"k": "voice", "t": f"{v['name']}" + (f" · {_voice_engine(v.get('voice_id'))}" if _voice_engine(v.get("voice_id")) else "")})
    kinds = sorted({str(x) for x in (sfx.get("map") or {}).values()})
    badges.append({"k": "sfx", "t": ("효과음 " + "·".join(kinds)) if kinds else "효과음 없음", "on": bool(kinds)})
    on_mo = (mo.get("graphics") not in (None, "off")) or (mo.get("pack") not in (None, "off"))
    badges.append({"k": "motion", "t": "모션그래픽" if on_mo else "모션그래픽 없음", "on": on_mo})
    badges.append({"k": "bgm", "t": "배경음악" if bgm.get("id") else "배경음악 없음", "on": bool(bgm.get("id"))})
    if d.get("thumb_card_face"):
        badges.append({"k": "face", "t": "연예인 얼굴 썸네일", "on": True})
    sid = style_id(stem)
    shots = (_preview_index().get(sid) or {}).get("files") or []   # 실제 완성본 장면(tools/claude_portal/style_previews.py)
    return {"id": sid, "shots": [f"r/out/assets/style-previews/{f}" for f in shots], "name":(nm.get("name") if (names.get("_styles") or {}).get(stem) else None) or brand or nm.get("name") or "이름 미정",
            "group": nm.get("group") or "기타", "desc": nm.get("desc") or "", "badges": badges, "_slug": slug}


def styles(store=None) -> list:
    d = _styles_dir()
    if not d:
        return []
    names = json.loads((HERE / "claude_preset_names.json").read_text(encoding="utf-8"))
    try:
        brands = json.loads((CP.channel_root() / "channel" / "브랜드.json").read_text(encoding="utf-8")).get("brands") or {}
    except (OSError, ValueError):
        brands = {}
    out = []
    for f in sorted(d.glob("*판.json")):
        try:
            out.append(style_summary(f.stem, json.loads(f.read_text(encoding="utf-8")), names, brands))
        except (OSError, ValueError):
            log.warning("claude_studio: 판 %s 를 못 읽었다", f.name)
    order = names.get("_groups") or []
    rank = {g: i for i, g in enumerate(order)}
    return sorted(out, key=lambda s: rank.get(s["group"], len(order)))


def _style_frame_pid(store, cid, st: dict | None) -> str | None:
    """판 → 미리보기 바탕 틀(같은 채널의 프리셋 틀). ★없으면 None — 남의 틀로 대신 그리면 여러 프리셋이 같은 그림으로 보인다
    (10-25 사장님 '이상해'). 그때 화면은 완성본 견본(shots)만 보여 주고, 템플릿을 고르면 템플릿으로 그린다."""
    plist = _presets(store, cid)
    if st:
        for p in plist:
            pp = CP._preset_by_id(store, p["id"])
            if pp and pp["slug"] == st.get("_slug"):
                return p["id"]
    return None


# ── 틀 프리셋 ────────────────────────────────────────────────────────────
def _presets(store, cid) -> list:
    _ensure(store)
    with CP._tx(store) as c:
        row = CP._row(c, "SELECT entitled_json FROM claude_licenses WHERE cid=?", (int(cid),))
    out = CP.preset_names(store, CP._entitled(store, cid, row))
    # 형식 묶음 순서 = 이름표의 _groups(사장님 10-24 묶음안 순서). 묶음 없는 것은 끝 '기타'로
    order = json.loads((HERE / "claude_preset_names.json").read_text(encoding="utf-8")).get("_groups") or []
    for p in out:
        p["group"] = p.get("group") or "기타"
    rank = {g: i for i, g in enumerate(order)}
    return sorted(out, key=lambda p: rank.get(p["group"], len(order)))


def _check_pid(store, cid, pid) -> dict:
    if not _PID_RE.match(str(pid or "")):
        raise StudioError("bad_request", "프리셋을 고르세요")
    _ensure(store)
    with CP._tx(store) as c:
        row = CP._row(c, "SELECT entitled_json FROM claude_licenses WHERE cid=?", (int(cid),))
    p = CP._preset_by_id(store, pid)
    if not p or pid not in CP._entitled(store, cid, row):
        raise StudioError("not_entitled", "쓸 수 없는 프리셋입니다")
    return p


# ── 화면 API ─────────────────────────────────────────────────────────────
def state(store, cid) -> dict:
    s = _read(store, cid)
    plist = _presets(store, cid)
    cur = s["current"] if any(p["id"] == s["current"] for p in plist) else (plist[0]["id"] if plist else None)
    cat = catalog()
    own = (s["channels"].get(cur) or {}).get("pack") or {} if cur else {}
    show = {k: v for k, v in cat.items() if k not in ("default_pack", "preset_defaults")}
    full = styles(store)
    sl = [{k: v for k, v in x.items() if not k.startswith("_")} for x in full]
    cur_st = next((x for x in full if x["id"] == s.get("style")), None)
    return {"host": "server", "presets": plist, "current": cur, "pack": pack_for(cat, cur, own) if cur else None,
            "styles": sl, "style": cur_st["id"] if cur_st else None,
            "style_has_frame": bool(cur_st and _style_frame_pid(store, cid, cur_st)),
            "requests": (s.get("requests") or [])[-20:], "extra": (s.get("extras") or {}).get(cur) or {},
            "changed": own, "catalog": show, "videos": [], "stamp": (s["channels"].get(cur) or {}).get("updated", 0) if cur else 0}


def select_style(store, cid, sid) -> dict:
    """프리셋(판) 고르기 — 판을 기억하고, 미리보기 바탕 틀은 그 판 채널의 틀로 맞춘다(템플릿을 고르면 템플릿이 덮는다)."""
    st = next((x for x in styles(store) if x["id"] == sid), None)
    if not st:
        raise StudioError("bad_request", "모르는 프리셋입니다")
    s = _read(store, cid)
    fp = _style_frame_pid(store, cid, st)
    # 틀이 없는 판은 설정 칸(채널명·글꼴·템플릿)을 담을 자리만 지금 것 그대로 쓴다 — 화면은 견본 그림을 보이고 '기본 틀'은 못 고른다
    s["style"], s["current"], s["current_at"] = sid, fp or s.get("current") or ((_presets(store, cid) or [{}])[0].get("id")), _ms()
    _write(store, cid, s)
    return {"ok": True, "current": s["current"], "has_frame": bool(fp)}


TTS_EMOTIONS = ("normal", "happy", "sad", "angry", "tonedown", "toneup", "whisper")   # 타입캐스트 감정 프리셋(라이브 /api/typecast/voices emotions 실측 10-25)


def save_extra(store, cid, pid, extra) -> dict:
    """엔진 팩 밖 칸(지금은 감정 하나) — 엔진 check 가 아직 모르는 칸이라 따로 둔다. 회원 PC 엔진이 받게 되면 팩으로 옮긴다."""
    _check_pid(store, cid, pid)
    e = extra if isinstance(extra, dict) else {}
    if set(e) - {"tts_emotion"} or (e.get("tts_emotion") not in TTS_EMOTIONS):
        raise StudioError("bad_request", "모르는 값입니다")
    s = _read(store, cid)
    s.setdefault("extras", {}).setdefault(pid, {}).update(e)
    _write(store, cid, s)
    return {"ok": True}


LOOK_MAX = 400_000   # 장면꾸미기 스냅샷 한도(글자 수) — 사진·영상은 안 들어간다(그림 자리·글·색·위치만)


def save_look(store, cid, pid, snapshot) -> dict:
    """꾸미기 단계 — 장면꾸미기 화면에서 '이 영상에 적용'한 모양(snapshot)을 프리셋별로 저장. 검사 = 렌더러와 같은 scene_style.validate_snapshot."""
    _check_pid(store, cid, pid)
    if not isinstance(snapshot, dict):
        raise StudioError("bad_request", "꾸민 모양을 받지 못했습니다")
    raw = json.dumps(snapshot, ensure_ascii=False)
    if len(raw) > LOOK_MAX:
        raise StudioError("bad_request", "꾸민 모양이 너무 큽니다")
    from shopping_shorts import scene_style
    try:
        snap = scene_style.validate_snapshot(snapshot)
    except Exception as e:  # noqa: BLE001 — 고객에게 이유 한 줄
        raise StudioError("bad_request", f"꾸민 모양을 저장할 수 없습니다: {e}")
    s = _read(store, cid)
    s.setdefault("looks", {})[pid] = {"snapshot": snap, "updated": _ms()}
    _write(store, cid, s)
    return {"ok": True}


def ask(store, cid, target, text) -> dict:
    """완성본 고치기 — 회원이 화면에서 짚은 곳(target)에 '이렇게 해 달라'(text)를 남긴다. 처리는 회원 PC 의 Claude(MCP)가 한다(서버는 보관만)."""
    text = str(text or "").strip()[:500]
    if not text:
        raise StudioError("bad_request", "무엇을 고칠지 적어 주세요")
    t = target if isinstance(target, dict) else {}
    t = {k: t[k] for k in ("track", "scene", "at", "label") if k in t}
    s = _read(store, cid)
    req = {"id": f"r{_ms()}", "at": _ms(), "target": t, "text": text, "state": "대기"}
    s["requests"] = ((s.get("requests") or []) + [req])[-50:]
    _write(store, cid, s)
    return {"ok": True, "request": req}


def _ms():
    return int(time.time() * 1000)


def select(store, cid, pid) -> dict:
    _check_pid(store, cid, pid)
    s = _read(store, cid)
    s["current"], s["current_at"] = pid, _ms()
    _write(store, cid, s)
    return {"ok": True}


def save(store, cid, pid, patch) -> dict:
    _check_pid(store, cid, pid)
    if not isinstance(patch, dict):
        raise StudioError("bad_request", "바꿀 값 모양이 다릅니다")
    s = _read(store, cid)
    prev = (s["channels"].get(pid) or {}).get("pack") or {}
    cat = catalog()
    whole = pack_for(cat, pid, _merge(prev, patch))
    r = WORKER_ONE.call({"op": "check", "pack": whole})
    if r.get("error"):
        return {"ok": False, "errors": [r["error"]]}
    if r.get("errors"):
        return {"ok": False, "errors": r["errors"]}
    s["channels"][pid] = {"pack": _merge(prev, patch), "updated": _ms()}
    s["current"], s["current_at"] = pid, _ms()
    _write(store, cid, s)
    return {"ok": True, "pack": whole}


def reset(store, cid, pid) -> dict:
    """프리셋 기본값으로 — 지우지 않고 빈 칸 + 시각을 남긴다(회원 PC 가 '더 최근 것이 이긴다'로 받아 같이 되돌린다)."""
    _check_pid(store, cid, pid)
    s = _read(store, cid)
    s["channels"][pid] = {"pack": {}, "updated": _ms()}
    (s.get("looks") or {}).pop(pid, None)          # 직접 꾸민 모양도 같이 되돌린다
    _write(store, cid, s)
    return {"ok": True}


# ── 회원 PC 와 맞추기(라이선스 키로 부른다) — 프리셋마다 더 최근에 바꾼 쪽이 이긴다 ──
def sync_merge(mine: dict, theirs: dict) -> tuple:
    """두 설정을 합친다(주인 함수 하나 — PC local_settings.syncFromServer 는 이 결과를 그대로 쓴다). (합친 것, 바뀐 칸 수)"""
    out = {**mine, "current": mine.get("current"), "current_at": mine.get("current_at") or 0,   # 판(style)·지시(requests)는 웹 쪽 칸 — 그대로 둔다
           "channels": dict(mine.get("channels") or {})}
    n = 0
    for pid, ch in (theirs.get("channels") or {}).items():
        if not _PID_RE.match(str(pid)) or not isinstance(ch, dict) or not isinstance(ch.get("pack", {}), dict):
            continue
        cur = out["channels"].get(pid) or {}
        if int(ch.get("updated") or 0) > int(cur.get("updated") or 0):
            out["channels"][pid] = {"pack": ch.get("pack") or {}, "updated": int(ch.get("updated") or 0)}
            n += 1
    if _PID_RE.match(str(theirs.get("current") or "")) and int(theirs.get("current_at") or 0) > out["current_at"]:
        out["current"], out["current_at"] = theirs["current"], int(theirs["current_at"])
        n += 1
    return out, n


def pc_sync(ctx: dict, body: dict | None, store=None) -> dict:
    """GET·POST /api/claude/studio — 회원 PC 가 자기 설정을 보내면(POST) 합쳐 저장하고, 합친 결과를 돌려준다.
    PC 에서 온 칸도 엔진 check 를 통과한 것만 받는다(서버가 믿는 경계)."""
    store = CP._store(store)
    CP.ensure_schema(store)
    cid, _, _ = CP._front(store, ctx, "studio")
    mine = _read(store, cid)
    theirs = body if isinstance(body, dict) else {}
    if theirs:
        cat = catalog()
        ok_ch = {}
        for pid, ch in (theirs.get("channels") or {}).items():
            if not isinstance(ch, dict):
                continue
            r = WORKER_ONE.call({"op": "check", "pack": pack_for(cat, pid, ch.get("pack") or {})})
            if r.get("error"):     # 검사 자체가 못 돌았다 — 합치지 않는다(PC 는 합친 결과를 그대로 쓰므로 멀쩡한 PC 칸이 지워진다)
                raise StudioError("disabled", "설정 검사를 지금 못 합니다 — 이 PC 설정 그대로 갑니다")
            if not r.get("errors"):
                ok_ch[pid] = ch
            else:
                log.warning("claude_studio: cid %s PC 설정 %s 거절 — %s", cid, pid, r.get("error") or r.get("errors"))
        merged, n = sync_merge(mine, {**theirs, "channels": ok_ch})
        if n:
            _write(store, cid, merged)
        mine = merged
    return {"ok": True, "settings": mine}


def preview(store, cid, pid, patch=None) -> dict:
    """그 프리셋 틀 + 회원 설정(+아직 저장 전 patch) → 렌더러 입력(snapshot·context). 계산은 엔진 preview 그대로."""
    p = _check_pid(store, cid, pid)
    s = _read(store, cid)
    own = (s["channels"].get(pid) or {}).get("pack") or {}
    if isinstance(patch, dict):
        own = _merge(own, patch)
    r = WORKER_ONE.call({"op": "preview", "preset": str(p["dir"]), "pack": pack_for(catalog(), pid, own)})
    if r.get("error"):
        return {"error": "미리보기를 그리지 못했습니다: " + r["error"]}
    look = ((s.get("looks") or {}).get(pid) or {}).get("snapshot")
    return {"snapshot": r["snapshot"], "context": r["context"], "applied": _applied_for_member(r.get("applied") or []),
            "title": r.get("title"), "look": look}


def _applied_for_member(lines: list) -> list:
    """엔진이 적은 '바꾼 것' 줄을 회원용으로 — 벤치 원본 글('골방 | 14:25' 같은 원래 채널명)·내부 값(목소리 id·편마다 값)은 뺀다.
    (10-25 실측: 원래 줄에 벤치 채널 옛 이름과 tc_… 목소리 id 가 그대로 보였다 — 고객에게 벤치를 안 보인다는 원칙)"""
    import re
    out = []
    for s in lines:
        s = str(s)
        if s.startswith(("제작 인자", "편마다 값")):
            continue
        s = re.sub(r"'[^']*' → ", "", s)                 # '원래 글' → '새 글'  →  '새 글'
        s = re.sub(r"^(hook|body|frame)\s*", "", s)       # 틀 안 칸 이름(내부)
        out.append(s)
    return out


def static_file(rel: str) -> Path | None:
    """렌더러 정적 파일 — 엔진 묶음 안, 허용 범위만."""
    if not STATIC_OK.match(rel) or ".." in rel:
        return None
    # 엔진 묶음 먼저, 없으면 저장소(템플릿 견본 그림 out/assets/scene-style/thumbnails 는 묶음에 없고 저장소에 있다 — 10-25 실측)
    for root in (engine_root().resolve(), ROOT.resolve()):
        f = (root / rel).resolve()
        if root in f.parents and f.is_file():
            return f
    return None
