# -*- coding: utf-8 -*-
"""회원 PC **실행기**(볼케이노형 손, 관제 234·097 2026-10-21). 서버 지시서(hybrid/flow.py)가 내려 준 do 목록을 그대로 돌리고 measure 를 낸다.
허용된 cmd 만 돈다(서버가 코드·명령줄을 보내지 않는다). 판단은 하지 않는다 — 판정 함수는 rules(서버와 같은 것)를 부른다.

    python -m tools.calcopy.hybrid.runner_ops <작업 폴더> <do.json>      → 표준출력 마지막 줄 = measure JSON {do id: 결과}

유튜브 받기는 yt() 한 곳(요청 사이 쉼 — 10-21 'not a bot' 차단 교훈 · 한국어 제목). SHORTEM_SOURCE_CACHE=<폴더> 면 받아 둔 파일만 쓰고
유튜브는 한 번도 두드리지 않는다(없으면 cache_miss — 시험용, 사장님 10-21 "유튜브는 두드리지 말고 기다려").
옛 자리: hybrid/customer.py(10-21 TheRose PC) 의 기계 함수들 — 볼케이노형 분해 때 이리로 옮겼다.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid import rules as RU  # noqa: E402
from tools.calcopy.hybrid.common import StageError, jload, jsave, run  # noqa: E402

CACHE = os.environ.get("SHORTEM_SOURCE_CACHE") or ""


class CacheMiss(Exception):
    pass


# ── 유튜브 한 곳 ──────────────────────────────────────────────────────────
_last_yt = [0.0]
YT_GAP = float(os.environ.get("SHORTEM_YT_GAP") or 4.0)   # 요청 사이 최소 쉼(초)


def yt(args: list, timeout: int = 300) -> subprocess.CompletedProcess:
    """yt-dlp 한 번 — 한국어 제목(lang=ko, 10-21 영어 번역 제목 #6) · 요청 사이 쉼(not a bot 차단) · 캐시 모드면 부르지 않는다."""
    if CACHE:
        raise CacheMiss("캐시 모드 — 유튜브를 부르지 않는다: " + " ".join(str(a) for a in args[-1:]))
    wait = YT_GAP - (time.time() - _last_yt[0])
    if wait > 0:
        time.sleep(wait)
    from tools.calcopy.origin_find import yt_auth          # 로그인 쿠키(파이어폭스 프로필)·JS 런타임 = 원본찾기와 같은 주인(10-21 회선 'not a bot' 우회)
    url = next((str(a) for a in reversed(args) if "youtu" in str(a) or str(a).startswith("ytsearch")), "https://www.youtube.com/")
    try:
        auth = yt_auth(url if "youtu" in url else "https://www.youtube.com/")
    except PermissionError as e:                 # 전용 프로필에 로그인이 없으면 받지 않는다(주인 = origin_find.yt_auth)
        raise CacheMiss(str(e))
    try:
        return subprocess.run(["yt-dlp", "--encoding", "utf-8", "--no-warnings", "--sleep-requests", "2", "--extractor-args", "youtube:lang=ko", *auth, *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    finally:
        _last_yt[0] = time.time()


def _guard_cache_mode():
    """캐시 모드에선 이 프로세스의 어떤 코드도 yt-dlp 를 못 띄운다(다른 모듈이 직접 부르는 길까지 막는 안전장치)."""
    if not CACHE:
        return
    real = subprocess.Popen.__init__

    def guarded(self, args, *a, **kw):
        first = str(args[0] if isinstance(args, (list, tuple)) else args).lower()
        if "yt-dlp" in first or "yt_dlp" in first:
            raise CacheMiss("캐시 모드 — yt-dlp 호출 막음")
        return real(self, args, *a, **kw)
    subprocess.Popen.__init__ = guarded


def cache_path(*parts) -> Path:
    return Path(CACHE, *parts)


def _safe(q: str) -> str:
    return re.sub(r'[\/:*?"<>|\s]+', "_", q).strip("_")[:80]


def _need(kind: str, items: list):
    """캐시 모드에서 없던 것 — 대신 받기 목록(cache/_need.json)에 쌓는다(10-21: 유튜브는 원본찾기 세션만 쓴다 → 그 세션에 부탁할 목록)."""
    if not CACHE or not items:
        return
    f = cache_path("_need.json")
    cur = jload(f) if f.exists() else {}
    cur.setdefault(kind, [])
    cur[kind] = list(dict.fromkeys(cur[kind] + list(items)))
    jsave(f, cur)


def vid_of(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url or "")
    return m.group(1) if m else (url if re.fullmatch(r"[\w-]{11}", url or "") else "")


# ── 기계 도구 ─────────────────────────────────────────────────────────────
def sheet(video: Path, dst: Path, fps: float = 1.0, cols: int = 6, rows: int = 5, w: int = 300, ss: float | None = None, t: float | None = None) -> Path:
    if Path(video).suffix.lower() in RU.STILL_EXT:      # 사진 재료는 줄여 쓰기만(ffmpeg fps·tile 은 사진 한 장에서 실패 — 98 #23)
        from PIL import Image
        dst.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(video).convert("RGB"); im.thumbnail((w * 2, w * 2)); im.save(dst, quality=85)
        return dst
    pre = (["-ss", f"{ss:.2f}"] if ss is not None else []) + (["-t", f"{t:.2f}"] if t is not None else [])
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", *pre, "-i", str(video), "-vf", f"fps={fps},scale={w}:-1,tile={cols}x{rows}", "-frames:v", "1", str(dst)])
    return dst


def frame(video: Path, t: float, dst: Path, crop: list | None = None) -> Path:
    vf = ["-vf", f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}"] if crop else []
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", *vf, str(dst)])
    return dst


def asr(path: Path, engine: str | None = None) -> list[dict]:
    """받아쓰기 → [{t0, t1, text}] — 창구 = engine/asr_local.transcribe 한 곳(스피치매틱스 = 회원 키 있을 때)."""
    from tools.calcopy.engine import asr_local
    r = asr_local.transcribe(str(path), engine=engine)
    return [{"t0": s.get("start", s.get("t0", 0)), "t1": s.get("end", s.get("t1", 0)), "text": s.get("text", "")} for s in (r.get("segments") or [])]


def have_speechmatics() -> bool:
    try:
        from tools.calcopy.engine import asr_local
        return bool(asr_local.speechmatics_key())
    except Exception:  # noqa: BLE001
        return False


def asr_cross(path: Path) -> dict:
    """사장님 10-21: 스피치매틱스 먼저 + 위스퍼 교차. 키 없으면 위스퍼만(single 표식)."""
    out = {"whisper": " ".join(x["text"] for x in asr(path, engine="whisper"))}
    if have_speechmatics():
        out["speechmatics"] = " ".join(x["text"] for x in asr(path, engine="speechmatics"))
    else:
        out["single"] = True
    return out


def dims(p: Path) -> dict:
    from tools.calcopy.hybrid.common import probe
    w, h, d = probe(p)
    return {"name": p.name, "w": w, "h": h, "dur": round(d, 2)}


def vtt_words(p: Path) -> list:
    from tools.calcopy.yanshot.common import vtt_words as V
    return [[round(float(t), 2), w] for t, w in V(p)]


def rel(W: Path, p: Path) -> str:
    return Path(os.path.relpath(p, W)).as_posix()


# ── cmd ───────────────────────────────────────────────────────────────────
def c_env(W, d):
    from tools.calcopy.hybrid import styles as STY
    du = shutil.disk_usage(str(W))
    voice = (STY.load(d["version"]).get("voice") or {}).get("voice_id", "")
    keys = {"elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY")), "typecast": bool(os.environ.get("TYPECAST_API_KEY")),
            "coupang": bool(os.environ.get("COUPANG_ACCESS_KEY") and os.environ.get("COUPANG_SECRET_KEY")), "speechmatics": have_speechmatics()}
    dev = os.environ.get("CALCOPY_DEV_MINA_SERVER") == "1" or os.environ.get("SHORTEM_DEV") == "1"
    tools = {t: bool(shutil.which(t)) for t in ("ffmpeg", "ffprobe")} | {"yt-dlp": bool(shutil.which("yt-dlp")) or bool(CACHE)}
    if not all(tools.values()):
        return {"error": f"실행 도구 없음: {[k for k, v in tools.items() if not v]}"}
    return {"keys": keys, "dev": dev, "cache": bool(CACHE), "disk_gb": round(du.free / 1e9, 1), "voice": voice}


def c_bench(W, d):
    bd = W / "bench"; bd.mkdir(exist_ok=True)
    url, vid = d["url"], vid_of(d["url"])
    mp4, info, vtt = bd / "bench.mp4", {}, None
    if CACHE:
        for ext, dst in ((".mp4", mp4), (".info.json", bd / "bench.info.json"), (".ko.vtt", bd / "bench.ko.vtt")):
            s = cache_path("yt", vid + ext)
            if s.exists():
                shutil.copyfile(s, dst)
        if not mp4.exists() and not (bd / "bench.ko.vtt").exists():
            return {"error": f"cache_miss: 벤치 {vid}"}
    else:
        yt(["-f", "bv*[height>=720]+ba/b", "--merge-output-format", "mp4", "--write-info-json", "--write-auto-subs", "--sub-langs", "ko",
            "-o", str(bd / "bench.%(ext)s"), url])
        if not mp4.exists():
            return {"error": "벤치 영상을 받지 못했다"}
    if (bd / "bench.info.json").exists():
        info = jload(bd / "bench.info.json")
    vtt = bd / "bench.ko.vtt" if (bd / "bench.ko.vtt").exists() else None
    out = {"id": info.get("id") or vid, "title": info.get("title"), "channel": info.get("channel"), "date": info.get("upload_date"),
           "dur": info.get("duration"), "desc": (info.get("description") or "")[:1500]}
    if mp4.exists():
        sheet(mp4, bd / "sheet.jpg")
        out["sheet"] = "bench/sheet.jpg"
        lines = asr(mp4)
    else:                              # 받아 둔 벤치에 영상이 없다(시험) — 자막 낱말을 3초씩 묶어 말 줄로
        lines, cur, t0 = [], [], None
        for t, w in vtt_words(vtt):
            if t0 is None:
                t0 = t
            cur.append(w)
            if t - t0 > 3.0:
                lines.append({"t0": t0, "t1": t, "text": " ".join(cur)}); cur, t0 = [], None
        if cur:
            lines.append({"t0": t0, "t1": t0, "text": " ".join(cur)})
        out["note"] = "벤치 영상 없음 — 자막으로 대신(시트 없음)"
    jsave(bd / "asr.json", lines)
    out["lines"] = lines
    return out


def _search(qs: list[str], n: int = 12, shorts: bool = False) -> list[dict]:
    """유튜브 검색(한국어 제목). shorts=True 면 '4분 이하' 필터 — 그냥 검색은 긴 영상만 줬다(10-21 선우용여)."""
    if CACHE:                       # 받아 둔 검색 결과 — 검색어별(search/<검색어>.json, 대신 받기) 있으면 그것, 없으면 _default(정답지 시험)
        out, seen, miss = [], set(), []
        for q in qs[:10]:
            f = cache_path("search", _safe(q) + ".json")
            if not f.exists():
                miss.append(q); continue
            for e in jload(f):
                if e.get("id") in seen:
                    next(x for x in out if x["id"] == e["id"])["qs"].append(q); continue
                seen.add(e.get("id")); out.append({**e, "q": q, "qs": [q]})
        if out or not cache_path("search", "_default.json").exists():
            _need("search", miss)
            return out
        return jload(cache_path("search", "_default.json"))
    from urllib.parse import quote
    seen: dict[str, dict] = {}
    for q in qs[:10]:
        src = (f"https://www.youtube.com/results?search_query={quote(q)}&sp=EgIYAQ%253D%253D" if shorts else f"ytsearch{n}:{q}")
        r = yt(["--flat-playlist", "-J", "--playlist-end", str(n), src], timeout=180)
        if r.returncode != 0 or not r.stdout.strip():
            continue
        for e in json.loads(r.stdout).get("entries") or []:
            if not e.get("id"):
                continue
            if e["id"] in seen:                       # 여러 검색어에 걸린 영상 = 원본일 가능성이 높다 — 걸린 검색어를 다 남긴다(서버가 순서를 정한다)
                seen[e["id"]]["qs"].append(q)
                continue
            seen[e["id"]] = {"id": e["id"], "title": e.get("title"), "channel": e.get("channel") or e.get("uploader"), "dur": e.get("duration"),
                             "views": e.get("view_count"), "q": q, "qs": [q], "channel_id": e.get("channel_id")}
    return list(seen.values())


def _blocked(r) -> bool:
    """유튜브 봇 확인(회선·계정 차단) — '원본 없음'과 갈라서 알린다(10-21 yt1 계정까지 막힘)."""
    t = (getattr(r, "stderr", "") or "")
    return "not a bot" in t or "봇이 아님" in t or "Sign in to confirm" in t


def c_search(W, d):
    return {"found": _search(d.get("queries") or [], int(d.get("n") or 12), bool(d.get("shorts")))}


def c_peer_sheet(W, d):
    """같은 연예인+제품을 다룬 남의 쇼츠의 '출처:' 글자 읽기용 장면 모음(사장님 10-21 "다른 사람이 만든 영상에 원본 출처가 나온다").
    그 쇼츠 영상은 재료로 쓰지 않는다(출처 읽기만)."""
    if CACHE:
        return {"sheet": None, "note": "캐시 모드 — 남의 쇼츠 출처 읽기 건너뜀"}
    from PIL import Image, ImageDraw
    found = _search(d.get("queries") or [], n=10, shorts=True)
    shorts = [c for c in found if c["id"] != d.get("bench_id") and 0 < (c.get("dur") or 0) <= 75][:5]
    pd = W / "peer"; pd.mkdir(exist_ok=True)
    rows = []
    for i, c in enumerate(shorts, 1):
        mp4 = pd / f"{c['id']}.mp4"
        if not mp4.exists():
            yt(["-f", "worst[height>=360][ext=mp4]/worst[ext=mp4]/worst", "--download-sections", "*0-20", "-o", str(mp4),
                f"https://www.youtube.com/watch?v={c['id']}"], timeout=180)
        if not mp4.exists():
            continue
        tiles = []
        for t in (1.5, 6.0, 12.0):
            f = pd / f"{c['id']}_{t}.jpg"
            try:
                frame(mp4, t, f)
                im = Image.open(f).convert("RGB"); im.thumbnail((200, 360)); tiles.append(im)
            except Exception:  # noqa: BLE001 — 짧은 쇼츠는 뒤 장면이 없을 수 있다
                pass
        if tiles:
            row = Image.new("RGB", (40 + 200 * len(tiles), 360), (0, 0, 0))
            ImageDraw.Draw(row).text((8, 170), str(i), fill=(255, 255, 0))
            for k, im in enumerate(tiles):
                row.paste(im, (40 + 200 * k, 0))
            rows.append(row)
    if not rows:
        return {"sheet": None}
    sh = Image.new("RGB", (max(x.width for x in rows), 360 * len(rows)), (0, 0, 0))
    for k, row in enumerate(rows):
        sh.paste(row, (0, 360 * k))
    sp = pd / "peer_sheet.jpg"; sh.save(sp, quality=85)
    return {"sheet": rel(W, sp), "n": len(rows)}


def c_channel_list(W, d):
    if CACHE:
        titles, miss = [], []
        for cid in (d.get("channels") or [])[:3]:
            f = cache_path("channel", f"{cid}.json")
            if f.exists():
                titles += jload(f)
            else:
                miss.append(cid)
        if not titles and cache_path("channel", "_default.json").exists():
            return {"titles": jload(cache_path("channel", "_default.json"))}
        _need("channel", miss)
        return {"titles": titles}
    titles = []
    for cid in (d.get("channels") or [])[:3]:
        r = yt(["--flat-playlist", "-J", "--playlist-end", str(int(d.get("n") or 300)), f"https://www.youtube.com/channel/{cid}/videos"], timeout=240)
        if r.returncode == 0 and r.stdout.strip():
            titles += [{"id": e["id"], "title": e.get("title"), "dur": e.get("duration")} for e in json.loads(r.stdout).get("entries") or [] if e.get("id")]
    return {"titles": titles}


def _origin_words(W: Path, vid: str) -> tuple[list, str]:
    """원본 후보의 말 낱말(초) — 자동자막(원래 말 ko-orig 먼저), 캐시에 자막이 없고 영상만 있으면 받아쓰기(표식 asr)."""
    od = W / "origin"; od.mkdir(exist_ok=True)
    if CACHE:
        v = cache_path("yt", vid + ".ko.vtt")
        if v.exists():
            return vtt_words(v), "자동자막"
        mp4 = cache_path("yt", vid + ".mp4")
        if mp4.exists():
            cw = od / f"{vid}.asrwords.json"
            if not cw.exists():
                words = []
                for s in asr(mp4):
                    toks = str(s["text"]).split()
                    for k, w in enumerate(toks):
                        words.append([round(float(s["t0"]) + (float(s["t1"]) - float(s["t0"])) * k / max(1, len(toks)), 2), w])
                jsave(cw, words)
            return jload(cw), "받아쓰기"
        return [], ""
    vtt = next(iter(sorted(od.glob(f"{vid}*.ko-orig.vtt")) + sorted(od.glob(f"{vid}*.ko.vtt"))), None)
    if not vtt:
        r = yt(["--skip-download", "--write-auto-subs", "--sub-langs", "ko-orig,ko", "-o", str(od / f"{vid}.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"], timeout=180)
        if _blocked(r):
            return [], "blocked"
        vtt = next(iter(sorted(od.glob(f"{vid}*.ko-orig.vtt")) + sorted(od.glob(f"{vid}*.ko.vtt"))), None)
    return (vtt_words(vtt), "자동자막") if vtt else ([], "")


def c_origin_subs(W, d):
    lines = jload(W / "bench" / "asr.json") if (W / "bench" / "asr.json").exists() else []
    matched, blocked, nosub, hits = {}, [], [], {}
    terms = [t for t in d.get("terms") or [] if t]
    for vid in d.get("ids") or []:
        words, how = _origin_words(W, vid)
        if how == "blocked":
            blocked.append(vid)
            if len(blocked) >= 2:                     # 막히면 더 두드리지 않는다(계정 보호)
                break
            continue
        if not words:
            nosub.append(vid)
            continue
        if terms:
            h = RU.word_hits(words, terms)         # 벤치가 내레이션뿐일 때 쓰는 단서(장면·제품 낱말 시각) — 낱말 본문은 PC 에 남긴다
            if h:
                hits[vid] = h
        m = RU.fingerprint(lines, words)
        if m:
            matched[vid] = m
            if len(m) >= 3:                          # 세 줄 이상 맞은 후보가 나왔다 — 나머지 자막은 받지 않는다(계정 한도 아끼기, 확정은 서버·판정이)
                break
    return {"matched": matched, "blocked": blocked, "nosub": nosub, "hits": hits}


def origin_offset(W: Path, vid: str, src: Path, guess: float, ts: list[float]) -> tuple[float, bool]:
    """받은 원본 파일 0초 = 원본 몇 초인가 — **잰다**(판단 주인). 구간 받기는 조각 단위로 잘려 요청보다 앞에서 시작한다
    (10-21 선우용여: 요청 360.5초 → 실제 약 340초) → 벤치 말이 맞은 자리 근처를 받아쓰고 원본 자막과 대조 → (원본 초 − 파일 초)의 가운데 값."""
    from statistics import median
    words, _ = _origin_words(W, vid)
    if not words or not ts:
        return guess, False
    f0 = max(0.0, min(ts) - guess - 45)
    wav = W / "origin" / "offset.wav"
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{f0:.2f}", "-t", "90", "-i", str(src), "-ac", "1", "-ar", "16000", str(wav)])
    diffs = []
    for seg in asr(wav):
        m = RU.fingerprint([seg], words)
        if m:
            diffs.append(m[0]["origin_t"] - (f0 + float(seg["t0"])))
    if len(diffs) < 2:
        return guess, False
    return round(median(diffs), 2), True


def c_origin_get(W, d):
    vid, a, b = d["vid"], float(d["a"]), float(d["b"])
    src = W / "src"; src.mkdir(exist_ok=True)
    dst = src / f"{vid}.mp4"
    if CACHE:
        s = cache_path("yt", vid + ".mp4")
        if not s.exists():
            return {"error": f"cache_miss: 원본 {vid}"}
        if not dst.exists():
            shutil.copyfile(s, dst)
        return {"files": [dims(dst)], "offset": 0.0, "measured": True, "note": "캐시 원본 = 전체 파일(0초 = 원본 0초)"}
    from tools.calcopy.hybrid import screen
    files = screen.download(W, [vid], [(a, b)], prefix="")
    if not files:
        return {"error": "원본 받기 실패"}
    guess = a
    if dims(Path(files[-1]))["dur"] > (b - a) + 120:   # 구간 대신 통째로 받았다(screen.download 대체 길) → 파일 0초 = 원본 0초에서 잰다
        guess = 0.0
    off, ok = origin_offset(W, vid, Path(files[-1]), guess, [float(x) for x in d.get("ts") or []])
    return {"files": [dims(Path(f)) for f in files], "offset": off, "measured": ok}


def c_sheet(W, d):
    p = sheet(W / d["src"], W / d["dst"], float(d.get("fps") or 1), int(d.get("cols") or 6), int(d.get("rows") or 5), int(d.get("w") or 300),
              d.get("ss"), d.get("t"))
    return {"file": rel(W, p)}


def c_frames(W, d):
    out = []
    for i, s in enumerate(d.get("items") or []):
        try:
            out.append(rel(W, frame(W / d["src"], float(s["t"]), W / f"{d['prefix']}{i + 1}.jpg", s.get("crop") if isinstance(s.get("crop"), list) else None)))
        except Exception:  # noqa: BLE001 — 자르기 실패한 장면은 빼고 나머지로
            continue
    return {"files": out}


def coupang_chrome(queries: list[str], home: Path) -> dict:
    """회원 파트너스 키가 없을 때(사장님 10-21) — 회원 PC 크롬 창(화면 뜸, 쿠팡은 헤드리스를 막는다)으로 검색 결과 카드만 읽는다.
    동선·추출·파싱 = 서비스 크롤러(shopping_shorts/coupang_search) 그대로 — 홈 먼저 → 검색 → 상품 칸 기다림."""
    from playwright.sync_api import sync_playwright
    from shopping_shorts import coupang_partners as cp, coupang_search as cs
    res = {}
    prof = home / "browser" / "coupang"
    prof.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(prof), headless=False, channel="chrome", locale="ko-KR", viewport={"width": 1366, "height": 900},
                                                   args=["--disable-blink-features=AutomationControlled"])
        try:
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                pg.goto("https://www.coupang.com/", wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_timeout(900)
            except Exception:  # noqa: BLE001 — 홈이 늦어도 검색은 해 본다
                pass
            for q in queries[:4]:
                pg.goto(cp.search_url(q), wait_until="domcontentloaded", timeout=30000)
                try:
                    pg.wait_for_selector("li[class*=ProductUnit_productUnit]", timeout=15000)
                except Exception:  # noqa: BLE001
                    pass
                items = cs.parse_items(pg.evaluate(cs._EXTRACT_JS, 12), limit=12)
                res[q] = {"ok": bool(items), "items": items}
                pg.wait_for_timeout(1500)                     # 몰아치면 쿠팡이 잠시 막는다(서비스 크롤러 실측)
        finally:
            ctx.close()
    return res


def c_coupang(W, d):
    from tools.calcopy import coupang_customer as C
    qs = [q for q in d.get("queries") or [] if q][:6]
    found = C.search(qs)
    home = Path(os.environ.get("SHORTEM_HOME") or (W.parent / "_home"))
    if any((v or {}).get("need") == "chrome" for v in found.values()):
        found = coupang_chrome(qs, home)
    elif not any(it.get("rating") for v in found.values() for it in (v or {}).get("items") or []):
        # 파트너스 API 는 후기 수 칸이 없다(98 #11) → 같은 검색어 크롬 카드에서 후기 수만 product_id 로 채운다. 막히면 빈 채로(대본에 '후기 많은'을 못 쓴다)
        try:
            rate = {str(it.get("product_id")): it.get("rating") for v in coupang_chrome(qs, home).values() for it in (v or {}).get("items") or [] if it.get("rating")}
        except Exception as e:  # noqa: BLE001
            rate = {}
            sys.stderr.write(f"[coupang] 후기 수 크롬 읽기 실패: {type(e).__name__}: {e}\n")
        for v in found.values():
            for it in (v or {}).get("items") or []:
                it["rating"] = rate.get(str(it.get("product_id")), it.get("rating") or "")
    jsave(W / "look" / f"coupang_{int(time.time())}.json", found)
    items, seen = [], set()
    for v in found.values():
        for it in (v or {}).get("items") or []:
            k = str(it.get("product_id") or it.get("productId") or it.get("id") or it.get("name"))
            if k not in seen:
                seen.add(k); items.append(it)
    return {"items": items[:16]}


def _naver_text(q: str, limit: int = 2500) -> str:
    """네이버 통합검색 글(연예인 이름 앞뒤만) — 회원 PC 에서 바로 연다(키 없음)."""
    import html as H
    import urllib.parse
    import urllib.request
    try:
        req = urllib.request.Request("https://search.naver.com/search.naver?query=" + urllib.parse.quote(q),
                                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36", "Accept-Language": "ko"})
        t = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — 포털이 막혀도 유튜브 글로 이어 간다(이유는 남긴다)
        return f"(네이버 검색 실패: {type(e).__name__})"
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", t)
    t = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", t)))
    key = q.split()[0]
    out, last = [], -1
    for m in re.finditer(re.escape(key), t):
        if m.start() < last:
            continue
        out.append(t[max(0, m.start() - 80):m.start() + 220]); last = m.start() + 220
    return " … ".join(out)[:limit]


def c_naver(W, d):
    return {"texts": {q: _naver_text(q) for q in (d.get("queries") or [])[:3]}}


def c_origin_words(W, d):
    words, how = _origin_words(W, d["vid"])
    if not words:                       # 자막이 아예 없다 → 받은 파일을 받아써 원본 초로(t0 더함)
        t0 = float(d.get("t0") or 0)
        for s in asr(W / d["src"]):
            words.append([round(float(s["t0"]) + t0, 2), s["text"]])
        how = "받아쓰기"
    return {"words": words, "from": how}


def c_screen(W, d):
    """재료 후보(제작순서 05) — 받기·시트는 screen 모듈(yt-dlp 만). 캐시 모드면 받아 둔 재료 영상으로 시트를 만든다."""
    skip = {d.get("bench_id"), d.get("origin_id")}
    sd = W / "screen"; sd.mkdir(parents=True, exist_ok=True)
    if CACHE:
        rows, sheets = [], []
        for mp4 in sorted(cache_path("material").glob("*.mp4")):
            vid = mp4.stem
            if vid in skip:
                continue
            info = jload(mp4.with_suffix(".info.json")) if mp4.with_suffix(".info.json").exists() else {}
            sp = sheet(mp4, sd / f"{vid}_sheet.jpg", fps=0.2, cols=6, rows=4, w=240)
            dd = dims(mp4)
            rows.append({"id": vid, "title": info.get("title"), "channel": info.get("channel"), "max_height": dd["h"], "dur": dd["dur"]})
            sheets.append(rel(W, sp))
        return {"rows": rows, "sheets": sheets, "note": "캐시 재료"}
    from tools.calcopy.hybrid import screen
    screen.search(W, d.get("queries") or [], n=10, exclude=d.get("exclude"), server=False)
    sj = screen.screen(W, d.get("keywords") or [], top=int(d.get("top") or 8))
    rows = [x for x in sj.get("rows") or [] if x.get("id") not in skip]
    sheets = [rel(W, W / "screen" / f"{x['id']}_sheet.jpg") for x in rows if (W / "screen" / f"{x['id']}_sheet.jpg").exists()][:8]
    meta = [{k: x.get(k) for k in ("id", "title", "channel", "max_height", "dur", "hits", "score")} for x in rows][:8]
    return {"rows": meta, "sheets": sheets}


def c_download(W, d):
    src = W / "src"; src.mkdir(exist_ok=True)
    files = []
    for it in d.get("items") or []:
        vid = it["id"]
        if CACHE:
            s = cache_path("material", vid + ".mp4")
            if s.exists():
                shutil.copyfile(s, src / f"{vid}.mp4")
                files.append(dims(src / f"{vid}.mp4"))
            continue
        from tools.calcopy.hybrid import screen
        secs = [tuple(x) for x in it.get("sections") or []] or None
        for f in screen.download(W, [vid], secs, prefix=""):
            files.append(dims(Path(f)))
    return {"files": files}


def c_product_stills(W, d):
    """고른 쿠팡 상품의 사진(쿠팡 검색 결과 image) → src/prod_<id>_<k>.jpg — 제작순서 05 '리뷰 영상이 없으면 쿠팡 상품 사진을 움직이는 컷으로'
    (10-21 선우용여: 제품 영상이 약사 설명·연출뿐이라 제품 컷 0개, 98 #22). 주소만 다르고 같은 사진은 거른다."""
    import hashlib
    import urllib.request
    pid = str(d.get("product_id") or "")
    if not pid:
        return {"files": []}
    urls = []
    for f in sorted((W / "look").glob("coupang*.json")):
        for v in jload(f).values():
            for it in (v or {}).get("items") or []:
                if str(it.get("product_id") or it.get("productId") or "") == pid and it.get("image") and it["image"] not in urls:
                    urls.append(it["image"])
    (W / "src").mkdir(exist_ok=True)
    out, seen, fail = [], set(), []
    for k, u in enumerate(urls[:int(d.get("n") or 4)]):
        dst = W / "src" / f"prod_{pid}_{k}.jpg"
        try:
            if not dst.exists():
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                dst.write_bytes(urllib.request.urlopen(req, timeout=20).read())
            h = hashlib.sha1(dst.read_bytes()).hexdigest()
            if h in seen:
                dst.unlink(); continue
            seen.add(h)
            if dst.stat().st_size > 2000:
                out.append(dims(dst))
        except Exception as e:  # noqa: BLE001 — 사진 하나 실패는 건너뛰되 남긴다
            fail.append(f"{u[:60]}: {type(e).__name__}")
    return {"files": out, **({"fail": fail} if fail else {})}


HEARD_MIN = 0.6       # 원음 줄 자막 ↔ 그 구간 받아쓰기 닮음 최소(10-21 선우용여: 맞는 줄 0.8+, 어긋난 줄 0.3~0.5)


def c_orig_heard(W, d):
    """원음 줄마다 그 구간을 **실제로 받아써** 자막과 대조 — 집 PC 워커가 귀로 하던 확인(98 #20). 다르면 앞뒤 3초 받아쓰기(파일 초)를 붙인다."""
    import difflib
    S = jload(W / "doc" / d["version"] / "대본.json")
    ad = W / "asr"; ad.mkdir(exist_ok=True)
    bad = []
    for l in S.get("lines") or []:
        if l.get("kind") != "orig" or not l.get("spans"):
            continue
        src = W / "src" / str(l.get("src") or "")
        if not src.exists():
            continue
        a, b = float(l["spans"][0][0]), float(l["spans"][-1][1])
        cap = RU.norm("".join(str(c[0]) for c in l.get("caps_rel") or []))
        w = ad / f"chk_{l['id']}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.2f}", "-to", f"{b:.2f}", "-i", str(src), "-ac", "1", "-ar", "16000", str(w)])
        heard = " ".join(x["text"] for x in asr(w))
        r = difflib.SequenceMatcher(None, cap, RU.norm(heard)).ratio() if cap else 1.0
        if r < HEARD_MIN:
            wide = ad / f"chk_{l['id']}_wide.wav"
            w0 = max(0.0, a - 3)
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{w0:.2f}", "-to", f"{b + 3:.2f}", "-i", str(src), "-ac", "1", "-ar", "16000", str(wide)])
            near = " / ".join(f"{w0 + float(x['t0']):.2f}~{w0 + float(x['t1']):.2f} {x['text']}" for x in asr(wide))
            bad.append(f"{l['id']}: 자막 '{' '.join(str(c[0]) for c in l.get('caps_rel') or [])}' 인데 {a:.2f}~{b:.2f}초에 실제로 들리는 말은 '{heard}'(닮음 {r:.2f}). "
                       f"앞뒤 받아쓰기(파일 초): {near} — 구간을 그 말이 들리는 자리로 옮기고, 다른 출연자 말이 섞이면 빼라")
    return {"bad": bad}


def c_asr_spans(W, d):
    """원음 구간 받아쓰기 — 스피치매틱스(키 있으면) + 위스퍼 교차(사장님 10-21)."""
    src = W / d["src"]
    ad = W / "asr"; ad.mkdir(exist_ok=True)
    out = []
    for s in d.get("spans") or []:
        wav = ad / f"{s.get('tag', 'O')}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{float(s['a']):.2f}", "-to", f"{float(s['b']):.2f}", "-i", str(src), "-ac", "1", "-ar", "16000", str(wav)])
        out.append({**s, "src": src.name, **asr_cross(wav)})
    jsave(ad / "result.json", {"spans": out})
    return {"spans": out}


def c_shot_sheets(W, d):
    """원본 샷(카메라가 바뀌는 곳) 표의 뼈대 + 판독용 모음 그림(8×5) — 판독(누가·제품·얼굴 가로 위치)은 회원 Claude 가 서버 질문으로."""
    from PIL import Image, ImageDraw
    from tools.calcopy.yanshot.plan import shots_in
    shots_all, sheets_all = {}, {}
    sd = W / "_shots"; sd.mkdir(exist_ok=True)
    for f in d.get("files") or []:
        src = W / f
        if not src.exists():
            continue
        dd = dims(src)["dur"]
        shots = [{"i": i, "a": round(a, 3), "b": round(b, 3)} for i, (a, b) in enumerate(shots_in(src, [(0.0, dd)]))]
        shots_all[src.stem], sheets_all[src.stem] = shots, []
        for k in range(0, len(shots), 40):
            part = shots[k:k + 40]
            sh = Image.new("RGB", (8 * 240, 5 * 160), (0, 0, 0))
            for j, s in enumerate(part):
                fp = sd / f"{src.stem}_{s['i']:03d}.jpg"
                try:
                    frame(src, (s["a"] + s["b"]) / 2, fp)
                    im = Image.open(fp).convert("RGB"); im.thumbnail((240, 160))
                except Exception:  # noqa: BLE001 — 못 뜬 샷은 빈칸(판독이 none 으로 둔다)
                    continue
                sh.paste(im, ((j % 8) * 240, (j // 8) * 160))
                dr = ImageDraw.Draw(sh)
                dr.rectangle(((j % 8) * 240, (j // 8) * 160, (j % 8) * 240 + 150, (j // 8) * 160 + 16), fill=(0, 0, 0))
                dr.text(((j % 8) * 240 + 3, (j // 8) * 160 + 2), f"#{s['i']} {s['a']:.1f}~{s['b']:.1f}", fill=(255, 255, 0))
            p = sd / f"{src.stem}_sheet{k // 40}.jpg"; sh.save(p, quality=85)
            sheets_all[src.stem].append(rel(W, p))
    return {"shots": shots_all, "sheets": sheets_all}


def c_mat_sheets(W, d):
    sheets, lst = [], []
    for f in d.get("files") or []:
        p = W / f
        if not p.exists():
            continue
        lst.append({"file": p.name, "dur": dims(p)["dur"]})
        sheets.append(rel(W, sheet(p, W / f"_sheet_{p.stem[:40]}.jpg", fps=0.5, cols=6, rows=5, w=240)))
    return {"sheets": sheets, "list": lst}


def c_write_doc(W, d):
    D = W / "doc"
    for relp, body in (d.get("files") or {}).items():
        p = D / relp
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, (dict, list)):
            if relp.endswith("재료.json") and d.get("cand_dir"):
                body = {**body, "cand_dir": str(W / "src")}
            jsave(p, body)
        else:
            p.write_text(str(body), encoding="utf-8")
    return {"ok": True}


def _cut_jumps(src: Path, ss: float, dur: float, fps: int = 10, n: int = 64) -> list[float]:
    """컷 구간 안 프레임끼리 바뀐 정도(회색 64칸 평균 차) — 장면 전환·끊김을 잰다(1초 시트 사이로 지나가는 0.5초 전환은 눈 검수가 못 본다)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.2f}", "-t", f"{dur:.2f}", "-i", str(src), "-vf", f"fps={fps},scale={n}:{n}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, stdin=subprocess.DEVNULL, timeout=120).stdout
    a = np.frombuffer(raw, np.uint8)
    if a.size < 2 * n * n:
        return []
    a = a[: a.size // (n * n) * n * n].reshape(-1, n, n).astype(float)
    return [float(x) for x in np.abs(np.diff(a, axis=0)).mean((1, 2))]


def source_rule_scan(W: Path, T: dict, origin_names: set) -> list[str]:
    """출처 규칙 ③ — 원본 밖 재료 컷에 장면 전환이 섞였나(10-21 이미도: 리뷰여왕 별 전환 최고 73·상위10% 53 / 다른 재료 컷 최고 28 이하)."""
    out = []
    for c in (T or {}).get("cuts") or []:
        src = str(c.get("src") or "")
        p = W / "src" / src
        if not src or src in origin_names or not p.exists() or not c.get("dur"):
            continue
        dd = [] if p.suffix.lower() in RU.STILL_EXT else _cut_jumps(p, float(c.get("ss") or 0), float(c["dur"]))
        if dd and (max(dd) > 40 or sum(x > 25 for x in dd) >= 3):
            out.append(f"{c.get('line')}: {src} {float(c.get('ss') or 0):.1f}초부터 {float(c['dur']):.1f}초 안에 장면 전환·끊김이 있다(남의 영상 편집 효과) — 시작점을 옮기거나 다른 장면으로")
        n = _cut_faces(W, p, float(c.get("ss") or 0), float(c["dur"]), c.get("crop"))
        if n:
            out.append(f"{c.get('line')}: {src} {float(c.get('ss') or 0):.1f}초부터 화면에 사람 얼굴이 보인다(원본 밖 영상의 다른 사람 — 광고 모델·리뷰어) — 원본 밖 재료는 사람 없는 제품 장면만")
    return out


FACE_OTHER_FRAC = 0.10     # 원본 밖 컷에서 '사람이 보인다'로 칠 얼굴 높이(화면 칸 높이 비율) — 10-22 고현정 편 롱샴 광고 모델 얼굴(칸 높이 약 0.2)


def _cut_faces(W: Path, src: Path, ss: float, dur: float, crop) -> int:
    """원본 밖 재료 컷(재료 영상·상품 사진) 안 사람 얼굴 수 — **잰다**(계획의 face 칸은 계획을 짠 쪽이 적는 값이라 광고 모델 얼굴을 ''로 적고 지나갔다, 98 #38).
    컷 안 세 시점(사진은 한 장)을 계획 칸(crop)대로 잘라 보고, 칸 높이의 FACE_OTHER_FRAC 이상인 얼굴이 하나라도 있으면 그 수."""
    import cv2
    import numpy as np
    from tools.calcopy.hybrid.common import FACE_MODEL
    from tools.calcopy.hybrid import thumb
    if not Path(FACE_MODEL).exists():
        sys.stderr.write(f"[faces] 얼굴 모델 없음 {FACE_MODEL} — 원본 밖 컷 얼굴 검사를 건너뜀\n")
        return 0
    det = cv2.FaceDetectorYN.create(FACE_MODEL, "", (320, 320), 0.6, 0.3, 50)
    tmp = W / "_faces"; tmp.mkdir(exist_ok=True)
    still = src.suffix.lower() in RU.STILL_EXT
    worst = 0
    for k, t in enumerate([0.0] if still else [ss + dur * f for f in (0.15, 0.5, 0.85)]):
        f = src if still else tmp / f"{src.stem}_{k}.jpg"
        if not still:
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1", str(f)])
        im = cv2.imdecode(np.fromfile(str(f), np.uint8), cv2.IMREAD_COLOR) if f.exists() else None   # cv2.imread 는 한글 경로를 못 연다
        if im is None:
            continue
        if isinstance(crop, list) and len(crop) == 4:
            x, y, w, h = [max(0, int(v)) for v in crop]
            im = im[y:y + h, x:x + w] if w > 0 and h > 0 else im
        H = im.shape[0]
        worst = max(worst, sum(1 for o in thumb.faces_of(det, im) if o["h"] >= FACE_OTHER_FRAC * H))
    return worst


def plan_sheet(W: Path, version: str, T: dict) -> Path:
    """계획 시간표의 컷마다 가운데 한 장(렌더러와 같은 크롭) → 모음 그림 — 렌더 전 눈 확인용."""
    from PIL import Image, ImageDraw
    from tools.calcopy.hybrid import render_bench, styles as STY
    M = jload(W / "doc" / version / "재료.json")
    cand = Path(M.get("cand_dir") or (W / "src"))
    _, _, ww, wh = STY.load(version)["frame"]["window"]
    tiles = []
    for i, c in enumerate(T.get("cuts") or []):
        src = cand / str(c.get("src") or "")
        if not src.exists():
            continue
        f = W / "_plan" / f"c{i:02d}.jpg"
        crop = c.get("crop", "face")
        t = float(c.get("ss") or 0) + min(0.5, float(c.get("dur") or 0) / 2)
        try:
            if crop == "face" and src.suffix.lower() not in render_bench.IMG_EXT:
                crop = render_bench.face_crop(src, t, ww / wh)
            frame(src, t, f, crop if isinstance(crop, list) else None)
            im = Image.open(f).convert("RGB")
            im.thumbnail((220, 220))
            dr = ImageDraw.Draw(im)
            dr.rectangle((0, 0, im.width, 18), fill=(0, 0, 0))
            dr.text((3, 2), f"{c.get('line')} {c.get('t0')}~{c.get('t1')}", fill=(255, 255, 0))
            tiles.append(im)
        except Exception:  # noqa: BLE001 — 못 뜬 컷은 시트에서 빠진다(검수가 본다)
            continue
    out = W / version / "plan_sheet.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = 6
    sh = Image.new("RGB", (220 * cols, 220 * max(1, -(-len(tiles) // cols))), (20, 20, 20))
    for k, im in enumerate(tiles):
        sh.paste(im, ((k % cols) * 220, (k // cols) * 220))
    sh.save(out, quality=85)
    return out


def _origin_names(W: Path, version: str) -> set:
    try:
        S = jload(W / "doc" / version / "대본.json")
        return {str(l.get("src")) for l in S.get("lines") or [] if l.get("kind") == "orig" and l.get("src")} | set(json.loads(os.environ.get("SHORTEM_ORIGIN_NAMES", "[]")))
    except Exception:  # noqa: BLE001
        return set()


def c_plan(W, d):
    from tools.calcopy.hybrid import render_bench
    v = d["version"]
    try:
        res, over = render_bench.render(v, W / "doc" / v, W / v, plan_only=True), ""
    except StageError as e:          # 컷이 원본 샷보다 길다 → 재료를 고치게 한다
        res, over = {"timeline": {"cuts": []}}, str(e)
    T = res.get("timeline") or {}
    out = {"over": over, "cuts": len(T.get("cuts") or [])}
    if T.get("cuts"):
        out["sheet"] = rel(W, plan_sheet(W, v, T))
        out["jumps"] = source_rule_scan(W, T, _origin_names(W, v) | set(d.get("origin_names") or []))
    return out


def c_render(W, d):
    from tools.calcopy.hybrid import render_bench
    v = d["version"]
    try:
        render_bench.render(v, W / "doc" / v, W / v)
    except StageError as e:
        return {"ok": False, "error": str(e)[:600]}
    T = jload(W / v / "render" / "timeline.json") if (W / v / "render" / "timeline.json").exists() else {}
    jumps = source_rule_scan(W, T, _origin_names(W, v) | set(d.get("origin_names") or []))
    return {"ok": (W / v / "render" / "final.mp4").exists() and not jumps, "jumps": jumps}


def c_check(W, d):
    from tools.calcopy.hybrid import bench_check
    v = d["version"]
    final = W / v / "render" / "final.mp4"
    if not final.exists():
        return {"error": "완성본 없음"}
    auto = bench_check.check(v, W / "doc" / v, W / v)
    sh = W / "doc" / v / "final_sheet_1s.jpg"
    if not sh.exists():
        sheet(final, sh, fps=1, cols=6, rows=6, w=240)
    rep = auto.get("report")
    if isinstance(rep, (str, Path)) and Path(rep).exists():          # bench_check 는 보고서 파일 경로를 준다 — 내용(6항목)을 싣는다(10-21: 경로만 가서 검수가 못 봤다)
        rep = jload(rep)
    rows = [{k: r.get(k) for k in ("what", "ok", "value")} for r in (rep or {}).get("rows") or []] if isinstance(rep, dict) else []
    return {"auto": {"ok": bool(auto.get("ok")), "rows": rows}, "heard": asr_cross(final), "sheet": rel(W, sh)}


def c_finish(W, d):
    v = d["version"]
    final = W / v / "render" / "final.mp4"
    return {"video": str(final)} if final.exists() else {"error": "완성본 없음"}


CMDS = {"env": c_env, "bench": c_bench, "search": c_search, "peer_sheet": c_peer_sheet, "channel_list": c_channel_list, "origin_subs": c_origin_subs,
        "origin_get": c_origin_get, "sheet": c_sheet, "frames": c_frames, "coupang": c_coupang, "naver": c_naver, "origin_words": c_origin_words,
        "screen": c_screen, "download": c_download, "product_stills": c_product_stills, "orig_heard": c_orig_heard, "asr_spans": c_asr_spans, "shot_sheets": c_shot_sheets, "mat_sheets": c_mat_sheets,
        "write_doc": c_write_doc, "plan": c_plan, "render": c_render, "check": c_check, "finish": c_finish}


def run_do(W: Path, do: list[dict], log=print) -> dict:
    """do 목록을 순서대로 — 허용 목록 밖 cmd 는 돌리지 않는다. 한 cmd 가 실패해도 그 결과에 error 를 담고 다음으로(판정은 서버)."""
    _guard_cache_mode()
    W.mkdir(parents=True, exist_ok=True)
    out = {}
    for d in do or []:
        fn = CMDS.get(str(d.get("cmd")))
        rid = str(d.get("id") or d.get("cmd"))
        if fn is None:
            out[rid] = {"error": f"허용되지 않은 명령: {d.get('cmd')}"}
            continue
        t0 = time.time()
        try:
            out[rid] = fn(W, d)
        except CacheMiss as e:
            out[rid] = {"error": f"cache_miss: {e}"}
        except StageError as e:
            out[rid] = {"error": str(e)[:600]}
        except Exception as e:  # noqa: BLE001 — 실패 이유를 서버에 그대로(조용히 삼키지 않는다)
            out[rid] = {"error": f"{type(e).__name__}: {str(e)[:500]}"}
        log(f"[runner] {d.get('cmd')} {time.time() - t0:.1f}s {'ERR ' + out[rid]['error'][:120] if isinstance(out[rid], dict) and out[rid].get('error') else 'ok'}")
    return out


def main():
    W, do = Path(sys.argv[1]), jload(sys.argv[2])
    res = run_do(W, do, log=lambda s: print(s, file=sys.stderr))
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
