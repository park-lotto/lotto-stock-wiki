"""인용 엔진 스파이크 — URL → 골든 발언 후보(quotes_candidates.json).
전문가 인용 몽타주 영상용. 기존 gemini_client(18키 폴백) 재활용."""
from __future__ import annotations
import glob
import json
import os
import re
import subprocess
import sys
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


HEAT_THRESHOLD = 0.7


def apply_heatmap(cands: list[QuoteCandidate], heatmap: list[dict]) -> None:
    for c in cands:
        for b in heatmap:
            if b["start"] <= c.ts < b["end"]:
                c.heat = b["value"]
                break


def assign_tiers(cands: list[QuoteCandidate]) -> None:
    for c in cands:
        if c.has_visual:
            c.tier = 1
        elif c.heat >= HEAT_THRESHOLD:
            c.tier = 2
        else:
            c.tier = 3


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


@dataclass
class QuoteCandidate:
    source: str
    ts: float
    text: str
    stance: str
    evidence: str
    score: int
    reasons: list[str] = field(default_factory=list)
    has_visual: bool = False
    heat: float = 0.0
    tier: int = 3
    media: dict | None = None


def chunk_segments(segments: list[Segment], max_chars: int = 8000) -> list[list[Segment]]:
    """긴 자막(수천~수만 세그먼트)을 Gemini 토큰 예산 안으로 잘라서 청크 리스트로.
    세그먼트 하나를 쪼개지 않고, 누적 텍스트 길이가 max_chars를 넘기 전까지 모은다."""
    chunks: list[list[Segment]] = []
    current: list[Segment] = []
    current_len = 0
    for seg in segments:
        seg_len = len(seg.text)
        if current and current_len + seg_len > max_chars:
            chunks.append(current)
            current = []
            current_len = 0
        current.append(seg)
        current_len += seg_len
    if current:
        chunks.append(current)
    return chunks


def build_score_prompt(topic: str, segments: list[Segment]) -> str:
    lines = "\n".join(f"[{to_mmss(s.start)}|{s.start:.1f}] {s.text}" for s in segments)
    return f"""너는 주식 영상 편집자다. 주제 "{topic}"에 대한 아래 자막에서 '골든 발언'만 골라라.

골든 규칙 — 필수 3개를 모두 넘어야 golden=true:
1) 주장 명확: 판단이 있는가 (인사말·물타기·"지켜봐야죠"는 탈락)
2) 근거 동반: 왜인가 (근거유형=수급|실적|밸류|공급망|기타)
3) 입장 존재: stance=강세|약세|중립|전환 중 하나로 분류 가능

가점(specific): 숫자·날짜·종목·조건이 있으면 true.

자막(각 줄 [MM:SS|초] 텍스트):
{lines}

JSON만 출력:
{{"quotes":[{{"ts":<초 float>,"text":"...","golden":true|false,
"stance":"강세|약세|중립|전환","evidence":"수급|실적|밸류|공급망|기타",
"specific":true|false,"reasons":["..."]}}]}}"""


def parse_score_reply(reply: dict, source: str) -> list[QuoteCandidate]:
    out: list[QuoteCandidate] = []
    for q in reply.get("quotes", []):
        if not q.get("golden"):
            continue
        score = 3 + (1 if q.get("specific") else 0)   # 필수3 통과=3, 구체성 가점
        out.append(QuoteCandidate(
            source=source,
            ts=float(q.get("ts", 0.0)),
            text=q.get("text", ""),
            stance=q.get("stance", "중립"),
            evidence=q.get("evidence", "기타"),
            score=score,
            reasons=q.get("reasons", []),
        ))
    return out


def score_quotes(topic: str, segments: list[Segment], source: str,
                  max_chars: int = 8000) -> list[QuoteCandidate]:
    """긴 자막을 청크로 쪼개 Gemini에 순차 채점 요청 → 골든 후보 전체를 합쳐 반환.
    청크 하나가 실패해도(타임아웃·파싱오류 등) 전체 실행은 중단하지 않고 건너뛴다."""
    import gemini_client
    chunks = chunk_segments(segments, max_chars=max_chars)
    all_candidates: list[QuoteCandidate] = []
    failed = 0
    for i, chunk in enumerate(chunks):
        prompt = build_score_prompt(topic, chunk)
        try:
            reply = gemini_client.call_json(prompt)
            all_candidates.extend(parse_score_reply(reply, source))
        except Exception as e:
            failed += 1
            print(f"[score_quotes] 청크 {i+1}/{len(chunks)} 실패, 건너뜀: {e}",
                  file=sys.stderr)
    if failed:
        print(f"[score_quotes] 총 {len(chunks)}개 청크 중 {failed}개 실패", file=sys.stderr)
    return all_candidates
