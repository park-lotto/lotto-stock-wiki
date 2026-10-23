"""렌더 — 원본 틀(refs/<id>.json 의 style·measured) + 이 편 내용(ep.json·voice.json) → out.mp4.

판단의 주인:
  · 글자 모양·위치·썸네일·워터마크 = refs/<id>.json "style" (원본 실측값. 여기 숫자를 새로 적지 않는다)
  · 무슨 말·어떤 사진·어디서 자르나 = ep.json(engine 의 script·shots 단계가 쓴다)
  · 자르는 시각 = cut_points() 하나 — 자막 조각 경계 중 원본 컷 길이에 가장 가깝게
움직임 = 사진 깊이(Depth Anything V2 small, onnx)로 가까운 것은 더·먼 것은 덜 커지게(원본 AI 영상의 입체감 대역, 무료·로컬).
"""
import itertools
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
FONT = Path.home() / ".shottem/packs/font"
DEPTH = Path.home() / "숏템자료/models/onnx/model.onnx"
FPS, WD, HT = 30, 1080, 1920
TAIL_S = 0.35

_sess = None


def ref_spec(ref_id):
    return json.loads((HERE / "refs" / (ref_id + ".json")).read_text(encoding="utf-8"))


def depth(img):
    """0(멀다)~1(가깝다). 경계에서 찢어지지 않게 부드럽게."""
    global _sess
    if _sess is None:
        import onnxruntime as ort
        if not DEPTH.exists():
            from huggingface_hub import hf_hub_download
            hf_hub_download("onnx-community/depth-anything-v2-small", "onnx/model.onnx", local_dir=str(DEPTH.parent.parent))
        _sess = ort.InferenceSession(str(DEPTH), providers=["CPUExecutionProvider"])
    h, w = img.shape[:2]
    x = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), (518, 518), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255
    x = ((x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).transpose(2, 0, 1)[None].astype(np.float32)
    d = cv2.resize(_sess.run(None, {_sess.get_inputs()[0].name: x})[0][0], (w, h), interpolation=cv2.INTER_CUBIC)
    d = (d - np.percentile(d, 2)) / max(1e-6, np.percentile(d, 98) - np.percentile(d, 2))
    return cv2.GaussianBlur(np.clip(d, 0, 1).astype(np.float32), (0, 0), 6)


def imread(p):
    return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)


def vertical(path, cx):
    """사진 → 9:16 세로(높이 꽉, 가운데 cx). 원본처럼 색을 진하게 + 확대 흐림을 선명화로 덮는다."""
    im = imread(path)
    h, w = im.shape[:2]
    if w / h > 9 / 16:
        cw = int(round(h * 9 / 16))
        x0 = int(np.clip(cx * w - cw / 2, 0, w - cw))
        im = im[:, x0:x0 + cw]
    else:                                   # 세로가 더 긴 사진은 가운데를 자른다
        ch = int(round(w * 16 / 9))
        y0 = (h - ch) // 2
        im = im[y0:y0 + ch]
    im = cv2.resize(im, (WD, HT), interpolation=cv2.INTER_LANCZOS4)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * 1.22, 0, 255)
    im = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    im = np.clip((im - 128) * 1.08 + 128, 0, 255)
    bl = cv2.GaussianBlur(im, (0, 0), 1.6)
    return np.clip(im * 1.55 - bl * 0.55, 0, 255).astype(np.uint8)


def dolly(img, dep, n, z0=0.03, zp=0.10, cy=0.55, lat=0.0):
    """화면 점 p ← 원본 q = c + (p-c)/s(q) - 옆 이동, s = 1 + u·(z0 + zp·깊이). s≥1 이라 바깥이 드러나지 않는다."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    c = (w * 0.5, h * cy)
    for k in range(n):
        u = k / max(1, n - 1)
        dq = dep
        for _ in range(3):
            s = 1 + u * (z0 + zp * dq)
            qx, qy = c[0] + (xx - c[0]) / s - u * lat * w * dq, c[1] + (yy - c[1]) / s
            dq = cv2.remap(dep, qx, qy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        yield cv2.remap(img, qx, qy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def text_layer(lines, sizes, ys, fonts, glow=14, strength=1.0, spacing=-0.04, squeeze=0.9, grow=13):
    """흰 글자 + 번지는 검은 그림자(원본 실측: 외곽선 없이 넓게 번진 어두운 후광). RGBA."""
    ink = Image.new("L", (WD, HT), 0)
    for t, sz, y, f in zip(lines, sizes, ys, fonts):
        ft = ImageFont.truetype(str(FONT / f), sz)
        adv = [ft.getlength(ch) + sz * spacing for ch in t]
        tw = int(sum(adv)) + sz
        one = Image.new("L", (tw, sz * 2), 0)
        od = ImageDraw.Draw(one)
        x = sz / 2
        for ch, a in zip(t, adv):
            od.text((x, sz), ch, font=ft, fill=255, anchor="lm")
            x += a
        one = one.resize((max(1, int(tw * squeeze)), sz * 2), Image.LANCZOS)
        ink.paste(one, (int((WD - one.width) / 2), int(y - sz)), one)
    sh = ink.filter(ImageFilter.MaxFilter(grow)).filter(ImageFilter.GaussianBlur(glow))
    sh = sh.point(lambda v: int(min(255, v * strength * 1.8)))
    lay = Image.new("RGBA", (WD, HT), (0, 0, 0, 0))
    lay.paste((0, 0, 0, 255), (0, 0), sh)
    lay = Image.alpha_composite(lay, Image.merge("RGBA", (ink.point(lambda v: 255),) * 3 + (ink,)))
    return np.array(lay)


def over(frame, rgba):
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (frame * (1 - a) + rgba[..., [2, 1, 0]].astype(np.float32) * a).astype(np.uint8)


def cut_points(row, end, k, target):
    """문장 안 컷 시작 k개 — 첫 조각에서 시작, 나머지는 조각 경계 중 컷 길이가 target 에 가장 가깝게."""
    best = None
    for comb in itertools.combinations(range(1, len(row)), k - 1):
        st = [row[0]] + [row[i] for i in comb]
        cost = sum((b - a - target) ** 2 for a, b in zip(st, st[1:] + [end]))
        if best is None or cost < best[0]:
            best = (cost, st)
    return best[1]


def timeline(job, ep, ref):
    """voice.json(어절 시각) + ep 조각·사진 → 자막·컷 시간표. 소리 파일(narr.wav)도 여기서 만든다."""
    v = json.loads((job / "voice.json").read_text(encoding="utf-8"))
    speed = ep["speed"]
    (job / "concat.txt").write_text("".join("file '%s'\n" % x["mp3"] for x in v), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", "concat.txt",
                    "-filter:a", "atempo=%.4f" % speed, "-ar", "44100", "narr.wav"], check=True, cwd=job)
    thumb_s = ref["measured"]["thumb_s"]
    t, rows = 0.0, []
    for x, line in zip(v, ep["lines"]):
        words = [(w.get("word") or w.get("w"), (t + w.get("start", w.get("t", 0))) / speed) for w in x["words"]]
        assert "".join(w for w, _ in words).replace(" ", "") == "".join(line["chunks"]).replace(" ", ""), (words, line["chunks"])
        k, row = 0, []
        for ch in line["chunks"]:
            row.append(thumb_s + words[k][1])
            k += len(ch.split())
        rows.append(row)
        t += x["dur"]
    total = thumb_s + t / speed + TAIL_S
    flat = [(tt, txt) for row, line in zip(rows, ep["lines"]) for tt, txt in zip(row, line["chunks"])]
    caps = [(a, flat[i + 1][0] if i + 1 < len(flat) else total, txt) for i, (a, txt) in enumerate(flat)]
    cuts = []
    for si, line in enumerate(ep["lines"]):
        end = rows[si + 1][0] if si + 1 < len(rows) else total
        starts = cut_points(rows[si], end, len(line["shots"]), ref["measured"]["cut_target_s"])
        if si == 0:
            starts[0] = thumb_s
        for sh, t0 in zip(line["shots"], starts):
            cuts.append([t0, None, sh["file"], sh.get("cx", 0.5)])
    for i in range(len(cuts)):
        cuts[i][1] = cuts[i + 1][0] if i + 1 < len(cuts) else total
    return total, caps, cuts


def render(job):
    job = Path(job)
    ep = json.loads((job / "ep.json").read_text(encoding="utf-8"))
    ref = ref_spec(ep["ref"])
    st = ref["style"]
    total, caps, cuts = timeline(job, ep, ref)
    plan = {"total": round(total, 3), "cuts": [[round(a, 2), round(b, 2), Path(f).name, c] for a, b, f, c in cuts],
            "caps": [[round(a, 2), round(b, 2), t] for a, b, t in caps]}
    (job / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("길이 %.2f초 · 컷 %d · 자막 %d · 컷 길이 %s" % (total, len(cuts), len(caps), [round(b - a, 2) for a, b, _, _ in cuts]), flush=True)

    c = st["caption"]
    cap_png = {}
    for _, _, txt in caps:
        shown = txt.replace(" ", "") if c.get("no_spaces") else txt
        cap_png[txt] = text_layer([shown], [c["size"]], [c["y"]], [c["font"]], glow=c["glow"], strength=c["strength"],
                                  spacing=c["spacing"], squeeze=c["squeeze"], grow=c["grow"])
    wmst = st["watermark"]
    wm = text_layer([ep["brand"]], [wmst["size"]], [wmst["y"]], [wmst["font"]], glow=4, strength=0.5, spacing=0, squeeze=1, grow=3)
    wm[..., 3] = (wm[..., 3] * wmst["alpha"]).astype(np.uint8)
    th, tst = ep["thumb"], st["thumb"]
    thumb_txt = text_layer([th["small"], th["big"]], [tst["small"]["size"], tst["big"]["size"]], [tst["small"]["y"], tst["big"]["y"]],
                           [tst["small"]["font"], tst["big"]["font"]], glow=tst["glow"], grow=tst["grow"])

    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % (WD, HT),
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                           "-pix_fmt", "yuv420p", str(job / "video.mp4")], stdin=subprocess.PIPE)
    fi = 0
    timg = over(vertical(th["file"], th.get("cx", 0.5)), thumb_txt)
    for _ in range(int(round(ref["measured"]["thumb_s"] * FPS))):
        ff.stdin.write(over(timg, wm).tobytes())
        fi += 1
    for ci, (a, b, f, cx) in enumerate(cuts):
        n = int(round(b * FPS)) - fi
        img = vertical(f, cx)
        lat = 0.012 * (1 if ci % 2 else -1)              # 컷마다 옆으로 번갈아 조금 — 앞뒤 어긋남(입체감)을 키운다
        for fr in dolly(img, depth(img), n, lat=lat):
            t = fi / FPS
            cap = next((x for x in caps if x[0] <= t < x[1]), None)
            if cap:
                fr = over(fr, cap_png[cap[2]])
            ff.stdin.write(over(fr, wm).tobytes())
            fi += 1
    ff.stdin.close()
    ff.wait()

    thumb_ms = ref["measured"]["thumb_s"] * 1000
    ins = ["-i", str(job / "video.mp4"), "-i", str(job / "narr.wav")]
    if ep.get("bgm"):
        ins += ["-i", ep["bgm"]]
        af = ("[1:a]adelay=%d|%d,apad=whole_dur=%.3f[nv];[2:a]atrim=0:%.3f,volume=0.16,afade=t=out:st=%.3f:d=0.4[bg];"
              "[nv][bg]amix=inputs=2:normalize=0,loudnorm=I=%.1f:TP=-1.0:LRA=7[a]" % (thumb_ms, thumb_ms, total, total, total - 0.4, ref["measured"]["lufs"]))
    else:
        af = "[1:a]adelay=%d|%d,apad=whole_dur=%.3f,loudnorm=I=%.1f:TP=-1.0:LRA=7[a]" % (thumb_ms, thumb_ms, total, ref["measured"]["lufs"])
    subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", af, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-t", "%.3f" % total, str(job / "out.mp4")], check=True)
    return job / "out.mp4"
