# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 키치잇판 — 이 편 전용 렌더(자막 입히기 직전까지) (관제 097, 2026-10-18).

    PYTHONUTF8=1 py channel/kitchit/하이브리드_성시경/render_kitchit.py [--sheet]

왜 전용: 키치잇 틀(검정 바탕·제목 2줄(흰 기울임 + 노랑 박스)·1080 정사각 창 y420·창 왼쪽 위 로고·창 아래 출처 줄)은
엔진 프리셋 렌더(preset_make·hybrid render_*)에 없는 배치라 이 편에서만 그린다. 공용 엔진은 고치지 않는다.
자막은 넣지 않는다(지휘자 지시 10-18: 자막팩에 키치잇 효과를 넣은 뒤 그 길로 입힌다) — 대신 자막표.json 을 쓴다.

판단 주인(이 편 안): 시각 = timeline() 한 곳. 화면 컷·소리·자막표가 전부 timeline 의 결과를 읽는다.
입력: 대본.json(줄·나레 구간·원음 구간·자막 조각) · 재료.json(줄별 컷) · 프리셋 channel/kitchit/preset/*/kitchit_frame.json(틀 숫자)
출력(C:/숏템_칼카피/kitchit/sinramen/render/): base_nocap.mp4 · timeline.json · 자막표.json(편 폴더에도 사본) · sheet_1s.jpg
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DOC = json.loads((HERE / "대본.json").read_text(encoding="utf-8"))
MAT = json.loads((HERE / "재료.json").read_text(encoding="utf-8"))
FRAME = json.loads((ROOT / "channel/kitchit/preset/kitchit_frame.json").read_text(encoding="utf-8"))
SRC = Path(MAT["src_dir"])
OUT = Path("C:/숏템_칼카피/kitchit/sinramen/render")
FONTS = ROOT / "shopping_shorts/static/fonts"
SFX = ROOT / "shopping_shorts/assets/sfx_packs/팩01"
BGM_DIR = ROOT / "shopping_shorts/assets/bgm_lib"
FACE_MODEL = "C:/calcopy_models/face_detection_yunet_2023mar.onnx"
FPS = 30
W, H = 1080, 1920
WIN = FRAME["window"]          # {"x":0,"y":420,"w":1080,"h":1080}


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode:
        raise RuntimeError(" ".join(map(str, cmd))[:300] + "\n" + r.stderr[-1200:])
    return r


def dur_of(p) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip())


# ── 소리 조각 ──────────────────────────────────────────────────────────
def speech_bounds(wav: Path, noise="-38dB") -> tuple[float, float]:
    e = run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", f"silencedetect=noise={noise}:d=0.06", "-f", "null", "-"]).stderr
    d = dur_of(wav)
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    en = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", e)]
    a = en[0] if st and st[0] <= 0.02 and en else 0.0
    b = st[-1] if st and (len(en) < len(st) or en[-1] >= d - 0.02) else d
    return max(0.0, a - 0.03), min(d, b + 0.05)


def make_piece(L: dict, tmp: Path) -> Path:
    """줄 하나의 소리(48k 모노 wav, -16 LUFS). tts = 나레 통 파일에서 문장 구간 → 앞뒤 무음 깎기 → atempo. orig = 원음 구간 그대로."""
    out = tmp / f"a_{L['id']}.wav"
    if L["kind"] == "tts":
        a, b = L["tts_span"]
        raw = tmp / f"raw_{L['id']}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b + 0.15:.3f}", "-i", DOC["narr_file"], "-ac", "1", "-ar", "48000", str(raw)])
        s, e = speech_bounds(raw)
        L["_trim"] = s
        af = f"atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,atempo={DOC['voice']['atempo']},loudnorm=I=-16:TP=-2:LRA=7"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", af, "-ar", "48000", str(out)])
    else:
        a, b = L["span"]
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(SRC / L["src"]), "-vn", "-ac", "1",
             "-af", "afade=t=in:d=0.03,loudnorm=I=-16:TP=-2:LRA=7", "-ar", "48000", str(out)])
    return out


# ── 시각의 주인 ────────────────────────────────────────────────────────
def timeline(tmp: Path) -> dict:
    t, rows = 0.0, []
    for L in DOC["lines"]:
        p = make_piece(L, tmp)
        d = dur_of(p)
        rows.append({"id": L["id"], "kind": L["kind"], "t0": round(t, 3), "t1": round(t + d, 3), "dur": round(d, 3), "wav": str(p),
                     "trim": L.get("_trim", 0.0)})
        t += d + DOC["gap"]
    total = round(t - DOC["gap"] + 0.35, 3)     # 끝 여운 0.35초(키치잇 끝 컷 ~0.3~0.5초 남김)
    # 화면 칸: 줄 i 의 칸 = [t0_i, t0_{i+1}) — 사이 틈은 앞 줄 화면이 채운다
    for i, r in enumerate(rows):
        r["v1"] = rows[i + 1]["t0"] if i + 1 < len(rows) else total
    return {"rows": rows, "total": total}


# ── 화면 ──────────────────────────────────────────────────────────────
_det = None


def face_x(src: Path, ss: float, side: int) -> int:
    global _det
    cap = cv2.VideoCapture(str(src)); cap.set(cv2.CAP_PROP_POS_MSEC, ss * 1000); ok, f = cap.read(); cap.release()
    if not ok:
        return (1920 - side) // 2
    if _det is None:
        _det = cv2.FaceDetectorYN.create(FACE_MODEL, "", (320, 320), 0.6, 0.3, 50)
    h, w = f.shape[:2]; _det.setInputSize((w, h))
    _, faces = _det.detect(f)
    if faces is None or not len(faces):
        return (w - side) // 2
    fx, fy, fw, fh = max(faces, key=lambda z: z[2] * z[3])[:4]
    return int(min(max(fx + fw / 2 - side / 2, 0), w - side))


def scene_cuts(src: Path, a: float, b: float) -> list[float]:
    """원음 구간 안 장면 바뀜(파일 초). 0.35 넘는 변화만."""
    e = run(["ffmpeg", "-hide_banner", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src), "-vf", "select='gt(scene,0.35)',showinfo",
             "-an", "-f", "null", "-"]).stderr
    return [round(a + float(x), 3) for x in re.findall(r"pts_time:([\d.]+)", e) if 0.25 < float(x) < (b - a) - 0.25]


def clip(src: Path, ss: float, dur: float, crop, out: Path, push=0.05):
    if crop == "face":
        side = 835; x = face_x(src, ss + min(dur / 2, 0.5), side); crop = [x, 0, side]
    x, y, s = crop
    n = max(1, round(dur * FPS))
    vf = (f"fps={FPS},crop={s}:{s}:{x}:{y},scale=1080:1080:flags=lanczos,"
          f"zoompan=z='1+{push}*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1080:fps={FPS},setsar=1")
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.3f}", "-i", str(src), "-t", f"{dur + 0.1:.3f}", "-an", "-vf", vf,
         "-frames:v", str(n), "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)])
    return {"crop": crop, "frames": n}


def video_plan(TL: dict) -> list[dict]:
    """줄마다 컷 목록(파일·시작·길이·크롭). 프레임 단위로 반올림해 줄 칸을 정확히 채운다."""
    plan = []
    for r in TL["rows"]:
        L = next(x for x in DOC["lines"] if x["id"] == r["id"])
        f0, f1 = round(r["t0"] * FPS), round(r["v1"] * FPS)
        if L["kind"] == "orig":
            src = SRC / L["src"]; a = L["span"][0]; b = a + (f1 - f0) / FPS
            pts = [a] + scene_cuts(src, a, min(b, L["span"][1])) + [b]
            fs = [f0 + round((p - a) * FPS) for p in pts]; fs[-1] = f1
            for i in range(len(pts) - 1):
                plan.append({"line": r["id"], "src": L["src"], "ss": pts[i], "f0": fs[i], "f1": fs[i + 1], "crop": "face", "push": 0.03,
                             "see": "원음 구간(입 맞음)"})
        else:
            cs = MAT["cuts"][r["id"]]; tw = sum(c["w"] for c in cs); acc = 0.0; prev = f0
            for i, c in enumerate(cs):
                acc += c["w"]; nxt = f1 if i == len(cs) - 1 else f0 + round((f1 - f0) * acc / tw)
                plan.append({"line": r["id"], "src": c["src"], "ss": c["ss"], "f0": prev, "f1": nxt, "crop": c["crop"], "push": 0.06,
                             "see": c["see"], "mark": c.get("mark")})
                prev = nxt
    return plan


def frame_png(path: Path):
    """틀 한 장(검정 바탕 위 제목 2줄·로고·출처) — 창 자리는 투명. 숫자는 프리셋 kitchit_frame.json."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([WIN["x"], WIN["y"], WIN["x"] + WIN["w"] - 1, WIN["y"] + WIN["h"] - 1], fill=(0, 0, 0, 0))
    T1, T2 = FRAME["title1"], FRAME["title2"]
    f1 = ImageFont.truetype(str(FONTS / T1["font_file"]), T1["size"])
    # 1줄 = 흰 기울임: 따로 그려 가로 기울임(shear) 뒤 붙인다
    tw = int(d.textlength(DOC["title"][0], font=f1)) + 80
    lay = Image.new("RGBA", (tw, T1["size"] + 40), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((40, 10), DOC["title"][0], font=f1, fill=tuple(T1["rgb"]))
    sh = T1["shear"]
    lay = lay.transform(lay.size, Image.AFFINE, (1, sh, -sh * lay.size[1] / 2, 0, 1, 0), Image.BICUBIC)
    bb = lay.getbbox(); lay = lay.crop(bb)
    im.alpha_composite(lay, (W // 2 - lay.size[0] // 2, T1["ink_top"]))
    # 2줄 = 노랑 박스 + 검정 글
    bx = T2["box"]; d.rectangle([bx[0], bx[1], bx[2], bx[3]], fill=tuple(T2["box_rgb"]))
    f2 = ImageFont.truetype(str(FONTS / T2["font_file"]), T2["size"])
    b2 = d.textbbox((0, 0), DOC["title"][1], font=f2)
    d.text((W // 2 - (b2[2] - b2[0]) // 2 - b2[0], (bx[1] + bx[3]) // 2 - (b2[3] + b2[1]) // 2), DOC["title"][1], font=f2, fill=tuple(T2["rgb"]))
    # 로고(창 왼쪽 위) — 반투명 회색 글 + 진회색 테두리
    LG = FRAME["logo"]; fl = ImageFont.truetype(str(FONTS / LG["font_file"]), LG["size"])
    lg = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
    ImageDraw.Draw(lg).text((LG["x"], 10), DOC["logo"], font=fl, fill=tuple(LG["rgba"]), stroke_width=LG["stroke"], stroke_fill=tuple(LG["stroke_rgba"]))
    im.alpha_composite(lg, (0, LG["y"] - 10))
    # 출처 줄
    CR = FRAME["credit"]; fc = ImageFont.truetype(str(FONTS / CR["font_file"]), CR["size"])
    bc = d.textbbox((0, 0), DOC["source_label"], font=fc)
    d.text((W // 2 - (bc[2] - bc[0]) // 2 - bc[0], CR["ink_top"] - bc[1]), DOC["source_label"], font=fc, fill=tuple(CR["rgb"]))
    im.save(path)


def flash_mask(TL) -> list[float]:
    """흰 번쩍임 자리 = 나레→원음, 원음→나레(하이브리드 이음) 바뀌는 줄 시작(키치잇: 전환에 흰 번쩍임·줌 블러)."""
    out, rows = [], TL["rows"]
    for i in range(1, len(rows)):
        if rows[i]["kind"] != rows[i - 1]["kind"]:
            out.append(rows[i]["t0"])
    return out


def render(tmp: Path):
    TL = timeline(tmp)
    plan = video_plan(TL)
    parts = []
    for k, c in enumerate(plan):
        p = tmp / f"v{k:02d}.mp4"
        info = clip(SRC / c["src"], c["ss"], (c["f1"] - c["f0"]) / FPS, c["crop"], p, c["push"])
        c.update(info); parts.append(p)
    lst = tmp / "v.txt"; lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    win = tmp / "window.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(win)])
    png = tmp / "frame.png"; frame_png(png)
    flashes = flash_mask(TL)
    fl = "+".join(f"between(T,{t:.3f},{t + 0.10:.3f})*(1-(T-{t:.3f})/0.10)" for t in flashes) or "0"
    total = TL["total"]
    # 소리: 나레·원음 줄 + BGM(원음 줄 덕킹) + 효과음(0초 띵 · 종류 바뀌는 자리 휙)
    voice_in, filt = [], []
    for i, r in enumerate(TL["rows"]):
        voice_in += ["-i", r["wav"]]
        filt.append(f"[{i + 2}:a]adelay={int(r['t0'] * 1000)}:all=1[v{i}]")
    n = len(TL["rows"])
    bgm = BGM_DIR / f"{DOC['bgm']['id']}.mp3"
    sfx = [(0.0, SFX / "ding.wav", -8)] + [(t - 0.12, SFX / "whoosh.wav", -10) for t in flashes]
    sfx_in = []
    for j, (t, f, db) in enumerate(sfx):
        sfx_in += ["-i", str(f)]
        filt.append(f"[{n + 3 + j}:a]volume={db}dB,adelay={max(0, int(t * 1000))}:all=1[s{j}]")
    duck = "+".join(f"between(t,{r['t0']:.3f},{r['t1']:.3f})" for r in TL["rows"] if r["kind"] == "orig") or "0"
    filt.append(f"[{n + 2}:a]aloop=-1:size=2e9,atrim=0:{total:.3f},loudnorm=I=-16:TP=-2,volume={DOC['bgm']['db'] + 16:.1f}dB,"
                f"volume='if({duck},{10 ** (DOC['bgm']['duck_orig_db'] / 20):.3f},1)':eval=frame,afade=t=out:st={total - 0.4:.3f}:d=0.4[bg]")
    mix = "".join(f"[v{i}]" for i in range(n)) + "[bg]" + "".join(f"[s{j}]" for j in range(len(sfx)))
    filt.append(f"{mix}amix=inputs={n + 1 + len(sfx)}:normalize=0:dropout_transition=0,atrim=0:{total:.3f},"
                f"loudnorm=I={DOC['lufs']}:TP=-1.5:LRA=7[aout]")
    vf = (f"[0:v][1:v]overlay={WIN['x']}:{WIN['y']}:shortest=0[base];[base][2:v]overlay=0:0[fr];"
          f"[fr]geq=lum='min(255,lum(X,Y)+255*({fl}))':cb='cb(X,Y)':cr='cr(X,Y)'[vout]") if flashes else \
         f"[0:v][1:v]overlay={WIN['x']}:{WIN['y']}[base];[base][2:v]overlay=0:0[vout]"
    out = OUT / "base_nocap.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={total:.3f}", "-i", str(win),
           "-loop", "1", "-t", f"{total:.3f}", "-i", str(png)]
    # 입력 번호: 0 바탕 · 1 창 · 2 틀 png → 소리 입력은 3부터. filt 의 번호를 맞춘다
    filt = [re.sub(r"\[(\d+):a\]", lambda m: f"[{int(m.group(1)) + 1}:a]", f) for f in filt]
    cmd += voice_in + ["-i", str(bgm)] + sfx_in
    cmd += ["-filter_complex", vf + ";" + ";".join(filt), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
            "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)]
    run(cmd)
    return TL, plan, flashes, out


# ── 자막표 ────────────────────────────────────────────────────────────
EMPH_CYCLE = FRAME["caption"]["emph_cycle"]


def caption_table(TL) -> list[dict]:
    al = json.loads(Path(DOC["narr_file"]).with_suffix(".json").read_text(encoding="utf-8"))["align"]
    chars, st = al["characters"], al["character_start_times_seconds"]
    full = "".join(chars)
    rows, k = [], 0
    for r in TL["rows"]:
        L = next(x for x in DOC["lines"] if x["id"] == r["id"])
        caps = L["caps"]
        if L["kind"] == "tts":
            a = L["tts_span"][0]
            base = full.find(L["text"].replace("1991년", "천구백구십일 년").replace("1위", "일 위")[:6], max(0, int(a * 5) - 40))
            starts = []
            pos = base
            spoken = L["text"].replace("1991년", "천구백구십일 년").replace("1위", "일 위")
            for c in caps:
                key = c["text"].replace("1991년", "천구백구십일 년").replace("1위", "일 위")[:3]
                j = full.find(key, pos)
                tt = st[j] if j >= 0 else a
                starts.append(r["t0"] + max(0.0, (tt - a - r["trim"])) / DOC["voice"]["atempo"])
                pos = j + 1 if j >= 0 else pos
            starts[0] = r["t0"]
        else:   # 원음: 글자 수 비율(근사 — 받아쓰기 글자 시각 없음)
            n = [len(re.sub(r"\s", "", c["text"])) for c in caps]; tot = sum(n); acc = 0; starts = []
            for m in n:
                starts.append(r["t0"] + r["dur"] * acc / tot); acc += m
        for i, c in enumerate(caps):
            t1 = starts[i + 1] if i + 1 < len(caps) else r["v1"] - 0.02
            color = EMPH_CYCLE[k % len(EMPH_CYCLE)] if c["emph"] else None
            if c["emph"]:
                k += 1
            rows.append({"line": r["id"], "kind": "나레" if L["kind"] == "tts" else "원음", "t0": round(starts[i], 2), "t1": round(t1, 2),
                         "text": c["text"], "emph": c["emph"], "emph_hex": color,
                         "enter": "pop" if i == 0 else "cut",
                         "typing": c["typing"], "outline2_hex": FRAME["caption"]["typing_ring_hex"] if c["typing"] else None,
                         "sticker": c["sticker"], "timing": "TTS 글자 시각" if L["kind"] == "tts" else "원음 글자 수 비율(근사)"})
    return rows


def sheet(mp4: Path, out: Path):
    run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", "fps=1,scale=216:384,tile=8x4", "-frames:v", "1", str(out)])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--keep", action="store_true"); a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True); tmp = OUT / "tmp"; tmp.mkdir(exist_ok=True)
    TL, plan, flashes, out = render(tmp)
    caps = caption_table(TL)
    meta = {"made_by": "channel/kitchit/하이브리드_성시경/render_kitchit.py", "total": TL["total"], "rows": TL["rows"], "cuts": plan, "flashes": flashes}
    (OUT / "timeline.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    cap_doc = {"_note": "자막 입히기 직전 표 — 지휘자가 자막팩(키치잇 팩) 길로 입힌다. 시각은 base_nocap.mp4 기준 초. 모양 사양 = channel/kitchit/자막팩_보강안.json",
               "video": str(out), "pack": "kitchit", "caption_box": FRAME["caption"], "rows": caps}
    for p in (OUT / "자막표.json", HERE / "자막표.json"):
        p.write_text(json.dumps(cap_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    sheet(out, OUT / "sheet_1s.jpg")
    print("OK", out, "길이", TL["total"], "컷", len(plan), "번쩍임", flashes)


if __name__ == "__main__":
    main()
