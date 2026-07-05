"""인용 엔진 스파이크 — URL → 골든 발언 후보(quotes_candidates.json).
전문가 인용 몽타주 영상용. 기존 gemini_client(18키 폴백) 재활용."""
from __future__ import annotations
import re
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
