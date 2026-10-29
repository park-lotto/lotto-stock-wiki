# -*- coding: utf-8 -*-
"""Claude로 만든 영상을 구글 드라이브 폴더에서 Buffer로 예약한다(관제 250, 2026-10-21 사장님).

    py tools/buffer_post.py scan                       # 폴더별 올릴 영상·짝 .txt 유무
    py tools/buffer_post.py post                       # 전 폴더 영상을 계정별 다음 빈 칸(매일 15:00·20:00 KST, 칸당 1개)에 유튜브+틱톡 예약
    py tools/buffer_post.py post --folder 995 --at "2026-10-22 19:00" [--gap 24]
                                                       # 시각 지정(한국시간). 영상 여러 개면 gap 시간 간격
    py tools/buffer_post.py test --folder 995          # 실제 시험: 올리기→공개주소 HEAD→30일 뒤 비공개 예약→즉시 삭제
    py tools/buffer_post.py cleanup                    # 게시 끝난 영상의 서버 사본 지우기(post 시작 때도 자동)

흐름(한 영상):
  ① 짝 .txt(같은 이름) 읽기 — 첫 줄=유튜브 제목(buffer_api._yt_title), 전체=설명. ★없으면 건너뛴다
     ★'인포크: [번호] 상품명' 줄이 있어야 하고 그 블록이 인포크 공개 페이지에 있어야 올린다(_inpock_check, 관제 282)
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
import random
import re
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


def _acct_no(folder):
    """폴더 이름의 계정 번호 — '995_2 얜샷템'·'995'·'숏템07(수창) 쓱싹템' → '995'·'995'·'07'."""
    m = re.match(r"^(\d+)", folder.replace("숏템", ""))
    return m.group(1) if m else ""


def _key_for(keys, folder):
    """장부 행의 Buffer 키(주인 한 곳 — cleanup·점검 도구가 같이 쓴다).
    폴더 이름이 바뀌어도(10-28 '995' → '995_1 썰템쇼'·'995_2 얜샷템') 같은 번호의 키가 하나뿐이면 그 키.
    번호가 같아도 키가 둘 이상이면 고르지 않는다(None) — 엉뚱한 계정 조회 금지."""
    if folder in keys:
        return keys[folder]
    no = _acct_no(folder)
    found = {v for k, v in keys.items() if no and _acct_no(k) == no}
    return found.pop() if len(found) == 1 else None


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


def _ssh(cmd, timeout=60):
    # 매시간 작업(스케줄러)에서 ssh 가 가끔 120초 멈춰 cleanup 전체가 죽었다(10-27~29 로그 53회).
    # stdin 을 닫고(BatchMode·DEVNULL) 응답 없는 연결은 ServerAlive 로 끊는다. 시간초과도 RuntimeError 로 — 부르는 쪽이 한 건만 건너뛴다.
    try:
        r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes",
                            "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3", "-i", KEY, HOST, cmd],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ssh 시간초과({timeout}초)")
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


def _safe_name(name):
    return bool(name) and all(c.isalnum() or c in "-_." for c in name)


def _remove_remote(*names):
    """서버 사본 지우기 — 여러 개를 ssh 한 번으로. 실패하면 RuntimeError(부르는 쪽이 다음 시간에 다시)."""
    names = [n for n in names if _safe_name(n)]
    if names:
        _ssh("rm -f " + " ".join(f"{REMOTE_DIR}/{n}" for n in names))


SLOTS = ((15, 30), (19, 30))   # 사장님(2026-10-29) "매일 3시반·7시반"(10-26 3시·8시에서 바뀜) / "한 번에 두 개는 없다" — 계정당 칸 하나에 영상 하나
SERVICES = ("youtube", "tiktok")   # 같은 영상을 같은 칸에 유튜브·틱톡 둘 다(10-26 실사용). 인스타는 950 계정이 잘못 붙어 있어 뺀다


def _taken(rows, folder):
    """그 계정이 이미 쓴 칸(UTC 'YYYY-MM-DDTHH:MM'). Buffer 에서 지운 것만 빈 칸으로 본다."""
    return {(r.get("due") or "")[:16] for r in rows
            if r.get("folder") == folder and r.get("final_status") != "deleted"}


def _order(vs):
    """칸에 넣는 순서 — 폴더에 둘 이상이면 무작위(사장님 10-29 "두 개 이상 있어도 랜덤으로 배정")."""
    vs = list(vs)
    random.shuffle(vs)
    return vs


def _slot_dues(rows, folder, n, now=None):
    """다음 빈 칸 n개(SLOTS, KST). 앞 칸이 지났거나 차 있으면 건너뛰고 다음 칸 — 영상이 하나면 그 날 남은 칸으로 간다."""
    now = now or dt.datetime.now(KST)
    taken, out, day = _taken(rows, folder), [], now.date()
    while len(out) < n:
        for h, m in SLOTS:
            t = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=KST)
            u = t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M")
            if t > now + dt.timedelta(minutes=20) and u not in taken and len(out) < n:
                out.append(u + ":00.000Z")
        day += dt.timedelta(days=1)
    return out


def _due_list(at, gap, n):
    if not at:
        return [None] * n
    t = dt.datetime.strptime(at, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    if t <= dt.datetime.now(KST):
        raise SystemExit(f"--at 이 지난 시각이다: {at}")
    return [(t + dt.timedelta(hours=gap * i)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            for i in range(n)]


def _targets(key, folder):
    """그 폴더 영상이 갈 Buffer 채널들 — 판단 주인은 여기 한 곳(post·test 둘 다 부른다).
    2026-10-28 계정마다 유튜브가 둘이 됐다(폴더 '995_1 썰템쇼'·'995_2 얜샷템'). 전엔 첫 유튜브를 골라
    새 채널(_2)이 앞에 오자 _1 영상이 _2 채널로 갈 뻔했다 → 유튜브는 폴더 이름의 채널명과 같은 것만.
    틱톡은 계정당 하나라 원래 채널(_1 또는 번호만) 폴더에만 붙인다(_2 까지 붙이면 틱톡 한 칸에 두 개)."""
    chs = buffer_api.channels(key)
    label = folder.split(" ", 1)[1] if " " in folder else folder
    yt = [c for c in chs if c.get("service") == "youtube"]
    hit = [c for c in yt if (c.get("name") or "") == label]
    if not hit and len(yt) == 1:
        hit = yt
    if not hit:
        raise RuntimeError(f"{folder}: 폴더 이름의 채널명 '{label}' 과 같은 유튜브 채널이 Buffer 에 없다 "
                           f"(있는 것: {[c.get('name') for c in yt]}) — 폴더 이름이나 Buffer 연결을 맞춰라")
    out = hit[:1]
    acct = folder.split(" ", 1)[0]
    if "_" not in acct or acct.endswith("_1"):
        out += [c for c in chs if c.get("service") == "tiktok"][:1]
    return out


def _channel(key, folder):
    return _targets(key, folder)[0]


INPOCK = "https://link.inpock.co.kr"
# 계정 번호 → 인포크 계정. 원본 = tools/shoplink/run.py INPOCK_BY_CHANNEL(쇼핑링크자동 트랙, 병합 전) — 이 트랙 안에선 여기 한 곳
INPOCK_BY_CHANNEL = {"987": "shocktem", "950": "streport", "999": "yeshot", "21": "ssldezip",
                     "998": "mtst", "995": "stems", "994": "ssult"}
INPOCK_LINE = "인포크:"     # .txt 안의 한 줄 — "인포크: [10] 조선미녀 맑은쌀 선크림" (Buffer 글에는 안 들어간다)


def _split_inpock(cap):
    """.txt 글에서 '인포크:' 줄을 떼어 (Buffer 에 보낼 글, 인포크 블록 제목) 으로."""
    keep, block = [], ""
    for line in cap.splitlines():
        if line.strip().startswith(INPOCK_LINE):
            block = line.strip()[len(INPOCK_LINE):].strip()
        else:
            keep.append(line)
    return "\n".join(keep).strip(), block


def _inpock_blocks(acct, cache={}):
    """인포크 공개 페이지의 링크 블록 [(제목, 주소, 공개여부)] — 공개 페이지에 박힌 "blocks":[…] 를 읽는다."""
    if acct not in cache:
        req = urllib.request.Request(f"{INPOCK}/{acct}", headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        i = html.find('"blocks":[')
        arr = json.JSONDecoder().raw_decode(html[i + 9:])[0] if i >= 0 else []
        cache[acct] = [(b.get("title") or "", b.get("url") or "", b.get("is_open", True))
                       for b in arr if b.get("block_type") == "link"]
    return cache[acct]


# 설명란 안내 한 줄(사장님 10-29 "설명란에 영상 속 제품은 프로필 링크 몇 번에 있습니다 / 채널별로 말투 다르게").
# 주인 = 여기 한 곳. 폴더 이름 → 말투. {n} = 인포크 블록 번호. 없는 폴더는 기본 문장.
LINK_LINE = {
    "950 숏템리폿": "📌 영상 속 제품은 프로필 링크 {n}번에 정리해 두었습니다.",
    "987_1 샥템스토리": "영상 속 그 제품, 프로필 링크 {n}번에 있어요 👀",
    "987_2 신박리포트": "🔎 영상 속 제품 정보는 프로필 링크 {n}번에서 확인하세요.",
    "994_1 썰템홈샷": "썰 속 그 제품은 프로필 링크 {n}번에 있어요!",
    "994_2 트롯파파": "영상에 나온 제품은 프로필 링크 {n}번에 있습니다~",
    "995_1 썰템쇼": "🎬 오늘 나온 제품은 프로필 링크 {n}번에 있어요!",
    "995_2 얜샷템": "이거 어디서 사냐고요? 프로필 링크 {n}번이에요 😎",
    "998_1 꿀템샷": "🍯 영상 속 꿀템은 프로필 링크 {n}번에 담아 뒀어요.",
    "998_2 별빛여행": "✨ 영상 속 아이템은 프로필 링크 {n}번에서 만나보세요.",
    "999_1 잇썸홈": "🏠 영상 속 살림템은 프로필 링크 {n}번에 있어요.",
    "999_2 재미썸홈": "궁금하셨죠? 영상 속 제품은 프로필 링크 {n}번이에요 😆",
    "21(수창) 쓸데수집": "🛒 영상 속 그 물건은 프로필 링크 {n}번에 있어요.",
    "숏템07(수창) 쓱싹템": "🧽 영상 속 제품은 프로필 링크 {n}번에 있어요.",
}
LINK_LINE_DEFAULT = "영상 속 제품은 프로필 링크 {n}번에 있습니다."


def _block_no(block):
    """'[10] 조선미녀…' · '13. 픽업브릭스…' → '10' · '13'."""
    m = re.match(r"^\s*\[?\s*(\d+)\s*[\].]", block or "")
    return m.group(1) if m else ""


def _with_link_line(folder, cap, block):
    """제목(첫 줄) 바로 아래에 채널 말투의 '프로필 링크 N번' 한 줄을 넣는다. 이미 '프로필 링크'가 있으면 그대로."""
    n = _block_no(block)
    if not n or "프로필 링크" in cap:
        return cap
    line = LINK_LINE.get(folder, LINK_LINE_DEFAULT).format(n=n)
    title, _, rest = cap.partition("\n")
    return f"{title}\n\n{line}\n\n{rest.strip()}".rstrip()


def _inpock_check(folder, block):
    """올리기 전 관문(사장님 10-26 "인포크 없으면 올리지 마라"): 그 계정 인포크 공개 페이지에 이 제목의 블록이
    공개·쿠팡 링크로 있어야 한다. 문제가 있으면 이유 문자열, 괜찮으면 None."""
    if not block:
        return f".txt 에 '{INPOCK_LINE} [번호] 상품명' 줄이 없음(쇼핑링크를 먼저 만들고 그 제목을 적는다)"
    acct = INPOCK_BY_CHANNEL.get(_acct_no(folder))
    if not acct:
        return f"이 계정({folder})의 인포크 계정이 정해지지 않음"
    try:
        blocks = _inpock_blocks(acct)
    except Exception as e:
        return f"인포크 {acct} 공개 페이지를 못 읽음 — {e}"
    hit = next((b for b in blocks if b[0].strip() == block), None)
    if not hit:
        return f"인포크 {acct} 공개 페이지에 '{block}' 블록이 없음"
    if not hit[2] or "link.coupang.com" not in hit[1]:
        return f"인포크 {acct} '{block}' 블록이 비공개거나 쿠팡 링크가 아님({hit[1] or '링크없음'})"
    return None


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
    """① Buffer 상태를 장부에 적는다(sent/deleted = 끝, 행마다 바로 저장) ② 끝난 행의 서버 사본을 ssh 한 번으로 지운다.
    error 는 끝이 아니다 — Buffer 에서 다시 시도하면 sent 가 되므로 서버 사본을 남겨 둔다(10-27 950 틱톡: 지워서 재시도 404).
    ssh 가 실패해도 장부는 이미 적혀 있고, 못 지운 사본은 다음 시간에 다시 지운다."""
    rows = _load(LEDGER, [])
    keys = _load(KEYS, {})
    done = 0
    for r in rows:
        # 게시됐는데 그때 G: 에 파일이 없어 못 옮긴 것 — 매번 다시 옮겨 본다(10-29: G: 끊김 뒤 7편이 예약\ 에 남았다)
        if r.get("final_status") == "sent" and r.get("done_where") == "G:에없음":
            w = _to_done(r)
            if w != r["done_where"]:
                r["done_where"] = w
                _save_ledger(rows)
            continue
        key = _key_for(keys, r.get("folder", ""))
        if r.get("final_status") in ("sent", "deleted") or not key:
            continue
        try:
            st = buffer_api.post_status(key, r["post_id"]).get("status")
        except buffer_api.BufferNotFound:
            st = "deleted"
        except Exception as e:
            print(f"   상태 조회 실패({r['folder']} {r['file']}): {e}")
            continue
        if st in ("sent", "deleted"):
            r["final_status"] = st
            if st == "sent":
                r["done_where"] = _to_done(r)
            _save_ledger(rows)          # 한 건마다 — 뒤에서 죽어도 여기까지는 남는다
            done += 1
        elif st == "error":
            if r.get("last_status") != "error":
                r["last_status"] = "error"
                _save_ledger(rows)
            print(f"   ⚠️ {r['folder']} {r['file']} {r.get('service')}: Buffer 상태 error — 서버 사본 남김(Buffer 에서 다시 시도 가능)")
    left = [r for r in rows if r.get("final_status") in ("sent", "deleted") and not r.get("cleaned") and r.get("remote")]
    removed = 0
    if left:
        try:
            _remove_remote(*[r["remote"] for r in left])
            now = dt.datetime.now(KST).isoformat(timespec="seconds")
            for r in left:
                r["cleaned"] = now
            removed = len(left)
            _save_ledger(rows)
        except RuntimeError as e:
            print(f"   ⚠️ 서버 사본 {len(left)}개 못 지움 — 다음 시간에 다시: {e}")
    print(f"상태 확정 {done}개 · 서버 사본 정리 {removed}개")
    return 0 if removed == len(left) else 1


def _to_done(r):
    """게시된 영상·.txt 를 '예약' → '완료' 로 옮긴다. 결과를 돌려준다(장부 done_where).
    G: 동기화가 안 내려와 예약\\ 에 파일이 없으면 'G:에없음' — 웹 드라이브에서 옮겨야 한다(buffer_drive_web_move)."""
    d = os.path.join(DRIVE, r["folder"])
    if not os.path.isdir(d):
        print(f"   ⚠️ {r['folder']} {r['file']}: 게시됨 — 드라이브 폴더가 안 보여 '{DONE}' 이동 못 함")
        return "폴더없음"
    moved = []
    for name in (r["file"], os.path.splitext(r["file"])[0] + ".txt"):
        src = os.path.join(d, RESERVED, name)
        if os.path.isfile(src):
            os.makedirs(os.path.join(d, DONE), exist_ok=True)
            shutil.move(src, os.path.join(d, DONE, name))
            moved.append(name)
    if moved:
        print(f"   {r['folder']} {r['file']}: 게시됨 → '{DONE}'")
        return DONE
    if os.path.isfile(os.path.join(d, DONE, r["file"])):
        return DONE
    print(f"   ⚠️ {r['folder']} {r['file']}: 게시됨 — G: '{RESERVED}' 에 파일이 없음(웹 드라이브에서 '{DONE}' 으로 옮겨야)")
    return "G:에없음"


def _fingerprint(path):
    """영상 내용 지문(sha256). 이름을 바꿔도 같은 영상이면 같은 값이다."""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _already_posted(rows, folder, d, v, fp, service="youtube"):
    """한 번 올린 영상을 다시 올리지 않는 장치(2026-10-26 사장님 "실수로 다시 올리면 안 된다").
    ① 같은 내용(지문)이 장부에 있으면 — 어느 계정이든 막는다(이름을 바꿔 다시 넣어도 걸린다)
    ② 같은 폴더·같은 이름이 장부에 있거나 그 폴더 예약/완료 에 같은 이름이 있으면 — 배지를 다시 입혀 지문이 바뀐 경우
    ③ cleanup 이 Buffer 상태 deleted 로 적은 행(final_status)은 '안 올린 것'으로 본다
    걸리면 사유 문자열, 아니면 None."""
    for r in rows:
        if r.get("final_status") == "deleted":      # 사장님이 Buffer 에서 지운 예약 = 안 올린 것
            continue
        if r.get("service", "youtube") != service:  # 같은 영상을 유튜브·틱톡에 한 번씩은 정상 — 서비스별로 따로 본다
            continue
        if fp and r.get("fp") == fp:
            return f"이미 올린 영상(같은 내용) — {r.get('folder')}/{r.get('file')} {r.get('due')}"
        if r.get("folder") == folder and r.get("file") == v:
            return f"이미 올린 이름 — {r.get('due')} 예약"
    for sub in (RESERVED, DONE):
        if service == "youtube" and os.path.isfile(os.path.join(d, sub, v)):
            return f"'{sub}' 폴더에 같은 이름이 있다"
    return None


def cmd_post(a):
    cmd_cleanup()
    rows = _load(LEDGER, [])
    ok = fail = 0
    for n, d, key in _folders(a.folder):
        vs = _order(_videos(d))
        if not vs:
            continue
        try:
            targets = [c for c in _targets(key, n) if c.get("service") in SERVICES]
        except RuntimeError as e:
            print(f"[{n}] {e} — 건너뜀")
            continue
        if not targets:
            print(f"[{n}] Buffer에 유튜브·틱톡 채널이 없다 — 건너뜀")
            continue
        # ① 올릴 수 있는 영상만 먼저 고른다 — 준비 안 된 영상이 칸을 차지하면 준비된 영상이 다음 날로 밀린다(10-29)
        ready = []
        for v in vs:
            cap, cap_path = _caption(d, v)
            if not cap:
                print(f"[{n}] {v}: .txt 없음 — 건너뜀(첫 줄 제목, 나머지 설명으로 같은 이름 .txt 를 써 두라)")
                continue
            cap, block = _split_inpock(cap)
            bad = _check(d, v) or _inpock_check(n, block)
            if bad:
                print(f"[{n}] {v}: {bad} — 건너뜀")
                continue
            if not _block_no(block):
                print(f"[{n}] {v}: 인포크 제목 '{block}' 에서 번호를 못 읽음 — 건너뜀(설명란 '프로필 링크 N번'을 못 쓴다)")
                continue
            cap = _with_link_line(n, cap, block)
            fp = _fingerprint(os.path.join(d, v))
            same = next((r[0] for r in ready if r[4] == fp), None)
            if same:     # 이번 묶음 안의 같은 영상(이름만 다름) — 장부엔 아직 없어 _already_posted 가 못 본다
                print(f"[{n}] {v}: ⛔ 중복 — 이번에 올리는 {same} 와 같은 영상 → 안 올림")
                continue
            todo = []
            for ch in targets:
                dup = _already_posted(rows, n, d, v, fp, ch.get("service"))
                if dup:
                    print(f"[{n}] {v} {ch.get('service')}: ⛔ 중복 — {dup} → 안 올림(정말 다시 올릴 거면 장부에서 그 행을 지워라)")
                else:
                    todo.append(ch)
            if todo:
                ready.append((v, cap, cap_path, block, fp, todo))
        if not ready:
            continue
        # ② 시각: --at 이면 그대로(칸이 차 있으면 거절), 없으면 그 계정의 다음 빈 칸(SLOTS) — 준비된 영상 수만큼만
        dues = _due_list(a.at, a.gap, len(ready)) if a.at else _slot_dues(rows, n, len(ready))
        for due in dues:
            if due and due[:16] in _taken(rows, n):
                raise SystemExit(f"[{n}] {due} 칸에 이미 예약이 있다 — 한 칸에 두 개는 없다(사장님 10-26)")
        for (v, cap, cap_path, block, fp, todo), due in zip(ready, dues):
            done_any = False
            for ch in todo:
                remote = None
                try:
                    remote, url = _upload(os.path.join(d, v))
                    res = buffer_api.schedule_video(key, ch["id"], cap, url, due_at=due, privacy=a.privacy)
                except Exception as e:
                    if remote:
                        try:
                            _remove_remote(remote)
                        except RuntimeError as e2:
                            print(f"   ⚠️ 서버 사본 {remote} 못 지움: {e2}")
                    print(f"[{n}] {v} {ch.get('service')}: 실패 — {e}")
                    fail += 1
                    continue
                rows.append({"folder": n, "channel": ch.get("name"), "service": ch.get("service"), "file": v,
                             "post_id": res["id"], "due": res.get("dueAt") or "큐", "remote": remote, "fp": fp,
                             "inpock": block, "at": dt.datetime.now(KST).isoformat(timespec="seconds")})
                _save_ledger(rows)          # 한 건마다 바로 적는다 — 중간에 끊겨도 다시 돌리면 중복 장치가 막는다
                print(f"[{n}] {v} → {ch.get('service')} {ch.get('name')} 예약 {res.get('dueAt')}  id={res['id']}")
                ok += 1
                done_any = True
            if done_any:
                rsv = os.path.join(d, RESERVED)
                os.makedirs(rsv, exist_ok=True)
                shutil.move(os.path.join(d, v), os.path.join(rsv, v))
                shutil.move(cap_path, os.path.join(rsv, os.path.basename(cap_path)))
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
                try:
                    _remove_remote(remote)
                except RuntimeError as e2:
                    print(f"   ⚠️ 서버 사본 {remote} 못 지움: {e2}")


def main(argv=None):
    p = argparse.ArgumentParser(description="드라이브 버퍼예약 폴더 → Buffer 예약")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "post", "test", "cleanup"):
        s = sub.add_parser(name)
        s.add_argument("--folder")
        if name == "post":
            s.add_argument("--at", help='한국시간 "YYYY-MM-DD HH:MM" (없으면 계정별 다음 빈 15:00·20:00 칸)')
            s.add_argument("--gap", type=float, default=24, help="영상 여러 개일 때 간격(시간)")
            s.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
        if name == "test":
            s.add_argument("--file", help="시험용 mp4(없으면 폴더 첫 영상)")
    a = p.parse_args(argv)
    return {"scan": cmd_scan, "post": cmd_post, "test": cmd_test, "cleanup": cmd_cleanup}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main() or 0)
