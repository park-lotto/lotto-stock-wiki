# -*- coding: utf-8 -*-
"""스냅봤니형(찰칵모먼트 임시 브랜드) 1편 — 원 촬영자 특崮斯 빌리빌리 BV1o67H6KEud 'Black or White' (2026-11-06).
판 값 = channel/snapbwatni/줄판독/d-jFF79JU2g.json 실측(창 y526~1920 · 제목 #000000/#EA23A2 · 나레 BMJUA 69px 흰+검 7px ·
등장 곡선 글리치 모임 0.2초 · 퇴장 1프레임 · 해설상자 노랑 #FCFF75/검 상자 -4° ±0.75° 0.5초 까딱 · 줄 끝 이모지).
소리 = 원본 소리 그대로(벤치 3편 TTS 0 — Jev q_voice A 확신 1.00). 인코딩 = engine.encoder.venc().
    PYTHONUTF8=1 py channel/snapbwatni/make1/make.py
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import encoder  # noqa: E402

SRC = Path(r"C:\숏템_칼카피\snapbwatni\origin\bili_BV1o67H6KEud.mp4")
OUT = Path(r"C:\숏템_칼카피\snapbwatni\out\chalkak_01_blackorwhite_v2.mp4")
W, H, FPS = 1080, 1920, 30
WIN_Y = 526                     # 창 위 끝(실측)
WIN_H = H - WIN_Y               # 1394
CROP_Y = 380                    # 원본 1080x1920 에서 창 높이만큼 — 머리~발 + 빌리빌리 워터마크(y<110) 잘림
FONT_T = str(ROOT / "out/fonts_thumb/Pretendard-Black.otf")
FONT_C = str(ROOT / "shopping_shorts/static/fonts/BMJUA.ttf")
FONT_E = r"C:\Windows\Fonts\seguiemj.ttf"

TITLE = [("교복 입고 또 시작된", "#000000"), ("중학생 MJ 블랙오어화이트", "#EA23A2")]
# (시작, 끝, 글, 줄끝 이모지)
LINES = [   # 2026-11-06 v2: 0.5초 시트(C:/t/bw/hs_*.jpg)로 동작을 보고 줄 시작 = 동작 시작 순간(움직임 크기 C:/t/bw/mot.npy)
    (0.20, 1.90, "친구들 앞에서 MJ 춤 췄던 그 중학생", ""),
    (1.90, 3.90, "이번엔 Black or White로 돌아옴", "✨"),
    (3.90, 5.40, "시작하자마자 두 팔 번쩍", "🙌"),
    (5.40, 7.90, "몸 던지는 거 보소 ㄷㄷ", ""),
    (7.90, 9.50, "손 쫙 펴고 하늘 보는 표정까지", ""),
    (9.50, 12.40, "발 차면서 옆으로 쭉쭉", ""),
    (12.40, 15.00, "주먹 들고 얼굴 가리는 포즈", ""),
    (15.00, 17.00, "손목 털면서 리듬 타는 거", ""),
    (17.00, 19.30, "어깨 튕기는 타이밍 정확함", ""),
    (19.30, 21.00, "가방 멘 채로 한 바퀴", "🎒"),
    (21.00, 25.00, "주머니에 손 넣고 잠깐 여유", ""),
    (25.00, 28.80, "웃으면서 추는 게 찐 행복", "😆"),
    (28.80, 30.00, "발차기 높이 실화냐", "🔥"),
    (30.00, 32.80, "허리 꺾는 MJ 동작까지", ""),
    (32.80, 35.00, "손바닥 쫙 펴고 흔들흔들", ""),
    (35.00, 38.30, "팔 벌리고 신난 거 다 보임", ""),
    (38.30, 40.00, "가방 휙 돌면서 턴", ""),
    (40.00, 42.00, "손 들고 인사하듯 흔들", "👋"),
    (42.00, 45.00, "벨트 잡고 들썩 MJ 그 자체", ""),
    (45.00, 48.30, "손가락 포인트도 안 놓침", ""),
    (48.30, 52.00, "몸 기울여서 팔 쭉쭉", ""),
    (52.00, 55.80, "뒤돌았다가 바로 정면 착지", ""),
    (55.80, 57.40, "마지막은 하늘 찌르는 포즈", "👆"),
    (57.40, 59.60, "다음 곡도 보고 싶으면 좋아요", "❤️"),
]
BOXES = [(13.40, 15.60, "이 포즈 소름 ㄷㄷ"), (38.30, 40.40, "가방 턴 뭐임 ㅋㅋ"), (55.80, 58.00, "엔딩 포즈 미쳤다;;")]
ENTER = [[0, 40, 3, 15], [.033, 78, 55, 3], [.067, 90, 80, 1], [.1, 95, 89, 0], [.133, 98, 92, 0], [.2, 100, 95, 0]]
CAP_SIZE, CAP_OUT, CAP_CY, CAP_MAXW = 80, 7, 1366, 980


def emoji_img(ch: str, px: int) -> Image.Image:
    f = ImageFont.truetype(FONT_E, 109)          # 컬러 이모지는 109 고정 크기에서만 그려진다
    im = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 5), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox() or (0, 0, 140, 140))
    return im.resize((int(im.width * px / im.height), px), Image.LANCZOS)


def caption_img(text: str, emo: str) -> Image.Image:
    size = CAP_SIZE
    while True:
        f = ImageFont.truetype(FONT_C, size)
        tw = int(f.getlength(text))
        ew = int(size * 0.95) + 10 if emo else 0
        if tw + ew <= CAP_MAXW or size <= 50:
            break
        size -= 2
    pad = CAP_OUT + 6
    im = Image.new("RGBA", (tw + ew + pad * 2, size + pad * 2 + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((pad, pad), text, font=f, fill="#FFFFFF", stroke_width=CAP_OUT, stroke_fill="#000000")
    if emo:
        e = emoji_img(emo, int(size * 0.95))
        im.alpha_composite(e, (pad + tw + 10, pad + (size - e.height) // 2 + 4))
    return im


def box_img(text: str) -> Image.Image:
    f = ImageFont.truetype(FONT_C, 54)
    tw = int(f.getlength(text))
    im = Image.new("RGBA", (tw + 48, 54 + 34), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=10, fill=(0, 0, 0, 235))
    d.text((24, 12), text, font=f, fill="#FCFF75")
    big = Image.new("RGBA", (im.width + 80, im.height + 80), (0, 0, 0, 0))
    glow = Image.new("RGBA", big.size, (0, 0, 0, 0))     # 뒤 노랑 가로 빛줄기(실측 '노랑 가로 빛줄기')
    ImageDraw.Draw(glow).rectangle((0, big.height // 2 - 6, big.width, big.height // 2 + 6), fill=(252, 255, 117, 110))
    big.alpha_composite(glow)
    big.alpha_composite(im, (40, 40))
    return big


def logo_img() -> Image.Image:
    im = Image.new("RGBA", (420, 130), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((4, 4, 122, 122), fill="#FF7A1A", outline="#111111", width=5)          # 우리 로고: 주황 원 + 셔터 모양
    for k in range(6):
        a = math.radians(k * 60 + 15)
        d.line((63 + 22 * math.cos(a), 63 + 22 * math.sin(a), 63 + 46 * math.cos(a + 0.9), 63 + 46 * math.sin(a + 0.9)), fill="#111111", width=6)
    d.ellipse((45, 45, 81, 81), fill="#FFFFFF", outline="#111111", width=4)
    f1 = ImageFont.truetype(FONT_T, 40)
    f2 = ImageFont.truetype(FONT_C, 36)
    d.text((138, 18), "Chalkak!", font=f1, fill="#111111")
    d.text((138, 70), "찰칵모먼트", font=f2, fill="#444444")
    return im


def frame_top() -> Image.Image:
    top = Image.new("RGBA", (W, WIN_Y), "#FFFFFF")
    top.alpha_composite(logo_img(), (110, 190))
    d = ImageDraw.Draw(top)
    for (txt, col), y in zip(TITLE, (342, 424)):
        size = 80
        while ImageFont.truetype(FONT_T, size).getlength(txt) > 940:
            size -= 2
        f = ImageFont.truetype(FONT_T, size)
        d.text(((W - f.getlength(txt)) / 2, y - 8), txt, font=f, fill=col)
    return top


def enter_state(dt: float):
    for k in range(len(ENTER) - 1):
        a, b = ENTER[k], ENTER[k + 1]
        if dt <= b[0]:
            r = (dt - a[0]) / (b[0] - a[0])
            return [a[i] + (b[i] - a[i]) * r for i in (1, 2, 3)]
    return [100, 100, 0]


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(SRC)],
                               capture_output=True, text=True, encoding="utf-8").stdout.strip())
    n = int(dur * FPS)
    top = np.asarray(frame_top().convert("RGB"))
    caps = [caption_img(t, e) for _, _, t, e in LINES]
    boxes = [box_img(t) for _, _, t in BOXES]
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(SRC), "-vf", f"fps={FPS},crop={W}:{WIN_H}:0:{CROP_Y}",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc_cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
               "-i", str(SRC), "-map", "0:v", "-map", "1:a", *encoder.venc(16), "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", str(OUT)]
    enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)
    fsz = W * WIN_H * 3
    for i in range(n):
        raw = dec.stdout.read(fsz)
        if len(raw) < fsz:
            break
        t = i / FPS
        canvas = Image.new("RGBA", (W, H))
        canvas.paste(Image.fromarray(top), (0, 0))
        canvas.paste(Image.fromarray(np.frombuffer(raw, np.uint8).reshape(WIN_H, W, 3)), (0, WIN_Y))
        for (t0, t1, _), im in zip(BOXES, boxes):
            if t0 <= t < t1:
                ang = -4 + 0.75 * math.sin(2 * math.pi * (t - t0) / 0.5)
                r = im.rotate(ang, resample=Image.BICUBIC, expand=True)
                canvas.alpha_composite(r, (40, WIN_Y + 70))
        for (t0, t1, _, _), im in zip(LINES, caps):
            if t0 <= t < t1:
                sx, al, dy = enter_state(t - t0)
                w2 = max(1, int(im.width * sx / 100))
                h2 = im.height if sx > 60 else int(im.height * 0.95)
                c = im.resize((w2, h2), Image.BICUBIC)
                if al < 99:
                    a = np.asarray(c).copy(); a[..., 3] = (a[..., 3] * (al / 100)).astype(np.uint8); c = Image.fromarray(a)
                if sx < 60:          # 첫 프레임 색 번짐(실측: 빨강·청록 갈라짐)
                    rr = Image.new("RGBA", c.size, (255, 40, 40, 0)); rr.putalpha(c.getchannel("A").point(lambda v: v // 2))
                    cc = Image.new("RGBA", c.size, (40, 230, 230, 0)); cc.putalpha(c.getchannel("A").point(lambda v: v // 2))
                    canvas.alpha_composite(rr, ((W - w2) // 2 - 8, int(CAP_CY - h2 / 2 + dy)))
                    canvas.alpha_composite(cc, ((W - w2) // 2 + 8, int(CAP_CY - h2 / 2 + dy)))
                canvas.alpha_composite(c, ((W - w2) // 2, int(CAP_CY - h2 / 2 + dy)))
        enc.stdin.write(canvas.convert("RGB").tobytes())
    enc.stdin.close(); enc.wait(); dec.wait()
    meta = {"src": str(SRC), "origin": "bilibili 特崮斯(uid 1426844633) BV1o67H6KEud", "bench": "스냅봤니 d-jFF79JU2g",
            "rules": "줄판독 d-jFF79JU2g.json 실측값", "voice": "없음(벤치 TTS 0, Jev A 1.00) · 판 voice 칸 = 타입캐스트 진우 tc_632293f759d649937b97f323",
            "encoder": encoder.kind(), "frames": n}
    OUT.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("완성", OUT, enc.returncode)


if __name__ == "__main__":
    main()
