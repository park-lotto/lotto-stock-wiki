"""후기 게시판·무료 자료실 — **판단의 주인**(관제 179, 2026-10-11).

"누가 보나 · 누가 받나 · 누가 쓰나 · 무엇을 받아 주나"는 전부 여기서만 정한다(0순위-C).
목록·글 보기·영상 재생·내려받기·업로드 라우트(board_routes.py)는 이 함수들을 **부르기만** 한다.
DB·웹 프레임워크에 기대지 않는 순수 함수라 표로 시험한다(tests/test_board.py).

칸: review(회원 후기 — 회원이 쓰고 관리자 승인 뒤 누구나 본다) / free(무료 자료실 — 관리자가 쓴다).
"""
import re
from pathlib import Path

BOARDS = ("review", "free")
STATUSES = ("pending", "approved", "hidden")

MAX_TOTAL_BYTES = 30 * 1024 ** 3      # board_media 전체 상한(서버 실측 2026-10-11: 여유 104G)

# kind -> (허용 확장자→MIME, 파일 하나의 최대 바이트)
LIMITS = {
    "video": ({".mp4": "video/mp4", ".mov": "video/quicktime"}, 200 * 1024 ** 2),
    "image": ({".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp"}, 12 * 1024 ** 2),
    "audio": ({".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4"}, 30 * 1024 ** 2),
    "file": ({".zip": "application/zip", ".rar": "application/vnd.rar",
              ".7z": "application/x-7z-compressed", ".pdf": "application/pdf"}, 1024 ** 3),
}
REVIEW_KINDS = ("video", "image")     # 후기 글에 붙일 수 있는 종류
REVIEW_MAX = {"video": 1, "image": 5}

_NICK_RE = re.compile(r"^[0-9A-Za-z가-힣_\-.]{2,12}$")


def viewer(cid, admin=False):
    """요청한 사람. cid 0/None = 비로그인.
    ★사장님 계정의 고객번호가 0이라 '0=비로그인'과 겹친다 — 그래서 admin 을 따로 든다.
      관리자는 번호와 무관하게 로그인한 사람이다(logged)."""
    try:
        cid = int(cid) if cid is not None else 0
    except (TypeError, ValueError):
        cid = 0
    admin = bool(admin)
    return {"cid": cid, "admin": admin, "logged": admin or cid > 0}


def _is_author(post, v):
    return v["logged"] and int(post.get("author_cid") or 0) == v["cid"]


def can_view(post, v):
    """이 글(과 거기 붙은 영상·사진·미리듣기)을 이 사람이 볼 수 있나."""
    if not post or post.get("board") not in BOARDS:
        return False
    if v["admin"]:
        return True
    if post.get("status") == "approved":
        return True
    # 승인 전·숨김: 후기는 쓴 사람 본인만 본다("썼는데 사라졌다"로 보이지 않게).
    return post["board"] == "review" and _is_author(post, v)


def can_download(post, v):
    """이 글의 파일(팩)을 이 사람이 내려받을 수 있나 — 볼 수 있고 로그인했으면."""
    return can_view(post, v) and v["logged"]


def can_write(board, v):
    """이 칸에 새 글을 쓸 수 있나."""
    if board == "free":
        return v["admin"]
    if board == "review":
        return v["logged"]
    return False


def can_edit(post, v):
    """이 글을 고치거나 지우거나 첨부를 올릴 수 있나 — 쓴 사람 본인 또는 관리자."""
    if not post:
        return False
    return v["admin"] or _is_author(post, v)


def accept_upload(board, kind, name, size, used_bytes, have):
    """올린 파일을 받아 줄 것인가. 반환 (ok, http 상태, 사람이 읽는 사유).

    have = 그 글에 이미 붙은 첨부 수 {kind: n}. size 는 지금까지 받은 바이트(청크로 누적해 부른다).
    """
    if kind not in LIMITS:
        return False, 422, "올릴 수 없는 종류예요"
    if board == "review" and kind not in REVIEW_KINDS:
        return False, 422, "후기에는 영상과 사진만 올릴 수 있어요"
    exts, cap = LIMITS[kind]
    if Path(name or "").suffix.lower() not in exts:
        return False, 422, "올릴 수 있는 파일: " + " · ".join(e.lstrip(".") for e in exts)
    if board == "review" and int((have or {}).get(kind, 0)) >= REVIEW_MAX[kind]:
        return False, 422, ("영상은 1개만 올릴 수 있어요" if kind == "video"
                            else "사진은 %d장까지 올릴 수 있어요" % REVIEW_MAX["image"])
    if size > cap:
        return False, 413, "파일이 너무 커요(최대 %dMB)" % (cap // 1024 ** 2)
    if used_bytes + size > MAX_TOTAL_BYTES:
        return False, 413, "지금은 올릴 수 없어요. 운영자에게 알렸어요"
    return True, 200, ""


def mime_of(kind, name):
    return LIMITS[kind][0].get(Path(name or "").suffix.lower(), "application/octet-stream")


def is_board_path(path):
    """게시판 주소인가 — 로그인 관문(_auth_guard)이 이걸로 통과시킨다.
    열람이 공개라서다. 쓰기·내려받기 권한은 핸들러가 위 함수들로 직접 본다."""
    return path == "/board" or path.startswith("/api/board/")


def valid_nick(s):
    return bool(_NICK_RE.match(s or ""))
