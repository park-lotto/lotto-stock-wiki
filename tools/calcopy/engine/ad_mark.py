# -*- coding: utf-8 -*-
"""완성본 오른쪽 위 '광고' 표시 — 판단 주인 한 곳(사장님 10-22 "모든 렌더 시 오른쪽 상단에 광고 표시 하나, 너무 크지 않게").
렌더러(render_bench·render_itssum·render_jaemi …)는 final.mp4 를 만든 뒤 apply_inplace(final) 하나만 부른다(각자 그리지 않는다).
글자는 그림(PNG)으로 만들어 덮는다 — ffmpeg drawtext 는 한글 경로에서 죽은 적이 있다(메모리 볼케이노 작업폴더 한글 금지).
크기 = 화면 너비 기준(1080 → 글자 30px · 상자 약 78×46 · 가장자리 24px). 소리는 그대로(복사)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FONT = ROOT / "shopping_shorts/static/fonts/Pretendard-Bold.otf"
TEXT = "광고"
FONT_FRAC = 0.028      # 글자 크기 = 화면 너비 × 이 값
MARGIN_FRAC = 0.022    # 오른쪽·위 가장자리
MARK = "ad_mark:v1"    # 완성본 표식(comment) — 두 번 덮지 않는다


def _probe(p: Path) -> tuple[int, int, str]:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format_tags=comment",
                        "-of", "json", str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    j = json.loads(r.stdout or "{}")
    s = (j.get("streams") or [{}])[0]
    return int(s.get("width") or 0), int(s.get("height") or 0), str(((j.get("format") or {}).get("tags") or {}).get("comment") or "")


def badge(width: int, dst: Path) -> tuple[Path, int]:
    """'광고' 상자 그림(반투명 검정 둥근 상자 + 흰 글자) → (파일, 가장자리 px)."""
    from PIL import Image, ImageDraw, ImageFont
    px = max(18, round(width * FONT_FRAC))
    f = ImageFont.truetype(str(FONT), px)
    l, t, r, b = f.getbbox(TEXT)
    pad_x, pad_y = round(px * 0.45), round(px * 0.28)
    w, h = (r - l) + pad_x * 2, (b - t) + pad_y * 2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=round(h * 0.25), fill=(0, 0, 0, 150))
    d.text((pad_x - l, pad_y - t), TEXT, font=f, fill=(255, 255, 255, 235))
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst)
    return dst, max(8, round(width * MARGIN_FRAC))


def apply_inplace(final: Path, log=print) -> dict:
    """final.mp4 에 광고 표시를 덮어 같은 이름으로(이미 표식이 있으면 그대로). 반환 = {applied, size}."""
    final = Path(final)
    w, h, comment = _probe(final)
    if MARK in comment:
        return {"applied": False, "why": "이미 있음"}
    png, m = badge(w, final.with_name("_ad_mark.png"))
    tmp = final.with_name(final.stem + "_ad.mp4")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(final), "-i", str(png),
                        "-filter_complex", f"[0:v][1:v]overlay=x=W-w-{m}:y={m}:format=auto,format=yuv420p[v]",
                        "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-c:a", "copy",
                        "-metadata", f"comment={(comment + ' ' if comment else '') + MARK}", "-movflags", "+faststart", str(tmp)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not tmp.exists():
        raise RuntimeError("광고 표시 덮기 실패: " + (r.stderr or "")[-300:])
    shutil.move(str(tmp), str(final))
    png.unlink(missing_ok=True)
    log(f"[ad_mark] 오른쪽 위 '광고' 표시 {w}x{h}")
    return {"applied": True, "size": [w, h]}
