# -*- coding: utf-8 -*-
"""고객 Claude 창구 — 고객 PC 모드에서 gemini_free.ask 대신 (관제 234, 2026-10-19 사장님 "워커들이 일하는 것, 지금 제미나이가 하는 걸 고객 Claude 가").

부르는 쪽은 아무것도 안 바꾼다: CALCOPY_GEMINI_BACKEND=client 이면 gemini_free.ask → 여기 ask().
  ask(parts, prompt, tag) -> (dict|None, 실패이유|None)   (gemini_free.ask 와 같은 꼴)

하는 일
  1. 요청 한 건 = SHORTEM_LLM_QUEUE/<id>/ 폴더. 그림 파트는 파일로, 소리 파트는 받아쓰기(asr_local: 위스퍼/스피치매틱스) 글로,
     영상 파트는 장면 그림 + 받아쓰기로 바꾼다 — Claude 는 소리·영상을 직접 못 받는다.
  2. request.json 을 **마지막에** 쓴다(임시 이름 → 바꿔 달기). MCP(shortem)가 이것을 보고 Claude 에게 "요청 N건" 으로 넘긴다.
  3. Claude 가 답한 answer.json(JSON 객체) 이 생기면 읽어 돌려준다. 모양이 틀리면 error.json 에 이유를 적고 한 번 더 기다린다
     (하이쿠도 돌게 — 조용히 넘기지 않는다). 시간 안에 답이 없으면 (None, "client_timeout").
  ★권장 등급(haiku/sonnet/opus)은 tier_of(tag) 한 곳 — 글쓰기(대본)는 opus, 판독·분류는 haiku, 나머지 sonnet.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

POLL_S = 0.5
TIMEOUT_S = float(os.environ.get("SHORTEM_LLM_TIMEOUT") or 3600)
RETRIES = 2                      # 모양이 틀린 답을 다시 묻는 횟수
VIDEO_FRAMES = 12                # 영상 파트 → 장면 그림 최대 장수
# tag 머리 → 권장 등급. 위에서부터 첫 일치. (대본 글쓰기 = 품질, 판독·분류 = 속도)
TIERS = (
    (r"^(draft|rewrite|narr|support|captions_line|style)", "opus"),
    (r"^(asr|tts_asr|ov|ovedge|ma_tag|tag|db_nouns|fit|channel_find:sample|frame_text)", "haiku"),
)


def tier_of(tag: str) -> str:
    for pat, tier in TIERS:
        if re.search(pat, tag or ""):
            return tier
    return "sonnet"


def queue_dir() -> Path:
    q = os.environ.get("SHORTEM_LLM_QUEUE")
    if not q:
        raise RuntimeError("SHORTEM_LLM_QUEUE 가 없다 — 고객 PC 모드는 MCP(shortem)가 줄 폴더를 정해 엔진을 띄운다")
    p = Path(q)
    p.mkdir(parents=True, exist_ok=True)
    return p


def describe_audio(path: str) -> str:
    """소리 → Claude 가 읽을 글: 받아쓰기 구절(시각·글) + 구절별 음높이(f0, 성별 짐작 재료)·크기(dB)."""
    from tools.calcopy.engine import asr_local
    r = asr_local.transcribe(path)
    lines = [f"[소리 판독 — {r['engine']} · 언어 {r.get('lang') or '?'} · 길이 {r['dur']}초 · 전체 크기 {r['db_all']}dB]",
             "구절(시작~끝 초 | 음높이 Hz(남 85~180 · 여 165~255) | 크기 dB | 글):"]
    for s in r["segments"]:
        lines.append(f"  {s['start']:.2f}~{s['end']:.2f} | {s['f0'] or '-'} | {s['db']} | {s['text']}")
    if not r["segments"]:
        lines.append("  (말소리 없음)")
    b = r.get("bed") or {}
    if b.get("nonspeech_s"):
        lines.append(f"말 없는 구간 {b['nonspeech_s']}초 중 소리 큼(> -35dB) {b['loud_s']}초({b['loud_share']:.0%}) · "
                     f"그중 한 음높이가 또렷함 {b['tonal_s']}초({b['tonal_share']:.0%})")
        lines.append("  → 말 없는 구간 대부분이 크면 배경음악이나 현장음이 깔린 것이다(이 판독으로는 둘을 못 가른다 — 2026-10-19 실측: 잡음·노래 모두 크게 잡힘). "
                     "이때 받아쓴 짧은 외국어 말은 노래 가사일 수 있다. 그 경우 bgm.present=true, 분위기는 모르면 빈 목록.")
    if r.get("note"):
        lines.append(f"  ※ {r['note']}")
    lines.append("※ 소리는 직접 못 들으니 위 판독으로 답하라. 효과음·배경음악처럼 판독에 없는 것은 모르면 비우거나 unknown.")
    return "\n".join(lines)


def _video_frames(path: str, d: Path, n: int = VIDEO_FRAMES) -> list[str]:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    dur = float(r.stdout.strip() or 0) or 1.0
    out = []
    for k in range(n):
        t = dur * (k + 0.5) / n
        f = d / f"v{k:02d}_{t:.1f}s.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=-2:640", str(f)],
                       check=False, stdin=subprocess.DEVNULL)
        if f.exists():
            out.append(f.name)
    return out


def _write_parts(parts: list, d: Path) -> list[dict]:
    items = []
    for i, p in enumerate(parts or []):
        if isinstance(p, (bytes, bytearray)):
            f = d / f"p{i:02d}.jpg"
            f.write_bytes(bytes(p))
            items.append({"kind": "image", "file": f.name})
        elif isinstance(p, tuple):
            data, mime = bytes(p[0]), str(p[1])
            if mime.startswith("image/"):
                f = d / f"p{i:02d}.{mime.split('/')[1].replace('jpeg', 'jpg')}"
                f.write_bytes(data)
                items.append({"kind": "image", "file": f.name})
            elif mime.startswith(("audio/", "video/")):
                with tempfile.NamedTemporaryFile(suffix="." + mime.split("/")[1], delete=False) as t:
                    t.write(data)
                    tmp = t.name
                try:
                    if mime.startswith("video/"):
                        items += [{"kind": "image", "file": x} for x in _video_frames(tmp, d)]
                    items.append({"kind": "text", "text": describe_audio(tmp)})
                finally:
                    os.unlink(tmp)
            else:
                items.append({"kind": "text", "text": data.decode("utf-8", "replace")})
        else:
            items.append({"kind": "text", "text": str(p)})
    return items


def _read_answer(f: Path) -> tuple[dict | None, str | None]:
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"JSON 이 아니다: {e}"
    if isinstance(d, list):
        d = {"items": d}
    if not isinstance(d, dict):
        return None, f"JSON 객체가 아니다({type(d).__name__})"
    return d, None


def ask(parts: list, prompt: str, tag: str = "", models: tuple | None = None) -> tuple[dict | None, str | None]:
    q = queue_dir()
    rid = time.strftime("%Y%m%d-%H%M%S") + "-" + re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", tag or "ask")[:40] + "-" + uuid.uuid4().hex[:6]
    d = q / rid
    d.mkdir()
    items = _write_parts(parts, d)
    req = {"id": rid, "tag": tag, "tier": tier_of(tag), "prompt": prompt, "parts": items,
           "answer": "answer.json 에 JSON 객체 하나(지시문이 정한 모양 그대로)", "made_at": time.time()}
    tmp = d / "request.json.tmp"
    tmp.write_text(json.dumps(req, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(d / "request.json")
    ans, err_f = d / "answer.json", d / "error.json"
    t0, tries = time.time(), 0
    while time.time() - t0 < TIMEOUT_S:
        if ans.exists():
            try:
                st = ans.stat()
            except OSError:
                st = None
            if st is None or st.st_size == 0 or time.time() - st.st_mtime < 1.0:
                time.sleep(POLL_S)       # 쓰는 중일 수 있다(10-19 실측: 빈 파일을 읽어 '틀린 답'으로 셌다) — 다 써진 뒤에 읽는다
                continue
            res, why = _read_answer(ans)
            if res is not None:
                res["_model"] = "client:" + str(res.pop("_tier", req["tier"]))
                res["_via"] = "client"
                (d / "done").write_text("", encoding="utf-8")
                return res, None
            tries += 1
            ans.replace(d / f"answer.bad{tries}.json")
            if tries > RETRIES:
                (d / "done").write_text("", encoding="utf-8")
                return None, f"client_bad_answer: {why}"
            err_f.write_text(json.dumps({"why": why, "try": tries}, ensure_ascii=False), encoding="utf-8")
        time.sleep(POLL_S)
    (d / "done").write_text("", encoding="utf-8")
    return None, "client_timeout"
