# -*- coding: utf-8 -*-
"""후기 게시판·무료 자료실 결과물 검사(관제 179) — **실제 서버**에 네 신분으로 요청해 응답을 대조한다.

    py tools/board_check.py                                    # 라이브(쿠키는 서버에서 만들어 받는다)
    py tools/board_check.py --base http://127.0.0.1:8850 --secret <DASH_SECRET>   # 로컬 서버

신분: 비로그인 · 작성자(시험 회원 A) · 다른 회원(시험 회원 B) · 관리자(0).
재는 것: 승인 전 후기가 남에게 새는가(목록·글·영상 주소 셋 다) / 승인 뒤 누구나 보는가 /
        영상·팩이 올린 바이트 그대로 나오는가(md5) / 내려받기가 로그인한 사람에게만 열리는가.
시험 글은 제목이 [점검]으로 시작하고 끝나면 지운다. 한 줄이라도 어긋나면 rc=1.

★시험 회원 번호는 실제 회원과 안 겹치는 큰 수다(회원 표에 행이 없다 = 관리자 아님·결제 무관).
"""
import argparse
import hashlib
import hmac
import os
import subprocess
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LIVE = "https://shoppingshorts.duckdns.org"
CID_A, CID_B = 990000001, 990000002
VIDEO = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 200
ZIP = b"PK\x03\x04" + os.urandom(4096)
PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 500


def _sign(secret, cid):
    exp = int(time.time()) + 3600
    p = "%d:%d" % (cid, exp)
    return p + ":" + hmac.new(secret.encode(), p.encode(), hashlib.sha256).hexdigest()


def _live_cookies():
    from tools import live_admin
    mint = (r'''set -a; . /etc/shopping-shorts.env; set +a; python3 -c "
import hmac,hashlib,os,time
e=int(time.time())+3600
for c in (0,%d,%d):
    p='%%d:%%d'%%(c,e); print(p+':'+hmac.new(os.environ['DASH_SECRET'].encode(),p.encode(),hashlib.sha256).hexdigest())"'''
            % (CID_A, CID_B))
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", live_admin.KEY, live_admin.HOST, mint],
                       capture_output=True, text=True, timeout=60)
    lines = [x for x in (r.stdout or "").strip().splitlines() if x.count(":") == 2]
    if r.returncode or len(lines) != 3:
        raise RuntimeError("쿠키를 못 만들었다: %s" % (r.stderr or r.stdout)[-300:])
    return lines


class Check:
    def __init__(self, base, cookies):
        self.base = base.rstrip("/")
        adm, a, b = cookies
        self.who = {"비로그인": {}, "작성자": {"dash_auth": a}, "다른회원": {"dash_auth": b},
                    "관리자": {"dash_auth": adm}}
        self.rows, self.made = [], []

    def req(self, who, method, path, **kw):
        with httpx.Client(cookies=self.who[who], timeout=120, follow_redirects=False) as c:
            return c.request(method, self.base + path, **kw)

    def expect(self, what, got, want):
        ok = got == want
        self.rows.append((ok, what, got, want))
        return ok

    def ids(self, who, board):
        r = self.req(who, "GET", "/api/board/list", params={"board": board})
        return [it["id"] for it in r.json().get("items", [])] if r.status_code == 200 else None

    def upload(self, who, pid, kind, name, data):
        return self.req(who, "POST", "/api/board/upload", data={"post_id": str(pid), "kind": kind},
                        files={"file": (name, data, "application/octet-stream")})

    def run(self):
        md5 = lambda b: hashlib.md5(b).hexdigest()      # noqa: E731
        E = self.expect
        # 쓰기 권한
        E("비로그인 후기 쓰기", self.req("비로그인", "POST", "/api/board/post",
                                  json={"board": "review", "title": "[점검] x", "consent": True}).status_code, 401)
        E("회원 자료실 쓰기", self.req("다른회원", "POST", "/api/board/post",
                                json={"board": "free", "title": "[점검] x"}).status_code, 403)
        self.req("작성자", "POST", "/api/board/nick", json={"nick": "점검용A"})
        E("동의 없이 후기 쓰기", self.req("작성자", "POST", "/api/board/post",
                                   json={"board": "review", "title": "[점검] x"}).status_code, 422)
        r = self.req("작성자", "POST", "/api/board/post",
                     json={"board": "review", "title": "[점검] 후기", "body": "점검 중", "consent": True})
        E("회원 후기 쓰기", r.status_code, 200)
        if r.status_code != 200:
            return
        pid = r.json()["id"]
        self.made.append(pid)
        up = self.upload("작성자", pid, "video", "check.mp4", VIDEO)
        E("후기 영상 올리기", up.status_code, 200)
        vurl = up.json()["file"]["url"] if up.status_code == 200 else "/api/board/media/0"

        # 승인 전
        for w in ("비로그인", "다른회원"):
            E("승인 전 · %s · 목록에 뜸" % w, pid in (self.ids(w, "review") or []), False)
            E("승인 전 · %s · 글" % w, self.req(w, "GET", "/api/board/post/%d" % pid).status_code, 404)
            E("승인 전 · %s · 영상" % w, self.req(w, "GET", vurl).status_code, 404)
        for w in ("작성자", "관리자"):
            E("승인 전 · %s · 목록에 뜸" % w, pid in (self.ids(w, "review") or []), True)
            E("승인 전 · %s · 글" % w, self.req(w, "GET", "/api/board/post/%d" % pid).status_code, 200)
            E("승인 전 · %s · 영상 md5" % w, md5(self.req(w, "GET", vurl).content), md5(VIDEO))
        E("회원이 승인 시도", self.req("다른회원", "POST", "/api/board/admin/act",
                                 json={"id": pid, "act": "approve"}).status_code, 403)
        E("관리자 승인", self.req("관리자", "POST", "/api/board/admin/act",
                              json={"id": pid, "act": "approve"}).status_code, 200)
        # 승인 뒤
        for w in ("비로그인", "다른회원"):
            E("승인 뒤 · %s · 목록에 뜸" % w, pid in (self.ids(w, "review") or []), True)
            E("승인 뒤 · %s · 글" % w, self.req(w, "GET", "/api/board/post/%d" % pid).status_code, 200)
            E("승인 뒤 · %s · 영상 md5" % w, md5(self.req(w, "GET", vurl).content), md5(VIDEO))
        rng = self.req("비로그인", "GET", vurl, headers={"Range": "bytes=100-199"})
        E("영상 구간 요청(탐색)", (rng.status_code, rng.content), (206, VIDEO[100:200]))
        self.req("관리자", "POST", "/api/board/admin/act", json={"id": pid, "act": "hide"})
        E("숨김 · 비로그인 · 글", self.req("비로그인", "GET", "/api/board/post/%d" % pid).status_code, 404)
        E("숨김 · 비로그인 · 영상", self.req("비로그인", "GET", vurl).status_code, 404)
        E("숨김 · 작성자 · 글", self.req("작성자", "GET", "/api/board/post/%d" % pid).status_code, 200)

        # 자료실
        r = self.req("관리자", "POST", "/api/board/post",
                     json={"board": "free", "title": "[점검] 자료", "body": "점검 중"})
        E("관리자 자료 올리기", r.status_code, 200)
        if r.status_code != 200:
            return
        fid = r.json()["id"]
        self.made.append(fid)
        furl = self.upload("관리자", fid, "file", "점검팩.zip", ZIP).json()["file"]["url"]
        purl = self.upload("관리자", fid, "image", "preview.png", PNG).json()["file"]["url"]
        E("자료 · 비로그인 · 목록에 뜸", fid in (self.ids("비로그인", "free") or []), True)
        E("자료 · 비로그인 · 글", self.req("비로그인", "GET", "/api/board/post/%d" % fid).status_code, 200)
        E("자료 · 비로그인 · 미리보기 md5", md5(self.req("비로그인", "GET", purl).content), md5(PNG))
        E("자료 · 비로그인 · 내려받기", self.req("비로그인", "GET", furl).status_code, 401)
        E("자료 · 팩을 재생 주소로 받기", self.req("다른회원", "GET", furl.replace("/download/", "/media/")).status_code, 404)
        d = self.req("다른회원", "GET", furl)
        E("자료 · 회원 · 내려받기 md5", (d.status_code, md5(d.content)), (200, md5(ZIP)))
        E("자료 · 회원 · 내려받는 파일로 옴", "attachment" in d.headers.get("content-disposition", ""), True)

    def cleanup(self):
        for pid in self.made:
            r = self.req("관리자", "DELETE", "/api/board/post/%d" % pid)
            self.expect("시험 글 %d 지우기" % pid, r.status_code, 200)
            self.expect("지운 글 %d 가 안 보임" % pid,
                        self.req("관리자", "GET", "/api/board/post/%d" % pid).status_code, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--secret", default="", help="로컬 서버의 DASH_SECRET. 없으면 라이브 서버에서 쿠키를 만든다")
    a = ap.parse_args()
    cookies = ([_sign(a.secret, c) for c in (0, CID_A, CID_B)] if a.secret else _live_cookies())
    ck = Check(a.base, cookies)
    try:
        ck.run()
    finally:
        ck.cleanup()
    bad = [r for r in ck.rows if not r[0]]
    for ok, what, got, want in ck.rows:
        print("%s %s" % ("OK  " if ok else "FAIL", what) + ("" if ok else "  → 나온 값 %r / 기대 %r" % (got, want)))
    print("\n%s — %d줄 중 어긋남 %d (%s)" % ("통과" if not bad else "실패", len(ck.rows), len(bad), a.base))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
