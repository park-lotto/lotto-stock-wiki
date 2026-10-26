# -*- coding: utf-8 -*-
"""유튜브 받기 주인 한 곳 — 구간 받기(HLS 먼저 + 진행 없음 감시) · 자막 따로(최선 노력) · 키워드 적중(NFC·띄어쓰기 무시) (관제 097, 2026-10-18).

왜 (10-18 실전 손태영·한혜진·김가연 세 편에서 시간이 간 곳):
  · DASH(137) `--download-sections` 는 ffmpeg 가 앞부분을 통째로 읽어 25분+ 0B 로 멈춘다 → 한 편 ~70분. HLS(m3u8) 구간은 85초가 42초.
    → 구간 받기는 **HLS 먼저**, 그리고 **진행 없음 감시**(STALL_SEC 동안 받은 파일 크기가 안 늘면 그 yt-dlp 만 끊고 다음 형식) — 300초 상한을 다 기다리지 않는다.
  · 자막 429 가 영상 받기까지 죽였다 → 자막은 영상과 **다른 호출**로, 실패해도 영상은 성공.
  · 제목이 NFD(맥 업로드 — '진생 로얄' 자모 분해)·띄어쓰기 차이('진생로얄실크')로 키워드 적중 × → kw_hit 한 곳에서 NFC·공백 제거 뒤 비교.

    from tools.calcopy.engine.yt_fetch import ytdlp, download_sections, fetch_subs, kw_hit
프로세스는 **핸들로만** 끊는다(이미지 이름으로 kill 금지 — 다른 세션의 yt-dlp 를 죽인다).
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

STALL_SEC = 60.0            # 이 동안 받는 파일이 안 자라면 멈춘 것으로 본다(10-18 한혜진: 137 구간 25분+ 0B)
POLL_SEC = 2.0
FMT_SECTION_1080 = ("bv*[height=1080][protocol^=m3u8]+ba[protocol^=m3u8]/bv*[height=1080][protocol^=m3u8]+ba/"
                    "bv*[height>=720][protocol^=m3u8]+ba/137+ba[ext=m4a]/bv*[height>=1080]+ba/bv*[height>=720]+ba/b")
FMT_PREVIEW_360 = "bv*[height<=360][protocol^=m3u8]/bv*[height<=360][ext=mp4]/bv*[height<=360]/wv*"


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str
    sec: float
    stalled: bool = False
    timed_out: bool = False


def _watch_size(paths: list[Path]) -> int:
    tot = 0
    for p in paths:
        try:
            tot += p.stat().st_size
        except OSError:
            pass
    return tot


def ytdlp(args: list, timeout: float = 600, stall_sec: float | None = None, watch: Path | None = None, log=None) -> Result:
    """yt-dlp 를 돌린다. watch(받는 파일 stem 경로)가 있으면 그 stem 으로 시작하는 파일들(.part·.mp4·.ytdl…)의 크기를 POLL_SEC 마다 재
    stall_sec 동안 안 늘면 **이 프로세스만** 끊는다(stalled=True). 예외를 올리지 않는다 — TimeoutExpired 도 결과(timed_out)로 돌려준다."""
    auth = []
    url = next((str(a) for a in args if "youtu" in str(a)), "")
    if url:                                       # 유튜브면 로그인 쿠키(파이어폭스 yt* 프로필)·JS 런타임 — 주인 = origin_find.yt_auth(10-21 회선 'not a bot' 우회)
        try:
            from tools.calcopy.origin_find import yt_auth
            auth = yt_auth(url)
        except PermissionError:
            raise                                  # 전용 계정이 없으면 받지 않는다(로그인 없이 회선 두드리기 금지)
        except Exception as e:  # noqa: BLE001 — 로그인 길을 못 쓰면 그대로 받되 이유를 남긴다
            if log:
                log(f"[yt_fetch] 로그인 쿠키 못 씀: {type(e).__name__}")
    cmd = ["yt-dlp", "--no-warnings", "--no-playlist", *auth, *[str(a) for a in args]]
    out_f = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
    err_f = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out_f, stderr=err_f)
    stalled = timed_out = False
    last_size, last_grow = -1, time.time()
    try:
        while True:
            try:
                proc.wait(timeout=POLL_SEC)
                break
            except subprocess.TimeoutExpired:
                pass
            now = time.time()
            if now - t0 > timeout:
                timed_out = True
                proc.kill(); proc.wait()
                break
            if stall_sec and watch is not None:
                size = _watch_size(list(watch.parent.glob(watch.name + "*")))
                if size != last_size:
                    last_size, last_grow = size, now
                elif now - last_grow > stall_sec:
                    stalled = True
                    proc.kill(); proc.wait()
                    break
    finally:
        out_f.seek(0); err_f.seek(0)
        so, se = out_f.read(), err_f.read()
        out_f.close(); err_f.close()
    if stalled:
        se += f"\n[yt_fetch] 진행 없음 {stall_sec}초 → 끊음({last_size}B)"
    if timed_out:
        se += f"\n[yt_fetch] 상한 {timeout}초 → 끊음"
    r = Result(proc.returncode if not (stalled or timed_out) else -9, so, se, round(time.time() - t0, 1), stalled, timed_out)
    if log and (stalled or timed_out):
        log(f"[yt_fetch] {'멈춤' if stalled else '시간초과'} {r.sec}초: {' '.join(cmd)[-120:]}")
    return r


def _valid(p: Path, min_dur: float | None = None) -> bool:
    if not p.exists() or p.stat().st_size < 1000:
        return False
    if min_dur is None:
        return True
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    try:
        return float(r.stdout.strip() or 0) >= min_dur
    except ValueError:
        return False


def _cleanup(dst: Path):
    for q in dst.parent.glob(dst.name + "*"):
        if q != dst or not _valid(dst):
            try:
                q.unlink()
            except OSError:
                pass


# ── DASH 조각 바로 받기(관제263 10-26) ─────────────────────────────────────────────────────────────────
# 왜: 10-26 이미숙 원본 uOj3ix7qCj8(2233초) = HLS 없음·DASH(mp4 299 avc1 / 399 av1, webm 303) 만. `--download-sections` 는 ffmpeg 가
#   영상 주소를 직접 읽다가 세 형식 모두 0B 로 60초씩 멈췄다(같은 날 실측, 직접 ffmpeg -ss 도 100초+ 0B) → 통째 722MB.
#   그런데 같은 주소에 '&range=a-b' 바이트 요청은 0.3초에 답한다 → DASH mp4 의 sidx(조각 목차)로 쓸 구간 조각의 바이트만 받는다.
#   조각은 키프레임에서 시작하고 안에 원본 시각(tfdt)이 있어 재인코딩 없이 이어 붙는다(영상 copy · 소리만 aac 로 맞춤).
DASH_CHUNK = 9_500_000        # 한 요청 바이트 상한(유튜브는 큰 range 를 느리게 준다 — yt-dlp http_chunk_size 10MB 와 같은 결)
DASH_HEAD = 65_536            # 머리(ftyp·moov·sidx) 첫 요청 크기 — 모자라면 sidx 크기만큼 더 받는다
DASH_MIN_LAND = 1080          # 가로 원본 최소 높이(사장님 10-26 '가로 원본 1080p 이상, 가능하면 최고')
DASH_MIN_PORT = 720           # 세로 원본 최소 폭(세로 720p 허용)


def _range_get(url: str, headers: dict, a: int, b: int, timeout: float = 60) -> bytes:
    """바이트 a..b(포함) — DASH_CHUNK 씩 나눠 '&range=' 로(헤더 Range 와 같은 답, 유튜브가 큰 요청을 늦추는 것을 피한다)."""
    import urllib.error
    import urllib.request
    out = bytearray()
    s = a
    while s <= b:
        e = min(b, s + DASH_CHUNK - 1)
        req = urllib.request.Request(f"{url}&range={s}-{e}", headers=headers)
        for k in range(4):                         # 10-26 실측: 갓 받은 주소가 403 을 주다가 잠시 뒤 같은 주소가 된다 — 쉬었다 다시(3번)
            try:
                part = urllib.request.urlopen(req, timeout=timeout).read()
                break
            except urllib.error.HTTPError as ex:
                if ex.code != 403 or k == 3:
                    raise
                time.sleep(4 * (k + 1))
        if not part:
            raise OSError(f"빈 응답 range={s}-{e}")
        out += part
        s += len(part)
    return bytes(out)


def _box_at(buf: bytes, off: int) -> tuple[str, int]:
    import struct
    size, typ = struct.unpack(">I4s", buf[off:off + 8])
    if size == 1:
        size = struct.unpack(">Q", buf[off + 8:off + 16])[0]
    return typ.decode("latin-1"), size


def dash_index(url: str, headers: dict) -> tuple[bytes, list[tuple[float, float, int, int]]]:
    """DASH mp4 머리(init = ftyp+moov 바이트)와 조각 목차 [(시작 초, 끝 초, 바이트 시작, 바이트 끝)] — sidx 를 읽는다. sidx 가 없으면 ValueError."""
    import struct
    head = _range_get(url, headers, 0, DASH_HEAD - 1)
    off, init_end = 0, None
    while off + 8 <= len(head):
        typ, size = _box_at(head, off)
        if typ == "moov":
            init_end = off + size
        if typ == "sidx":
            if off + size > len(head):
                head += _range_get(url, headers, len(head), off + size - 1)
            box = head[off:off + size]
            ver = box[8]
            p = 12 + 4                                   # 버전·플래그 + reference_ID
            scale = struct.unpack(">I", box[p:p + 4])[0]; p += 4
            if ver == 0:
                t, first = struct.unpack(">II", box[p:p + 8]); p += 8
            else:
                t, first = struct.unpack(">QQ", box[p:p + 16]); p += 16
            p += 2
            n = struct.unpack(">H", box[p:p + 2])[0]; p += 2
            byte = off + size + first
            refs = []
            for _ in range(n):
                rs, dur = struct.unpack(">II", box[p:p + 8]); p += 12
                rs &= 0x7FFFFFFF
                refs.append((t / scale, (t + dur) / scale, byte, byte + rs - 1))
                t += dur; byte += rs
            if init_end is None:
                raise ValueError("moov 없음")
            return head[:init_end], refs
        if size <= 0:
            break
        off += size
    raise ValueError("sidx 없음(조각 목차를 못 찾음)")


def dash_pick(info: dict) -> tuple[dict | None, dict | None, str]:
    """받을 영상·소리 형식(mp4 DASH 만 — sidx 가 있다). 영상 = 가로면 높이≥DASH_MIN_LAND·세로면 폭≥DASH_MIN_PORT 중 해상도 가장 큰 것,
    같은 해상도면 avc1(디코딩 가벼움 — av1 1080p60 은 프레임 뽑기가 느리다, 10-26 관문 115초) > 그 밖, 그다음 fps. 소리 = 140(m4a) 먼저."""
    fm = [f for f in info.get("formats") or [] if f.get("protocol") == "https" and f.get("ext") in ("mp4", "m4a") and f.get("url")]
    vids = [f for f in fm if (f.get("vcodec") or "none") != "none" and (f.get("acodec") or "none") == "none" and f.get("width") and f.get("height")]
    ok = [f for f in vids if (f["height"] >= DASH_MIN_LAND if f["width"] >= f["height"] else f["width"] >= DASH_MIN_PORT)]
    if not ok:
        best = max(vids, key=lambda f: f["width"] * f["height"], default=None)
        return None, None, f"화질 미달(가장 큰 mp4 = {best['width']}x{best['height']})" if best else "mp4 DASH 영상 형식 없음"
    v = max(ok, key=lambda f: (f["width"] * f["height"], str(f.get("vcodec")).startswith("avc1"), f.get("fps") or 0))
    auds = [f for f in fm if (f.get("vcodec") or "none") == "none" and (f.get("acodec") or "none") != "none"]
    a = next((f for f in auds if str(f.get("format_id")) == "140"), None) or max(auds, key=lambda f: f.get("abr") or 0, default=None)
    return v, a, ""


def _merge_spans(spans: list[tuple[float, float]], pad: float) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted((max(0.0, float(a) - pad), float(b) + pad) for a, b in spans):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def _segs_for(refs: list, spans: list[tuple[float, float]]) -> list[int]:
    return sorted({k for k, (t0, t1, _, _) in enumerate(refs) for a, b in spans if t1 > a and t0 < b})


def _probe_dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    try:
        return float(r.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return 0.0


def _frag_file(p: Path, f: dict, init: bytes, refs: list, ks: list[int]) -> int:
    """init + 고른 조각(이웃 조각은 한 요청) → p. 받은 바이트 수."""
    got = 0
    with open(p, "wb") as fh:
        fh.write(init)
        k = 0
        while k < len(ks):
            j = k
            while j + 1 < len(ks) and ks[j + 1] == ks[j] + 1:
                j += 1
            b = _range_get(f["url"], f.get("http_headers") or {}, refs[ks[k]][2], refs[ks[j]][3])
            fh.write(b); got += len(b)
            k = j + 1
    return got


def dash_sections(url: str, spans: list[tuple[float, float]], dst: Path, pad: float = 2.0, log=print, info: dict | None = None) -> dict | None:
    """쓸 구간(±pad 초)만 DASH 조각 바이트로 받아 dst(.mp4). 구간이 여러 개면 빈틈 없이 이어 붙인다(멈춘 화면이 안 생기게).
    옆에 <dst>.sections.json {t0(파일 0초의 원본 초), map:[[파일 초, 원본 시작, 원본 끝]], fmt, res, bytes, sec} · <dst>.info.json.
    파일 초 → 원본 초 = map 의 그 칸(구간 하나면 파일 초 + t0). 조각은 키프레임에서 시작 — 영상 copy(화질 그대로), 소리만 aac 로 영상 첫 프레임에 맞춘다.
    실패(형식·sidx 없음·화질 미달·네트워크)면 None — 부르는 쪽이 다음 길로. 예외를 올리지 않는다."""
    import json
    t_start = time.time()
    dst = Path(dst); dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if info is None:
            r = ytdlp(["-J", url], timeout=180, log=log)
            if r.returncode != 0 or not r.stdout.strip():
                log(f"[yt_fetch] DASH 조각: 영상 정보 실패 rc={r.returncode} {r.stderr[-160:].strip()}")
                return None
            info = json.loads(r.stdout)
        v, a, why = dash_pick(info)
        if v is None:
            log(f"[yt_fetch] DASH 조각 못 씀: {why}")
            return None
        vinit, vrefs = dash_index(v["url"], v.get("http_headers") or {})
        ainit, arefs = dash_index(a["url"], a.get("http_headers") or {}) if a is not None else (b"", [])
        wins = _merge_spans([(s, e) for s, e in ((vrefs[k][0], vrefs[k][1]) for k in _segs_for(vrefs, _merge_spans(spans, pad)))], 0.0)
        if not wins:
            log(f"[yt_fetch] DASH 조각: 구간 {spans} 이 영상 길이 밖")
            return None
        got, parts, mp, at = 0, [], [], 0.0
        for i, (w0, w1) in enumerate(wins):
            vk = _segs_for(vrefs, [(w0, w1)])
            vp = dst.with_name(dst.stem + f".dash_v{i}.mp4")
            got += _frag_file(vp, v, vinit, vrefs, vk)
            cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(vp)]
            if a is not None:
                ak = _segs_for(arefs, [(w0, w1)])
                ap = dst.with_name(dst.stem + f".dash_a{i}.mp4")
                got += _frag_file(ap, a, ainit, arefs, ak)
                lead = max(0.0, w0 - arefs[ak[0]][0])     # 소리 첫 조각은 영상보다 앞에서 시작한다 — 영상 첫 프레임에 맞춰 자른다
                cmd += ["-ss", f"{lead:.3f}", "-i", str(ap), "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"]
            pp = dst.with_name(dst.stem + f".dash_p{i}.mp4")
            cmd += ["-c:v", "copy", str(pp)]
            rr = subprocess.run(cmd, capture_output=True, text=True, errors="replace", stdin=subprocess.DEVNULL, timeout=600)
            if rr.returncode != 0 or not _valid(pp):
                log(f"[yt_fetch] DASH 조각 합치기 실패: {rr.stderr[-200:].strip()}")
                return None
            d = _probe_dur(pp)
            mp.append([round(at, 3), round(w0, 3), round(w0 + d, 3)])
            at += d
            parts.append(pp)
        tmp = dst.with_suffix(".dash.mp4")
        if len(parts) == 1:
            os.replace(parts[0], tmp)
        else:                                             # 구간마다 파일 0초부터 — concat 이 시각을 이어 준다(빈틈 없음)
            lst = dst.with_name(dst.stem + ".dash_list.txt")
            lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
            rr = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(tmp)],
                                capture_output=True, text=True, errors="replace", stdin=subprocess.DEVNULL, timeout=600, cwd=str(dst.parent))
            if rr.returncode != 0:
                log(f"[yt_fetch] DASH 조각 잇기 실패: {rr.stderr[-200:].strip()}")
                return None
        need = max(0.3, min(b - a_ for a_, b in spans) * 0.5) if spans else None
        if not _valid(tmp, need):
            log("[yt_fetch] DASH 조각: 결과 파일이 비었거나 짧다")
            return None
        os.replace(tmp, dst)
        meta = {"how": "dash_range", "t0": mp[0][1], "map": mp, "asked": [[float(s), float(e)] for s, e in spans], "pad": pad,
                "fmt": f"{v.get('format_id')}+{a.get('format_id') if a else ''}", "res": f"{v['width']}x{v['height']}", "vcodec": v.get("vcodec"),
                "bytes": got, "sec": round(time.time() - t_start, 1)}
        dst.with_suffix(".sections.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        dst.with_suffix(".info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        log(f"[yt_fetch] DASH 조각 구간 {len(mp)}개 {meta['sec']}초 {meta['res']} {meta['fmt']} t0={meta['t0']} → {dst} {dst.stat().st_size / 1e6:.1f}MB")
        return meta
    except Exception as e:  # noqa: BLE001 — 이 길이 안 되면 다음 길(형식 사슬·통째)로. 이유는 남긴다
        log(f"[yt_fetch] DASH 조각 실패 → 다음 길: {type(e).__name__}: {str(e)[:200]}")
        return None
    finally:
        for q in dst.parent.glob(dst.stem + ".dash*"):
            try:
                q.unlink()
            except OSError:
                pass


def sections_meta(dst: Path) -> dict | None:
    """dash_sections 가 남긴 구간 표(파일 0초 = 원본 t0). 없으면 None(형식 사슬로 받은 파일 = 시작 시각을 따로 재야 한다)."""
    import json
    p = Path(dst).with_suffix(".sections.json")
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() and Path(dst).exists() and p.stat().st_mtime >= Path(dst).stat().st_mtime - 5 else None
    except (OSError, ValueError):
        return None


SECTIONS_BAD_SEC = 6 * 3600   # 구간 받기가 멈춘 PC 는 이 동안 구간 받기를 건너뛴다(통째로 바로)


def _sections_mark() -> Path:
    return Path(os.environ.get("SHORTEM_HOME") or (Path.home() / ".shortem")) / "yt_sections_stall"


def sections_bad() -> bool:
    """이 PC(회선·계정)에서 구간 받기가 최근 멈췄나 — 10-21·22 yt3: 구간 받기가 형식마다 60초씩 멈춘 뒤 통째로(재료 1편 120초+ 헛기다림)."""
    f = _sections_mark()
    return f.exists() and time.time() - f.stat().st_mtime < SECTIONS_BAD_SEC


def _mark_sections_bad(log=print):
    f = _sections_mark()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        log(f"[yt_fetch] 구간 받기가 이 PC 에서 멈춤 — {SECTIONS_BAD_SEC // 3600}시간 동안 구간 받기를 건너뛰고 통째로 받는다({f})")
    except OSError as e:
        log(f"[yt_fetch] 구간 멈춤 표식을 못 씀: {e}")


def download_sections(url: str, spans: list[tuple[float, float]], dst: Path, fmts=(FMT_SECTION_1080, "137+ba[ext=m4a]/bv*[height>=1080]+ba/b"),
                      pad: float = 0.0, timeout: float = 900, stall_sec: float = STALL_SEC, extra: list | None = None, log=print) -> Result | None:
    """구간들만 받아 dst(.mp4) 로. 형식 사슬을 차례로(HLS 먼저) — 멈추거나(stall) 시간초과·빈 파일이면 다음 형식. 성공하면 Result, 전부 실패면 None.
    이 PC 에서 최근 구간 받기가 멈췄으면(sections_bad) 시도하지 않고 None — 부르는 쪽이 통째로 받는다.
    ★먼저 DASH 조각 바로 받기(dash_sections — ffmpeg 가 주소를 읽지 않아 sections_bad 와 무관). 안 되면 아래 형식 사슬."""
    if spans and dash_sections(url, spans, dst, pad=pad, log=log) is not None:
        return Result(0, "", "", 0.0)
    if sections_bad():
        log("[yt_fetch] 구간 받기 건너뜀(이 PC 최근 멈춤) → 통째로")
        return None
    dst = Path(dst); dst.parent.mkdir(parents=True, exist_ok=True)
    need = max(0.3, min(b - a for a, b in spans) * 0.5) if spans else None
    last = None
    stalls = 0
    for fmt in fmts:
        args = ["-f", fmt, "--merge-output-format", "mp4", "-o", str(dst.with_suffix(".%(ext)s")), *(extra or [])]
        for a, b in spans:
            args += ["--download-sections", f"*{max(0.0, a - pad):.1f}-{b + pad:.1f}"]
        args += ["--force-keyframes-at-cuts", url]
        last = ytdlp(args, timeout=timeout, stall_sec=stall_sec, watch=dst.with_suffix(""), log=log)
        if _valid(dst, need):
            log(f"[yt_fetch] 구간 {len(spans)}개 {last.sec}초 fmt={fmt[:40]}… → {dst} {dst.stat().st_size // 1_000_000}MB")
            return last
        _cleanup(dst)
        stalls += 1 if (last.stalled or last.timed_out) else 0
        log(f"[yt_fetch] 형식 실패({'멈춤' if last.stalled else '시간초과' if last.timed_out else 'rc=' + str(last.returncode)}) → 다음 형식: {last.stderr[-160:].strip()}")
    if stalls == len(fmts):
        _mark_sections_bad(log)
    return None


def storyboard_tiles(info: dict, max_tiles: int = 160) -> list[tuple[float, "object"]]:
    """yt-dlp 정보(-J)의 스토리보드(유튜브 미리보기 그림 모음, 약 5초 간격) → [(초, PIL 그림)] — 영상을 받지 않는다(10-22 실측 17조각 3.1초).
    sb0(359×180) 먼저 — 칸이 max_tiles 를 넘으면 sb1(179×90). 원본 찾기·재료 고르기가 같이 쓴다(주인 한 곳)."""
    import io
    import urllib.request
    from PIL import Image
    dur = float(info.get("duration") or 0)
    fmts = [f for f in info.get("formats") or [] if str(f.get("format_id", "")).startswith("sb") and f.get("fragments")]
    fmts.sort(key=lambda f: -(f.get("width") or 0))
    pick = next((f for f in fmts if dur * float(f.get("fps") or 0.2) <= max_tiles), fmts[-1] if fmts else None)
    if not pick:
        return []
    rows, cols, fw, fh = int(pick.get("rows") or 1), int(pick.get("columns") or 1), int(pick["width"]), int(pick["height"])
    step = 1.0 / float(pick.get("fps") or 0.2)
    out = []
    for fr in pick["fragments"]:
        u = fr.get("url") or (str(pick.get("fragment_base_url") or "") + str(fr.get("path") or ""))
        try:
            im = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())).convert("RGB")
        except Exception:  # noqa: BLE001 — 한 조각이 빠져도 나머지로(빠진 칸은 시각이 밀리지 않게 건너뛴다)
            out += [(None, None)] * (rows * cols)
            continue
        for y in range(rows):
            for x in range(cols):
                t = len(out) * step
                if t <= dur:
                    out.append((round(t, 1), im.crop((x * fw, y * fh, (x + 1) * fw, (y + 1) * fh))))
    return [(t, im) for t, im in out if im is not None]


def download_full(url: str, dst: Path, fmt: str = "137+ba[ext=m4a]/bv*[height>=1080]+ba/bv*[height>=720]+ba/b", timeout: float = 1800,
                  stall_sec: float = STALL_SEC * 2, extra: list | None = None, log=print) -> Result:
    """통째 받기(자막 없이 — 자막은 fetch_subs 로 따로). 멈춤 감시 포함."""
    dst = Path(dst); dst.parent.mkdir(parents=True, exist_ok=True)
    args = ["-f", fmt, "--merge-output-format", "mp4", "--write-info-json", "-o", str(dst.with_suffix(".%(ext)s")), *(extra or []), url]
    return ytdlp(args, timeout=timeout, stall_sec=stall_sec, watch=dst.with_suffix(""), log=log)


def fetch_subs(url: str, stem: Path, langs: str = "ko,ko-orig", tries: int = 3, log=print) -> list[Path]:
    """자동/수동 자막(vtt)만 — 유튜브가 429 를 자주 준다: 쉬었다 다시, 그래도 없으면 빈 목록(영상 받기와 무관)."""
    stem = Path(stem)
    found = sorted(stem.parent.glob(stem.name + "*.vtt"))
    if found:
        return found
    for attempt in range(tries):
        r = ytdlp(["--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", langs, "--sub-format", "vtt", "--ignore-errors",
                   "--sleep-subtitles", "3", "-o", str(stem), url], timeout=180)
        found = sorted(stem.parent.glob(stem.name + "*.vtt"))
        if found or "429" not in r.stderr:
            break
        time.sleep(10 * (attempt + 1))
    if not found:
        log(f"[yt_fetch] 자막 없음(영상과 무관): {stem.name} {r.stderr[-100:].strip()}")
    return found


def _norm(t: str) -> str:
    return unicodedata.normalize("NFC", t or "").lower().replace(" ", "")


def kw_hit(text: str, keywords: list[str]) -> bool:
    """키워드 적중 — NFC 로 맞추고(맥 업로드 제목은 NFD) 띄어쓰기를 지워 비교('진생 로얄' ↔ '진생로얄실크')."""
    t = _norm(text)
    return any(_norm(k) and _norm(k) in t for k in keywords)
