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
PAID_OFF = os.environ.get("SHORTEM_NO_PAID") == "1"     # '돈 0' 스위치(개발 완주·시험) — TTS 는 캐시만, 스피치매틱스·VMake 안 부름(관제 263 08)


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
    if PAID_OFF:
        return False
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
LOGIN_OK = {"youtube": ("youtube.com", ("__Secure-3PSID", "SAPISID")), "instagram": ("instagram.com", ("sessionid",)),
            "tiktok": ("tiktok.com", ("sessionid", "sid_tt"))}     # 숏템 MCP logins.js PLATFORMS 와 같은 표(회원이 설정 화면 '영상 받기 계정'에서 연결)


def _cookie_ok(platform: str) -> bool:
    """회원 PC 로그인 연결 — 숏템 MCP 가 만든 cookies.txt(엔진 환경 YTDLP_COOKIES_YOUTUBE)에 그 사이트 로그인 쿠키가 살아 있나. 이름·만료만 보고 값은 읽지 않는다."""
    f = os.environ.get("YTDLP_COOKIES_YOUTUBE") or ""
    if platform == "instagram" and os.path.isfile(os.environ.get("INSTAGRAM_SESSION_PATH") or ""):
        return True
    if not f or not os.path.isfile(f):
        return False
    dom, names = LOGIN_OK[platform]
    now = time.time()
    for ln in Path(f).read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln or (ln.startswith("#") and not ln.startswith("#HttpOnly_")):
            continue
        r = ln.replace("#HttpOnly_", "", 1).split("\t")
        if len(r) >= 7 and r[0].lstrip(".").endswith(dom) and r[5] in names and r[6] and (r[4] == "0" or float(r[4] or 0) > now):
            return True
    return False


def need_list(version: str, url: str = "", fmt: str = "") -> list[dict]:
    """첫 제작 요청 준비 점검 — 판단 주인 한 곳(사장님 10-26 "제작에 필요한 도구·API 키를 처음에 점검, 없으면 한 번에 요구 · 도중엔 요구 금지").
    이 판(목소리 엔진·형식·박힌 글자 처리)과 소재 주소에 **실제로 쓰이는 것만** 잰다. 있음 판정은 실제로 부르는 쪽 함수를 그대로 부른다(두 벌 금지).
    → [{id, label(회원 화면 이름), how(setting·login·disk·install)}] — 빈 목록 = 준비 끝. 키 값은 읽어 '있음/없음'만, 출력하지 않는다."""
    from tools.calcopy.hybrid import styles as STY
    from tools.calcopy.engine import voices as VO
    out = []
    tools = {t: bool(shutil.which(t)) for t in ("ffmpeg", "ffprobe")} | {"yt-dlp": bool(shutil.which("yt-dlp")) or bool(CACHE)}
    if not all(tools.values()):
        out.append({"id": "tools:" + ",".join(k for k, v in tools.items() if not v), "label": "숏템 영상 도구", "how": "install"})
    customer = os.environ.get("CALCOPY_CUSTOMER_MODE") == "1"
    st = STY.load(version)
    voice = st.get("voice") or {}
    prov = VO.provider_of(voice)
    if not PAID_OFF:                    # 돈 0 스위치 = 합성은 캐시만(tts_cache_miss) — 목소리 키를 부르지 않는다
        if prov in (None, "typecast"):  # 옛 꼴 모르는 id = 타입캐스트 길(narr_align.old_path)
            from shopping_shorts.channelkit import providers
            if not providers.typecast_key(None):          # narr_align 합성이 쓰는 그 함수(환경변수 → ~/.volcano/keys/typecast)
                out.append({"id": "typecast", "label": "목소리 키(타입캐스트)", "how": "setting"})
        elif prov == "elevenlabs":      # narr_align._synth_eleven 과 같은 조건 — 회원 PC 만 회원 키(우리 PC 는 서버 미나)
            if customer and not os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("CALCOPY_DEV_MINA_SERVER") != "1":
                out.append({"id": "elevenlabs", "label": "목소리 키(일레븐랩스)", "how": "setting"})
        elif prov == "fish":
            from tools.calcopy.engine import preset_make as PM
            if not PM._member_key("fish"):
                out.append({"id": "fish", "label": "목소리 키(피쉬)", "how": "setting"})
    if not PAID_OFF and not have_speechmatics():     # 받아쓰기(원음·완성본 줄별 대조 narr_verify·asr_cross) — 사장님 10-26 '스피치매틱스도 무료 API 필요'. 키 자리 = asr_local.speechmatics_key
        out.append({"id": "speechmatics", "label": "스피치매틱스 키(무료)", "how": "setting"})
    if fmt == "해외원본형":              # 박힌 자막 지우기(VMake)는 이 형식만 부른다(flow f_clean·f_render) — 판 orig_text.mode·키 자리 판단 = vmake_clean.ready
        from tools.calcopy import vmake_clean as VC
        if VC.ready(VC.style_mode(version))["mode"] == "need_key":
            out.append({"id": "vmake", "label": "VMake 키(원본 자막 지우기)", "how": "setting"})
    if not CACHE:                       # 영상 받기·원본 찾기 = 유튜브(모든 형식) + 소재가 인스타·틱톡이면 그 계정
        if customer:
            if not _cookie_ok("youtube"):
                out.append({"id": "login:youtube", "label": "유튜브 계정 연결", "how": "login"})
        else:                            # 우리 PC = 파이어폭스 전용 프로필(주인 origin_find.yt_auth) — 묶음을 정했는데 로그인이 없으면 못 받는다
            from tools.calcopy.origin_find import yt_auth
            try:
                yt_auth("https://www.youtube.com/")
            except PermissionError:
                out.append({"id": "login:youtube", "label": "유튜브 계정 연결", "how": "login"})
        u = str(url or "").lower()
        for pf, name in (("instagram", "인스타그램"), ("tiktok", "틱톡")):
            if LOGIN_OK[pf][0] in u and customer and not _cookie_ok(pf):
                out.append({"id": "login:" + pf, "label": name + " 계정 연결", "how": "login"})
    return out


def c_env(W, d):
    from tools.calcopy.hybrid import styles as STY
    du = shutil.disk_usage(str(W))
    voice = (STY.load(d["version"]).get("voice") or {}).get("voice_id", "")
    keys = {"elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY")), "typecast": bool(os.environ.get("TYPECAST_API_KEY")),
            "coupang": bool(os.environ.get("COUPANG_ACCESS_KEY") and os.environ.get("COUPANG_SECRET_KEY")), "speechmatics": have_speechmatics()}
    dev = os.environ.get("CALCOPY_DEV_MINA_SERVER") == "1" or os.environ.get("SHORTEM_DEV") == "1"
    missing = need_list(d["version"], d.get("url") or "", d.get("fmt") or "")
    if du.free / 1e9 < 1.5:
        missing.append({"id": "disk", "label": "C 드라이브 빈 공간 1.5GB", "how": "disk"})
    try:
        from tools.calcopy.engine import encoder
        enc = encoder.kind()
    except Exception:  # noqa: BLE001 — 도구 없음은 missing 이 이미 알린다
        enc = "cpu"
    return {"keys": keys, "dev": dev, "cache": bool(CACHE), "disk_gb": round(du.free / 1e9, 1), "voice": voice, "missing": missing,
            "encoder": enc}       # 'gpu'(NVENC) | 'cpu' — 그래픽카드 있으면 렌더가 GPU 우선(98 #79)


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
        # 출처 글자 읽기용 큰 장면 한 장(98 #69: 시트 칸 300px 이면 '출처 : 셀코TV' 가 8px — 같은 영상을 '없음'·'쌩코TV'로 읽었다)
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{min(1.5, float(out.get('dur') or 3) / 2):.2f}", "-i", str(mp4), "-frames:v", "1",
             "-vf", "scale=720:-2", str(bd / "big.jpg")])
        if (bd / "big.jpg").exists():
            out["big"] = "bench/big.jpg"
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


def _vsearch(q: str, n: int = 20) -> tuple[list[dict], bool]:
    r = yt(["--flat-playlist", "-J", "--playlist-end", str(n), f"ytsearch{n}:{q}"], timeout=120)
    if _blocked(r):
        return [], True
    if r.returncode != 0 or not r.stdout.strip():
        return [], False
    return [{"id": e["id"], "title": e.get("title"), "dur": e.get("duration"), "channel": e.get("channel"), "channel_id": e.get("channel_id")}
            for e in json.loads(r.stdout).get("entries") or [] if e.get("id")], False


def c_channel_find(W, d):
    """출처 글자 → 실제 채널(사장님 10-22 "가져오는 채널에 출처가 반드시 있다"). 판단 = 서버가 준 kind(채널|프로그램).
    채널: '<출처> 채널' 채널 검색 첫 결과(10-22 강주은: 이름이 같은 채널 8개·인증 표시는 동명이인 — '강주은 채널' 검색 첫 결과는 진짜 '깡주은').
    프로그램: '<연예인> <프로그램>' 영상 검색 → 제목·채널에 프로그램 이름 든 영상만(98 #40)."""
    if CACHE:
        return {"channels": [], "titles": [], "note": "캐시 모드 — 출처 채널 찾기 건너뜀(검색 길로)"}
    from urllib.parse import quote
    label, celeb = str(d.get("label") or ""), str(d.get("celeb") or "")
    nl, nc = RU.norm(label), RU.norm(celeb)
    n = int(d.get("n") or 60)
    if d.get("kind") == "program":
        found, blocked = _vsearch(f"{celeb} {label}".strip())
        if blocked:
            return {"blocked": True, "channels": [], "titles": []}
        titles = [x for x in found if nl and (nl in RU.norm(x["title"] or "") or nl in RU.norm(x["channel"] or ""))]
        return {"channels": [], "picked": [], "how": "search", "titles": titles}
    # 채널: '<출처> 채널' 채널 검색 첫 결과 — 비교하지 않는다(사장님 10-22 "유튜브에 직접 '강주은 채널' 검색하면 바로 된다").
    #   실측: 강주은 채널 → 깡주은 · 고현정 채널 → 고현정 · 요정재형 채널 → 요정재형 (프로그램 이름은 채널이 없어 위 영상 검색 길)
    r = yt(["--flat-playlist", "-J", "--playlist-end", "3", f"https://www.youtube.com/results?search_query={quote(label + ' 채널')}&sp=EgIQAg%253D%253D"], timeout=120)
    if _blocked(r):
        return {"blocked": True, "channels": [], "titles": []}
    chans = []
    if r.returncode == 0 and r.stdout.strip():
        chans = [{"id": e.get("channel_id") or e.get("id"), "name": e.get("channel") or e.get("title"), "handle": e.get("uploader_id")}
                 for e in json.loads(r.stdout).get("entries") or [] if (e.get("channel_id") or e.get("id"))]
    pick = chans[:1]
    if not pick and celeb:
        # 채널 검색이 비면 출처 글자를 잘못 읽었을 수 있다(98 #67: '셀코TV'를 '쌩코TV'로 — 채널 검색 0건) →
        #   '<연예인> <출처>' 영상 검색에서 채널 이름이 출처 글자와 가장 닮은 채널(닮음 0.5 이상, 같은 점수면 많이 나온 쪽)
        #   ('<연예인> <쌩코TV>' 검색은 0건 — 유튜브는 틀린 이름을 고쳐 주지 않는다 → 원본 판독이 낸 '<연예인> <낱말>' 검색 결과의 채널 이름으로 맞춘다)
        import difflib
        found = []
        for q in [f"{celeb} {label}".strip()] + [x for x in d.get("queries") or [] if x][:2]:
            got, blocked = _vsearch(q)
            if blocked:
                return {"blocked": True, "channels": [], "titles": []}
            found += got
        score: dict = {}
        for x in found:
            cname = str(x.get("channel") or "")
            if x.get("channel_id") and cname:
                sim = difflib.SequenceMatcher(None, nl, RU.norm(cname.split("/")[0])).ratio()
                if sim >= 0.5:
                    k = (x["channel_id"], cname)
                    score[k] = (max(sim, score.get(k, (0, 0))[0]), score.get(k, (0, 0))[1] + 1)
        if score:
            (cid, cname), _ = max(score.items(), key=lambda kv: kv[1])
            pick = [{"id": cid, "name": cname, "handle": None, "fuzzy": True}]
    # 채널 안 검색('<연예인> <낱말>') 먼저 — 98 #65: 셀코TV 원본(함익병 기미)은 최신 60편 밖이라 목록만 봐서는 7분 넘게 헤매다 놓쳤다.
    #   채널 안 검색은 2초에 원본이 1위(10-24 실측). 찾은 순서를 searched 로 돌려주고 판단(순서 매기기)은 서버(flow.ph_src_got)가 한다.
    searched: list[dict] = []
    for q in [x for x in d.get("queries") or [] if x][:2] if pick else []:
        r2 = yt(["--flat-playlist", "-J", "--playlist-end", "10", f"https://www.youtube.com/channel/{pick[0]['id']}/search?query={quote(q)}"], timeout=120)
        if _blocked(r2):
            break
        if r2.returncode == 0 and r2.stdout.strip():
            searched += [{"id": e["id"], "title": e.get("title"), "dur": e.get("duration")} for e in json.loads(r2.stdout).get("entries") or []
                         if e.get("id") and e["id"] not in {s["id"] for s in searched}]
    titles = c_channel_list(W, {"channels": [c["id"] for c in pick], "n": n})["titles"] if pick else []
    seen = {t["id"] for t in titles}
    return {"channels": chans, "picked": pick, "how": "channel", "searched": [s["id"] for s in searched],
            "titles": titles + [s for s in searched if s["id"] not in seen]}


def _storyboard_sheet(W: Path, vid: str, fmts: list, dur: float, cols: int = 10) -> dict | None:
    """스토리보드 → 칸마다 '분:초' 를 적은 시트 한 장(영상을 받지 않고 장면 대조). 그림 조각 받기 = engine/yt_fetch.storyboard_tiles(주인)."""
    from tools.calcopy.engine import yt_fetch as YF
    tiles = YF.storyboard_tiles({"formats": fmts, "duration": dur})
    if not tiles:
        return None
    p = tile_sheet(tiles, W / "look" / f"sb_{vid}.jpg", cols)
    return {"file": rel(W, p), "step": round(tiles[1][0] - tiles[0][0], 2) if len(tiles) > 1 else 0, "tiles": len(tiles)}


def tile_sheet(tiles: list, dst: Path, cols: int = 10, tag: str = "") -> Path:
    """[(초, 그림)] → 칸마다 노란 '분:초'(+tag) 를 적은 시트(원본 찾기·재료 고르기 공용)."""
    from PIL import Image, ImageDraw
    fw, fh = tiles[0][1].size
    nrow = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * fw, nrow * fh), (0, 0, 0))
    dr = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(tiles):
        x, y = (i % cols) * fw, (i // cols) * fh
        sheet.paste(im.resize((fw, fh)), (x, y))
        s = int(t)
        lab = f"{tag}{s // 60}:{s % 60:02d}"
        dr.rectangle((x, y, x + 7 * len(lab) + 4, y + 11), fill=(0, 0, 0))
        dr.text((x + 2, y), lab, fill=(255, 255, 0))
    dst.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dst, quality=85)
    return dst


def c_origin_probe(W, d):
    """출처 채널 후보를 하나씩 — 유튜브 요청 **한 번**(-J)으로 올린 날짜·자막 주소·스토리보드를 같이 받는다(영상은 안 받는다).
    벤치보다 늦게 올라온 영상은 건너뛰고, 자막은 주소로 바로(실측 0.3초), 벤치 말 지문이 세 줄 이상 맞으면 거기서 멈춘다.
    지문이 없는 후보(벤치 = 내레이션)는 스토리보드 시트를 만들어 둔다 — 서버가 화면 대조를 묻는다."""
    import urllib.request
    lines = jload(W / "bench" / "asr.json") if (W / "bench" / "asr.json").exists() else []
    terms = [t for t in d.get("terms") or [] if t]
    before = str(d.get("before") or "")
    out = {"matched": {}, "hits": {}, "sheets": {}, "dates": {}, "skipped": [], "blocked": []}
    od = W / "origin"; od.mkdir(exist_ok=True)
    ids = list(d.get("ids") or [])
    for i, vid in enumerate(ids):
        progress(W, "원본 후보 조사", i + 1, len(ids))
        r = yt(["-J", f"https://www.youtube.com/watch?v={vid}"], timeout=120)
        if _blocked(r):
            out["blocked"].append(vid)
            break
        try:
            info = json.loads(r.stdout)
        except ValueError:
            continue
        date = str(info.get("upload_date") or "")
        out["dates"][vid] = date
        if before and date and date > before:                 # 벤치보다 늦게 올라온 영상은 원본일 수 없다
            out["skipped"].append(vid)
            continue
        words = []
        caps = info.get("subtitles") or {}
        caps = {**(info.get("automatic_captions") or {}), **caps}
        k = next((k for k in ("ko-orig", "ko") if k in caps), None)
        u = next((x.get("url") for x in caps.get(k) or [] if x.get("ext") == "vtt"), None) if k else None
        if u:
            try:
                p = od / f"{vid}.{k}.vtt"
                p.write_bytes(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
                words = vtt_words(p)
            except Exception as e:  # noqa: BLE001
                sys.stderr.write(f"[probe] {vid} 자막 바로 받기 실패({e}) → 로그인한 yt-dlp 로\n")   # 10-22 이영애: 429 로 자막 없이 넘어감
                words, _ = _origin_words(W, vid)
        m = RU.fingerprint(lines, words) if words else []
        if terms and words:
            h = RU.word_hits(words, terms)
            if h:
                out["hits"][vid] = h
        if m:
            out["matched"][vid] = m
            if len(m) >= 3:
                break
            continue
        sh = _storyboard_sheet(W, vid, info.get("formats") or [], float(info.get("duration") or 0))
        if sh:
            out["sheets"][vid] = sh
        if len(out["sheets"]) >= int(d.get("max_sheets") or 4):
            break
    return out


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
    ids = list(d.get("ids") or [])
    for i, vid in enumerate(ids):
        progress(W, "원본 후보 조사", i + 1, len(ids))
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
    files = screen.download(W, [vid], None if d.get("full") else [(a, b)], prefix="")   # full = 통째로 바로(구간 받기가 멈추는 회선에서 기다림 150초+를 버린다, 10-22 실측 통째 47~53초)
    if not files:
        return {"error": "원본 받기 실패"}
    whole = d.get("full") or dims(Path(files[-1]))["dur"] > (b - a) + 120
    if whole:                                         # 통째로 받은 파일은 0초 = 원본 0초 — 잴 것이 없다(10-22: 90초 받아쓰기로 재느라 원본 받기 118초)
        return {"files": [dims(Path(f)) for f in files], "offset": 0.0, "measured": True}
    off, ok = origin_offset(W, vid, Path(files[-1]), a, [float(x) for x in d.get("ts") or []])
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


REVIEW_JS = r"""() => {
  const out = [];
  document.querySelectorAll('.sdp-review article').forEach(a => {
    const body = a.querySelector('[class*=review__content], [class*=article__list__review__content]');
    const help = (a.innerText.match(/(\d+)명에게 도움/) || [])[1];
    const txt = (body ? body.innerText : a.innerText).trim();
    if (txt.length > 15) out.push({text: txt.slice(0, 600), helpful: help ? parseInt(help) : 0});
  });
  return out.slice(0, 12);
}"""


def c_coupang_reviews(W, d):
    """쿠팡 상품 페이지 베스트 후기(도움 순) — 대본 뒷부분 셀링포인트·소구점의 근거(사장님 10-22 "후기 베스트에 나오는 셀링포인트"). 회원 PC 크롬 창(쿠팡은 헤드리스를 막는다).
    실측 10-22 8003851952: 페이지 열고 후기 칸까지 약 5초 · 첫 후기 '18명에게 도움' — 수납·어울림·어깨끈 같은 소구점이 그대로 나온다."""
    from playwright.sync_api import sync_playwright
    pid = str(d.get("product_id") or "")
    if not pid.isdigit():
        return {"reviews": [], "error": "상품 번호가 없다"}
    home = Path(os.environ.get("SHORTEM_HOME") or (W.parent / "_home"))
    got = _cp_cached(_cp_cache(home, "reviews", pid))         # 같은 상품 페이지는 저장본(TTL 안) — 다시 열지 않는다
    if got:
        jsave(W / "look" / f"reviews_{pid}.json", got)
        return {"reviews": got, "cached": True}
    prof = home / "browser" / "coupang"
    prof.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(prof), headless=False, channel="chrome", locale="ko-KR", viewport={"width": 1366, "height": 900},
                                                   args=["--disable-blink-features=AutomationControlled"])
        try:
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                pg.goto("https://www.coupang.com/", wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_timeout(800)
            except Exception:  # noqa: BLE001 — 홈이 늦어도 상품 페이지는 열어 본다
                pass
            pg.goto(f"https://www.coupang.com/vp/products/{pid}", wait_until="domcontentloaded", timeout=30000)
            pg.wait_for_timeout(1500)
            if "사용권한이 제한된" in (pg.evaluate("()=>document.body.innerText.slice(0,400)") or ""):
                return {"reviews": [], "blocked": True}      # 쿠팡이 이 PC 를 잠시 막았다(10-22 실측 — 짧은 시간에 여러 번 열면) — 더 두드리지 않는다
            for _ in range(14):                        # 후기는 내려가야 불러온다(한 번에 건너뛰면 안 생긴다 — 10-22 실측 0개)
                if pg.evaluate("()=>document.querySelectorAll('.sdp-review article').length") > 0:
                    break
                pg.mouse.wheel(0, 1400)
                pg.wait_for_timeout(700)
                pg.evaluate("()=>{const e=document.querySelector('.sdp-review'); if(e) e.scrollIntoView();}")
            pg.wait_for_timeout(1200)
            rows = pg.evaluate(REVIEW_JS) or []
            if not rows:                               # 칸 이름이 바뀌었을 때 — 후기 칸 글 전체에서라도
                txt = pg.evaluate("()=>{const e=document.querySelector('.sdp-review'); return e ? e.innerText : ''}") or ""
                rows = [{"text": t.strip()[:600], "helpful": 0} for t in txt.split("신고하기") if len(t.strip()) > 30][:12]
        finally:
            ctx.close()
    rows.sort(key=lambda r: -int(r.get("helpful") or 0))
    out = [{"id": f"r{i + 1}", **r} for i, r in enumerate(rows[:10])]
    jsave(W / "look" / f"reviews_{pid}.json", out)
    if out:
        jsave(_cp_cache(home, "reviews", pid), out)
    return {"reviews": out}


def c_cand_sheet(W, d):
    """쿠팡 후보 사진 시트 — 파트너스 API 가 준 대표 이미지 주소(ads-partners)만 받는다(상품 페이지는 열지 않는다).
    같은 제품 판정이 이름만 보고 고르던 것(10-22 강주은: 둥근 실버 잠금 가방을 '그린 버클 소가죽' 이름만으로 같은 제품)을 막는다."""
    import io
    import urllib.request
    from PIL import Image, ImageDraw
    tiles = []
    for i, it in enumerate((d.get("items") or [])[:12]):
        u = str(it.get("image") or "")
        if not u.startswith("http"):
            continue
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read()
            im = Image.open(io.BytesIO(b)).convert("RGB")
        except Exception as e:  # noqa: BLE001 — 한 장이 빠져도 나머지로(이유는 남긴다)
            sys.stderr.write(f"[cand_sheet] #{i + 1} 사진 실패: {type(e).__name__}\n")
            continue
        im.thumbnail((300, 300))
        tile = Image.new("RGB", (300, 330), (255, 255, 255))
        tile.paste(im, ((300 - im.size[0]) // 2, 30 + (300 - im.size[1]) // 2))
        ImageDraw.Draw(tile).text((6, 6), f"#{i + 1} {it.get('product_id')}", fill=(200, 0, 0))
        tiles.append(tile)
    if not tiles:
        return {"file": None}
    cols = 4
    sheet = Image.new("RGB", (cols * 300, ((len(tiles) + cols - 1) // cols) * 330), (230, 230, 230))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * 300, (i // cols) * 330))
    out = W / "look" / "cand_sheet.jpg"
    out.parent.mkdir(exist_ok=True)
    sheet.save(out, quality=85)
    return {"file": rel(W, out), "n": len(tiles)}


COUPANG_TTL = 24 * 3600      # 쿠팡 결과 저장본 유효 시간 — 같은 검색어·같은 상품 페이지는 이 안에선 다시 요청하지 않는다(사장님 10-26 '한 번 불러 저장')


def _cp_cache(home: Path, kind: str, key: str) -> Path:
    import hashlib
    return home / "coupang_cache" / kind / (hashlib.md5(key.encode("utf-8")).hexdigest()[:16] + ".json")


def _cp_cached(f: Path):
    """저장본이 있고 TTL 안이면 그 값 — 실패(ok 아님·빈 결과)는 저장하지 않으니 여기 있는 건 성공한 것만."""
    if f.exists() and time.time() - f.stat().st_mtime < COUPANG_TTL:
        try:
            return jload(f)
        except Exception:  # noqa: BLE001 — 깨진 저장본은 무시하고 새로 부른다
            return None
    return None


def c_coupang(W, d):
    from tools.calcopy import coupang_customer as C
    qs = [q for q in d.get("queries") or [] if q][:6]
    home = Path(os.environ.get("SHORTEM_HOME") or (W.parent / "_home"))
    rated = bool(d.get("ratings"))
    hit = {q: v for q in qs if (v := _cp_cached(_cp_cache(home, "search_r" if rated else "search", q)))}
    miss = [q for q in qs if q not in hit]
    found = C.search(miss) if miss else {}
    if any((v or {}).get("need") == "chrome" for v in found.values()):
        found = coupang_chrome(miss, home)
    elif d.get("ratings") and not any(it.get("rating") for v in found.values() for it in (v or {}).get("items") or []):
        # 후기 수는 대체 제품 고를 때만(flow.ph_best 가 ratings 로 부른다) — 같은 제품 찾기마다 크롬을 띄우면 검색어 3개에 18초(10-22 실측, API 는 2.9초)
        # 파트너스 API 는 후기 수 칸이 없다(98 #11) → 같은 검색어 크롬 카드에서 후기 수만 product_id 로 채운다. 막히면 빈 채로(대본에 '후기 많은'을 못 쓴다)
        try:
            rate = {str(it.get("product_id")): it.get("rating") for v in coupang_chrome(qs, home).values() for it in (v or {}).get("items") or [] if it.get("rating")}
        except Exception as e:  # noqa: BLE001
            rate = {}
            sys.stderr.write(f"[coupang] 후기 수 크롬 읽기 실패: {type(e).__name__}: {e}\n")
        for v in found.values():
            for it in (v or {}).get("items") or []:
                it["rating"] = rate.get(str(it.get("product_id")), it.get("rating") or "")
    for q, v in found.items():                  # 성공한 검색어만 저장본으로(막힘·빈 결과는 다음에 다시 부른다)
        if (v or {}).get("ok") and (v or {}).get("items"):
            jsave(_cp_cache(home, "search_r" if rated else "search", q), v)
    if hit:
        sys.stderr.write(f"[coupang] 저장본 재사용 {len(hit)}개 · 새로 부름 {len(miss)}개\n")
    found = {**hit, **found}
    jsave(W / "look" / f"coupang_{int(time.time())}.json", found)
    items, seen = [], set()
    for v in found.values():
        for it in (v or {}).get("items") or []:
            k = str(it.get("product_id") or it.get("productId") or it.get("id") or it.get("name"))
            if k not in seen:
                seen.add(k); items.append(it)
    # 검색어가 하나도 성공 못 했으면(쿠팡이 회선을 막음·창 실패) '제품 없음'이 아니다 — flow 가 '막힘·다시 시도'로 멈추게 표시(10-26)
    failed = bool(found) and not any((v or {}).get("ok") for v in found.values())
    return {"items": items[:16], **({"search_failed": True} if failed and not items else {})}


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
        cap = RU.norm(str(l.get("said") or "") or "".join(str(c[0]) for c in l.get("caps_rel") or []))   # said(원문 그대로)가 있으면 그것 — 해외원본형은 자막이 번역이라 소리와 글이 다르다(관제 263 08)
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
    ad = W / "asr"; ad.mkdir(exist_ok=True)
    out = []
    for s in d.get("spans") or []:
        src = W / "src" / str(s["src"]) if s.get("src") else W / d["src"]      # 해외원본형 = 구간마다 원본 파일이 다르다(spans[].src)
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
        win = d.get("window") if isinstance(d.get("window"), list) and len(d["window"]) == 2 else None
        a0, b0 = (max(0.0, float(win[0])), min(dd, float(win[1]))) if win else (0.0, dd)   # 쓰는 구간 앞뒤만(원본 통째 받기 뒤 17분 전체를 자르던 것, 10-22)
        shots = [{"i": i, "a": round(a, 3), "b": round(b, 3)} for i, (a, b) in enumerate(shots_in(src, [(a0, b0)]))]
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
    import threading
    face_lock = threading.Lock()      # face_crop 의 얼굴 검출기는 나눠 쓰면 안 된다 — 한 번에 하나

    def tile(ic):
        i, c = ic
        src = cand / str(c.get("src") or "")
        if not src.exists():
            return None
        f = W / "_plan" / f"c{i:02d}.jpg"
        crop = c.get("crop", "face")
        t = float(c.get("ss") or 0) + min(0.5, float(c.get("dur") or 0) / 2)
        try:
            if crop == "face" and src.suffix.lower() not in render_bench.IMG_EXT:
                with face_lock:
                    crop = render_bench.face_crop(src, t, ww / wh)
            frame(src, t, f, crop if isinstance(crop, list) else None)
            im = Image.open(f).convert("RGB")
            im.thumbnail((220, 220))
            dr = ImageDraw.Draw(im)
            dr.rectangle((0, 0, im.width, 18), fill=(0, 0, 0))
            dr.text((3, 2), f"c{i} {c.get('line')} {c.get('t0')}~{c.get('t1')}", fill=(255, 255, 0))   # c{i} = 썸네일 안의 part 번호(flow THUMB_ASK)
            return im
        except Exception:  # noqa: BLE001 — 못 뜬 컷은 시트에서 빠진다(검수가 본다)
            return None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(render_bench.FRAME_JOBS) as ex:      # 컷마다 ffmpeg 한 장 — 동시(순서는 컷 순서 그대로, 10-26 계획 속도)
        tiles = [im for im in ex.map(tile, enumerate(T.get("cuts") or [])) if im is not None]
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


def tts_cache_miss(W: Path, v: str) -> str:
    """SHORTEM_NO_PAID 일 때 — 렌더·계획이 부를 TTS 합성이 캐시에 있나(열쇠 = engine/narr_align.cache_key, 같은 글·목소리·배속). 없으면 이유, 있으면 ''.
    합성 함수(narr_align.synth_cached)는 캐시가 없으면 돈 드는 합성을 하므로 여기서 미리 막는다."""
    if not PAID_OFF:
        return ""
    from tools.calcopy.engine import narr_align as NA
    from tools.calcopy.hybrid import render_itssum as RI, styles as STY
    S = jload(W / "doc" / v / "대본.json")
    if not any(l.get("kind") == "tts" for l in S.get("lines") or []):
        return ""
    st = STY.load(v)
    S.setdefault("voice", {k: st["voice"][k] for k in ("name", "voice_id") if k in st["voice"]})
    key = NA.voice_key(RI.tts_text({**S, "lines": [l for l in S["lines"] if l["kind"] == "tts"]}), S["voice"]["voice_id"], S["voice"].get("tempo"), NA.TTS_MODEL, **RI.voice_args(S))
    sc = W / v / "render" / "narr_full.mp3.tts.json"
    have = json.loads(sc.read_text(encoding="utf-8")).get("key") if sc.exists() else None
    return "" if have == key else f"TTS 캐시 없음(SHORTEM_NO_PAID — 돈 드는 합성 막음): 열쇠 {key[:8]} ≠ 캐시 {str(have)[:8]}"


def _conflict_of(res) -> dict | None:
    """placement 가 낸 충돌 {axis, need, cap, cause}(표준 §11-5 ㉛ — 뼈대 최소 개수 > 업그레이드 상한이면 어느 쪽도 늘리지 않고 멈춘다, 주인 placement·지시서 15).
    판단은 하지 않고 그대로 싣는다(flow 가 대본 단계로 되돌린다)."""
    if not isinstance(res, dict):
        return None
    for c in ((res.get("placement") or {}).get("conflict"), res.get("conflict"), (res.get("placement_check") or {}).get("conflict")):
        if c:
            return c if isinstance(c, dict) else {"cause": str(c)[:300]}
    return None


def _log_beat(W, what: str):
    """render_bench 로그 한 줄 = 진행 신호(감시의 '멈춤 아님') + stderr 에 시각과 함께 — 어느 칸에서 오래 걸렸는지 남긴다(10-26 계획 무음 180초 끔)."""
    def f(msg=""):
        progress(W, what)
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {str(msg)[:300]}\n")
    return f


def c_plan(W, d):
    from tools.calcopy.hybrid import render_bench
    v = d["version"]
    miss = tts_cache_miss(W, v)
    if miss:
        return {"error": miss}
    try:
        # 계획 안 관문(장면 경계·컷 내용 — 긴 원본 프레임 읽기)은 로그 없이 수 분 걸린다(10-26 524초 원본: 로그 끝 뒤 180초+ 무음으로 꺼짐).
        #   같은 프로세스 안 계산이라 무음 = 멈춤이 아니다 → 계산이 살아 있는 동안 30초마다 진행 신호. 끝없는 계산은 예산(plan 600초)이 끊는다.
        import threading
        alive = threading.Event()

        def _beat():
            while not alive.wait(30):
                progress(W, "장면 맞추기")
        threading.Thread(target=_beat, daemon=True).start()
        try:
            res = render_bench.render(v, W / "doc" / v, W / v, plan_only=True, tts=True, report=True, log=_log_beat(W, "장면 맞추기"))
        finally:
            alive.set()      # 진짜 목소리 길이로 계획 · report = 넘침·길이를 멈추지 않고 돌려받아 재료 고치기 안내(관문 ⑧)(합성은 캐시 — 렌더가 그대로 쓴다)
        over = res.get("over") or ""
    except StageError as e:          # 컷이 원본 샷보다 길다 → 재료를 고치게 한다
        res, over = {"timeline": {"cuts": []}}, str(e)
    T = res.get("timeline") or {}
    out = {"over": over, "cuts": len(T.get("cuts") or []), "length": res.get("length")}
    cf = _conflict_of(res)
    if cf:
        out["conflict"] = cf
    if T.get("cuts"):
        out["sheet"] = rel(W, plan_sheet(W, v, T))
        out["jumps"] = source_rule_scan(W, T, _origin_names(W, v) | set(d.get("origin_names") or []))
    return out


def c_render(W, d):
    from tools.calcopy.hybrid import render_bench
    v = d["version"]
    miss = tts_cache_miss(W, v)
    if miss:
        return {"ok": False, "error": miss}
    try:
        info = render_bench.render(v, W / "doc" / v, W / v)
    except StageError as e:
        return {"ok": False, "error": str(e)[:600]}
    cf = _conflict_of(info)
    if cf:
        return {"ok": False, "conflict": cf}
    T = jload(W / v / "render" / "timeline.json") if (W / v / "render" / "timeline.json").exists() else {}
    jumps = source_rule_scan(W, T, _origin_names(W, v) | set(d.get("origin_names") or []))
    return {"ok": (W / v / "render" / "final.mp4").exists() and not jumps, "jumps": jumps}


EYE_FILES = ("시트_1초.jpg", "벤치대조_시트.jpg", "벤치대조_등장.jpg", "훅3초_0.1초.jpg", "끝2초_0.1초.jpg")
EYE_TEXTS = ("받아쓰기대조.md", "줄컷대조.md")


def c_check(W, d):
    """완성본 검사 = quality_gate.gate 한 벌(표준 §5-1 — 우리 PC 와 같은 함수, 관제 263 08). 1단 결과 + 눈 2단 묶음(<판>/eye/ 그림·대조표)을 싣는다.
    QG_FORCE_FAIL=1 = 사보타주 — 관문을 돈 뒤 결과를 강제로 ×(flow 가 고치기 2회 뒤 멈추는지 보는 시험, 08 합격 검사 3)."""
    from tools.calcopy.hybrid import quality_gate as QG, styles as STY
    v = d["version"]
    final = W / v / "render" / "final.mp4"
    if not final.exists():
        return {"error": "완성본 없음"}
    r = QG.gate(v, W / "doc" / v, W / v, mode="full" if d.get("mode", "full") == "full" else "fast", log=lambda s: print(s, file=sys.stderr))
    rows = [{k: x.get(k) for k in ("group", "what", "ok", "value")} | ({"ref": True} if x.get("ref") else {}) for x in r.get("rows") or []]
    ok = bool(r.get("ok"))
    if os.environ.get("QG_FORCE_FAIL") == "1":
        rows.append({"group": "표식", "what": "QG_FORCE_FAIL(사보타주)", "ok": False, "value": "환경변수로 강제 ×"})
        ok = False
    E = Path(r.get("eye_pack_dir") or (W / v / "eye"))
    eye_files = [rel(W, E / n) for n in EYE_FILES if (E / n).exists()]
    eye_texts = {n: (E / n).read_text(encoding="utf-8")[:6000] for n in EYE_TEXTS if (E / n).exists()}
    return {"auto": {"ok": ok, "rows": rows, "report": str(r.get("report")), "n_bad": sum(1 for x in rows if x.get("ok") is False),
                     "n_unmeasured": sum(1 for x in rows if x.get("ok") is None and not x.get("ref"))},
            "eye_files": eye_files, "eye_texts": eye_texts, "upgrade": bool(STY.load(v).get("base")),
            "sheet": eye_files[0] if eye_files else None}


# ── 해외원본형(관제 263 08) ────────────────────────────────────────────────
OF_FRAMES = (0.15, 0.35, 0.55, 0.75)     # 렌즈 장면 = 원본찾기와 같은 자리(origin_find.FRAMES)
OF_SHEET_N = 24                         # 판정 시트 한 장 칸 수(8열 — origin_find.judge_same 과 같은 꼴)


def _of_seed_frames(W: Path) -> list[Path]:
    from tools.calcopy.origin_find import FRAMES
    src = W / "bench" / "bench.mp4"
    out = []
    if not src.exists():
        return out
    du = dims(src)["dur"]
    for f in FRAMES:
        p = W / "origin_foreign" / f"seed_{int(f * 100)}.jpg"
        if not p.exists():
            frame(src, du * f, p)
        if p.exists():
            out.append(p)
    return out


def _of_thumb(W: Path, c: dict):
    """후보 썸네일(PIL) — 캐시 모드 = 받아 둔 영상 30% 장면, 아니면 썸네일 주소. 못 받으면 None(미판정 — '다르다'로 단정하지 않는다)."""
    import io
    import urllib.request
    from PIL import Image
    vid = str(c.get("id") or "")
    if CACHE:
        for sub in ("yt", "material", "origin_foreign"):
            for ext in (".jpg", ".mp4"):
                f = cache_path(sub, vid + ext)
                if f.exists():
                    if ext == ".jpg":
                        return Image.open(f).convert("RGB")
                    p = W / "origin_foreign" / f"thumb_{vid}.jpg"
                    if not p.exists():
                        frame(f, dims(f)["dur"] * 0.3, p)
                    return Image.open(p).convert("RGB") if p.exists() else None
        return None
    u = c.get("thumb") or (f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if c.get("platform") == "yt" else None)
    if not u:
        return None
    try:
        return Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())).convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def _of_sheets(W: Path, seeds: list[Path], cands: list[dict]) -> list[str]:
    """맨 위 줄 S1~S4 = 소재 장면, 아래 파란 번호 칸 = 후보 썸네일(번호 = 후보 n, 시트가 여러 장이어도 이어서) — 판정은 회원 Claude(flow)."""
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    pool = [(c, im) for c in cands for im in [_of_thumb(W, c)] if im is not None]
    for c in cands:
        c["thumb_ok"] = any(x is c for x, _ in pool)
    out = []
    cw, chh, cols = 200, 300, 8
    for s0 in range(0, len(pool), OF_SHEET_N):
        part = pool[s0:s0 + OF_SHEET_N]
        rows_n = 1 + (len(part) + cols - 1) // cols
        sh = Image.new("RGB", (cw * cols, (chh + 34) * rows_n), "white")
        dr = ImageDraw.Draw(sh)
        for k, p in enumerate(seeds[:4]):
            im = Image.open(p).convert("RGB"); im.thumbnail((cw, chh)); sh.paste(im, (k * cw, 34)); dr.text((k * cw + 4, 2), f"S{k + 1}", fill="red", font=font)
        for j, (c, im) in enumerate(part):
            x, y = (j % cols) * cw, (1 + j // cols) * (chh + 34)
            im = im.copy(); im.thumbnail((cw, chh)); sh.paste(im, (x, y + 34)); dr.text((x + 4, y + 2), str(c["n"]), fill="blue", font=font)
        p = W / "origin_foreign" / f"judge_{s0 // OF_SHEET_N}.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        sh.save(p, quality=82)
        out.append(rel(W, p))
    return out


def c_origin_foreign(W, d):
    """해외 원본 후보 + 판정 시트. mode lens = 소재(한국 재편집) 장면 4장 → 구글 렌즈 → 영상 링크 → 메타(origin_find 와 같은 함수) /
    mode peers = 영어 검색어로 같은 제품 다른 해외 반응 쇼츠. 같은 영상·같은 제품 판정은 하지 않는다(서버 질문 — 회원 Claude 눈).
    캐시 모드: lens = <캐시>/origin_foreign/<소재 id>.json {cands:[…]} · peers = 검색 캐시(search/<검색어>.json 또는 _default) — 유튜브·구글 0회."""
    from tools.calcopy import origin_find as OF
    mode = d.get("mode") or "lens"
    seeds = _of_seed_frames(W)
    skip = set(d.get("skip") or [])
    raw: list[dict] = []
    if mode == "lens":
        if CACHE:
            f = cache_path("origin_foreign", f"{d.get('bench_id')}.json")
            if not f.exists():
                _need("origin_foreign", [d.get("bench_id")])
                return {"mode": mode, "error": f"cache_miss: 렌즈 결과 {d.get('bench_id')}", "cands": [], "sheets": []}
            raw = jload(f).get("cands") or []
        else:
            if not seeds:
                return {"mode": mode, "error": "소재 장면을 못 뽑았다", "cands": [], "sheets": []}
            from tools.calcopy import lens as LN
            found: dict = {}
            with LN.lens_page() as pg:
                for im in seeds:
                    try:
                        rows = LN.lens_rows(pg, str(im), skip=LN.SKIP_VIDEO)
                    except Exception as e:  # noqa: BLE001 — 한 장 실패는 남기고 나머지
                        sys.stderr.write(f"[origin_foreign] 렌즈 실패 {im.name}: {type(e).__name__} {str(e)[:80]}\n"); rows = []
                    for r in rows:
                        k = OF.vkey(r["href"])
                        if k and k[1] != d.get("bench_id"):
                            found.setdefault(k, {"href": r["href"], "text": r["text"], "hits": 0})["hits"] += 1
            for (pf, vid), x in list(found.items())[:40]:
                m = OF.meta(OF.url_of(pf, vid, x["href"]))
                raw.append({"platform": pf, "id": vid, "url": OF.url_of(pf, vid, x["href"]), "lens_text": x["text"], "lens_hits": x["hits"], **m})
    else:
        for e in _search(d.get("queries") or [], int(d.get("n") or 12)):
            raw.append({"platform": "yt", "id": e.get("id"), "url": f"https://www.youtube.com/shorts/{e.get('id')}", **{k: e.get(k) for k in ("title", "channel", "channel_id", "dur", "views", "date")}})
    cands, seen = [], set()
    for c in raw:
        if not c.get("id") or c["id"] in skip or c["id"] in seen or c.get("why"):
            continue
        seen.add(c["id"])
        c["korean"] = OF.is_korean(f"{c.get('title') or ''} {c.get('lens_text') or ''}", c.get("channel") or "")   # 주인 = origin_find.is_korean
        c["n"] = len(cands) + 1
        cands.append(c)
    sheets = _of_sheets(W, seeds, cands) if cands else []
    jsave(W / "origin_foreign" / f"cands_{mode}.json", cands)
    return {"mode": mode, "cands": [{k: c.get(k) for k in ("n", "platform", "id", "url", "title", "channel", "channel_id", "date", "dur", "views", "korean", "thumb_ok")} for c in cands],
            "sheets": sheets, "seed": [rel(W, p) for p in seeds]}


def c_clean_text(W, d):
    """박힌 글자 지우기 — 판단은 vmake_clean 한 곳(사장님 10-26: 장면 편집 뒤 자막 있는 컷 구간만 VMake). 여기는 부르기만.
    d.check = 돈 없이 준비만(ready — 키 없으면 need_key) · 아니면 d.version 판의 확정 계획(doc/<판>/plan/계획_시간표.json, d.replan 이면 계획을 다시 써서)에서
    d.shots(샷 표 글자 샷) 와 겹치는 컷 구간만 잘라 VMake → 원본에 덮어 끼움(d.done = 이미 지운 구간). 장부 = <작업>/src/vmake_log.json(구간·보낸 초)."""
    from tools.calcopy import vmake_clean as VC
    mode = "blur" if PAID_OFF else VC.style_mode(d.get("version"))
    if d.get("check"):
        return VC.ready(mode)
    v = d["version"]
    if d.get("replan"):                     # 재료가 계획 뒤에 바뀌었다(렌더 고치기) — 같은 계획 함수로 시간표만 새로(합성은 캐시)
        from tools.calcopy.hybrid import render_bench
        try:
            render_bench.render(v, W / "doc" / v, W / v, plan_only=True, tts=True, report=True)
        except StageError:
            pass                            # 관문 멈춤이어도 시간표는 관문 앞에서 저장된다
    t0 = time.strftime("%Y-%m-%d %H:%M:%S")
    src, send, used = VC.plan_spans(W / "doc" / v, d.get("shots") or {}, d.get("done") or {})
    r = VC.clean_used(src, send, mode, log=lambda s: print(s, file=sys.stderr))
    sent = VC.sent_from_ledger(src, t0)
    r.update({"send": send, "used_sec": VC.span_sec(used), "send_sec": VC.span_sec(send), "sent": sent, "sent_bad": VC.sent_check(sent, used)})
    sys.stderr.write(f"[clean_text] 쓰는 구간 {r['used_sec']}초 중 자막 컷 {r['send_sec']}초 → VMake {r['calls']}회 · 보낸 초 {sent} · {r['mode']}: {r.get('why')}\n")
    return r


def c_materials_draft(W, d):
    """재료 초안(ititemlog_make.draft — 원본별 시간순·재사용 0·확대 1.0·박힌 글자 표시) → <doc>/<판>/재료_초안.json + 본문."""
    from tools.calcopy import ititemlog_make as IM
    from tools.calcopy.hybrid import styles as STY
    v = d["version"]
    _, _, ww, wh = STY.load(v)["frame"]["window"]
    files = [dims(W / "src" / n) for n in d.get("files") or [] if (W / "src" / n).exists()]
    res = IM.draft(files, d.get("shots") or {}, ww / wh, d.get("cleaned") or [])
    jsave(W / "doc" / v / "재료_초안.json", res)
    return {"draft": res, "file": f"doc/{v}/재료_초안.json"}


def c_finish(W, d):
    v = d["version"]
    final = W / v / "render" / "final.mp4"
    return {"video": str(final)} if final.exists() else {"error": "완성본 없음"}


CMDS = {"env": c_env, "bench": c_bench, "search": c_search, "peer_sheet": c_peer_sheet, "channel_list": c_channel_list, "origin_subs": c_origin_subs,
        "origin_get": c_origin_get, "channel_find": c_channel_find, "origin_probe": c_origin_probe, "sheet": c_sheet, "frames": c_frames, "coupang": c_coupang, "coupang_reviews": c_coupang_reviews, "cand_sheet": c_cand_sheet, "naver": c_naver, "origin_words": c_origin_words,
        "screen": c_screen, "download": c_download, "product_stills": c_product_stills, "orig_heard": c_orig_heard, "asr_spans": c_asr_spans, "shot_sheets": c_shot_sheets, "mat_sheets": c_mat_sheets,
        "write_doc": c_write_doc, "plan": c_plan, "render": c_render, "check": c_check, "finish": c_finish,
        "origin_foreign": c_origin_foreign, "clean_text": c_clean_text, "materials_draft": c_materials_draft}


# ── 시간 예산·진행 신호·감시(사장님 10-26 "가만히 있으면 한없이 진행되는 게 제일 문제") ─────────────────────────
# 주인 = 여기 한 곳(실행기). 예산(초) = 10-21~26 회원 경로 runner 기록 17개 실측 max(120, p90×1.5, 최장×1.1) — 적은 표본이라 최장도 본다.
#   실측 p90/최장: bench 802/802 · origin_get 209/273 · origin_probe 146/146 · channel_find 110/110 · render 222/701 · download 665/665 ·
#   screen 282/282 · shot_sheets 219/219 · check 150/150 · coupang 75/75 · coupang_reviews 99/99 · plan 67/79 · origin_words 59/154
#   ★plan 120→600(기미크림 10-26): 위 plan 실측 17개는 --plan 이 TTS·줄별 받아쓰기(관문 7a95600f8)를 하기 전 — 지금 계획은 바뀐 줄 합성+스피치매틱스+긴 원본 장면 경계(524초 원본)까지 해 120초에 두 번 잘렸다(회원 마스크편). 진짜 멈춤은 STALL_SEC 180초가 잡는다.
BUDGET = {"bench": 900, "origin_get": 320, "origin_probe": 240, "channel_find": 180, "origin_subs": 180, "search": 180, "channel_list": 180,
          "render": 780, "download": 740, "screen": 420, "shot_sheets": 330, "check": 240, "coupang": 120, "coupang_reviews": 150,
          "plan": 600, "origin_words": 180, "orig_heard": 120, "asr_spans": 120, "origin_foreign": 120, "clean_text": 900}
BUDGET_DEFAULT = 300
BUDGET_FLOOR = 600   # 바닥(10-26 run4: 바닥 120초로 plan 120.2초·asr_spans 120.2초를 끊어 멀쩡한 편을 멈췄다 — 98 #124). 한없이 도는 일은 STALL_SEC 가 잡는다
CMD_LABEL = {"env": "준비 확인", "bench": "영상 받기", "channel_find": "출처 채널 찾기", "origin_probe": "원본 후보 조사", "search": "원본 검색",
             "channel_list": "채널 영상 목록", "origin_subs": "원본 자막 대조", "origin_get": "원본 영상 받기", "coupang": "쿠팡 찾기", "coupang_reviews": "쿠팡 후기",
             "naver": "자료 찾기", "download": "영상 조각 받기", "screen": "장면 고르기", "shot_sheets": "장면 정리", "plan": "장면 맞추기",
             "render": "영상 만들기", "check": "완성본 확인", "clean_text": "자막 지우기", "finish": "마무리"}   # 회원 화면 진행 줄(내부 이름 금지)
STALL_SEC = float(os.environ.get("SHORTEM_STALL_SEC") or 180)    # 진행 신호(명시 progress 또는 작업 폴더 파일 변화)가 이만큼 없으면 멈춘 것
_PROG: dict = {"t": 0.0}
_CHILDREN: set = set()


class _TrackedPopen(subprocess.Popen):
    """실행기가 띄운 하위 프로그램(yt-dlp·ffmpeg) 목록 — 감시가 시간 초과 때 끈다(그냥 두면 끊은 뒤에도 받기를 계속한다, 10-26 run3)."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _CHILDREN.add(self)
        _PROG["t"] = time.time()          # 새 하위 프로그램을 띄웠다 = 일이 앞으로 가는 중(계획은 ffprobe·ffmpeg 를 짧게 여러 번 부른다)


def _child_cpu() -> float:
    """살아 있는 하위 프로그램들의 CPU 시간 합(초) — 늘고 있으면 일하는 중(10-26 run4: 계획 199초를 '진행 없음'으로 오판해 끊었다, 98 #125).
    네트워크에 걸려 멈춘 받기는 CPU 가 안 는다 → 그때만 멈춤으로 본다. 윈도는 GetProcessTimes, 그 밖은 /proc 없으면 0."""
    tot = 0.0
    for pr in list(_CHILDREN):
        if pr.poll() is not None:
            continue
        try:
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes
                ft = [wintypes.FILETIME() for _ in range(4)]
                if ctypes.windll.kernel32.GetProcessTimes(wintypes.HANDLE(int(pr._handle)), *[ctypes.byref(f) for f in ft]):
                    tot += sum(((f.dwHighDateTime << 32) | f.dwLowDateTime) / 1e7 for f in ft[2:])
            else:
                with open(f"/proc/{pr.pid}/stat") as fh:
                    x = fh.read().split()
                tot += (int(x[13]) + int(x[14])) / os.sysconf("SC_CLK_TCK")
        except Exception:  # noqa: BLE001
            pass
    return tot


subprocess.Popen = _TrackedPopen


def progress(W: Path, what: str, n: int | None = None, m: int | None = None) -> None:
    """진행 신호 — '무엇을 하는 중 n/m' 를 작업 폴더 progress.json 에(회원 화면 진행 줄이 읽는다) · 감시의 '멈춤 아님' 신호."""
    _PROG.update(t=time.time(), what=str(what)[:60], n=n, m=m)
    try:
        jsave(Path(W) / "progress.json", {"what": _PROG["what"], "n": n, "m": m, "t": round(_PROG["t"], 1)})
    except OSError:
        pass


def _dir_sig(W: Path, cap: int = 4000) -> tuple:
    """작업 폴더 파일 크기 합·개수 — 받기·렌더처럼 파일이 자라면 진행 중(명시 신호 없는 긴 일도 멈춤으로 오판하지 않게)."""
    tot = cnt = 0
    stack = [str(W)]
    while stack and cnt < cap:
        try:
            with os.scandir(stack.pop()) as it:
                for e in it:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    else:
                        try:
                            tot += e.stat().st_size; cnt += 1
                        except OSError:
                            pass
        except OSError:
            pass
    return tot, cnt


def _kill_children() -> int:
    n = 0
    for pr in list(_CHILDREN):
        if pr.poll() is None:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pr.pid)], capture_output=True, timeout=20)
                else:
                    pr.kill()
                n += 1
            except Exception:  # noqa: BLE001
                pass
        _CHILDREN.discard(pr)
    return n


def _watch(W: Path, items: list, run_one, out: dict, log, budget_of, stall: float) -> None:
    """items 를 각자 스레드로 돌리고 감시 — 예산 초과·진행 신호 stall 초 없음이면 그 일을 '시간 초과' 오류로 끝내고 하위 프로그램을 끈다.
    (판정은 서버 flow — 오류를 받으면 스스로 한 번 다시·다음 방법·회원 선택지로. 실행기는 절대 한없이 기다리지 않는다.)"""
    import threading
    th = []
    for d in items:
        t = threading.Thread(target=run_one, args=(d,), daemon=True)
        t.start()
        th.append((d, t, time.time()))
    sig, last, cpu = _dir_sig(W), time.time(), _child_cpu()
    _PROG["t"] = time.time()
    while any(t.is_alive() for _, t, _ in th):
        next((t for _, t, _ in th if t.is_alive()), th[0][1]).join(1.0 if stall > 5 else 0.2)   # 끝나면 바로 깨어난다(잠만 자면 일마다 1초씩 늦는다)
        now = time.time()
        s2, c2 = _dir_sig(W), _child_cpu()
        if s2 != sig or c2 > cpu + 0.5:            # 파일이 자라거나 하위 프로그램이 CPU 를 0.5초 넘게 더 쓰면 진행 중
            sig, last, cpu = s2, now, c2
        cpu = min(cpu, c2)                        # 하위 프로그램이 끝나 합이 줄면 기준도 내린다
        last = max(last, float(_PROG.get("t") or 0))
        for d, t, t0 in th:
            rid = str(d.get("id") or d.get("cmd"))
            if not t.is_alive() or rid in out:
                continue
            bud = float(d.get("budget") or budget_of(str(d.get("cmd"))))
            # 예산을 넘어도 일하는 중(진행 신호·파일·CPU)이면 끊지 않는다 — 넘은 뒤엔 60초만 조용해도 끊고, 예산 3배면 무조건
            #   (10-26 run4: 계획 600.8초를 예산으로 끊어 같은 편이 10/13 에서 세 번 멈췄다 — 98 #126)
            over = (now - t0 > bud and now - last > min(stall, 60.0)) or now - t0 > 3 * bud
            stuck = now - last > stall
            if over or stuck:
                why = f"시간 초과({'예산 ' + str(int(now - t0)) + '초' if over else '진행 신호 ' + str(int(now - last)) + '초 없음'})"
                out[rid] = {"error": why, "timed_out": True}
                k = _kill_children()
                log(f"[runner] {d.get('cmd')} {now - t0:.1f}s ERR {why} — 하위 프로그램 {k}개 끔")
        if all((not t.is_alive()) or (str(d.get("id") or d.get("cmd")) in out) for d, t, _ in th):
            break


def run_do(W: Path, do: list[dict], log=print, stall: float | None = None) -> dict:
    """do 목록을 순서대로 — 허용 목록 밖 cmd 는 돌리지 않는다. 한 cmd 가 실패해도 그 결과에 error 를 담고 다음으로(판정은 서버).
    일마다 시간 예산(BUDGET)·진행 감시(STALL_SEC) — 넘으면 '시간 초과' 오류로 끝낸다(멈춘 채 대기 금지)."""
    _guard_cache_mode()
    W.mkdir(parents=True, exist_ok=True)
    out = {}
    stall = STALL_SEC if stall is None else stall

    def one(d):
        fn = CMDS.get(str(d.get("cmd")))
        rid = str(d.get("id") or d.get("cmd"))
        if fn is None:
            out[rid] = {"error": f"허용되지 않은 명령: {d.get('cmd')}"}
            return
        t0 = time.time()
        progress(W, CMD_LABEL.get(str(d.get("cmd")), "만드는 중"))
        try:
            res = fn(W, d)
            if rid not in out:                     # 감시가 이미 '시간 초과'로 끝낸 일은 늦게 온 결과로 덮지 않는다
                out[rid] = res
            return
        except CacheMiss as e:
            out.setdefault(rid, {"error": f"cache_miss: {e}"})
        except StageError as e:
            out.setdefault(rid, {"error": str(e)[:600]})
        except Exception as e:  # noqa: BLE001 — 실패 이유를 서버에 그대로(조용히 삼키지 않는다)
            out.setdefault(rid, {"error": f"{type(e).__name__}: {str(e)[:500]}"})
        finally:
            r0 = out.get(rid)
            if isinstance(r0, dict) and not r0.get("timed_out"):
                log(f"[runner] {d.get('cmd')} {time.time() - t0:.1f}s {'ERR ' + str(r0.get('error'))[:120] if r0.get('error') else 'ok'}")

    batch: list = []

    budget_of = lambda c: max(BUDGET_FLOOR, BUDGET.get(c, BUDGET_DEFAULT))  # noqa: E731

    def flush():
        if batch:
            _watch(W, list(batch), one, out, log, budget_of, stall)
        batch.clear()

    for d in do or []:
        if str(d.get("cmd")) in PARALLEL_OK:      # 서로 기다릴 필요 없는 일은 한꺼번에(10-22 받아쓰기 46초 + 샷 72초 → 둘 중 긴 쪽)
            batch.append(d)
            continue
        flush()
        _watch(W, [d], one, out, log, budget_of, stall)   # 나머지(유튜브·쓰기·계획·렌더)는 차례대로 — 앞 결과를 뒤가 읽는다·유튜브는 한 번에 하나
    flush()
    return out


PARALLEL_OK = {"asr_spans", "shot_sheets", "frames", "coupang", "naver", "product_stills", "mat_sheets", "sheet"}   # 유튜브를 부르지 않고 서로의 결과를 읽지 않는 일


def main():
    W, do = Path(sys.argv[1]), jload(sys.argv[2])
    res = run_do(W, do, log=lambda s: print(s, file=sys.stderr))
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
