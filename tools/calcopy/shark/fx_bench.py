# -*- coding: utf-8 -*-
"""샥탬스토리 벤치(해외쇼츠 8편) 자막 강조색·효과·효과음 실측 — 재는 일만(판단은 caption_style.py·fx.py) (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/shark/fx_bench.py capsheet [vid…]   # 자막 칸(scan 변화점 +0.15초)마다 자막 띠 크롭 시트 + 칸별 색 픽셀 수
    PYTHONUTF8=1 py tools/calcopy/shark/fx_bench.py frames <vid> <t0> <t1> [fps]   # 창 10fps 프레임 시트(효과 모양·움직임 눈 판독)
    PYTHONUTF8=1 py tools/calcopy/shark/fx_bench.py sound [vid…]      # 말 아닌 구간 소리 사건(onset)·BGM 바닥·스펙트럼 그림

결과 = C:/숏템_칼카피/foreignshowshow/fx_bench/ (시트·json). 칸별 낱말 강조 판독 결과(눈)는 channel/foreignshowshow/preset/_hand/emph_read.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

MP4 = Path("C:/숏템_칼카피/foreignshowshow/mp4")
PW = Path("C:/숏템_칼카피/foreignshowshow/preset_work")
OUT = Path("C:/숏템_칼카피/foreignshowshow/fx_bench"); OUT.mkdir(parents=True, exist_ok=True)
IDS = ["QMJtjJz4M6w", "kmQGQNJgSVo", "2jJoIbdciDY", "vbxJ_v132ao", "hZgCO9PEnO8", "mVzrvBpMu3E", "aFqKN8s2cA8", "HI--3fL7nt4"]
# 프리셋 manifest channel_rules.captions.highlight_palette(8편 실측) — 여기선 픽셀 셈에만 쓴다
PAL = {"노랑": (252, 226, 61), "주황": (245, 155, 72), "빨강": (235, 78, 79), "초록": (66, 252, 81),
       "민트": (64, 248, 240), "파랑": (67, 165, 246), "분홍": (242, 98, 146)}


def grab(src, t: float, w=1080, h=1920) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(h, w, 3)


def color_px(band: np.ndarray) -> dict:
    """자막 띠(채움 글자만: 진한 색)에서 팔레트 색별 픽셀 수 + 흰 글자 픽셀 수. 번짐 빛(옅은 색)은 거리 40 밖이라 안 센다."""
    a = band.astype(int)
    out = {"흰": int((a.min(axis=2) > 225).sum())}
    for k, c in PAL.items():
        d = np.abs(a - np.array(c)).sum(axis=2)
        out[k] = int((d < 60).sum())
    return out


def capsheet(ids):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 22)
    caps = json.loads((PW / "caps.json").read_text(encoding="utf-8"))
    stats = {}
    for v in ids:
        items = caps[v]["items"]
        tiles, st = [], []
        for it in items:
            img = grab(MP4 / f"{v}.mp4", it["t"])
            band = img[790:1180]
            px = color_px(band[:, 30:1050])
            st.append({"t": it["t"], "px": px, "lines": len(it["lines"])})
            tl = Image.fromarray(band).resize((540, 195))
            ImageDraw.Draw(tl).text((6, 4), f"{it['t']:.2f}", font=font, fill=(255, 255, 0), stroke_width=2, stroke_fill=(0, 0, 0))
            tiles.append(tl)
        stats[v] = st
        per = 16
        for k in range(0, len(tiles), per):
            ch = tiles[k:k + per]
            sheet = Image.new("RGB", (540 * 2, 195 * ((len(ch) + 1) // 2)), (40, 40, 40))
            for i, tl in enumerate(ch):
                sheet.paste(tl, ((i % 2) * 540, (i // 2) * 195))
            sheet.save(OUT / f"cap_{v}_{k // per}.jpg", quality=88)
        print(v, len(items), "칸")
    f = OUT / "cap_px.json"
    old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    f.write_text(json.dumps({**old, **stats}, ensure_ascii=False), encoding="utf-8")


def frames(vid: str, t0: float, t1: float, fps: float = 10, src=None, tag=""):
    """창(y 434~1486)을 fps 로 뽑아 1/3 크기 시트 — 효과 등장·크기·움직임 판독."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 20)
    src = Path(src) if src else MP4 / f"{vid}.mp4"
    W, H = 360, 351
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t0:.3f}", "-i", str(src), "-t", f"{t1 - t0:.3f}",
                        "-vf", f"fps={fps},crop=1080:1052:0:434,scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, check=True)
    n = len(p.stdout) // (W * H * 3)
    cols = 6
    sheet = Image.new("RGB", (W * cols, H * ((n + cols - 1) // cols)), (30, 30, 30))
    for i in range(n):
        a = np.frombuffer(p.stdout[i * W * H * 3:(i + 1) * W * H * 3], np.uint8).reshape(H, W, 3)
        tl = Image.fromarray(a)
        ImageDraw.Draw(tl).text((4, 2), f"{t0 + i / fps:.2f}", font=font, fill=(255, 255, 0), stroke_width=2, stroke_fill=(0, 0, 0))
        sheet.paste(tl, ((i % cols) * W, (i // cols) * H))
    dst = OUT / f"fr_{tag or vid}_{t0:.1f}_{t1:.1f}.jpg"
    sheet.save(dst, quality=85)
    print(dst)
    return dst


def sound(ids):
    """말 아닌 구간의 소리 사건: 16kHz 모노, 20ms 창 에너지·스펙트럼 중심 → 급등(onset, +9dB 이상)·바닥 크기.
    말 구간 = 원음+나레 둘 다 있으므로 받아쓰기로 못 뺀다 → 사건 시각을 효과 시각과 맞춰 보고, 스펙트럼 그림을 눈으로 본다."""
    from PIL import Image
    res = {}
    for v in ids:
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(MP4 / f"{v}.mp4"), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                           capture_output=True, check=True)
        x = np.frombuffer(r.stdout, np.float32)
        hop = 320
        n = len(x) // hop
        fr = x[:n * hop].reshape(n, hop)
        db = 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-9)
        spec = np.abs(np.fft.rfft(fr * np.hanning(hop), axis=1))
        fq = np.fft.rfftfreq(hop, 1 / 16000)
        cent = (spec * fq).sum(axis=1) / (spec.sum(axis=1) + 1e-9)
        hi = 20 * np.log10(spec[:, fq > 4000].sum(axis=1) + 1e-9)
        on = []
        for i in range(5, n):
            if db[i] - db[i - 5:i].mean() > 9 and db[i] > -35:
                if not on or i * 0.02 - on[-1][0] > 0.25:
                    on.append((round(i * 0.02, 2), round(float(db[i]), 1), int(cent[i])))
        res[v] = {"onsets": on, "floor_p10_db": round(float(np.percentile(db, 10)), 1), "median_db": round(float(np.median(db)), 1)}
        # 스펙트로그램 그림(0~8kHz, 50px/초)
        S = 20 * np.log10(spec.T[::-1] + 1e-6)
        S = np.clip((S + 40) / 60, 0, 1)
        im = Image.fromarray((S * 255).astype(np.uint8)).resize((int(n * 0.02 * 50), 300))
        im.save(OUT / f"spec_{v}.png")
        print(v, "onset", len(on), "바닥 p10", res[v]["floor_p10_db"])
    f = OUT / "sound.json"
    old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    f.write_text(json.dumps({**old, **res}, ensure_ascii=False), encoding="utf-8")


def specev(vid: str, ts: list[float], src=None, tag=""):
    """사건 시각마다 [t-0.5, t+1.5] 스펙트로그램(0~8kHz) 띠를 2열로 — 효과음(가로 줄=음 높이 있는 소리·띠링, 휘는 줄=슬라이드, 넓은 띠=휙) 눈 판독."""
    from PIL import Image, ImageDraw, ImageFont
    src = Path(src) if src else MP4 / f"{vid}.mp4"
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "22050", "-f", "f32le", "-"], capture_output=True, check=True)
    x = np.frombuffer(r.stdout, np.float32); sr, win, hop = 22050, 1024, 110
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 16)
    rows = []
    for t in ts:
        a = max(0, int((t - 0.5) * sr)); seg = x[a:a + int(2.0 * sr)]
        n = (len(seg) - win) // hop
        if n < 10:
            continue
        F = np.array([np.abs(np.fft.rfft(seg[i * hop:i * hop + win] * np.hanning(win))) for i in range(n)]).T[:372]
        S = 20 * np.log10(F + 1e-6); S = np.clip((S - S.max() + 70) / 70, 0, 1)[::-1]
        im = Image.fromarray((S * 255).astype(np.uint8)).convert("RGB").resize((n, 186))
        d = ImageDraw.Draw(im)
        for k in range(5):
            xx = int(k * 0.5 * sr / hop); d.line([(xx, 0), (xx, 186)], fill=(255, 0, 0))
            d.text((xx + 2, 2), f"{t - 0.5 + k * 0.5:.1f}", font=font, fill=(255, 255, 0))
        rows.append(im)
    W = max(i.size[0] for i in rows)
    sh = Image.new("RGB", (W * 2, 186 * ((len(rows) + 1) // 2)))
    for i, im in enumerate(rows):
        sh.paste(im, ((i % 2) * W, (i // 2) * 186))
    dst = OUT / f"specev_{tag or vid}.png"
    sh.save(dst)
    print(dst)
    return dst


def main():
    cmd = sys.argv[1]
    if cmd == "capsheet":
        capsheet(sys.argv[2:] or IDS)
    elif cmd == "frames":
        frames(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]) if len(sys.argv) > 5 else 10)
    elif cmd == "specev":
        specev(sys.argv[2], [float(t) for t in sys.argv[3:]])
    elif cmd == "sound":
        sound(sys.argv[2:] or IDS)


if __name__ == "__main__":
    main()
