# -*- coding: utf-8 -*-
"""컨셉 스튜디오 서버 API(관제 213) — 웹 스튜디오와 고객 PC 설치팩(MCP)을 잇는 다리.

  웹(로그인 쿠키)            POST /api/studio/link            연결 코드 발급(한 번만 보여 준다)
                             GET/POST /api/studio/settings    내 설정(컨셉별 팩 선택)
  설치팩(X-Studio-Token)     GET /api/studio/mcp/me           계정·컨셉 목록·내 설정
                             GET /api/studio/mcp/packs        팩 목록(글꼴·효과음·배경음·짤) + 지문
                             GET /api/studio/mcp/file/<종류>/<이름>   팩 파일 하나

★설치팩 요청은 로그인 쿠키가 없다 → /api/studio/mcp/ 는 로그인·등급 게이트를 건너뛰고(app.py 두 곳)
  여기서 연결 코드로 직접 가린다. 코드는 지문(sha256)만 저장한다 — 원문은 발급 순간 한 번만 보인다.
판단 주인: 컨셉 정의 = core.load_concept / 설정 합치기 = core.resolve_settings (여기서 다시 적지 않는다).
"""
import hashlib
import os
import secrets

from fastapi import APIRouter, Header, Request
from fastapi.responses import FileResponse, JSONResponse

from shopping_shorts.concept_studio import core

router = APIRouter()

_SS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FONT_DIR = os.path.join(_SS, "static", "fonts")


def _store():
    from shopping_shorts.app import DB_PATH
    from shopping_shorts.store import Store
    return Store(DB_PATH)


def _cid(request):
    return getattr(request.state, "customer_id", 0)


def _tok_key(token):
    return "studio_tok::" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _who(token):
    """연결 코드 → 고객 번호. 모르면 None."""
    if not token or len(token) < 20:
        return None
    v = _store().get_pref(_tok_key(token), customer_id=0)
    return int(v) if isinstance(v, int) or (isinstance(v, str) and v.isdigit()) else None


def _deny():
    return JSONResponse(status_code=401, content={"ok": False, "error": "연결 코드가 없거나 틀렸다 — 웹 컨셉 스튜디오에서 다시 받으세요"})


# ── 웹(로그인) ───────────────────────────────────────────────────────
@router.post("/api/studio/link")
def studio_link(request: Request):
    """연결 코드 새로 발급. 옛 코드는 바로 죽는다(한 계정 한 코드)."""
    cid = _cid(request)
    st = _store()
    old = st.get_pref("studio_token_key", customer_id=cid)
    if old:
        st.set_pref(old, None, customer_id=0)
    token = "st_" + secrets.token_urlsafe(24)
    k = _tok_key(token)
    st.set_pref(k, cid, customer_id=0)
    st.set_pref("studio_token_key", k, customer_id=cid)
    return {"ok": True, "token": token, "note": "이 코드는 지금 한 번만 보입니다. 설치팩 설정 칸에 붙여 넣으세요."}


@router.get("/api/studio/settings")
def studio_settings_get(request: Request):
    return {"ok": True, "settings": _store().get_pref("studio_settings", customer_id=_cid(request), default={}) or {},
            "concepts": core.list_concepts()}


@router.post("/api/studio/settings")
def studio_settings_set(request: Request, body: dict):
    """body: {packs: {<컨셉id>: {<칸>: 값}}} — 컨셉이 '고객이 바꿀 수 있다'고 한 칸만 남긴다."""
    packs = {}
    for cid_, sel in ((body or {}).get("packs") or {}).items():
        try:
            c = core.load_concept(cid_)
        except (KeyError, ValueError):
            continue
        allow = set(c.get("customer_can_change") or [])
        packs[cid_] = {k: v for k, v in (sel or {}).items() if k in allow}
    s = {"packs": packs}
    _store().set_pref("studio_settings", s, customer_id=_cid(request))
    return {"ok": True, "settings": s}


# ── 설치팩(연결 코드) ────────────────────────────────────────────────
@router.get("/api/studio/mcp/me")
def mcp_me(x_studio_token: str = Header(default="")):
    cid = _who(x_studio_token)
    if cid is None:
        return _deny()
    s = _store().get_pref("studio_settings", customer_id=cid, default={}) or {}
    concepts = []
    for c in core.list_concepts():
        full = core.load_concept(c["id"])
        concepts.append(dict(full, resolved=core.resolve_settings(full, s)))
    return {"ok": True, "customer_id": cid, "concepts": concepts, "settings": s}


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


_SHA_CACHE = {}


def _entry(kind, name, path):
    st = os.stat(path)
    key = (path, st.st_size, int(st.st_mtime))
    if key not in _SHA_CACHE:
        _SHA_CACHE[key] = _sha(path)
    return {"kind": kind, "name": name, "bytes": st.st_size, "sha256": _SHA_CACHE[key],
            "url": f"/api/studio/mcp/file/{kind}/{name}"}


def _pack_files():
    """{kind: {name: 절대경로}} — 내려줄 수 있는 팩 파일 전부(이 표 하나가 목록·파일 둘 다의 기준)."""
    out = {"font": {}, "sfx": {}, "bgm": {}}
    for f in sorted(os.listdir(FONT_DIR)) if os.path.isdir(FONT_DIR) else []:
        if f.lower().endswith((".ttf", ".otf")):
            out["font"][f] = os.path.join(FONT_DIR, f)
    try:
        from shopping_shorts import sfx_pack
        for pname, d in sfx_pack.list_packs():
            for s in sfx_pack.SLOTS:
                out["sfx"][f"{pname}__{s}.wav"] = os.path.join(d, s + ".wav")
    except Exception:  # noqa: BLE001 — 효과음 모듈이 없으면 그 종류만 빈다(목록에 이유 표시)
        out["sfx"] = {}
    try:
        from shopping_shorts import bgm_lib
        for t in bgm_lib.list_tracks():
            out["bgm"][t["id"] + ".mp3"] = bgm_lib.path_of(t["id"])
    except Exception:  # noqa: BLE001
        out["bgm"] = {}
    return out


@router.get("/api/studio/mcp/packs")
def mcp_packs(x_studio_token: str = Header(default="")):
    if _who(x_studio_token) is None:
        return _deny()
    files = _pack_files()
    return {"ok": True, "packs": {k: [_entry(k, n, p) for n, p in v.items()] for k, v in files.items()}}


@router.get("/api/studio/mcp/file/{kind}/{name}")
def mcp_file(kind: str, name: str, x_studio_token: str = Header(default="")):
    if _who(x_studio_token) is None:
        return _deny()
    p = _pack_files().get(kind, {}).get(name)       # 목록에 있는 이름만 — 경로 조작이 끼어들 틈이 없다
    if not p or not os.path.isfile(p):
        return JSONResponse(status_code=404, content={"ok": False, "error": "없는 파일"})
    return FileResponse(p)
