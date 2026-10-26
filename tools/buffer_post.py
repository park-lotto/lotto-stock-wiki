# -*- coding: utf-8 -*-
"""Claude로 만든 영상을 구글 드라이브 폴더에서 Buffer로 예약한다(관제 250, 2026-10-21 사장님).

    py tools/buffer_post.py scan                       # 폴더별 올릴 영상·짝 .txt 유무
    py tools/buffer_post.py post                       # 전 폴더 영상을 Buffer 큐(그 계정 시간표)에 넣기
    py tools/buffer_post.py post --folder 995 --at "2026-10-22 19:00" [--gap 24]
                                                       # 시각 지정(한국시간). 영상 여러 개면 gap 시간 간격
    py tools/buffer_post.py test --folder 995          # 실제 시험: 올리기→공개주소 HEAD→30일 뒤 비공개 예약→즉시 삭제
    py tools/buffer_post.py cleanup                    # 게시 끝난 영상의 서버 사본 지우기(post 시작 때도 자동)

흐름(한 영상):
  ① 짝 .txt(같은 이름) 읽기 — 첫 줄=유튜브 제목(buffer_api._yt_title), 전체=설명. ★없으면 건너뛴다
     (제목·설명은 Claude가 .txt로 먼저 써 둔다. 이 도구는 글을 지어내지 않는다)
  ② scp로 서버 data/buffer_drop/<무작위>.mp4 에 올림 → 공개 주소 /api/share/f/<이름> (app.api_share_f)
  ③ HEAD 200·video/mp4 확인 뒤 buffer_api.schedule_video  ④ 영상·.txt를 그 폴더 '예약\'으로 옮기고 장부에 적는다
  ⑤ cleanup(post 시작 때도 자동)이 Buffer 상태 sent 를 보면 '예약\' → '완료\'  (완료 = 유튜브에 실제로 올라감)

폴더 = G:\\내 드라이브\\버퍼예약\\<폴더명>, 키 = ~/.claude/buffer_keys.json {폴더명: Buffer API 키}.
★키 파일은 git·드라이브에 두지 않는다. 장부 = ~/.claude/buffer_post_ledger.json
"""
import argparse
import datetime as dt
import json
import os
import secrets
import shutil
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from shopping_shorts import buffer_api  # noqa: E402
from tools.live_admin import BASE, HOST, KEY  # noqa: E402

DRIVE = r"G:\내 드라이브\버퍼예약"
RESERVED = "예약"     # Buffer 에 넘긴 것(아직 안 올라감) — 2026-10-24 사장님 "예약폴더는 올려져있는걸로"
DONE = "완료"         # 유튜브에 실제로 게시된 것 — cleanup 이 status sent 를 보고 예약 → 완료로 옮긴다
KEYS = os.path.expanduser("~/.claude/buffer_keys.json")
LEDGER = os.path.expanduser("~/.claude/buffer_post_ledger.json")
REMOTE_DIR = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/buffer_drop"
KST = dt.timezone(dt.timedelta(hours=9))
MAX_SEC = 180          # Buffer 유튜브 쇼츠 자동게시 한도 3분(support.buffer.com, 2026-10-21 확인)


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def _save_ledger(rows):
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


def _folders(only=None, need_dir=True):
    """need_dir=False: test --file 처럼 드라이브 폴더 없이 키만 쓰는 경우(드라이브 G: 가 안 붙어 있어도 시험)."""
    keys = _load(KEYS, {})
    names = [only] if only else sorted(keys)
    if need_dir and not os.path.isdir(DRIVE):
        raise SystemExit(f"드라이브 폴더가 안 보인다: {DRIVE} — 구글 드라이브(G:)가 연결돼 있나 확인")
    for n in names:
        if n not in keys:
            raise SystemExit(f"키 없음: {n} — {KEYS} 에 등록돼 있지 않다")
        d = os.path.join(DRIVE, n)
        if need_dir and not os.path.isdir(d):
            # ★멈추지 않는다 — 2026-10-24 '997(미사용)' 하나 때문에 뒤의 998·999·숏템07 을 통째로 못 봤다
            print(f"폴더 없음(건너뜀): {d}")
            continue
        yield n, d, keys[n]


def _videos(d):
    return sorted(f for f in os.listdir(d) if f.lower().endswith(".mp4") and os.path.isfile(os.path.join(d, f)))


def _caption(d, mp4):
    p = os.path.join(d, os.path.splitext(mp4)[0] + ".txt")
    if not os.path.isfile(p):
        return None, p
    with open(p, encoding="utf-8-sig") as f:
        return f.read().strip(), p


def _probe(path):
    """(길이초, 가로, 세로). ffprobe 없으면 None — 규격 검사를 건너뛰었다고 알린다."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                              "-show_entries", "stream=width,height:format=duration",
                              "-of", "json", path], capture_output=True, text=True, timeout=60).stdout
        j = json.loads(out)
        s = j["streams"][0]
        return float(j["format"]["duration"]), int(s["width"]), int(s["height"])
    except Exception as e:
        print(f"   ⚠️ 규격 확인 못 함({e}) — Buffer가 거절하면 그때 알 수 있다")
        return None


def _ssh(cmd):
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", KEY, HOST, cmd],
                       capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise RuntimeError(f"ssh 실패: {(r.stderr or r.stdout)[-300:]}")
    return r.stdout


def _upload(path):
    """서버 buffer_drop 에 무작위 이름으로 올리고 공개 주소를 준다. HEAD 200 까지 확인."""
    name = secrets.token_urlsafe(24) + ".mp4"           # 32자 [A-Za-z0-9_-] — app._BUFFER_DROP_NAME 과 짝
    _ssh(f"mkdir -p {REMOTE_DIR}")
    r = subprocess.run(["scp", "-q", "-o", "ConnectTimeout=15", "-i", KEY, path, f"{HOST}:{REMOTE_DIR}/{name}"],
                       capture_output=True, text=True, timeout=1800)
    if r.returncode:
        raise RuntimeError(f"scp 실패: {(r.stderr or r.stdout)[-300:]}")
    url = f"{BASE}/api/share/f/{name}"
    h = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30)
    size = int(h.headers.get("Content-Length") or 0)
    if h.status != 200 or "video/mp4" not in (h.headers.get("Content-Type") or "") or size != os.path.getsize(path):
        raise RuntimeError(f"공개 주소 확인 실패: {h.status} {h.headers.get('Content-Type')} {size}B")
    return name, url


def _remove_remote(name):
    if name and all(c.isalnum() or c in "-_." for c in name):
        _ssh(f"rm -f {REMOTE_DIR}/{name}")


def _due_list(at, gap, n):
    if not at:
        return [None] * n
    t = dt.datetime.strptime(at, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    if t <= dt.datetime.now(KST):
        raise SystemExit(f"--at 이 지난 시각이다: {at}")
    return [(t + dt.timedelta(hours=gap * i)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            for i in range(n)]


def _channel(key, folder):
    chs = buffer_api.channels(key)
    yt = [c for c in chs if c.get("service") == "youtube"] or chs
    if not yt:
        raise RuntimeError(f"{folder}: Buffer에 연결된 채널이 없다 — Buffer에서 유튜브를 먼저 연결")
    return yt[0]


def _check(d, mp4):
    """올리기 전 규격. 문제 문장을 돌려준다(없으면 "")."""
    pr = _probe(os.path.join(d, mp4))
    if not pr:
        return ""
    sec, w, h = pr
    if sec > MAX_SEC:
        return f"{sec:.0f}초 — Buffer 쇼츠 자동게시는 {MAX_SEC}초까지"
    if w > h:
        return f"가로 영상({w}x{h}) — 쇼츠는 세로(9:16)"
    return ""


def cmd_scan(a):
    for n, d, _k in _folders(a.folder):
        vs = _videos(d)
        print(f"[{n}] {len(vs)}개")
        for v in vs:
            cap, _ = _caption(d, v)
            print(f"   {v}  {'.txt 있음' if cap else '★.txt 없음(건너뜀)'}  {_check(d, v)}")


def cmd_cleanup(a=None):
    rows = _load(LEDGER, [])
    keys = _load(KEYS, {})
    changed = 0
    for r in rows:
        if r.get("cleaned") or r.get("folder") not in keys:
            continue
        try:
            st = buffer_api.post_status(keys[r["folder"]], r["post_id"]).get("status")
        except buffer_api.BufferNotFound:
            st = "deleted"
        except Exception as e:
            print(f"   상태 조회 실패({r['file']}): {e}")
            continue
        if st in ("sent", "deleted", "error"):
            _remove_remote(r["remote"])
            r["cleaned"], r["final_status"] = dt.datetime.now(KST).isoformat(timespec="seconds"), st
            changed += 1
            if st == "sent":
                _to_done(r)
            else:
                print(f"   ⚠️ {r['folder']} {r['file']}: Buffer 상태 {st} — '{RESERVED}' 폴더에 그대로 둔다(확인 필요)")
    if changed:
        _save_ledger(rows)
    print(f"서버 사본 정리 {changed}개")


def _to_done(r):
    """게시된 영상·.txt 를 '예약' → '완료' 로 옮긴다. 이미 완료에 있으면(옛 방식으로 옮긴 것) 그대로."""
    d = os.path.join(DRIVE, r["folder"])
    if not os.path.isdir(d):
        return
    for name in (r["file"], os.path.splitext(r["file"])[0] + ".txt"):
        src = os.path.join(d, RESERVED, name)
        if os.path.isfile(src):
            os.makedirs(os.path.join(d, DONE), exist_ok=True)
            shutil.move(src, os.path.join(d, DONE, name))
    print(f"   {r['folder']} {r['file']}: 게시됨 → '{DONE}'")


def _fingerprint(path):
    """영상 내용 지문(sha256). 이름을 바꿔도 같은 영상이면 같은 값이다."""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _already_posted(rows, folder, d, v, fp):
    """한 번 올린 영상을 다시 올리지 않는 장치(2026-10-26 사장님 "실수로 다시 올리면 안 된다").
    ① 같은 내용(지문)이 장부에 있으면 — 어느 계정이든 막는다(이름을 바꿔 다시 넣어도 걸린다)
    ② 같은 폴더·같은 이름이 장부에 있거나 그 폴더 예약/완료 에 같은 이름이 있으면 — 배지를 다시 입혀 지문이 바뀐 경우
    ③ cleanup 이 Buffer 상태 deleted 로 적은 행(final_status)은 '안 올린 것'으로 본다
    걸리면 사유 문자열, 아니면 None."""
    for r in rows:
        if r.get("final_status") == "deleted":      # 사장님이 Buffer 에서 지운 예약 = 안 올린 것
            continue
        if fp and r.get("fp") == fp:
            return f"이미 올린 영상(같은 내용) — {r.get('folder')}/{r.get('file')} {r.get('due')}"
        if r.get("folder") == folder and r.get("file") == v:
            return f"이미 올린 이름 — {r.get('due')} 예약"
    for sub in (RESERVED, DONE):
        if os.path.isfile(os.path.join(d, sub, v)):
            return f"'{sub}' 폴더에 같은 이름이 있다"
    return None


def cmd_post(a):
    cmd_cleanup()
    rows = _load(LEDGER, [])
    ok = fail = 0
    for n, d, key in _folders(a.folder):
        vs = _videos(d)
        if not vs:
            continue
        ch = _channel(key, n)
        dues = _due_list(a.at, a.gap, len(vs))
        for v, due in zip(vs, dues):
            cap, cap_path = _caption(d, v)
            if not cap:
                print(f"[{n}] {v}: .txt 없음 — 건너뜀(첫 줄 제목, 나머지 설명으로 같은 이름 .txt 를 써 두라)")
                continue
            bad = _check(d, v)
            if bad:
                print(f"[{n}] {v}: {bad} — 건너뜀")
                continue
            fp = _fingerprint(os.path.join(d, v))
            dup = _already_posted(rows, n, d, v, fp)
            if dup:
                print(f"[{n}] {v}: ⛔ 중복 — {dup} → 안 올리고 건너뜀(정말 다시 올릴 거면 장부에서 그 행을 지워라)")
                continue
            remote = None
            try:
                remote, url = _upload(os.path.join(d, v))
                res = buffer_api.schedule_video(key, ch["id"], cap, url, due_at=due, privacy=a.privacy)
            except Exception as e:
                if remote:
                    _remove_remote(remote)
                print(f"[{n}] {v}: 실패 — {e}")
                fail += 1
                continue
            rsv = os.path.join(d, RESERVED)
            os.makedirs(rsv, exist_ok=True)
            shutil.move(os.path.join(d, v), os.path.join(rsv, v))
            shutil.move(cap_path, os.path.join(rsv, os.path.basename(cap_path)))
            rows.append({"folder": n, "channel": ch.get("name"), "file": v, "post_id": res["id"],
                         "due": res.get("dueAt") or "큐", "remote": remote, "fp": fp,
                         "at": dt.datetime.now(KST).isoformat(timespec="seconds")})
            _save_ledger(rows)
            print(f"[{n}] {v} → {ch.get('name')} 예약 {res.get('dueAt') or '(Buffer 큐 시간표)'}  id={res['id']}")
            ok += 1
    print(f"끝: 예약 {ok} · 실패 {fail}")


def cmd_test(a):
    """실제 시험 — 게시하지 않는다: 30일 뒤 비공개 예약 → 상태 scheduled 확인 → 삭제 → NOT_FOUND 확인."""
    due = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    src = a.file
    for n, d, key in _folders(a.folder, need_dir=not src):
        try:
            ch = _channel(key, n)
        except RuntimeError as e:
            print(f"[{n}] {e}")
            continue
        path = src or next((os.path.join(d, v) for v in _videos(d)), None)
        if not path:
            print(f"[{n}] 시험할 영상 없음(--file 로 지정)")
            continue
        remote = None
        try:
            remote, url = _upload(path)
            res = buffer_api.schedule_video(key, ch["id"], "[시험] 버퍼예약 도구 점검 — 곧 삭제\n#test", url,
                                            due_at=due, privacy="private")
            st = buffer_api.post_status(key, res["id"]).get("status")
            buffer_api.delete_post(key, res["id"])
            try:
                buffer_api.post_status(key, res["id"])
                gone = "★삭제 안 됨 — Buffer에서 직접 지워라"
            except buffer_api.BufferNotFound:
                gone = "삭제 확인"
            print(f"[{n}] {ch.get('name')}: 공개주소 HEAD 200 · 예약 {st} · {gone}")
        except Exception as e:
            print(f"[{n}] 실패 — {e}")
        finally:
            if remote:
                _remove_remote(remote)


def main(argv=None):
    p = argparse.ArgumentParser(description="드라이브 버퍼예약 폴더 → Buffer 예약")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "post", "test", "cleanup"):
        s = sub.add_parser(name)
        s.add_argument("--folder")
        if name == "post":
            s.add_argument("--at", help='한국시간 "YYYY-MM-DD HH:MM" (없으면 Buffer 큐 시간표)')
            s.add_argument("--gap", type=float, default=24, help="영상 여러 개일 때 간격(시간)")
            s.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
        if name == "test":
            s.add_argument("--file", help="시험용 mp4(없으면 폴더 첫 영상)")
    a = p.parse_args(argv)
    {"scan": cmd_scan, "post": cmd_post, "test": cmd_test, "cleanup": cmd_cleanup}[a.cmd](a)


if __name__ == "__main__":
    main()
