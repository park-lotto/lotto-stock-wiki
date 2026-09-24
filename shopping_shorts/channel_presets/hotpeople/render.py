# -*- coding: utf-8 -*-
"""렌더 — 배경판(흰 바탕·로고·헤드라인) + 컷마다 [장면 클립 → 슬롯] + [자막판] → mp4. 나레 없음, BGM만.

그림은 PIL로 좌표를 직접 그린다(브라우저 캡처 금지 — memory `템플릿영상은 브라우저캡처 말고 좌표렌더`).
좌표·색·글꼴은 전부 spec(역분석 실측).
"""
import os
import random
import subprocess

from PIL import Image, ImageDraw, ImageFont

from . import spec
from . import rules


def _font(path, px):
    return ImageFont.truetype(path, px)


def _center_line(d, y, line, font, bolden, color, red_words=(), red_rgb=None, mark=None):
    """한 줄을 가운데 정렬로 그린다. red_words 는 그 부분만 빨강. mark=(rgb,pad_x,pad_y,radius)면 줄 뒤 형광펜."""
    W = spec.CANVAS_W
    l, t, r, b = font.getbbox(line, stroke_width=bolden)
    w = r - l
    x0 = (W - w) // 2 - l
    if mark:
        rgb, px, pt, pb, rad = mark
        d.rounded_rectangle([x0 + l - px, y + t - pt, x0 + r + px, y + b + pb], radius=rad, fill=rgb)
    # 빨강 구간 나누기
    spans, i = [], 0
    while i < len(line):
        hit = next(((i, w_) for w_ in red_words if w_ and line.startswith(w_, i)), None)
        if hit:
            spans.append((line[i:i + len(hit[1])], red_rgb)); i += len(hit[1])
        else:
            if spans and spans[-1][1] is None:
                spans[-1] = (spans[-1][0] + line[i], None)
            else:
                spans.append((line[i], None))
            i += 1
    x = x0
    for txt, col in spans:
        c = col or color
        d.text((x, y), txt, font=font, fill=c, stroke_width=bolden, stroke_fill=c)
        x += font.getlength(txt)
    return b - t


def background(title, out_png):
    """흰 바탕 + 로고(우리 채널) + 헤드라인 2줄. 슬롯 자리는 비워 둔다(클립이 덮는다)."""
    im = Image.new("RGB", (spec.CANVAS_W, spec.CANVAS_H), spec.BG_RGB)
    d = ImageDraw.Draw(im)
    # 로고: 원형 아이콘 + 채널명/핸들 두 줄 (원본 로고·이름은 쓰지 않는다)
    cy = (spec.LOGO_Y0 + spec.LOGO_Y1) // 2
    r = spec.LOGO_ICON // 2
    d.ellipse([spec.LOGO_X, cy - r, spec.LOGO_X + 2 * r, cy + r], fill=spec.POLICY_LOGO_RGB)
    ini = _font(spec.HEAD_FONT, 52)
    ch = spec.POLICY_CHANNEL_NAME[:1]
    l, t, rr, bb = ini.getbbox(ch)
    d.text((spec.LOGO_X + r - (rr - l) // 2 - l, cy - (bb - t) // 2 - t), ch, font=ini, fill="white")
    nf, hf = _font(spec.LOGO_NAME_FONT, 30), _font(spec.LOGO_NAME_FONT, 28)
    tx = spec.LOGO_X + 2 * r + 16
    d.text((tx, cy - 36), spec.POLICY_CHANNEL_NAME, font=nf, fill=(20, 20, 20))
    d.text((tx, cy + 2), spec.POLICY_CHANNEL_HANDLE, font=hf, fill=(20, 20, 20))
    # 헤드라인 2줄 — 강조 줄은 빨강 또는 노랑+검정 테두리
    lines = [title.get("h1", ""), title.get("h2", "")]
    px = spec.HEAD_FONT_PX
    while px > 60 and max(rules.ink_width(x, spec.HEAD_FONT, px, spec.HEAD_BOLDEN_PX) for x in lines) > 1000:
        px -= 4
    f = _font(spec.HEAD_FONT, px)
    hs = [f.getbbox(x, stroke_width=spec.HEAD_BOLDEN_PX) for x in lines]
    gap = 14
    total = sum(b - t for _, t, _, b in hs) + gap
    y = spec.HEADLINE_Y0 + (spec.HEADLINE_Y1 - spec.HEADLINE_Y0 - total) // 2
    for k, (line, (l, t, r_, b)) in enumerate(zip(lines, hs), start=1):
        emph = title.get("emph") == k
        yy = y - t
        if emph and title.get("emph_color") == "yellow":
            w = r_ - l; x = (spec.CANVAS_W - w) // 2 - l
            d.text((x, yy), line, font=f, fill=spec.HEAD_YELLOW_RGB, stroke_width=spec.HEAD_YELLOW_STROKE, stroke_fill=(0, 0, 0))
        else:
            col = spec.HEAD_RED_RGB if emph else spec.HEAD_RGB
            _center_line(d, yy, line, f, spec.HEAD_BOLDEN_PX, col)
        y += (b - t) + gap
    im.save(out_png)
    return out_png


def subtitle(group, out_png):
    """투명 판에 자막 1~2줄(가운데). mark면 줄마다 형광펜, red 단어는 빨강."""
    im = Image.new("RGBA", (spec.CANVAS_W, spec.CANVAS_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = _font(spec.SUB_FONT, spec.SUB_FONT_PX)
    y = spec.SUB_TOP
    mark = (spec.MARK_RGB, spec.MARK_PAD_X, spec.MARK_PAD_TOP, spec.MARK_PAD_BOTTOM, spec.MARK_RADIUS) if group.get("mark") else None
    # 줄 위치는 **잉크 윗선** 기준 — 원본 실측이 잉크 시작 y(1285)와 줄 간격(80)이라서
    ref_t = f.getbbox("가", stroke_width=spec.SUB_BOLDEN_PX)[1]     # 글자마다 윗선이 달라 한글 기준 글자로 고정
    for k, line in enumerate(group.get("lines") or [group.get("text", "")]):
        _center_line(d, y + k * spec.SUB_LINE_PITCH - ref_t, line, f, spec.SUB_BOLDEN_PX, spec.SUB_RGB,
                     group.get("red") or (), spec.RED_RGB, mark)
    im.save(out_png)
    return out_png


def _ff(argv, what):
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f"render.{what}: ffmpeg {r.returncode} — {r.stderr[-400:]}")


def cut_clip(bg_png, sub_png, src, start, sec, out_mp4):
    f = (f"[1:v]scale={spec.SLOT_W}:{spec.SLOT_H}:force_original_aspect_ratio=increase,crop={spec.SLOT_W}:{spec.SLOT_H},"
         f"setsar=1,fps={spec.FPS},tpad=stop_mode=clone:stop_duration=4[v];"
         f"[0:v][v]overlay={spec.SLOT_X}:{spec.SLOT_Y}[b];[b][2:v]overlay=0:0,format=yuv420p[o]")
    _ff(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(spec.FPS), "-i", bg_png,
         "-ss", f"{start:.2f}", "-i", src, "-loop", "1", "-framerate", str(spec.FPS), "-i", sub_png,
         "-filter_complex", f, "-map", "[o]", "-t", f"{sec:.2f}", "-r", str(spec.FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an", out_mp4], "cut")


def _bgm(total, wd):
    d = spec.POLICY_BGM_DIR
    files = sorted(os.path.join(d, x) for x in os.listdir(d) if x.lower().endswith((".mp3", ".wav", ".m4a"))) if d and os.path.isdir(d) else []
    out = os.path.join(wd, "render", "bgm.wav")
    if files:
        src = random.Random(total).choice(files)
        _ff(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", src, "-t", f"{total:.2f}",
             "-af", f"loudnorm=I={spec.POLICY_BGM_LUFS}:TP=-2,afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5",
             "-ar", "48000", "-ac", "2", out], "bgm")
        return out, src
    _ff(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{total:.2f}", out], "silence")
    return out, None


def build(wd, script, footage, log=print):
    """→ {"mp4", "total", "cuts":[{i,sec,src,start,url}], "bgm"}"""
    rd = os.path.join(wd, "render")
    os.makedirs(rd, exist_ok=True)
    bg = background(script["title"], os.path.join(rd, "bg.png"))
    parts, plan, total = [], [], 0.0
    for i, (g, c) in enumerate(zip(script["groups"], footage["cuts"])):
        sec = rules.sub_seconds(g.get("text") or " ".join(g.get("lines") or []))
        sp = subtitle(g, os.path.join(rd, f"sub_{i:02d}.png"))
        mp = os.path.join(rd, f"cut_{i:02d}.mp4")
        cut_clip(bg, sp, c["src"], c["start"], sec, mp)
        parts.append(mp); total += sec
        plan.append({"i": i, "sec": sec, "src": os.path.basename(c["src"]), "start": c["start"], "url": c.get("url")})
    lst = os.path.join(rd, "concat.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        fh.writelines(f"file '{os.path.basename(p)}'\n" for p in parts)
    silent = os.path.join(rd, "video.mp4")
    _ff(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], "concat")
    audio, bgm_src = _bgm(total, wd)
    os.makedirs(os.path.join(wd, "out"), exist_ok=True)
    mp4 = os.path.join(wd, "out", "final.mp4")
    _ff(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", audio, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-shortest", "-movflags", "+faststart", mp4], "mux")
    log(f"[hotpeople.render] {mp4} ({total:.1f}s, 컷 {len(parts)}, BGM {'있음' if bgm_src else '없음(무음)'})")
    return {"mp4": mp4, "total": round(total, 2), "cuts": plan, "bgm": bgm_src}
