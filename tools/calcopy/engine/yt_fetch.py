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
    cmd = ["yt-dlp", "--no-warnings", "--no-playlist", *[str(a) for a in args]]
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


def download_sections(url: str, spans: list[tuple[float, float]], dst: Path, fmts=(FMT_SECTION_1080, "137+ba[ext=m4a]/bv*[height>=1080]+ba/b"),
                      pad: float = 0.0, timeout: float = 900, stall_sec: float = STALL_SEC, extra: list | None = None, log=print) -> Result | None:
    """구간들만 받아 dst(.mp4) 로. 형식 사슬을 차례로(HLS 먼저) — 멈추거나(stall) 시간초과·빈 파일이면 다음 형식. 성공하면 Result, 전부 실패면 None."""
    dst = Path(dst); dst.parent.mkdir(parents=True, exist_ok=True)
    need = max(0.3, min(b - a for a, b in spans) * 0.5) if spans else None
    last = None
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
        log(f"[yt_fetch] 형식 실패({'멈춤' if last.stalled else '시간초과' if last.timed_out else 'rc=' + str(last.returncode)}) → 다음 형식: {last.stderr[-160:].strip()}")
    return None


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
