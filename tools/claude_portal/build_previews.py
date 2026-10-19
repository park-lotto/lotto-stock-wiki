# -*- coding: utf-8 -*-
"""클로드형 견본 굽기(관제 234, 설계 §8-1) — 페이지가 보여 주는 것은 견본뿐이다. 원본을 대체할 수 없게 미리 구워 둔다.

규격(§8-1):
  글꼴     PNG 720px 폭, 고정 문구 "숏템메이커 1234 가나다" — 글꼴 파일은 안 보낸다
  효과음   팩당 대표 1개(오프너), 1.4초 + 끝 0.3초 페이드 + 0.1초 서버 톤 = 1.5초, 64kbps mono mp3
  BGM     15초(곡 30% 지점), 64kbps mono, 페이드 인/아웃, 5초마다 워터마크 톤
          ★설계는 "TTS 보이스 워터마크"지만 서버 TTS 키 없이 굽게 하려고 톤 비프로 대신한다(출력에 적는다)
  목소리   voice_samples 앞 3초, 64kbps mono, 끝 페이드
  템플릿   360px 폭 축소 + 대각선 반투명 "SHORTEM PREVIEW" (투명 바탕 유지 PNG)
  짤       240px 긴 변 썸네일, 대각선 워터마크, JPEG q50 스프라이트(한 장 48칸) — 원본이 있는 곳에서만
  통과작   720p(긴 변 1280) + 워터마크 mp4(스트리밍 전용)
각 견본 옆에 <id>.json 사이드카: made_by "preview v1"·원본 sha256·규격. 재료는 claude_assets 의 원본 blob(assets/<sha256>) — 경로 하나.

    py tools/claude_portal/build_previews.py --db <reference.db> [--store <CLAUDE_STORE_DIR>] [--kinds font,sfx,...] [--force]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SS = ROOT / "shopping_shorts"

MADE_BY = "preview v1"
FONT_TEXT = "숏템메이커 1234 가나다"
WM_TEXT = "SHORTEM PREVIEW"
WM_FONT = SS / "static" / "fonts" / "NotoSansKR-Bold.otf"
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


def _sidecar(dst: Path, kind, pid, src_sha, spec):
    dst.with_suffix(".json").write_text(json.dumps({"made_by": MADE_BY, "kind": kind, "id": pid, "src_sha256": src_sha,
                                                    "spec": spec}, ensure_ascii=False, indent=1), encoding="utf-8")


def _ff(args):
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[-400:])


def _wm(img, alpha=70, step=None):
    """대각선 반투명 워터마크 — 이미지 전체에 반복."""
    from PIL import Image, ImageDraw, ImageFont
    w, h = img.size
    size = max(12, int(min(w, h) / 9))
    font = ImageFont.truetype(str(WM_FONT), size)
    layer = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    step = step or size * 4
    xstep = int(font.getlength(WM_TEXT) + size * 2)
    for y in range(0, h * 2, step):
        for x in range(0, w * 2, xstep):
            d.text((x, y), WM_TEXT, font=font, fill=(255, 255, 255, alpha), stroke_width=1, stroke_fill=(0, 0, 0, alpha))
    layer = layer.rotate(30, resample=Image.BICUBIC).crop((w // 2, h // 2, w // 2 + w, h // 2 + h))
    base = img.convert("RGBA")
    return Image.alpha_composite(base, layer)


FONT_TEXT_LATIN = "Shortem Maker 1234 ABC"


def _has_hangul(src: Path) -> bool:
    """한글 글자가 없는 글꼴(영문 전용)은 한글 문구를 네모로 그린다 → 영문 문구로 보여 준다."""
    try:
        from fontTools.ttLib import TTFont
        cmap = TTFont(str(src), lazy=True).getBestCmap() or {}
        return all(ord(ch) in cmap for ch in "숏템가나다")
    except Exception:      # noqa: BLE001 — 못 읽으면 한글 문구로(종전대로) 그린다
        return True


def font_preview(src: Path, dst: Path):
    from PIL import Image, ImageDraw, ImageFont
    W, size = 720, 64
    text = FONT_TEXT if _has_hangul(src) else FONT_TEXT_LATIN
    font = ImageFont.truetype(str(src), size)
    while font.getlength(text) > W - 40 and size > 20:
        size -= 2
        font = ImageFont.truetype(str(src), size)
    img = Image.new("RGB", (W, 120), (255, 255, 255))
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), text, font=font)
    d.text(((W - (bb[2] - bb[0])) / 2 - bb[0], (120 - (bb[3] - bb[1])) / 2 - bb[1]), text, font=font, fill=(20, 20, 24))
    img.save(dst, "PNG", optimize=True)
    return {"width": W, "text": text}


def sfx_preview(src: Path, dst: Path):
    fc = ("[0:a]aformat=sample_rates=44100:channel_layouts=mono,apad=whole_dur=1.4,atrim=0:1.4,asetpts=PTS-STARTPTS,"
          "afade=t=out:st=1.1:d=0.3[a];sine=f=1200:d=0.1:sample_rate=44100,volume=0.25,aformat=channel_layouts=mono[b];"
          "[a][b]concat=n=2:v=0:a=1[o]")
    _ff(["-i", str(src), "-filter_complex", fc, "-map", "[o]", "-ac", "1", "-b:a", "64k", "-ar", "44100", str(dst)])
    return {"seconds": 1.5, "kbps": 64, "channels": 1, "tone_end_s": 0.1, "fade_s": 0.3}


def _dur(src: Path) -> float:
    r = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def bgm_preview(src: Path, dst: Path):
    d = _dur(src)
    off = round(max(0.0, min(d * 0.3, d - 15)), 2) if d > 15 else 0.0
    beep = "aevalsrc=exprs='0.22*sin(2*PI*880*t)*lt(mod(t\\,5)-2.4\\,0.3)*gt(mod(t\\,5)-2.4\\,0)':d=15:s=44100,aformat=channel_layouts=mono[b]"
    fc = (f"[0:a]aformat=sample_rates=44100:channel_layouts=mono,apad=whole_dur=15,atrim=0:15,asetpts=PTS-STARTPTS,"
          f"afade=t=in:d=0.5,afade=t=out:st=14:d=1,volume=0.8[a];{beep};[a][b]amix=inputs=2:normalize=0:duration=first[o]")
    _ff(["-ss", str(off), "-i", str(src), "-filter_complex", fc, "-map", "[o]", "-ac", "1", "-b:a", "64k", "-ar", "44100", "-t", "15", str(dst)])
    return {"seconds": 15, "kbps": 64, "channels": 1, "from_s": off, "watermark": "tone 880Hz 0.3s every 5s (TTS 대신)"}


def voice_preview(src: Path, dst: Path):
    _ff(["-i", str(src), "-af", "aformat=channel_layouts=mono,atrim=0:3,asetpts=PTS-STARTPTS,afade=t=out:st=2.6:d=0.4",
         "-ac", "1", "-b:a", "64k", "-ar", "44100", "-t", "3", str(dst)])
    return {"seconds": 3, "kbps": 64, "channels": 1}


def template_preview(src: Path, dst: Path):
    from PIL import Image
    im = Image.open(src).convert("RGBA")
    w = 360
    im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    _wm(im, alpha=90).save(dst, "PNG", optimize=True)
    return {"width": w, "watermark": WM_TEXT}


def meme_sprites(rows, out_dir: Path, blob_dir: Path):
    """감정(grp)별 스프라이트 — 칸 240px 긴 변, 48칸, 워터마크, JPEG q50."""
    from PIL import Image
    made = []
    groups = {}
    for r in rows:
        groups.setdefault(r["grp"], []).append(r)
    for grp, items in groups.items():
        for k in range(0, len(items), 48):
            chunk = items[k:k + 48]
            cells = []
            with tempfile.TemporaryDirectory() as td:
                for i, r in enumerate(chunk):
                    png = Path(td) / f"{i}.png"
                    try:
                        _ff(["-ss", "0.5", "-i", str(blob_dir / r["sha256"]), "-frames:v", "1",
                             "-vf", "scale='if(gt(iw,ih),240,-2)':'if(gt(iw,ih),-2,240)'", str(png)])
                        cells.append(Image.open(png).convert("RGB"))
                    except RuntimeError:
                        try:
                            im = Image.open(blob_dir / r["sha256"]).convert("RGB")
                            im.thumbnail((240, 240))
                            cells.append(im)
                        except OSError:
                            continue
            if not cells:
                continue
            cols = 8
            rows_n = (len(cells) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * 240, rows_n * 240), (30, 30, 30))
            for i, im in enumerate(cells):
                sheet.paste(im, ((i % cols) * 240 + (240 - im.width) // 2, (i // cols) * 240 + (240 - im.height) // 2))
            pid = f"sprite_{grp}_{k // 48 + 1}"
            dst = out_dir / f"{pid}.jpg"
            _wm(sheet, alpha=80).convert("RGB").save(dst, "JPEG", quality=50)
            _sidecar(dst, "meme", pid, None, {"cell": 240, "quality": 50, "cells": len(cells), "watermark": WM_TEXT})
            made.append(pid)
    return made


def result_preview(src: Path, dst: Path, td: Path):
    font = td / "wm.otf"
    shutil.copy(WM_FONT, font)
    vf = ("scale='if(gt(iw,ih),1280,-2)':'if(gt(iw,ih),-2,1280)',"
          "drawtext=fontfile=wm.otf:text='SHORTEM PREVIEW':fontcolor=white@0.45:fontsize=h/22:x=(w-tw)/2:y=h*0.18,"
          "drawtext=fontfile=wm.otf:text='SHORTEM PREVIEW':fontcolor=white@0.45:fontsize=h/22:x=(w-tw)/2:y=h*0.72")
    r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vf", vf, "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dst)],
                       cwd=str(td), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[-400:])
    return {"long_edge": 1280, "watermark": WM_TEXT, "crf": 30}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--store", default="")
    ap.add_argument("--kinds", default="font,sfx,bgm,template,voice,meme,result")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.store:
        os.environ["CLAUDE_STORE_DIR"] = a.store
    from shopping_shorts import claude_portal as cp
    from shopping_shorts.store import Store
    st = Store(a.db)
    cp.ensure_schema(st)
    kinds = [k.strip() for k in a.kinds.split(",") if k.strip()]
    pv = cp.store_dir() / "preview"
    blob_dir = cp.store_dir() / "assets"
    made, fail, skip = {}, [], {}
    notes = []

    def _do(kind, pid, src, ext, fn, src_sha):
        d = pv / kind
        d.mkdir(parents=True, exist_ok=True)
        dst = d / f"{pid}.{ext}"
        if dst.exists() and dst.with_suffix(".json").exists() and not a.force:
            skip[kind] = skip.get(kind, 0) + 1
            return
        try:
            spec = fn(src, dst)
            _sidecar(dst, kind, pid, src_sha, spec)
            made[kind] = made.get(kind, 0) + 1
        except Exception as e:      # noqa: BLE001 — 한 견본 실패가 나머지를 막지 않게. 실패는 목록으로 출력·종료코드 1
            fail.append(f"{kind}:{pid} — {type(e).__name__}: {str(e)[:160]}")

    rows = cp._assets(st)
    if "font" in kinds:
        for r in [r for r in rows if r["kind"] == "font"]:
            _do("font", r["preview_id"], blob_dir / r["sha256"], "png", font_preview, r["sha256"])
    if "sfx" in kinds:
        packs = {}
        for r in [r for r in rows if r["kind"] == "sfx"]:
            packs.setdefault(r["grp"], []).append(r)
        for grp, items in packs.items():
            rep = next((r for r in items if r["name"].startswith("opener")), items[0])   # 대표 = 오프너(팩의 첫 소리)
            _do("sfx", grp, blob_dir / rep["sha256"], "mp3", sfx_preview, rep["sha256"])
    if "bgm" in kinds:
        for r in [r for r in rows if r["kind"] == "bgm"]:
            _do("bgm", r["preview_id"], blob_dir / r["sha256"], "mp3", bgm_preview, r["sha256"])
        notes.append("BGM 워터마크 = 톤 비프(880Hz 0.3초, 5초마다) — 설계의 TTS 보이스 워터마크는 서버 TTS 키 없이 못 구워 톤으로 대체")
    if "template" in kinds:
        for r in [r for r in rows if r["kind"] == "template"]:
            _do("template", r["preview_id"], blob_dir / r["sha256"], "png", template_preview, r["sha256"])
    if "voice" in kinds:
        for v in cp._voices():
            f = SS / "assets" / "voice_samples" / str(v.get("sample_file") or "")
            if v.get("preset_id") and f.is_file():
                _do("voice", v["preset_id"], f, "mp3", voice_preview, None)
    if "meme" in kinds:
        mrows = [r for r in rows if r["kind"] == "meme"]
        if mrows:
            d = pv / "meme"
            d.mkdir(parents=True, exist_ok=True)
            made["meme"] = len(meme_sprites(mrows, d, blob_dir))
        else:
            notes.append("짤: claude_assets 에 짤 원본이 0개 — 스프라이트를 못 구웠다(서버에서 sync_assets 뒤 다시 돌린다)")
    if "result" in kinds:
        from shopping_shorts import calcopy_board
        led = calcopy_board.preset_home(cp.channel_root())
        with tempfile.TemporaryDirectory() as td:
            for r in [r for r in led.get("results") or [] if r.get("state") == "통과"]:
                src = Path(str(r.get("path") or ""))
                if not src.is_file():
                    skip["result_없음"] = skip.get("result_없음", 0) + 1
                    continue
                _do("result", str(r["n"]), src, "mp4", lambda s, d_, _td=Path(td): result_preview(s, d_, _td), None)
    print("구움:", made or "0", "| 이미 있음:", skip or "0", "| 실패:", len(fail))
    for f in fail:
        print("  실패", f)
    for n in notes:
        print("  참고", n)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
