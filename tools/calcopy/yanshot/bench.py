# -*- coding: utf-8 -*-
"""① 벤치 — 판단 주인: bench(url, W) (관제 097, 2026-10-17).

받기(영상·자동자막·설명란) → 출처 표기 두 곳(설명란 '출처' 줄 · 화면 하단 '출처 : ○○' 판독) → 인물·제품·검색 낱말
→ 벤치 수치(bench_one.measure: 길이·LUFS·컷 중앙·창) → 1초 시트. 결과 W/bench.json.
화면 판독은 무료 제미나이 1회(프레임 4장) — 제목 2줄·출처 글·인물·제품·브랜드를 한 번에 읽는다.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from tools.calcopy.yanshot.common import BENCH_FMT, GEM_MODELS, StageError, dur_of, jload, jsave, run

SRC_LINE = re.compile(r"(?:영상\s*)?출처\s*[:：]?\s*(.+)")


def vid_of(url: str) -> str:
    m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not m:
        raise StageError(f"유튜브 영상 id 를 못 읽음: {url}")
    return m.group(1)


def source_label(desc: str, ocr: str | None) -> dict:
    """출처 표기 → {channel, raw, from}. 설명란 '출처:' 줄이 먼저, 없으면 화면 판독 글."""
    for line in (desc or "").splitlines():
        m = SRC_LINE.search(line.strip().lstrip("※*·- "))
        if m:
            raw = m.group(1).strip()
            ch = re.split(r"\s+유튜브|\s+20\d{2}[.\-/]|\s*[|,·]", raw)[0].strip()
            return {"channel": ch, "raw": raw, "from": "설명란"}
    if ocr:
        raw = re.sub(r"^\s*(?:영상\s*)?출처\s*[:：]?\s*", "", ocr).strip()
        if raw:
            return {"channel": re.split(r"\s+유튜브|\s+20\d{2}[.\-/]", raw)[0].strip(), "raw": raw, "from": "화면"}
    return {"channel": "", "raw": "", "from": None}


def sheet(mp4, out, step: float = 1.0, cols: int = 8, cw: int = 180):
    """1초 시트(칸마다 시각) — 사람·클로드가 눈으로 읽는 판."""
    out = Path(out)
    tmp = out.parent / f"_{out.stem}"
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.glob("*.jpg"):
        f.unlink()
    run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", f"fps={1 / step},scale={cw}:-2", str(tmp / "%04d.jpg")])
    fr = sorted(tmp.glob("*.jpg"))
    if not fr:
        raise StageError(f"시트 프레임 0장: {mp4}")
    w, h = Image.open(fr[0]).size
    rows = (len(fr) + cols - 1) // cols
    sh = Image.new("RGB", (cols * w, rows * (h + 16)), "white")
    d = ImageDraw.Draw(sh)
    for i, f in enumerate(fr):
        x, y = i % cols * w, i // cols * (h + 16)
        sh.paste(Image.open(f), (x, y + 16))
        d.text((x + 3, y + 2), f"{i * step + step / 2:.1f}s", fill=(220, 0, 0))
    sh.save(out, quality=82)
    for f in fr:
        f.unlink()
    tmp.rmdir()
    return out


def _frame_jpg(mp4, t: float, w: int = 540) -> bytes:
    return subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={w}:-2",
                           "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True).stdout


READ_PROMPT = """위 4장은 한국 '연예인 쇼핑템' 쇼츠의 프레임이다(시각 순). 화면에 보이는 글을 읽어라.
- screen_title: 화면 위 큰 제목(줄바꿈 \\n 으로 2줄 그대로)
- source_ocr: 화면 아래쪽 '출처 : ○○' 같은 출처 글(없으면 빈 글)
- person: 이 영상의 주인공 연예인 이름(제목·자막에서)
- product: 소개하는 제품 종류를 짧게(예: '수건', '실내화', '채소 보관통')
- brand: 상표·브랜드 이름(보이면, 없으면 빈 글)
- keywords: 원본 영상에서 그 제품을 말할 때 쓸 낱말 2~4개(예: ['수건','테클라'])
JSON만: {"screen_title":"","source_ocr":"","person":"","product":"","brand":"","keywords":[]}"""


def read_screen(mp4, dur: float, ask=None) -> dict:
    if ask is None:
        from tools.calcopy.engine.gemini_free import ask as ask_
        ask = ask_
    ts = [min(dur - 0.3, x) for x in (1.0, dur * 0.35, dur * 0.65, dur - 1.0)]
    d, why = ask([_frame_jpg(mp4, t) for t in ts], READ_PROMPT, tag="yanshot_bench_read", models=GEM_MODELS)
    if d is None:
        raise StageError(f"벤치 화면 판독 실패: {why}")
    return d


def bench(url: str, W: Path, ask=None, measure=True, log=print) -> dict:
    """(판단 주인) 벤치 한 편 → W/bench.json."""
    W = Path(W)
    bd = W / "bench"
    bd.mkdir(parents=True, exist_ok=True)
    vid = vid_of(url)
    mp4 = bd / "bench.mp4"
    if not mp4.exists():
        run(["yt-dlp", "--no-update", "--socket-timeout", "20", "-f", BENCH_FMT, "--merge-output-format", "mp4", "--write-auto-subs", "--write-subs",
             "--sub-langs", "ko-orig,ko", "--sub-format", "vtt", "--write-info-json", "-o", str(bd / "bench.%(ext)s"),
             f"https://www.youtube.com/shorts/{vid}"], timeout=600)
    info = jload(bd / "bench.info.json")
    vtts = sorted(bd.glob("bench*.vtt"))
    vtt = next((v for v in vtts if ".ko-orig." in v.name), None) or next((v for v in vtts if ".ko." in v.name), None)
    if not vtt:
        raise StageError("벤치 자동자막(ko) 없음 — 지문 대조 불가")
    dur = dur_of(mp4)
    scr = read_screen(mp4, dur, ask=ask)
    lab = source_label(info.get("description") or "", scr.get("source_ocr"))
    B = {"id": vid, "url": url, "channel": info.get("channel") or info.get("uploader"), "title": info.get("title"),
         "views": info.get("view_count"), "upload": info.get("upload_date"), "description": info.get("description") or "",
         "mp4": str(mp4), "vtt": str(vtt), "dur": round(dur, 2), "screen_title": scr.get("screen_title") or "",
         "person": (scr.get("person") or "").strip(), "product": (scr.get("product") or "").strip(), "brand": (scr.get("brand") or "").strip(),
         "keywords": [k for k in (scr.get("keywords") or []) if isinstance(k, str)] or [scr.get("product") or ""],
         "source_label": lab, "read_model": scr.get("_model")}
    if measure:
        from tools.calcopy.engine import bench_one
        m = bench_one.measure(str(mp4))
        c = m.get("cuts") or {}
        a = m.get("audio") or {}
        B["measure"] = {"shot_median": c.get("shot_median"), "shots": c.get("shots"), "cuts": c.get("cuts"), "lufs": a.get("I"), "tp": a.get("TP"),
                        "window": (m.get("vl") or {}).get("window"), "errors": m.get("errors")}
    sheet(mp4, bd / "sheet_1s.jpg")
    jsave(W / "bench.json", B)
    log(f"[bench] {vid} {B['channel']} {B['dur']}초 · 인물 {B['person']} · 제품 {B['product']} · 출처 {lab['raw'] or '(없음)'}({lab['from']}) "
        f"· 컷 중앙 {(B.get('measure') or {}).get('shot_median')} · LUFS {(B.get('measure') or {}).get('lufs')}")
    return B
