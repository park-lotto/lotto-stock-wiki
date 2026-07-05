"""인용 엔진 스파이크 — URL → 골든 발언 후보(quotes_candidates.json).
전문가 인용 몽타주 영상용. 기존 gemini_client(18키 폴백) 재활용."""
from __future__ import annotations
import glob
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field


@dataclass
class Segment:
    start: float   # seconds
    text: str


def to_mmss(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"


_TS = re.compile(r"(\d\d):(\d\d):(\d\d)\.(\d{3})\s*-->")
_TAG = re.compile(r"<[^>]+>")


def parse_vtt(vtt_text: str) -> list[Segment]:
    """WEBVTT → Segment 리스트. 큐 시작시각(초) + 태그제거 텍스트."""
    segs: list[Segment] = []
    lines = vtt_text.splitlines()
    i = 0
    while i < len(lines):
        m = _TS.search(lines[i])
        if not m:
            i += 1
            continue
        h, mm, ss, ms = (int(x) for x in m.groups())
        start = h * 3600 + mm * 60 + ss + ms / 1000
        i += 1
        buf = []
        while i < len(lines) and lines[i].strip() and not _TS.search(lines[i]):
            buf.append(_TAG.sub("", lines[i]).strip())
            i += 1
        text = " ".join(x for x in buf if x)
        if text:
            segs.append(Segment(start=start, text=text))
    return segs


def fetch_info(url: str) -> dict:
    """yt-dlp 단일 JSON 메타 (다운로드 없이). heatmap 포함."""
    cmd = ["python", "-m", "yt_dlp", "--skip-download",
           "--dump-single-json", "--no-warnings", url]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=90)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"yt-dlp 메타 타임아웃: {url}")
    if out.returncode != 0:
        raise RuntimeError(f"yt-dlp 메타 실패: {out.stderr[:300]}")
    try:
        raw = json.loads(out.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"yt-dlp 메타 파싱 실패: {e}")
    return {
        "title": raw.get("title", ""),
        "channel": raw.get("channel") or raw.get("uploader", ""),
        "duration": raw.get("duration", 0),
        "webpage_url": raw.get("webpage_url", url),
        "heatmap": raw.get("heatmap"),
    }


def parse_heatmap(info: dict) -> list[dict]:
    """info.heatmap → [{start,end,value}]. 없으면 []."""
    hm = info.get("heatmap")
    if not hm:
        return []
    out = []
    for b in hm:
        out.append({
            "start": float(b.get("start_time", 0.0)),
            "end": float(b.get("end_time", 0.0)),
            "value": float(b.get("value", 0.0)),
        })
    return out


class TranscriptUnavailable(Exception):
    pass


def _transcript_cmd(url: str, lang: str, workdir: str) -> list[str]:
    outtmpl = os.path.join(workdir, "%(id)s.%(ext)s")
    return ["python", "-m", "yt_dlp", "--skip-download",
            "--write-auto-sub", "--write-sub", "--sub-lang", lang,
            "--sub-format", "vtt", "--no-warnings", "-o", outtmpl, url]


def get_transcript(url: str, lang: str = "ko", workdir: str | None = None) -> list[Segment]:
    """yt-dlp 자막(auto 포함) 다운로드 → Segment. 없으면 TranscriptUnavailable."""
    own = workdir is None
    workdir = workdir or tempfile.mkdtemp(prefix="qe_sub_")
    try:
        cmd = _transcript_cmd(url, lang, workdir)
        try:
            subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        except subprocess.TimeoutExpired:
            raise TranscriptUnavailable(f"자막 타임아웃: {url}")
        vtts = glob.glob(os.path.join(workdir, f"*{lang}*.vtt")) or \
               glob.glob(os.path.join(workdir, "*.vtt"))
        if not vtts:
            raise TranscriptUnavailable(
                f"{url}: {lang} 자막 없음 (후속: Whisper 폴백은 스파이크 범위 밖)")
        return parse_vtt(open(vtts[0], encoding="utf-8").read())
    finally:
        if own:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)
