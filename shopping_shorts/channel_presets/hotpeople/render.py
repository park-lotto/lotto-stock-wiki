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


def cover_vf(w=None, h=None):
    """소스 → 덮개 그림(아래 자막 18% 버리고 슬롯을 덮을 만큼 키움, 아직 안 자름). 가로가 슬롯보다 넓다."""
    w, h = w or spec.SLOT_W, h or spec.SLOT_H
    keep = 1 - spec.POLICY_SOURCE_CROP_BOTTOM
    return f"crop=iw:ih*{keep:.3f}:0:0,scale={w}:{h}:force_original_aspect_ratio=increase"


def slot_vf(w=None, h=None, x=None):
    """소스 → 슬롯 크롭 필터 = cover_vf + 슬롯 크기로 자르기. x=None 이면 가운데, 숫자면 그 x(★face_crop_x 가 정한 값만).
    ★렌더·footage 장면 자르기·후보 썸네일·태깅 프레임이 전부 이것을 쓴다 —
    장면을 다른 그림(전체 화면)으로 자르면 크롭 뒤에만 보이는 컷이 자막 안으로 샌다(v002 cut_03 실측)."""
    w, h = w or spec.SLOT_W, h or spec.SLOT_H
    return f"{cover_vf(w, h)},crop={w}:{h}" + (f":{int(x)}" if x is not None else "")


<<<<<<< HEAD
def clip_vf(w=None, h=None, x=None):
    """★소스 → 슬롯 영상의 **픽셀 사슬 전부**(크롭 + 프레임률 변환). 렌더(cut_clip)와 장면 자르기(footage.scene_changes)가
    이것 하나를 쓴다 — 검수 자(review.slot_cuts)가 보는 그림과 장면 자르기가 보는 그림이 같아야 한다.
    ★프레임률은 framerate(섞기)로 바꾼다. 우상혁 v2 실측: 25fps 소스를 fps=30(복제)으로 바꾸면 다섯 장에 한 장이 복제되고,
      움직이는 화면에서 복제 다음 장마다 장면 점수가 0.34~0.39로 튀어(0.2초 간격) 검수가 '자막 안 컷' 6개·컷 26개로 셌다.
      화면도 0.2초마다 끊겨 보인다. 섞기로 바꾸면 같은 구간 최대 0.244·0.12(컷 아님)."""
    return f"{slot_vf(w, h, x)},setsar=1,framerate=fps={spec.FPS}"


_COVER_W = {}


def crop_x(src, face_cx, w=None, h=None):
    """★자르기 창 x — 장면 자르기(절반 크기)·태깅(원래 크기)·렌더(원래 크기)가 전부 이것으로 정한다.
    덮개 폭은 그 소스·그 크기의 실제 덮개 그림에서 잰다(ffmpeg 반올림을 다시 계산하지 않는다)."""
    w, h = w or spec.SLOT_W, h or spec.SLOT_H
    key = (os.path.abspath(src), w, h)
    if key not in _COVER_W:
        _COVER_W[key] = cover_frame(src, 0.0, w, h).shape[1]
    return face_crop_x(_COVER_W[key], w, face_cx)


=======
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
def face_crop_x(cover_w, slot_w, face_cx):
    """★칼카피 규칙 9 — 인물 중심 크롭의 **유일한** 판단. 덮개 그림(폭 cover_w)에서 슬롯(폭 slot_w)을 자를 x.
    얼굴 중심(face_cx, 덮개 폭 대비 0~1)이 슬롯 가운데 오게 옮기고 덮개 밖으로 안 나가게 가둔다. 얼굴 없으면 가운데.
    원본 9편 얼굴 중심 편차 중앙 0.052(최대 0.13) vs v3 0.15(가운데 크롭) — 기준표 §19."""
    room = max(0, int(cover_w) - int(slot_w))
    if face_cx is None:
        return room // 2                       # ffmpeg crop 기본 x=(iw-ow)/2 와 같다
    return int(min(max(round(face_cx * cover_w - slot_w / 2), 0), room))


def cover_frame(src, t, w=None, h=None):
    """소스 t초 덮개 그림 한 장(BGR). 태깅이 쓰는 그림 = 렌더가 자르는 그림(같은 cover_vf)."""
    import numpy as np
    w, h = w or spec.SLOT_W, h or spec.SLOT_H
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", "-vf", cover_vf(w, h),
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, timeout=120)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"render.cover_frame: {os.path.basename(src)} {t:.2f}s 프레임 실패 — {r.stderr[-200:]!r}")
    import cv2
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def slot_from_cover(cover, x, w=None, h=None):
    """덮개 그림 → 슬롯(ffmpeg crop=w:h:x 와 같은 자리: y 는 가운데)."""
    w, h = w or spec.SLOT_W, h or spec.SLOT_H
    H = cover.shape[0]
    y = max(0, (H - h) // 2)
    return cover[y:y + h, x:x + w]


<<<<<<< HEAD
def clip_frames(sec):
    """★자막 한 컷의 프레임 수 — 유일한 판단. 내림(장면 끝을 넘지 않게, footage.fits 는 sub_seconds 로 검사했다).
    예전엔 -t sec 로 ffmpeg 가 반올림 → 컷마다 +0~0.017초가 쌓여 우상혁 v2에서 실제 경계가 계획보다 0.117초 늦었고,
    review.inner_cuts(계획 경계 기준)가 진짜 경계 3개를 "자막 안 컷"으로 셌다."""
    import math
    return max(1, math.floor(sec * spec.FPS + 1e-6))


=======
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
def cut_clip(bg_png, sub_png, src, start, sec, out_mp4, crop_x=None):
    # setpts=PTS-STARTPTS: -ss 뒤 영상 첫 pts가 0이 아니면 overlay 첫 프레임이 빈 흰 슬롯이 된다
    # (v3 1차 실측: cut_05·cut_10 첫 프레임 평균 248(흰 바탕) → 자막 경계 12곳에서 컷이 두 번 잡혀 컷 수 37)
    # crop_x: footage 태깅이 face_crop_x 로 정한 값(없으면 가운데)
<<<<<<< HEAD
    f = (f"[1:v]setpts=PTS-STARTPTS,{clip_vf(x=crop_x)},"
         f"tpad=stop_mode=clone:stop_duration=4[v];"
=======
    f = (f"[1:v]setpts=PTS-STARTPTS,{slot_vf(x=crop_x)},"
         f"setsar=1,fps={spec.FPS},tpad=stop_mode=clone:stop_duration=4[v];"
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
         f"[0:v][v]overlay={spec.SLOT_X}:{spec.SLOT_Y}[b];[b][2:v]overlay=0:0,format=yuv420p[o]")
    _ff(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(spec.FPS), "-i", bg_png,
         "-ss", f"{start:.2f}", "-i", src, "-loop", "1", "-framerate", str(spec.FPS), "-i", sub_png,
         "-filter_complex", f, "-map", "[o]", "-frames:v", str(clip_frames(sec)), "-r", str(spec.FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an", out_mp4], "cut")


def pick_bgm(seed_text):
    """원본 사용 비율(3:3:2:1)대로, 씨앗 글자로 정해지는 곡 하나 → (경로, 시작초) 또는 None."""
    d = spec.POLICY_BGM_DIR
    have = [(f, st, w) for f, st, w in spec.BGM_TRACKS if d and os.path.isfile(os.path.join(d, f))]
    if not have:
        return None
    rnd = random.Random(seed_text or "")
    f, st, _ = rnd.choices(have, weights=[w for _, _, w in have])[0]
    return os.path.join(d, f), st


def _lufs(argv_in):
    """ffmpeg 입력 인자 → 통합 음량(LUFS). audio.py 와 같은 자(ebur128 마지막 I:)."""
    import re
    r = subprocess.run(["ffmpeg", "-nostats"] + argv_in + ["-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    got = re.findall(r"^\s*I:\s*(-?[\d.]+) LUFS", r.stderr, re.M)
    if not got:
        raise RuntimeError(f"render.bgm: 음량 측정 실패 — {r.stderr[-300:]}")
    return float(got[-1])


def bgm_gain_db(src, start, total):
    """★칼카피 6 — BGM 음량은 **고정 이득 하나**(편 전체 같은 dB)로 BGM_LUFS에 맞춘다.
    원본 7편을 같은 곡·같은 시작점 원곡과 0.25초 단위로 대조하면 이득이 첫 0.25초 뒤로 평평(±0.3dB) —
    페이드인도 음량 자동조절도 없다. 원본 "첫 3초가 2.3 LU 조용"은 **곡 자체의 그 구간 모양**이다.
    예전 loudnorm(동적)은 첫 1.5초를 +1.8~+4.2dB 끌어올리고 본편에서 이득을 흔들었다(std 0.7~1.9dB) → v002 오프닝 +2.2 LU."""
    return round(spec.BGM_LUFS - _lufs(["-ss", f"{start:.2f}", "-t", f"{total:.2f}", "-i", src]), 2)


def _bgm(total, wd, seed_text=""):
    out = os.path.join(wd, "render", "bgm.wav")
    got = pick_bgm(seed_text)
    if got:
        src, start = got
        g = bgm_gain_db(src, start, total)
        # 32비트 실수 wav — 원본도 트루피크가 0을 넘는다(10/10, +0.1~+1.5). 16비트로 쓰면 그 위가 잘린다
        _ff(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", src, "-t", f"{total:.2f}",
             "-af", f"volume={g}dB,afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5",
             "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", out], "bgm")
        return out, f"{os.path.basename(src)}@{start}s"
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
        if c.get("end") is not None and c["start"] + sec > c["end"] + 0.01:
            # ★칼카피 1: 자막 하나 = 장면 하나. 장면이 모자라면 소스의 다음 장면이 자막 안으로 들어온다 — 조용히 넘기지 않는다
            raise RuntimeError(f"render: 자막 {i} {sec}s > 장면 {c['start']}~{c['end']} — footage가 짧은 장면을 골랐다(footage부터)")
        sp = subtitle(g, os.path.join(rd, f"sub_{i:02d}.png"))
        mp = os.path.join(rd, f"cut_{i:02d}.mp4")
<<<<<<< HEAD
        sec = clip_frames(sec) / spec.FPS                 # 계획 = 실제 프레임(검수가 이 경계로 잰다)
        x = crop_x(c["src"], c["face_cx"]) if "face_cx" in c else c.get("crop_x")   # 태깅과 같은 함수로 다시 정한다
        cut_clip(bg, sp, c["src"], c["start"], sec, mp, crop_x=x)
        parts.append(mp); total += sec
        plan.append({"i": i, "sec": sec, "src": os.path.basename(c["src"]), "start": c["start"], "url": c.get("url"),
                     "crop_x": x})
=======
        cut_clip(bg, sp, c["src"], c["start"], sec, mp, crop_x=c.get("crop_x"))
        parts.append(mp); total += sec
        plan.append({"i": i, "sec": sec, "src": os.path.basename(c["src"]), "start": c["start"], "url": c.get("url"),
                     "crop_x": c.get("crop_x")})
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
    lst = os.path.join(rd, "concat.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        fh.writelines(f"file '{os.path.basename(p)}'\n" for p in parts)
    silent = os.path.join(rd, "video.mp4")
    _ff(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], "concat")
    audio, bgm_src = _bgm(total, wd, script.get("person", ""))
    # ★out/final.mp4 는 여기서 안 쓴다 — 내용 관문(review.finalize)을 통과해야만 out/ 으로 나간다(우상혁 v001 사고)
    mp4 = os.path.join(rd, "unchecked.mp4")
    _ff(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", audio, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-shortest", "-movflags", "+faststart", mp4], "mux")
    log(f"[hotpeople.render] {mp4} ({total:.1f}s, 컷 {len(parts)}, BGM {'있음' if bgm_src else '없음(무음)'})")
    return {"mp4": mp4, "total": round(total, 2), "cuts": plan, "bgm": bgm_src}
