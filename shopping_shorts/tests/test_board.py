"""후기 게시판·무료 자료실(관제 179) — 판단 표 · 저장 · 신분별 API 응답.

★신분은 넷이다: 관리자(1) · 작성자(7) · 다른 회원(8) · 비로그인(쿠키 없음).
  승인 전 후기가 비로그인에게 새는지가 이 파일의 핵심이다 — 목록·글·영상 주소 **셋 다** 본다.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts import board, board_routes
from shopping_shorts import board_store as bs
from shopping_shorts.store import Store

A, U, O, N = (board.viewer(0, True), board.viewer(7, False),
              board.viewer(8, False), board.viewer(None, False))


def P(board_, status, author=7):
    return {"board": board_, "status": status, "author_cid": author}


# ── 판단 ─────────────────────────────────────────────────────────────────
def test_can_view_table():
    rows = [  # 글, 관리자, 작성자(7), 다른 회원(8), 비로그인
        (P("review", "pending"), True, True, False, False),
        (P("review", "approved"), True, True, True, True),
        (P("review", "hidden"), True, True, False, False),
        (P("free", "approved"), True, True, True, True),
        (P("free", "hidden", 0), True, False, False, False),
    ]
    for post, a, u, o, n in rows:
        assert [board.can_view(post, v) for v in (A, U, O, N)] == [a, u, o, n], post


def test_guest_is_not_author_of_admin_post():
    """사장님 고객번호가 0이라 '비로그인(0)'과 겹친다 — 비로그인이 운영자 글의 주인이 되면 안 된다."""
    post = P("review", "pending", author=0)
    assert not board.can_view(post, N) and not board.can_edit(post, N)
    assert board.can_edit(post, A)


def test_can_download_needs_login():
    post = P("free", "approved", 0)
    assert board.can_download(post, O) and board.can_download(post, A)
    assert not board.can_download(post, N)
    assert not board.can_download(P("free", "hidden", 0), O)


def test_can_write():
    assert board.can_write("review", O) and not board.can_write("review", N)
    assert board.can_write("free", A) and not board.can_write("free", O)
    assert not board.can_write("nope", A)


def test_accept_upload():
    assert board.accept_upload("review", "video", "a.mp4", 10, 0, {})[0]
    assert board.accept_upload("review", "video", "a.exe", 10, 0, {})[1] == 422
    assert board.accept_upload("review", "video", "a.mp4", 201 * 1024 ** 2, 0, {})[1] == 413
    assert board.accept_upload("review", "video", "a.mp4", 10, 0, {"video": 1})[1] == 422
    assert board.accept_upload("review", "file", "a.zip", 10, 0, {})[1] == 422
    assert board.accept_upload("free", "file", "a.zip", 10, board.MAX_TOTAL_BYTES, {})[1] == 413
    assert board.accept_upload("free", "file", "a.zip", 10, 0, {"file": 9})[0]     # 자료실은 개수 제한 없음


def test_paths_and_nick():
    assert board.is_board_path("/board") and board.is_board_path("/api/board/list")
    assert not board.is_board_path("/boarding") and not board.is_board_path("/api/boardx")
    assert board.valid_nick("숏템왕")
    assert not board.valid_nick("a") and not board.valid_nick("a b") and not board.valid_nick("x" * 13)


# ── 저장 ─────────────────────────────────────────────────────────────────
def test_store_roundtrip(tmp_path):
    db = str(tmp_path / "b.db")
    assert bs.nick_set(db, 7, "숏템왕") and not bs.nick_set(db, 8, "숏템왕")
    assert bs.nick_get(db, 7) == "숏템왕" and bs.nick_get(db, 9) is None
    pid = bs.post_add(db, "review", 7, "제목", "본문", "pending", 1)
    fid = bs.file_add(db, pid, "video", "내영상.mp4", "abc.mp4", 123)
    bs.file_add(db, pid, "image", "poster.jpg", "abc_p.jpg", 5, hidden=1)
    assert bs.post_get(db, pid)["status"] == "pending"
    assert [f["kind"] for f in bs.files_of(db, pid)] == ["video", "image"]
    assert bs.file_get(db, fid)["post_id"] == pid and bs.used_bytes(db) == 128
    bs.post_update(db, pid, status="approved", pinned=1)
    p2 = bs.post_add(db, "review", 8, "둘째", "", "approved", 1)
    assert [p["id"] for p in bs.post_list(db, "review")] == [pid, p2]      # 고정 먼저
    assert sorted(bs.post_delete(db, pid)) == ["abc.mp4", "abc_p.jpg"]
    assert bs.post_get(db, pid) is None and bs.files_of(db, pid) == []


# ── API ──────────────────────────────────────────────────────────────────
VIDEO = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40     # 영상 흉내(썸네일은 실패해도 올라간다)
ZIP = b"PK\x03\x04" + b"pack" * 500
PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 300


def _cookie(cid):
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return {"dash_auth": appmod._sign_session(cid, exp)}


ADMIN, AUTHOR, OTHER, GUEST = _cookie(1), _cookie(7), _cookie(8), {}


@pytest.fixture()
def cl(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    monkeypatch.setattr(appmod, "_is_admin", lambda cid: cid == 1)
    monkeypatch.setattr(board_routes, "MEDIA_DIR", tmp_path / "media")
    Store(db).ensure_paywall_schema()
    global ADMIN, AUTHOR, OTHER
    ADMIN, AUTHOR, OTHER = _cookie(1), _cookie(7), _cookie(8)     # 비밀값을 바꾼 뒤 다시 서명
    return TestClient(appmod.app)


def _nick(cl, who, nick):
    r = cl.post("/api/board/nick", json={"nick": nick}, cookies=who)
    assert r.status_code == 200, r.text


def _review(cl, who=None, title="내 첫 영상 후기", nick="숏템왕"):
    who = who or AUTHOR
    _nick(cl, who, nick)
    r = cl.post("/api/board/post", cookies=who,
                json={"board": "review", "title": title, "body": "조회수 터졌어요", "consent": True})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _upload(cl, who, pid, kind, name, data):
    return cl.post("/api/board/upload", cookies=who, data={"post_id": str(pid), "kind": kind},
                   files={"file": (name, data, "application/octet-stream")})


def _ids(cl, who, b="review"):
    r = cl.get("/api/board/list", params={"board": b}, cookies=who)
    assert r.status_code == 200, r.text
    return [it["id"] for it in r.json()["items"]]


def test_review_flow_visibility(cl):
    pid = _review(cl)
    up = _upload(cl, AUTHOR, pid, "video", "내영상.mp4", VIDEO)
    assert up.status_code == 200, up.text
    vurl = up.json()["file"]["url"]

    # 승인 전: 작성자·관리자만. 남에게는 목록·글·영상 주소 **셋 다** 닫혀 있어야 한다.
    for who in (GUEST, OTHER):
        assert pid not in _ids(cl, who)
        assert cl.get(f"/api/board/post/{pid}", cookies=who).status_code == 404
        assert cl.get(vurl, cookies=who).status_code == 404
    for who in (AUTHOR, ADMIN):
        assert pid in _ids(cl, who)
        assert cl.get(f"/api/board/post/{pid}", cookies=who).status_code == 200
        assert cl.get(vurl, cookies=who).content == VIDEO

    assert cl.post("/api/board/admin/act", json={"id": pid, "act": "approve"},
                   cookies=OTHER).status_code == 403
    assert cl.post("/api/board/admin/act", json={"id": pid, "act": "approve"},
                   cookies=ADMIN).status_code == 200

    # 승인 뒤: 비로그인도 본다. 영상은 올린 바이트 그대로.
    for who in (GUEST, OTHER):
        assert pid in _ids(cl, who)
        got = cl.get(f"/api/board/post/{pid}", cookies=who)
        assert got.status_code == 200 and got.json()["post"]["nick"] == "숏템왕"
        assert cl.get(vurl, cookies=who).content == VIDEO

    cl.post("/api/board/admin/act", json={"id": pid, "act": "hide"}, cookies=ADMIN)
    assert pid not in _ids(cl, GUEST)
    assert cl.get(f"/api/board/post/{pid}", cookies=GUEST).status_code == 404
    assert cl.get(vurl, cookies=GUEST).status_code == 404
    assert cl.get(f"/api/board/post/{pid}", cookies=AUTHOR).json()["post"]["status"] == "hidden"


def test_review_requires_consent_and_nick(cl):
    r = cl.post("/api/board/post", cookies=AUTHOR,
                json={"board": "review", "title": "t", "body": "", "consent": True})
    assert r.status_code == 409 and r.json()["need_nick"]
    _nick(cl, AUTHOR, "숏템왕")
    r = cl.post("/api/board/post", cookies=AUTHOR, json={"board": "review", "title": "t", "body": ""})
    assert r.status_code == 422
    r = cl.post("/api/board/nick", json={"nick": "숏템왕"}, cookies=OTHER)
    assert r.status_code == 409                                    # 남이 쓰는 이름


def test_write_requires_login(cl):
    r = cl.post("/api/board/post", json={"board": "review", "title": "t", "consent": True})
    assert r.status_code == 401
    pid = _review(cl)
    assert _upload(cl, GUEST, pid, "video", "a.mp4", VIDEO).status_code == 401
    assert cl.post("/api/board/nick", json={"nick": "손님이름"}).status_code == 401


def test_free_board_admin_only_and_download(cl):
    body = {"board": "free", "title": "효과음팩 1탄", "body": "120개"}
    assert cl.post("/api/board/post", json=body, cookies=OTHER).status_code == 403
    r = cl.post("/api/board/post", json=body, cookies=ADMIN)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    pid = r.json()["id"]
    assert _upload(cl, OTHER, pid, "file", "pack.zip", ZIP).status_code == 404     # 남의 글엔 못 올린다
    furl = _upload(cl, ADMIN, pid, "file", "효과음팩.zip", ZIP).json()["file"]["url"]
    purl = _upload(cl, ADMIN, pid, "image", "미리보기.png", PNG).json()["file"]["url"]

    # 목록·글·미리보기는 누구나.
    assert pid in _ids(cl, GUEST, "free")
    post = cl.get(f"/api/board/post/{pid}").json()["post"]
    assert post["can_download"] is False and post["n_files"] == 1
    assert cl.get(purl).content == PNG
    # 내려받기는 로그인해야. 파일은 재생 주소(media)로는 안 나간다.
    assert furl.startswith("/api/board/download/")
    r = cl.get(furl)
    assert r.status_code == 401 and r.json()["need_login"]
    assert cl.get(furl.replace("/download/", "/media/")).status_code == 404
    r = cl.get(furl, cookies=OTHER)
    assert r.status_code == 200 and r.content == ZIP
    assert "attachment" in r.headers.get("content-disposition", "")

    cl.post("/api/board/admin/act", json={"id": pid, "act": "hide"}, cookies=ADMIN)
    assert cl.get(furl, cookies=OTHER).status_code == 404
    assert cl.get(purl).status_code == 404


def test_edit_resets_pending_and_delete_removes_files(cl, tmp_path):
    pid = _review(cl)
    _upload(cl, AUTHOR, pid, "video", "a.mp4", VIDEO)
    cl.post("/api/board/admin/act", json={"id": pid, "act": "approve"}, cookies=ADMIN)
    edit = {"title": "고친 제목", "body": "고친 본문"}
    assert cl.post(f"/api/board/post/{pid}", json=edit, cookies=OTHER).status_code == 404
    r = cl.post(f"/api/board/post/{pid}", json=edit, cookies=AUTHOR)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert pid not in _ids(cl, GUEST)                              # 고친 글은 다시 승인 전

    media = tmp_path / "media"
    assert [p for p in media.iterdir() if p.suffix == ".mp4"]
    assert cl.delete(f"/api/board/post/{pid}", cookies=OTHER).status_code == 404
    assert cl.delete(f"/api/board/post/{pid}", cookies=AUTHOR).status_code == 200
    assert list(media.iterdir()) == []                             # 영상·썸네일 다 지워졌다
    assert cl.get(f"/api/board/post/{pid}", cookies=AUTHOR).status_code == 404


def test_upload_limits(cl, tmp_path):
    pid = _review(cl)
    assert _upload(cl, AUTHOR, pid, "video", "a.exe", VIDEO).status_code == 422
    assert _upload(cl, AUTHOR, pid, "file", "a.zip", ZIP).status_code == 422       # 후기엔 영상·사진만
    assert _upload(cl, AUTHOR, pid, "video", "a.mp4", b"").status_code == 422
    assert _upload(cl, AUTHOR, pid, "video", "a.mp4", VIDEO).status_code == 200
    assert _upload(cl, AUTHOR, pid, "video", "b.mp4", VIDEO).status_code == 422    # 영상은 1개
    assert not [p for p in (tmp_path / "media").iterdir() if p.suffix == ".part"]  # 거절분이 안 남는다


def test_admin_pending_list(cl):
    pid = _review(cl)
    assert cl.get("/api/board/admin/pending", cookies=AUTHOR).status_code == 403
    assert cl.get("/api/board/admin/pending").status_code == 403
    r = cl.get("/api/board/admin/pending", cookies=ADMIN)
    assert [it["id"] for it in r.json()["items"]] == [pid]
    assert cl.get("/api/board/me", cookies=ADMIN).json()["pending"] == 1
    assert cl.get("/api/board/me").json() == {"ok": True, "logged": False, "admin": False,
                                              "nick": None, "pending": 0}


def test_login_gate_untouched(cl):
    """게시판을 관문에서 통과시킨 것이 다른 주소를 열지 않았다."""
    r = cl.get("/api/outreach", follow_redirects=False)
    assert r.status_code in (401, 303, 307)
    assert cl.get("/board").status_code == 200
