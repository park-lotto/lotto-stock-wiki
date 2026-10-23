# -*- coding: utf-8 -*-
"""썸네일 = 무조건 연예인 얼굴(사장님 2026-10-18 "그게 후킹의 시작") — ① 첫 프레임·H(TTS 한마디) 구간 얼굴 검사 ② 업로드용 썸네일 JPG 자동 생성 (관제 097).

    PYTHONUTF8=1 py tools/calcopy/hybrid/thumb.py check <final.mp4> <frame_A.json> [--h-span a-b]
    PYTHONUTF8=1 py tools/calcopy/hybrid/thumb.py make <doc_dir> <work_dir>          # render_info.json 을 읽어 후보 프레임 → <final>.jpg (1080×1920)

① face_check: 얼굴 검출 = OpenCV YuNet(onnx, C:/calcopy_models — 한글 경로는 OpenCV 가 못 읽어 ASCII 경로에 둔다). 0초 프레임과 H 구간 0.5초 간격 프레임마다
   얼굴이 **정확히 1개** · 얼굴 높이 ≥ 창 높이의 FACE_MIN_FRAC · 얼굴 가운데가 창 가로 가운데 60% 안 · 눈·입 랜드마크가 창 안 — 하나라도 깨지면 반려(ok=False).
   제품 컷으로 시작하면 0초에서 바로 걸린다(기존 잇썸홈판 다수가 그랬다).
② make_thumb: 자막 없는 A 합성본(잇썸 render/a_seg.mp4 · 재미썸은 work/matA.mp4 를 틀로 한 번 합성)에서 원음·H 구간 프레임을 0.25초마다 뽑아
   얼굴 1개·크기·정면성(두 눈 간격/얼굴 폭)·선명도(라플라시안 분산)로 점수 → 1등 프레임을 1080×1920 JPG 로. 영상과 같은 이름 .jpg.
판단 주인: score()·face_check() 이 파일 한 곳. checks.py 는 face_check 결과를 B표 행으로만 옮긴다.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import FPS, StageError, dur_of, jload, jsave, run  # noqa: E402

from tools.calcopy.hybrid.common import FACE_MODEL as _FM  # noqa: E402 — 주인 = common.FACE_MODEL
MODEL = Path(_FM)
MODEL_SRC = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
FACE_MIN_FRAC = 0.20          # 얼굴 높이 / 창 높이 하한 — 10-18 실측: 바탕화면 15판 첫 프레임 0.28~1.0 · 옛 장윤정 재미썸 전신 0.12(작다·반려) · 옛 최은경 재미썸 0.27(얼굴 큼·통과)
FACE_MIN_FRAC_THUMB = 0.12    # 썸네일 후보 고르기는 느슨하게(있는 것 중 가장 큰 얼굴을 고른다 — 반려 관문은 FACE_MIN_FRAC)
FACE_CENTER_FRAC = 0.60       # 얼굴 가운데가 창 가로 가운데 이 비율 안
FACE_CONF = 0.80
FACE_BG_FRAC = 0.45           # 가장 큰 얼굴 높이의 이 비율 미만인 작은 얼굴(배경 포스터·액자)은 무시 — 10-18 한혜진: 포스터 얼굴을 '얼굴 2개'로 반려
EYE_OPEN = 0.26               # 눈 뜸 지표(눈 패치 어두운 픽셀 비율, 두 눈 중 작은 쪽) 이상이면 뜬 눈 — 10-18 손태영 실측: 뜬 0.30~0.37 · 감음/반쯤 0.14~0.20
STEP_CHECK, STEP_PICK = 0.5, 0.25


def _detector():
    import cv2
    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        run(["curl", "-sL", "-o", str(MODEL), MODEL_SRC])
    return cv2.FaceDetectorYN.create(str(MODEL), "", (320, 320), 0.6, 0.3, 50)


def _frame(mp4, t: float, crop=None):
    import cv2
    vf = f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}" if crop else "null"
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", "-vf", vf, "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True, stdin=subprocess.DEVNULL).stdout
    return cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_COLOR) if b else None


SCALES = (480, 320, 240)      # 10-18 실측: 1080 그대로 넣으면 창을 꽉 채운 근접 얼굴(강민경·함익병·박세리)을 conf 0.72~0.83·틀린 상자로 놓친다. 축소 입력 여러 개 → 합침


def _iou(a, b):
    x0, y0 = max(a["x"], b["x"]), max(a["y"], b["y"])
    x1, y1 = min(a["x"] + a["w"], b["x"] + b["w"]), min(a["y"] + a["h"], b["y"] + b["h"])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return inter / (a["w"] * a["h"] + b["w"] * b["h"] - inter + 1e-9)


def faces_of(det, im) -> list[dict]:
    """여러 축소 크기로 검출해 같은 얼굴(IoU≥0.4)은 가장 높은 conf 하나만 — 큰 얼굴·작은 얼굴 둘 다 잡는다."""
    import cv2
    H, W = im.shape[:2]
    found = []
    for w in SCALES:
        s = min(1.0, w / max(W, H))
        small = cv2.resize(im, (max(16, int(round(W * s))), max(16, int(round(H * s))))) if s < 1.0 else im
        det.setInputSize((small.shape[1], small.shape[0]))
        _, f = det.detect(small)
        for r in (f if f is not None else []):
            x, y, w_, h_ = [float(v) / s for v in r[:4]]
            lm = [(float(r[4 + 2 * i]) / s, float(r[5 + 2 * i]) / s) for i in range(5)]   # 오른눈·왼눈·코·오른입·왼입
            found.append({"x": x, "y": y, "w": w_, "h": h_, "conf": round(float(r[-1]), 3), "lm": lm, "scale": w})
    out = []
    for f in sorted(found, key=lambda f: -f["conf"]):
        if all(_iou(f, o) < 0.4 for o in out):
            out.append(f)
    out = [o for o in out if o["conf"] >= FACE_CONF]
    if out:                                                   # 주인공 기준: 가장 큰 얼굴의 FACE_BG_FRAC 미만 작은 얼굴은 배경(포스터) — 센 수에서 뺀다
        big = max(o["h"] for o in out)
        out = [o for o in out if o["h"] >= big * FACE_BG_FRAC]
    return out


def judge(faces: list[dict], W: int, H: int, min_frac: float = FACE_MIN_FRAC) -> tuple[bool, str, dict]:
    if len(faces) != 1:
        return False, f"얼굴 {len(faces)}개", {}
    f = faces[0]
    frac = f["h"] / H
    cx = (f["x"] + f["w"] / 2) / W
    inside = all(0 <= px < W and 0 <= py < H for px, py in f["lm"])
    info = {"h_frac": round(frac, 3), "cx": round(cx, 3), "conf": f["conf"], "landmarks_in": inside}
    if frac < min_frac:
        return False, f"얼굴 작음 {frac:.2f}<{min_frac}", info
    if not (0.5 - FACE_CENTER_FRAC / 2 <= cx <= 0.5 + FACE_CENTER_FRAC / 2):
        return False, f"얼굴 치우침 cx={cx:.2f}", info
    if not inside:
        return False, "눈·입이 창 밖", info
    return True, "○", info


def face_check(final, win: tuple, h_span: tuple[float, float] | None, log=print) -> dict:
    """0초 + H 구간(0.5초 간격) 프레임의 연예인 얼굴 검사. win=(x,y,w,h) 영상 창. 반환 {"ok", "frames":[{t, ok, why, …}]}."""
    det = _detector()
    ts = [round(THUMB_FRAMES / FPS + 0.01, 3)]      # 맨 앞 THUMB_FRAMES 는 썸네일 카드(10-24 — 카드 규칙은 card() 몫) → 그 바로 뒤 첫 영상 프레임
    if h_span:
        a, b = h_span
        t = a + 0.1
        while t < b - 0.05:
            ts.append(round(t, 2)); t += STEP_CHECK
    rows = []
    for t in ts:
        im = _frame(final, t, win)
        if im is None:
            rows.append({"t": t, "ok": False, "why": "프레임 없음"}); continue
        ok, why, info = judge(faces_of(det, im), im.shape[1], im.shape[0])
        rows.append({"t": t, "ok": ok, "why": why, **info})
    res = {"ok": all(r["ok"] for r in rows), "frames": rows, "rule": f"얼굴 1개 · 높이≥{FACE_MIN_FRAC} · 가운데 {FACE_CENTER_FRAC} · 눈입 안"}
    log(f"[thumb] 얼굴 검사 {'○' if res['ok'] else '×'}: " + " ".join(f"{r['t']}s:{'○' if r['ok'] else r['why']}" for r in rows))
    return res


def eye_open(im, f: dict) -> float:
    """눈 뜸 지표 — 눈 랜드마크 둘레 패치에서 '뺨 밝기의 55% 보다 어두운 픽셀' 비율(홍채·동공이 보이면 ↑, 감으면 속눈썹 선만 남아 ↓), 두 눈 중 작은 쪽.
    10-18 손태영 실측(a_seg·thumb_base): 뜬 눈 0.30~0.37, 반쯤·감음 0.14~0.20(자동이 골랐던 2.55초·3.6초). 랜드마크만으로 재서 추가 모델이 없다."""
    import cv2
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    H, W = g.shape[:2]
    cheek = g[int(f["y"] + f["h"] * 0.55):int(f["y"] + f["h"] * 0.7), int(f["x"] + f["w"] * 0.3):int(f["x"] + f["w"] * 0.7)]
    skin = float(np.median(cheek)) if cheek.size else 128.0
    vals = []
    for ex, ey in f["lm"][:2]:
        r, rv = int(f["w"] * 0.11), int(f["w"] * 0.07)
        p = g[max(0, int(ey - rv)):min(H, int(ey + rv)), max(0, int(ex - r)):min(W, int(ex + r))]
        if p.size:
            vals.append(float((p < skin * 0.55).mean()))
    return round(min(vals), 3) if vals else 0.0


def score(det, im) -> tuple[float, dict]:
    import cv2
    fs = faces_of(det, im)
    H, W = im.shape[:2]
    ok, why, info = judge(fs, W, H, FACE_MIN_FRAC_THUMB)
    if not ok:
        return -1.0, {"why": why, **info}
    f = fs[0]
    (rx, ry), (lx, ly) = f["lm"][0], f["lm"][1]
    frontal = abs(lx - rx) / max(f["w"], 1)                        # 정면일수록 눈 간격/얼굴 폭 ↑(≈0.4)
    x0, y0, x1, y1 = int(max(0, f["x"])), int(max(0, f["y"])), int(min(W, f["x"] + f["w"])), int(min(H, f["y"] + f["h"]))
    g = cv2.cvtColor(im[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    sharp = float(cv2.Laplacian(g, cv2.CV_64F).var()) if g.size else 0.0
    eye = eye_open(im, f)
    s = (f["h"] / H) * 3.0 + min(frontal, 0.45) * 4.0 + min(sharp / 400.0, 1.0) * 1.0 + min(eye, 0.4) / 0.4 * 3.0
    if eye < EYE_OPEN:
        s -= 3.0                                                    # 감은/반쯤 감은 눈은 뒤로(10-18 사장님 "눈 감은 썸네일" 두 판 다 손으로 다시 뽑음)
    return round(s, 3), {**info, "frontal": round(frontal, 3), "sharp": round(sharp, 1), "eye": eye, "eye_open": eye >= EYE_OPEN}


def _clean_a(doc: Path, work: Path, info: dict) -> Path:
    """자막 없는 A 합성본(틀 제목·출처 들어감). 잇썸 = render/a_seg.mp4 그대로. 재미썸 = work/matA.mp4 를 틀로 합성(한 번)."""
    R = work / "render"
    if info.get("version") == "잇썸홈판":
        return R / "a_seg.mp4"
    out = R / "thumb_base.mp4"
    if out.exists():
        return out
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    frame = jload(R / "frame_A.json")
    S = jload(doc / "대본.json")
    mat = R / "work" / "matA.mp4"
    if not mat.exists():
        raise StageError(f"재미썸 A 재료(work/matA.mp4)가 없다 — 렌더 뒤에 불러라: {mat}")
    d = dur_of(mat)
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": d, "narration": "", "caption_lines": [], "role": "hook", "primary": {"video_id": "s0", "start": 0.0, "end": d}}]
    shutil.rmtree(R / "work_thumb", ignore_errors=True)
    scene_style.compose(str(mat), tl, scene_style.validate_snapshot(to_snapshot.to_snapshot(frame)), str(out), R / "work_thumb", {"text": S["title"]})
    return out


def windows_of(info: dict) -> tuple[list[tuple[float, float]], tuple[float, float] | None]:
    """render_info → (연예인이 보이는 창들[원음 구간], H(TTS 한마디) 구간)."""
    if info.get("version") == "잇썸홈판":
        T = info["timeline"]
        return [(p["t0"], p["t1"]) for p in T["opos"]], tuple(T["lines"][T["h_id"]])
    rep = info["report"]
    f1 = [p for p in info["pieces"] if p["line"] == 0]
    return [(0.0, rep["orig_sec"])], (f1[0]["t"][0], f1[-1]["t"][1])


def make_thumb(doc: Path, work: Path, dst: Path | None = None, log=print) -> dict:
    """썸네일 JPG. 대본 thumb{"at": 초} 가 있으면 그 시각(사람이 고른 것) · thumb{"keep": true} 또는 final.jpg.manual 표식이 있으면 기존 JPG 를 덮어쓰지 않는다
    (10-18 손태영: checks 다시 돌려 손으로 뽑은 썸네일을 자동이 덮어썼다)."""
    import cv2
    doc, work = Path(doc), Path(work)
    R = work / "render"
    info = jload(R / "render_info.json")
    S = jload(doc / "대본.json") if (doc / "대본.json").exists() else {}
    tc = S.get("thumb") or {}
    dst = Path(dst) if dst else R / "final.jpg"
    if (tc.get("keep") or dst.with_suffix(".jpg.manual").exists()) and dst.exists():
        log(f"[thumb] 손으로 고른 썸네일 유지(덮어쓰지 않음): {dst}")
        return {"jpg": str(dst), "picked": {"manual": True}, "n_candidates": 0, "n_face": 0, "kept": True}
    base = _clean_a(doc, work, info)
    frame = jload(R / "frame_A.json")
    v = next(l for l in frame["layers"] if l.get("kind") == "video")
    win = (int(v["x"]), int(v["y"]), int(v["w"]), int(v["h"]))
    det = _detector()
    if tc.get("at") is not None:                                   # 사람이 고른 시각 — 점수 없이 그 프레임(얼굴 정보만 적어 둔다)
        t = float(tc["at"])
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", base, "-frames:v", "1", "-q:v", "2", "-vf", "scale=1080:1920", dst])
        im = _frame(base, t, win)
        s, inf = score(det, im) if im is not None else (-1.0, {})
        jsave(R / "thumb_candidates.json", {"base": str(base), "picked": {"t": t, "score": s, "manual_at": True, **inf}, "candidates": []})
        shutil.copy(dst, doc / "thumb.jpg")
        log(f"[thumb] 대본 thumb.at={t}s → {dst} (얼굴 {inf})")
        return {"jpg": str(dst), "picked": {"t": t, "manual_at": True, **inf}, "n_candidates": 1, "n_face": int(s > 0)}
    wins, h_span = windows_of(info)
    cands = []
    bd = dur_of(base)
    for a, b in wins + ([h_span] if h_span else []):
        t = a + 0.05
        while t < min(b, bd) - 0.05:
            im = _frame(base, t, win)
            if im is not None:
                s, inf = score(det, im)
                cands.append({"t": round(t, 2), "score": s, **inf})
            t += STEP_PICK
    good = [c for c in cands if c["score"] > 0]
    if not good:
        raise StageError("썸네일 후보 프레임에 연예인 얼굴(1개·크게·가운데)이 없다 — A 구간 컷을 바꿔라")
    best = max(good, key=lambda c: c["score"])
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{best['t']:.3f}", "-i", base, "-frames:v", "1", "-q:v", "2", "-vf", "scale=1080:1920", dst])
    sheet = R / "thumb_candidates.json"
    jsave(sheet, {"base": str(base), "picked": best, "candidates": sorted(cands, key=lambda c: -c["score"])[:20]})
    shutil.copy(dst, doc / "thumb.jpg")
    log(f"[thumb] {dst} ← {base.name}@{best['t']}s 점수 {best['score']} 눈 {best.get('eye')} (후보 {len(cands)}, 얼굴 있는 것 {len(good)}, 눈 뜬 것 {sum(1 for c in good if c.get('eye_open'))})")
    return {"jpg": str(dst), "picked": best, "n_candidates": len(cands), "n_face": len(good)}


# ── 썸네일 카드(궁금 장치) — 판단 주인: 이 아래 card() 한 곳 ──────────────────────────────────────────
# 10-23 사장님 "맨 앞에 썸네일 아주 잠깐 / 가장 눈에 띄고 클릭할 수밖에 없는 장면 + 궁금한 장치(멘트·화살표) / 사진으로 몇 개씩 / 대충 만들지 마".
# 벤치 실측(잇템로그 aUic·ro1l 첫 2프레임): 틀(제목 2줄) 그대로 + 창 안 장면 + 빨강 굵은 글('이거 맞아..??!', 검정 외곽·번진 그림자) + 빨간 원.
# 장면 = 그 편 render/parts 컷 조각(자막·광고표시 없는 창 화면) — 본편에 실제로 나오는 장면만(낚시 금지).
# 썸네일.json = {"options":[{"id","part","t","why", "zoom":[x,y,w,h]?, "text":[{"lines":[…],"xy":[cx,cy],"px","color"?,"rot"?}],
#   "circle":[[cx,cy,r],…]?, "arrow":[[[x0,y0],[x1,y1]],…]?, "q":[[cx,cy,px],…]?, "hide":[[x,y,w,h],…]?}]}  좌표 = 창 안(1080×1434) 기준.
CARD_RED = (236, 22, 30)
CARD_FONT = "GmarketSansBold.otf"
# 10-24 사장님 "웃긴 거는 ㅋㅋ ㅎㅎ 번갈아 / 황당한 건 ㄷㄷ / (A·B·C 중) 랜덤으로": 안마다 mood = funny|wow → 글 끝 꼬리표.
# funny 의 ㅋㅋ·ㅎㅎ = 편 번호(문서 폴더 epNN) 홀수 ㅋㅋ · 짝수 ㅎㅎ — 이웃 편끼리 번갈아 나온다.
def mood_tag(doc: Path, mood: str | None) -> str:
    import re
    if mood == "wow":
        return "ㄷㄷ"
    if mood == "funny":
        m = re.search(r"ep(\d+)", Path(doc).name)
        return "ㅋㅋ" if (int(m.group(1)) if m else 1) % 2 else "ㅎㅎ"
    return ""


def pick_option(doc: Path, spec: dict) -> str:
    """보일 안 = 썸네일.json 의 pick(한 번 정하면 고정). 없으면 무작위로 정해 적는다."""
    import random
    if not spec.get("pick"):
        spec["pick"] = random.choice([o["id"] for o in spec["options"]])
        jsave(Path(doc) / "썸네일.json", spec)
    return spec["pick"]


def _part_frame(work: Path, part: int, t: float):
    from PIL import Image
    p = Path(work) / "render/parts" / f"c{part:02d}.mp4"
    w, h = 1080, 1434
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(p), "-frames:v", "1", "-vf", f"scale={w}:{h}:flags=lanczos",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    if len(raw) != w * h * 3:
        raise StageError(f"썸네일 장면 프레임을 못 뽑음: {p} @{t}")
    return Image.frombytes("RGB", (w, h), raw)


def _shadow_text(layer, xy, lines, font, fill, stroke, line_gap=1.08, rot=0.0):
    """굵은 글 + 검정 외곽 + 번진 그림자(벤치 썸네일 글)를 layer(RGBA)에 가운데 정렬로 얹는다."""
    from PIL import Image, ImageDraw, ImageFilter
    asc, desc = font.getmetrics()
    lh = int((asc + desc) * line_gap)
    tw = int(max(font.getlength(s) for s in lines)) + stroke * 4
    th = lh * len(lines) + stroke * 4
    t = Image.new("RGBA", (tw + 60, th + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    for i, s in enumerate(lines):
        x = (t.size[0] - font.getlength(s)) / 2
        y = 30 + stroke * 2 + i * lh
        d.text((x, y), s, font=font, fill=fill + (255,), stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    sh = Image.new("RGBA", t.size, (0, 0, 0, 0))
    sh.putalpha(t.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.85)))
    out = Image.new("RGBA", t.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (6, 10))
    out.alpha_composite(t)
    if rot:
        out = out.rotate(rot, resample=Image.BICUBIC, expand=True)
    x = min(max(int(xy[0] - out.size[0] / 2), -20), layer.size[0] - out.size[0] + 20)      # 창 밖으로 안 나가게(그림자 여백 20)
    layer.alpha_composite(out, (x, int(xy[1] - out.size[1] / 2)))


def _arrow(d, a, b, width=26, head=70):
    import math
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    base = (b[0] - head * 0.8 * math.cos(ang), b[1] - head * 0.8 * math.sin(ang))
    left = (b[0] - head * math.cos(ang - 0.5), b[1] - head * math.sin(ang - 0.5))
    right = (b[0] - head * math.cos(ang + 0.5), b[1] - head * math.sin(ang + 0.5))
    for col, add in (((0, 0, 0, 255), 10), (CARD_RED + (255,), 0)):
        d.line([tuple(a), base], fill=col, width=width + add)
        d.polygon([tuple(b), left, right] if not add else [
            (b[0] + 8 * math.cos(ang), b[1] + 8 * math.sin(ang)),
            (left[0] - 6 * math.cos(ang - 1.57), left[1] - 6 * math.sin(ang - 1.57)),
            (right[0] + 6 * math.cos(ang - 1.57), right[1] + 6 * math.sin(ang - 1.57))], fill=col)


def card(style_name: str, doc: Path, work: Path, opt: dict, out: Path) -> Path:
    """한 안(opt)을 1080×1920 JPG 로 — 틀(판 설정 frame·대본 title_lines) + 창 장면 + 장치."""
    from PIL import Image, ImageDraw, ImageFilter
    from tools.calcopy.hybrid import styles as ST
    from tools.calcopy.hybrid.render_bench import _font, frame_png
    st = ST.load(style_name)
    S = jload(Path(doc) / "대본.json")
    x0, y0, ww, wh = st["frame"]["window"]
    if opt.get("file"):      # 컷 조각이 없을 때(작업 폴더 정리 뒤) = 본편이 쓴 원본 영상 그 자리·같은 크롭
        from PIL import Image as _I
        fx, fy, fw, fh = opt["crop"]
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{float(opt['ss']):.3f}", "-i", opt["file"], "-frames:v", "1", "-vf",
                              f"crop={fw}:{fh}:{fx}:{fy},scale={ww}:{wh}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, stdin=subprocess.DEVNULL).stdout
        if len(raw) != ww * wh * 3:
            raise StageError(f"썸네일 장면 프레임을 못 뽑음: {opt['file']} @{opt['ss']}")
        scene = _I.frombytes("RGB", (ww, wh), raw)
    else:
        part = opt.get("part")
        if opt.get("line"):      # 줄 + 그 줄 안 몇 번째 컷 — 컷 수가 바뀌어도 번호가 안 밀린다(10-24 09: 첫 줄 컷 2→1 로 번호가 밀려 실패)
            tl = jload(Path(work) / "render/timeline.json")["cuts"]
            ks = [k for k, c in enumerate(tl) if c["line"] == opt["line"]]
            if len(ks) <= int(opt.get("nth", 0)):
                raise StageError(f"썸네일 장면 줄 {opt['line']} 에 {opt.get('nth', 0)}번째 컷이 없다")
            part = ks[int(opt.get("nth", 0))]
        scene = _part_frame(work, int(part), float(opt.get("t", 0.0)))
    if opt.get("zoom"):
        zx, zy, zw, zh = opt["zoom"]
        scene = scene.crop((zx, zy, zx + zw, zy + zh)).resize((ww, wh), Image.LANCZOS)
    scene = scene.convert("RGBA")
    for hx, hy, hw, hh in opt.get("hide") or []:          # 제품 가리기 = 흐림(정체 숨김 → '뭐길래?')
        box = scene.crop((hx, hy, hx + hw, hy + hh)).filter(ImageFilter.GaussianBlur(28))
        scene.paste(box, (hx, hy))
    lay = Image.new("RGBA", scene.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for cx, cy, r in opt.get("circle") or []:
        d.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3], outline=(0, 0, 0, 200), width=20)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=CARD_RED + (255,), width=13)
    for a, b in opt.get("arrow") or []:
        _arrow(d, a, b)
    for cx, cy, px in opt.get("q") or []:
        _shadow_text(lay, (cx, cy), ["?"], _font(CARD_FONT, px), (255, 225, 0), max(8, px // 12))
    tag = mood_tag(doc, opt.get("mood"))
    for i, tx in enumerate(opt.get("text") or []):
        lines = list(tx["lines"])
        if i == 0 and tag:
            lines[-1] = f"{lines[-1]} {tag}"
        px = tx.get("px", 120)
        while px > 70 and max(_font(tx.get("font", CARD_FONT), px).getlength(t) for t in lines) > 1000:
            px -= 4                                            # 꼬리표가 붙어 넘치면 줄인다(창 폭 1080 − 여백)
        _shadow_text(lay, tx["xy"], lines, _font(tx.get("font", CARD_FONT), px),
                     tuple(tx.get("color", CARD_RED)), tx.get("stroke", 11), rot=tx.get("rot", 0.0))
    scene.alpha_composite(lay)
    fr = Image.open(frame_png(S, st, Path(work) / "render/thumb_frame.png")).convert("RGBA")
    full = Image.new("RGBA", fr.size, (0, 0, 0, 255))
    full.paste(scene, (x0, y0))
    full.alpha_composite(fr)
    out.parent.mkdir(parents=True, exist_ok=True)
    full.convert("RGB").save(out, quality=94)
    return out


def cards(style_name: str, doc: Path, work: Path, log=print) -> dict:
    """<doc>/썸네일.json 의 안마다 <doc>/thumb/<id>.jpg + 나란히 본 시트 thumb/시트.jpg."""
    from PIL import Image, ImageDraw
    from tools.calcopy.hybrid.render_bench import _font
    doc = Path(doc)
    spec = jload(doc / "썸네일.json")
    outs = []
    for o in spec["options"]:
        p = card(style_name, doc, work, o, doc / "thumb" / f"{o['id']}.jpg")
        outs.append((o, p))
        log(f"[card] {o['id']} {p}")
    tw, th = 432, 768
    sheet = Image.new("RGB", (len(outs) * (tw + 16) + 16, th + 80), (24, 24, 24))
    dd = ImageDraw.Draw(sheet)
    for i, (o, p) in enumerate(outs):
        sheet.paste(Image.open(p).resize((tw, th), Image.LANCZOS), (16 + i * (tw + 16), 64))
        dd.text((16 + i * (tw + 16), 12), f"{o['id']}  {o.get('why', '')}"[:40], font=_font("Pretendard-Bold.otf", 30), fill=(255, 230, 0))
    sp = doc / "thumb" / "시트.jpg"
    sheet.save(sp, quality=90)
    pk = pick_option(doc, spec)
    return {"sheet": str(sp), "cards": [str(p) for _, p in outs], "pick": pk, "pick_jpg": str(doc / "thumb" / f"{pk}.jpg")}


THUMB_FRAMES = 2      # 벤치 실측: 0초 첫 2프레임(약 0.07초)만 썸네일 그림


def stamp_video(video: Path, jpg: Path, frames: int = THUMB_FRAMES) -> None:
    """완성본 맨 앞 frames 프레임을 썸네일 그림으로 덮는다(길이·소리 그대로)."""
    from PIL import Image
    from tools.calcopy.engine import ad_mark
    tmp = Path(video).with_suffix(".thumb.mp4")
    card_png = Path(video).with_name("_thumb_stamp.png")
    im = Image.open(jpg).convert("RGBA").resize((1080, 1920))
    bp, m = ad_mark.badge(1080, Path(video).with_name("_thumb_badge.png"))      # 카드 프레임에도 '광고'(주인 ad_mark — 모든 프레임)
    b = Image.open(bp)
    im.alpha_composite(b, (1080 - b.size[0] - m, m))
    im.convert("RGB").save(card_png)
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", card_png, "-filter_complex",
         f"[1:v]scale=1080:1920,setsar=1[t];[0:v][t]overlay=0:0:enable='lt(n,{frames})',format=yuv420p[v]", "-map", "[v]", "-map", "0:a",
         "-map_metadata", "0", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-c:a", "copy", "-movflags", "+faststart", tmp])
    shutil.move(str(tmp), str(video))
    card_png.unlink(missing_ok=True); Path(bp).unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("final"); c.add_argument("frame"); c.add_argument("--h-span")
    m = sub.add_parser("make"); m.add_argument("doc"); m.add_argument("work"); m.add_argument("--dst")
    k = sub.add_parser("card"); k.add_argument("style"); k.add_argument("doc"); k.add_argument("work")
    a = ap.parse_args()
    if a.cmd == "card":
        print(json.dumps(cards(a.style, Path(a.doc), Path(a.work)), ensure_ascii=False, indent=1))
    elif a.cmd == "check":
        fr = jload(a.frame)
        v = next(l for l in fr["layers"] if l.get("kind") == "video")
        hs = tuple(map(float, a.h_span.split("-"))) if a.h_span else None
        print(json.dumps(face_check(a.final, (int(v["x"]), int(v["y"]), int(v["w"]), int(v["h"])), hs), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(make_thumb(Path(a.doc), Path(a.work), Path(a.dst) if a.dst else None), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
