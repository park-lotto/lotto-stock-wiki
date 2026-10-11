"""후기 게시판·무료 자료실 — 주소(관제 179).

app.py 가 register() 를 한 번 부른다. 권한 판단은 전부 board.py 를 **부른다** — 여기 새로 적지 않는다.

★게시판 주소는 로그인 관문(_auth_guard)을 통째로 지나온다(board.is_board_path) — 열람이 공개라서다.
  그래서 request.state.customer_id 가 안 채워진다. 신분은 _viewer() 한 곳에서 쿠키를 직접 검증해 만든다.
"""
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from shopping_shorts import board
from shopping_shorts import board_store as bs

MEDIA_DIR = Path(__file__).parent / "data" / "board_media"
_STATIC = Path(__file__).parent / "static"
_NOCACHE = {"Cache-Control": "no-cache, must-revalidate"}
_PAGE = 20
_TITLE_MAX, _BODY_MAX = 80, 5000
ADMIN_NICK = "운영자"


def _err(status, msg, **extra):
    return JSONResponse(status_code=status, content={"ok": False, "error": msg, **extra})


def _poster(src: Path, dest: Path):
    """영상 첫 장면 1장. 실패하면 False — 사유는 로그에 남긴다(썸네일 없이도 글은 올라간다)."""
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "0.5", "-i", str(src),
                        "-frames:v", "1", "-vf", "scale=480:-2", str(dest)],
                       check=True, timeout=60)
        return dest.exists() and dest.stat().st_size > 0
    except Exception as e:      # noqa: BLE001
        print(f"[board] 썸네일 실패(글은 올라감): {e!r}", file=sys.stderr)
        return False


def register(app, *, db_path, auth_on, verify_session, is_admin, send_media, alert=None):
    """db_path · auth_on 은 **부를 때마다 읽는 함수**다(테스트가 app 모듈 값을 바꾼다)."""

    def _db():
        return db_path()

    def _dir():
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        return MEDIA_DIR

    def _viewer(request):
        if not auth_on():
            return board.viewer(0, True)             # 인증 없는 로컬 = 사장님(_auth_guard 와 같은 규약)
        cid = verify_session(request.cookies.get("dash_auth"))
        if cid is None:
            return board.viewer(None, False)
        return board.viewer(cid, is_admin(cid))

    def _nick_of(v):
        return bs.nick_get(_db(), v["cid"]) or (ADMIN_NICK if v["admin"] else None)

    def _notify(kind, title, detail=""):
        if alert is None:
            return
        try:
            alert(kind, title, detail)
        except Exception as e:      # noqa: BLE001 — 알림 실패로 글쓰기를 막지 않는다
            print(f"[board] 알림 실패: {e!r}", file=sys.stderr)

    def _file_out(f):
        url = "/api/board/%s/%d" % ("download" if f["kind"] == "file" else "media", f["id"])
        return {"id": f["id"], "kind": f["kind"], "name": f["orig_name"], "size": f["size"], "url": url}

    def _post_out(p, files, nicks, v, full=False):
        shown = [f for f in files if not f["hidden"]]
        thumb = next((f for f in files if f["kind"] == "image"), None)
        d = {"id": p["id"], "board": p["board"], "title": p["title"],
             "nick": nicks.get(p["author_cid"]) or ADMIN_NICK,
             "status": p["status"], "pinned": bool(p["pinned"]),
             "created_at": p["created_at"], "mine": board.can_edit(p, v),
             "thumb": "/api/board/media/%d" % thumb["id"] if thumb else "",
             "has_video": any(f["kind"] == "video" for f in shown),
             "n_files": sum(1 for f in shown if f["kind"] == "file"),
             "excerpt": (p["body"] or "")[:120]}
        if full:
            d["body"] = p["body"] or ""
            d["files"] = [_file_out(f) for f in shown]
            d["can_download"] = board.can_download(p, v)
        return d

    # ── 화면 ─────────────────────────────────────────────────────────────
    @app.get("/board")
    def page_board():
        return FileResponse(str(_STATIC / "board.html"), media_type="text/html; charset=utf-8",
                            headers=_NOCACHE)

    @app.get("/api/board/me")
    def api_board_me(request: Request):
        v = _viewer(request)
        pending = len(bs.post_list_status(_db(), "pending")) if v["admin"] else 0
        return {"ok": True, "logged": v["logged"], "admin": v["admin"],
                "nick": _nick_of(v) if v["logged"] else None, "pending": pending}

    # ── 읽기 ─────────────────────────────────────────────────────────────
    @app.get("/api/board/list")
    def api_board_list(request: Request, board_: str = Query("review", alias="board"), page: int = 1):
        if board_ not in board.BOARDS:
            return _err(422, "없는 칸이에요")
        v = _viewer(request)
        posts = [p for p in bs.post_list(_db(), board_) if board.can_view(p, v)]
        total = len(posts)
        page = max(1, int(page))
        posts = posts[(page - 1) * _PAGE: page * _PAGE]
        files = bs.files_of_many(_db(), [p["id"] for p in posts])
        nicks = bs.nick_map(_db(), [p["author_cid"] for p in posts])
        return {"ok": True, "total": total, "page": page, "per_page": _PAGE,
                "can_write": board.can_write(board_, v),
                "items": [_post_out(p, files[p["id"]], nicks, v) for p in posts]}

    @app.get("/api/board/post/{post_id}")
    def api_board_post(post_id: int, request: Request):
        v = _viewer(request)
        p = bs.post_get(_db(), post_id)
        if not board.can_view(p, v):
            return _err(404, "없는 글이에요")       # 승인 전·숨김 글은 있는지조차 알리지 않는다
        nicks = bs.nick_map(_db(), [p["author_cid"]])
        return {"ok": True, "post": _post_out(p, bs.files_of(_db(), post_id), nicks, v, full=True)}

    def _file_and_post(file_id):
        f = bs.file_get(_db(), file_id)
        p = bs.post_get(_db(), f["post_id"]) if f else None
        return f, p

    @app.get("/api/board/media/{file_id}")
    def api_board_media(file_id: int, request: Request):
        """영상·사진·미리듣기. 내려받는 파일(kind=file)은 여기로 안 나간다."""
        f, p = _file_and_post(file_id)
        if not f or f["kind"] == "file" or not board.can_view(p, _viewer(request)):
            return _err(404, "없는 파일이에요")
        path = _dir() / f["stored_name"]
        if not path.is_file():
            print(f"[board] 첨부 {file_id} 가 디스크에 없다: {path}", file=sys.stderr)
            return _err(404, "없는 파일이에요")
        return send_media(str(path), request, board.mime_of(f["kind"], f["stored_name"]))

    @app.get("/api/board/download/{file_id}")
    def api_board_download(file_id: int, request: Request):
        v = _viewer(request)
        f, p = _file_and_post(file_id)
        if not f or f["kind"] != "file" or not board.can_view(p, v):
            return _err(404, "없는 파일이에요")
        if not board.can_download(p, v):
            return _err(401, "무료 가입하면 바로 받을 수 있어요", need_login=True)
        path = _dir() / f["stored_name"]
        if not path.is_file():
            print(f"[board] 첨부 {file_id} 가 디스크에 없다: {path}", file=sys.stderr)
            return _err(404, "없는 파일이에요")
        return send_media(str(path), request, board.mime_of("file", f["stored_name"]),
                          filename=f["orig_name"])

    # ── 쓰기 ─────────────────────────────────────────────────────────────
    @app.post("/api/board/nick")
    def api_board_nick(request: Request, body: dict):
        v = _viewer(request)
        if not v["logged"]:
            return _err(401, "로그인이 필요해요", need_login=True)
        nick = str(body.get("nick") or "").strip()
        if not board.valid_nick(nick):
            return _err(422, "닉네임은 2~12자(한글·영문·숫자)로 정해 주세요")
        if nick == ADMIN_NICK and not v["admin"]:
            return _err(409, "이미 쓰는 닉네임이에요")
        if not bs.nick_set(_db(), v["cid"], nick):
            return _err(409, "이미 쓰는 닉네임이에요")
        return {"ok": True, "nick": nick}

    def _clean(body):
        title = str(body.get("title") or "").strip()
        text = str(body.get("body") or "").strip()
        if not title or len(title) > _TITLE_MAX:
            return None, None, _err(422, "제목은 1~%d자로 적어 주세요" % _TITLE_MAX)
        if len(text) > _BODY_MAX:
            return None, None, _err(422, "본문은 %d자까지 쓸 수 있어요" % _BODY_MAX)
        return title, text, None

    @app.post("/api/board/post")
    def api_board_post_new(request: Request, body: dict):
        v = _viewer(request)
        b = str(body.get("board") or "")
        if b not in board.BOARDS:
            return _err(422, "없는 칸이에요")
        if not v["logged"]:
            return _err(401, "로그인이 필요해요", need_login=True)
        if not board.can_write(b, v):
            return _err(403, "이 칸은 운영자만 쓸 수 있어요")
        title, text, bad = _clean(body)
        if bad:
            return bad
        if b == "review":
            if not body.get("consent"):
                return _err(422, "공개 동의에 체크해 주세요")
            if not _nick_of(v):
                return _err(409, "닉네임을 먼저 정해 주세요", need_nick=True)
        # 자료실은 운영자 글이라 바로 공개. 후기는 운영자가 쓴 것도 승인 대기를 거친다 — 규칙을 가르지 않는다.
        status = "approved" if b == "free" else "pending"
        pid = bs.post_add(_db(), b, v["cid"], title, text, status, bool(body.get("consent")))
        if b == "review" and not v["admin"]:
            _notify("board_new_review", "새 후기가 승인을 기다려요", "%s — /board 승인 대기 탭" % title)
        return {"ok": True, "id": pid, "status": status}

    @app.post("/api/board/post/{post_id}")
    def api_board_post_edit(post_id: int, request: Request, body: dict):
        v = _viewer(request)
        p = bs.post_get(_db(), post_id)
        if not board.can_view(p, v) or not board.can_edit(p, v):
            return _err(404, "없는 글이에요")
        title, text, bad = _clean(body)
        if bad:
            return bad
        fields = {"title": title, "body": text}
        if p["board"] == "review" and not v["admin"]:
            fields["status"] = "pending"            # 고친 후기는 다시 승인을 받는다
        bs.post_update(_db(), post_id, **fields)
        return {"ok": True, "status": fields.get("status", p["status"])}

    def _unlink(names):
        for n in names:
            try:
                (_dir() / n).unlink(missing_ok=True)
            except OSError as e:
                print(f"[board] 파일 삭제 실패 {n}: {e!r}", file=sys.stderr)

    @app.delete("/api/board/post/{post_id}")
    def api_board_post_delete(post_id: int, request: Request):
        v = _viewer(request)
        p = bs.post_get(_db(), post_id)
        if not board.can_view(p, v) or not board.can_edit(p, v):
            return _err(404, "없는 글이에요")
        _unlink(bs.post_delete(_db(), post_id))
        return {"ok": True}

    @app.delete("/api/board/file/{file_id}")
    def api_board_file_delete(file_id: int, request: Request):
        v = _viewer(request)
        f, p = _file_and_post(file_id)
        if not f or not board.can_view(p, v) or not board.can_edit(p, v):
            return _err(404, "없는 파일이에요")
        bs.file_delete(_db(), file_id)
        _unlink([f["stored_name"]])
        return {"ok": True}

    @app.post("/api/board/upload")
    async def api_board_upload(request: Request, post_id: int = Form(...), kind: str = Form(...),
                               file: UploadFile = File(...)):
        """첨부 1개. 크기는 청크로 누적하며 잰다(통째로 읽은 뒤 재면 방어가 안 된다)."""
        v = _viewer(request)
        if not v["logged"]:
            return _err(401, "로그인이 필요해요", need_login=True)
        p = bs.post_get(_db(), post_id)
        if not board.can_view(p, v) or not board.can_edit(p, v):
            return _err(404, "없는 글이에요")
        have = {}
        for f in bs.files_of(_db(), post_id):
            if not f["hidden"]:
                have[f["kind"]] = have.get(f["kind"], 0) + 1
        used = bs.used_bytes(_db())
        name = file.filename or ""
        ok, status, why = board.accept_upload(p["board"], kind, name, 0, used, have)
        if not ok:
            return _err(status, why)
        token = uuid.uuid4().hex
        ext = Path(name).suffix.lower()
        part = _dir() / (token + ".part")           # 끝까지 받은 뒤에만 진짜 이름이 된다
        total = 0
        try:
            with open(part, "wb") as out:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    ok, status, why = board.accept_upload(p["board"], kind, name, total, used, have)
                    if not ok:
                        break
                    out.write(chunk)
        except Exception:
            part.unlink(missing_ok=True)
            raise
        if ok and total == 0:
            ok, status, why = False, 422, "빈 파일이에요"
        if not ok:
            part.unlink(missing_ok=True)
            if status == 413 and used + total > board.MAX_TOTAL_BYTES:
                _notify("board_disk_full", "후기·자료실 저장 공간이 찼어요",
                        "board_media 사용 %d바이트 / 상한 %d" % (used, board.MAX_TOTAL_BYTES))
            return _err(status, why)
        stored = token + ext
        part.rename(_dir() / stored)
        fid = bs.file_add(_db(), post_id, kind, Path(name).name[:200], stored, total)
        if kind == "video":
            poster = _dir() / (token + "_poster.jpg")
            if _poster(_dir() / stored, poster):
                bs.file_add(_db(), post_id, "image", "poster.jpg", poster.name,
                            poster.stat().st_size, hidden=1)
        return {"ok": True, "file": _file_out(bs.file_get(_db(), fid))}

    # ── 관리 ─────────────────────────────────────────────────────────────
    @app.get("/api/board/admin/pending")
    def api_board_admin_pending(request: Request):
        v = _viewer(request)
        if not v["admin"]:
            return _err(403, "운영자만 볼 수 있어요")
        posts = bs.post_list_status(_db(), "pending")
        files = bs.files_of_many(_db(), [p["id"] for p in posts])
        nicks = bs.nick_map(_db(), [p["author_cid"] for p in posts])
        return {"ok": True, "items": [_post_out(p, files[p["id"]], nicks, v) for p in posts]}

    @app.post("/api/board/admin/act")
    def api_board_admin_act(request: Request, body: dict):
        v = _viewer(request)
        if not v["admin"]:
            return _err(403, "운영자만 할 수 있어요")
        p = bs.post_get(_db(), int(body.get("id") or 0))
        if not p:
            return _err(404, "없는 글이에요")
        act = body.get("act")
        if act == "approve":
            bs.post_update(_db(), p["id"], status="approved", approved_at=bs._now())
        elif act == "hide":
            bs.post_update(_db(), p["id"], status="hidden")
        elif act == "pin":
            bs.post_update(_db(), p["id"], pinned=1)
        elif act == "unpin":
            bs.post_update(_db(), p["id"], pinned=0)
        else:
            return _err(422, "모르는 동작이에요")
        return {"ok": True, "post": bs.post_get(_db(), p["id"])}
