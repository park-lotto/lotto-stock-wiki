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
    이 PC 에서 최근 구간 받기가 멈췄으면(sections_bad) 시도하지 않고 None — 부르는 쪽이 통째로 받는다."""
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
