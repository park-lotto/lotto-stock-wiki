# -*- coding: utf-8 -*-
"""클로드형 견본 전수 규격 검사(관제 234, 설계 §8-1) — 기준 밖 견본이 **하나라도** 있으면 종료코드 1.

재는 것(ffprobe·PIL — 사이드카 값을 믿지 않고 파일을 직접 잰다):
  공통     사이드카 <id>.json 이 있고 made_by == "preview v1"
  글꼴     PNG, 폭 720
  효과음   mp3, 길이 1.0~1.6초, 비트레이트 ≤ 72kbps, mono
  BGM     mp3, 길이 14.5~15.5초, ≤ 72kbps, mono
  목소리   mp3, 길이 ≤ 3.2초, ≤ 72kbps, mono
  템플릿   폭 360, 워터마크 = 원본 blob 을 같은 크기로 줄인 것과 픽셀 차(평균) ≥ 1.0 (원본 blob 이 있을 때)
  짤       JPEG, 칸 ≤ 240(사이드카 cell), 사이드카 quality ≤ 50
  통과작   mp4, 긴 변 ≤ 1280

    py tools/claude_portal/check_previews.py [--store <CLAUDE_STORE_DIR>]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

EXT = {"font": ("png",), "sfx": ("mp3",), "bgm": ("mp3",), "template": ("png", "jpg"), "meme": ("jpg",),
       "voice": ("mp3",), "result": ("mp4",)}
MAX_KBPS = 72


def _probe(f: Path) -> dict:
    r = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries",
                        "format=duration,bit_rate:stream=codec_type,channels,width,height,bit_rate", "-of", "json", str(f)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout or "{}")
    except ValueError:
        return {}


def _audio(f, lo, hi):
    d = _probe(f)
    errs = []
    fmt = d.get("format") or {}
    a = next((s for s in d.get("streams") or [] if s.get("codec_type") == "audio"), None)
    if not a:
        return ["소리 줄 없음"]
    dur = float(fmt.get("duration") or 0)
    if not lo <= dur <= hi:
        errs.append(f"길이 {dur:.2f}초(기준 {lo}~{hi})")
    br = int(a.get("bit_rate") or fmt.get("bit_rate") or 0)
    if br > MAX_KBPS * 1000:
        errs.append(f"비트레이트 {br // 1000}kbps(기준 ≤{MAX_KBPS})")
    if int(a.get("channels") or 0) != 1:
        errs.append(f"채널 {a.get('channels')}(기준 mono)")
    return errs


def check_file(kind, f: Path, blob_dir: Path) -> list:
    errs = []
    side = f.with_suffix(".json")
    meta = {}
    try:
        meta = json.loads(side.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        errs.append("사이드카(made_by) 없음")
    if meta and meta.get("made_by") != "preview v1":
        errs.append(f"made_by {meta.get('made_by')!r}")
    if kind in ("sfx", "bgm", "voice"):
        errs += _audio(f, *{"sfx": (1.0, 1.6), "bgm": (14.5, 15.5), "voice": (0.3, 3.2)}[kind])
    elif kind in ("font", "template", "meme"):
        from PIL import Image
        try:
            im = Image.open(f)
            im.load()
        except OSError:
            return errs + ["그림을 못 연다"]
        if kind == "font" and (im.format != "PNG" or im.width != 720):
            errs.append(f"{im.format} 폭 {im.width}(기준 PNG 720)")
        if kind == "template":
            if im.width != 360:
                errs.append(f"폭 {im.width}(기준 360)")
            src = blob_dir / str(meta.get("src_sha256") or "-")
            if src.is_file():
                from PIL import ImageChops, ImageStat
                plain = Image.open(src).convert("RGBA").resize(im.size, Image.LANCZOS)
                diff = ImageStat.Stat(ImageChops.difference(plain, im.convert("RGBA"))).mean
                if sum(diff) / len(diff) < 1.0:
                    errs.append("워터마크가 안 보인다(원본 축소본과 같다)")
        if kind == "meme":
            if im.format != "JPEG":
                errs.append(f"{im.format}(기준 JPEG)")
            if int((meta.get("spec") or {}).get("cell") or 999) > 240 or int((meta.get("spec") or {}).get("quality") or 100) > 50:
                errs.append("칸 > 240 또는 품질 > 50")
    elif kind == "result":
        v = next((s for s in _probe(f).get("streams") or [] if s.get("codec_type") == "video"), None)
        if not v:
            errs.append("영상 줄 없음")
        elif max(int(v.get("width") or 0), int(v.get("height") or 0)) > 1280:
            errs.append(f"{v.get('width')}x{v.get('height')}(기준 긴 변 ≤1280)")
    return errs


def run(store_dir: Path) -> tuple:
    pv = store_dir / "preview"
    total, bad = {}, []
    for kind, exts in EXT.items():
        d = pv / kind
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if f.suffix.lstrip(".") not in exts:
                continue
            total[kind] = total.get(kind, 0) + 1
            e = check_file(kind, f, store_dir / "assets")
            if e:
                bad.append((f"{kind}/{f.name}", e))
    return total, bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="")
    a = ap.parse_args(argv)
    if a.store:
        os.environ["CLAUDE_STORE_DIR"] = a.store
    from shopping_shorts import claude_portal as cp
    total, bad = run(cp.store_dir())
    print("검사:", total or "견본 0개", f"| 기준 밖 {len(bad)}개")
    for name, e in bad[:50]:
        print("  ✗", name, "—", "; ".join(e))
    if not total:
        print("견본이 하나도 없다 — build_previews 를 먼저 돌려라")
        return 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
