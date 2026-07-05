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

import gemini_client


@dataclass
class Segment:
    start: float   # seconds
    text: str


def to_mmss(sec: float) -> str:
    total = int(sec)
    if total >= 3600:
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    m, s = divmod(total, 60)
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
    cmd = [sys.executable, "-m", "yt_dlp", "--skip-download",
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
CAPTURE_FALLBACK_CAP = 8

_VID = re.compile(r"(?:v=|youtu\.be/|/live/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")


def parse_video_id(url: str) -> str:
    m = _VID.search(url or "")
    return m.group(1) if m else ""


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
    return [sys.executable, "-m", "yt_dlp", "--skip-download",
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


def _capture_cmd(stream_url: str, ts: float, out_path: str) -> list[str]:
    # -ss 를 -i 앞에 두면 키프레임 기준 빠른 seek (전체 디코드 안 함)
    return ["ffmpeg", "-y", "-ss", f"{ts}", "-i", stream_url,
            "-frames:v", "1", "-q:v", "2", out_path]


def _stream_url(url: str) -> str:
    try:
        out = subprocess.run([sys.executable, "-m", "yt_dlp", "-g", "-f",
                              "best[height<=720]", "--no-warnings", url],
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=90)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"스트림 URL 타임아웃: {url}")
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"스트림 URL 실패: {out.stderr[:200]}")
    return out.stdout.strip().splitlines()[0]


def capture_frame(url: str, ts: float, out_path: str) -> str:
    stream = _stream_url(url)
    try:
        r = subprocess.run(_capture_cmd(stream, ts, out_path),
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"프레임 캡처 타임아웃 @ {ts}s")
    if r.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(f"프레임 캡처 실패 @ {ts}s: {r.stderr[:200]}")
    return out_path


def detect_visuals(frame_paths: list[str]) -> list[bool]:
    """각 프레임에 리포트/차트/슬라이드가 있는지 Gemini 비전 판정."""
    from google.genai import types
    import gemini_client
    results: list[bool] = []
    for p in frame_paths:
        data = open(p, "rb").read()
        contents = types.Content(parts=[
            types.Part(inline_data=types.Blob(mime_type="image/png", data=data)),
            types.Part(text='이 화면에 리포트·표·차트·슬라이드 같은 "자료"가 '
                            '떠 있으면 {"visual":true}, 사람 얼굴/배경만이면 '
                            '{"visual":false} JSON만 출력.'),
        ])
        resp = gemini_client._generate("gemini-3-flash-preview", contents,
                                       types.GenerateContentConfig(temperature=0))
        results.append(bool(gemini_client._parse_json_text(resp.text).get("visual")))
    return results


def candidate_to_dict(c: QuoteCandidate) -> dict:
    return {
        "source": c.source, "ts": to_mmss(c.ts), "ts_sec": c.ts,
        "text": c.text, "tier": c.tier, "has_visual": c.has_visual,
        "heat": c.heat, "stance": c.stance, "evidence": c.evidence,
        "score": c.score, "reasons": c.reasons, "media": c.media,
    }


def _ts_to_sec(v) -> float:
    """'MM:SS' / 'H:MM:SS' / 숫자 → 초(float)."""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    parts = s.split(":")
    try:
        if len(parts) == 3:
            h, m, sec = parts
            return int(h) * 3600 + int(m) * 60 + float(sec)
        if len(parts) == 2:
            m, sec = parts
            return int(m) * 60 + float(sec)
        return float(s)
    except ValueError:
        return 0.0


def build_video_prompt(topic: str) -> str:
    """call_video용 루브릭 프롬프트 — Gemini가 영상 보고 골든 발언 JSON 반환."""
    t = f'주제 "{topic}"에 관한 ' if topic else ''
    return (
        f"너는 주식 영상 편집자다. 이 영상을 보고 {t}'골든 발언'만 골라라.\n"
        "골든 규칙 — 필수 3개를 모두 넘어야 golden=true:\n"
        "1) 주장 명확: 판단이 있는가 (인사말·물타기·\"지켜봐야죠\"는 탈락)\n"
        "2) 근거 동반: 왜인가 (근거유형=수급|실적|밸류|공급망|기타)\n"
        "3) 입장 존재: stance=강세|약세|중립|전환 중 하나\n"
        "가점: specific(숫자·날짜·종목·조건 있으면 true), "
        "has_visual(말할 때 화면에 리포트·차트·슬라이드 등 자료가 떠 있으면 true).\n"
        "발언은 최대 8개. JSON만 출력:\n"
        '{"quotes":[{"ts":"MM:SS","text":"발언 그대로","golden":true,'
        '"stance":"강세|약세|중립|전환","evidence":"수급|실적|밸류|공급망|기타",'
        '"specific":true,"has_visual":true,"reasons":["..."]}]}'
    )


def parse_video_reply(text: str, source: str) -> list[QuoteCandidate]:
    """call_video 텍스트 응답 → 골든 QuoteCandidate 리스트 (has_visual 포함)."""
    t = re.sub(r'```(?:json)?', '', text).strip('`').strip()
    try:
        reply = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]+\}', t)
        reply = json.loads(m.group()) if m else {"quotes": []}
    out = []
    for q in reply.get("quotes", []):
        if not q.get("golden"):
            continue
        score = 3 + (1 if q.get("specific") else 0) + (1 if q.get("has_visual") else 0)
        out.append(QuoteCandidate(
            source=source, ts=_ts_to_sec(q.get("ts", 0)), text=q.get("text", ""),
            stance=q.get("stance", "중립"), evidence=q.get("evidence", "기타"),
            score=score, reasons=q.get("reasons", []),
            has_visual=bool(q.get("has_visual"))))
    return out


def _extract_via_video(url, topic):
    """Gemini가 영상을 직접 시청해 골든 발언 추출 (yt-dlp 봇차단 우회 — 서버 경로)."""
    yield {"type": "progress", "phase": "제미니 영상 시청"}
    source = url
    try:
        text = gemini_client.call_video(url, build_video_prompt(topic),
                                        model="gemini-2.5-flash")
        cands = parse_video_reply(text, source)
    except Exception as e:
        print(f"[extract_stream] call_video 실패: {e}", file=sys.stderr)
        yield {"type": "error", "message": f"영상 분석 실패: {str(e)[:160]}"}
        return
    assign_tiers(cands)   # heatmap 없음 → has_visual만 T1, 나머지 T3
    cands.sort(key=lambda c: (c.tier, -c.score, -c.heat))
    doc = {"topic": topic, "source": source,
           "quotes": [candidate_to_dict(c) for c in cands]}
    yield {"type": "result", "doc": doc}


def extract_stream(url, topic, max_segments=None):
    """스트리밍 오케스트레이터 — 진행이벤트 + 최종 결과를 yield.
    yt-dlp 자막 경로를 먼저 시도(로컬은 됨), 봇차단 등 실패 시 Gemini
    call_video 경로로 폴백(서버 IP는 유튜브 직접접근이 봇차단됨).
    capture는 하지 않음(MVP 픽전용)."""
    yield {"type": "progress", "phase": "메타"}
    try:
        info = fetch_info(url)
        source = f"{info['channel']} / {info['webpage_url']}"
        yield {"type": "progress", "phase": "자막"}
        segments = get_transcript(url)
    except Exception as e:
        # yt-dlp 봇차단(서버) 등 → Gemini 영상 시청으로 폴백
        print(f"[extract_stream] yt-dlp 경로 실패 → call_video 폴백: {e}", file=sys.stderr)
        yield from _extract_via_video(url, topic)
        return

    if max_segments:
        yield {"type": "progress", "phase": "bound",
               "used": max_segments, "total": len(segments)}
        segments = segments[:max_segments]

    chunks = chunk_segments(segments)
    cands = []
    for i, ch in enumerate(chunks):
        yield {"type": "progress", "phase": "채점", "done": i, "total": len(chunks)}
        try:
            reply = gemini_client.call_json(build_score_prompt(topic, ch))
            cands.extend(parse_score_reply(reply, source))
        except Exception as e:
            print(f"[extract_stream] 청크 {i} 실패: {e}", file=sys.stderr)
            yield {"type": "progress", "phase": "청크실패",
                   "done": i, "total": len(chunks)}

    apply_heatmap(cands, parse_heatmap(info))
    assign_tiers(cands)
    cands.sort(key=lambda c: (c.tier, -c.score, -c.heat))
    doc = {"topic": topic, "source": source,
           "quotes": [candidate_to_dict(c) for c in cands]}
    yield {"type": "result", "doc": doc}


def extract(url: str, topic: str, capture: bool = False,
            out_path: str | None = None,
            max_segments: int | None = None) -> dict:
    info = fetch_info(url)
    source = f"{info['channel']} / {info['webpage_url']}"
    segments = get_transcript(url)

    scored_segments = segments
    if max_segments is not None:
        scored_segments = segments[:max_segments]
        print(f"[extract] {max_segments}/{len(segments)} 세그먼트만 채점(bounded smoke)",
              file=sys.stderr)

    cands = score_quotes(topic, scored_segments, source)
    apply_heatmap(cands, parse_heatmap(info))
    assign_tiers(cands)

    if capture and cands:
        import shutil
        wd = tempfile.mkdtemp(prefix="qe_cap_")
        try:
            targets = [c for c in cands if c.tier <= 2]
            if not targets:
                targets = sorted(cands, key=lambda c: -c.score)[:CAPTURE_FALLBACK_CAP]
                print(f"[extract] tier<=2 후보 없음, 상위 {len(targets)}개만 캡처 "
                      f"(cap={CAPTURE_FALLBACK_CAP})", file=sys.stderr)
            paths = []
            for i, c in enumerate(targets):
                fp = os.path.join(wd, f"cap_{i:03d}.png")
                try:
                    capture_frame(url, c.ts, fp); paths.append((c, fp))
                except Exception:
                    pass
            if paths:
                try:
                    flags = detect_visuals([p for _, p in paths])
                    for (c, _), v in zip(paths, flags):
                        c.has_visual = c.has_visual or v
                    assign_tiers(cands)   # 화면근거 반영 재-tier
                except Exception as e:
                    print(f"[extract] 비전 판정 실패, 캡처 스킵: {e}", file=sys.stderr)
        finally:
            shutil.rmtree(wd, ignore_errors=True)

    cands.sort(key=lambda c: (c.tier, -c.score, -c.heat))
    doc = {"topic": topic, "source": source,
           "quotes": [candidate_to_dict(c) for c in cands]}
    if out_path:
        import json as _j
        open(out_path, "w", encoding="utf-8").write(
            _j.dumps(doc, ensure_ascii=False, indent=2))
    return doc


if __name__ == "__main__":
    import argparse, json as _j
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--max-segments", type=int, default=None,
                     help="스모크용: 앞에서 N개 세그먼트만 채점(생략 시 전체)")
    a = ap.parse_args()
    doc = extract(a.url, a.topic, capture=a.capture, out_path=a.out,
                  max_segments=a.max_segments)
    print(_j.dumps(doc, ensure_ascii=False, indent=2)[:2000])
    print(f"\n총 {len(doc['quotes'])}개 후보 "
          f"(T1={sum(q['tier']==1 for q in doc['quotes'])} "
          f"T2={sum(q['tier']==2 for q in doc['quotes'])} "
          f"T3={sum(q['tier']==3 for q in doc['quotes'])})")
