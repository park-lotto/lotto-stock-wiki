# -*- coding: utf-8 -*-
"""꾸밈 자리 검출 — 채널 무관(표준 §3-3 A3, 관제 263 지시서 03, 2026-10-24).

왜: 스티커·짤·화살표/원 자리를 눈대중 고정 좌표(hearts x50 y41·object_pop x62% y54%)로 두면 대상과 어긋난다
(handoff 10-18 샥탬 "빨간원 너무 안 맞는다"). 샥탬 `shark/fx_place.py`(hook_object·on_target·object_box)만 검출로 자리를 잡았다 —
그 논리를 채널 규칙(shark rules.json)에서 떼어 어느 판이든 쓰게 한 것이 이 모듈. shark/fx_place.py 는 그대로 둔다(샥탬 세션 영역).

(판단 주인)
  무엇이 어디 있나  find()       — face = YuNet(hybrid/thumb 모델) · object = 손 상자 | Claude CLI(claude_cli.ask, 제미나이 금지) ·
                                   caption_side = 자막 띠 바깥 가장 가까운 빈 자리(얼굴 피함). avoid 'face' 면 얼굴과 겹치는 물건 상자는 None.
  꾸밈을 어디 두나  on_target()  — 대상 상자 → 원(상자 감쌈)·화살표(끝이 상자 가장자리, 위→아래→왼→오른 순) 자리.
                                   자막 띠를 덮거나 창 밖이면 None(억지로 딴 데 두지 않는다 — 샥탬 R4).
  배치에 꽂기       locator()    — placement.place(locate=…) 가 부르는 함수를 만든다(덩어리 시각의 프레임에서 find).

    PYTHONUTF8=1 py tools/calcopy/hybrid/fx_target.py find object <mp4|png> <t> --win 0,434,1080,1052 --what "노란 수세미" [--how claude]
    PYTHONUTF8=1 py tools/calcopy/hybrid/fx_target.py find face <mp4|png> <t>
    PYTHONUTF8=1 py tools/calcopy/hybrid/fx_target.py bench [--out <json>]   # 샥탬 손 상자(foreignshowshow 재료 red_circle target)와 적중 표(IoU)
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CANVAS = (1080, 1920)
CONF_MIN = 0.6                 # 검출 확신 하한(check_place 와 같은 값 — 아래면 None)
FACE_OVERLAP = 0.10            # 물건 상자 넓이 중 얼굴(정수리까지) 상자와 겹친 몫이 이보다 크면 '얼굴 겹침'


# ── 그림 ─────────────────────────────────────────────────────────────────
def frame_of(src, t: float | None = None) -> np.ndarray:
    """RGB 배열. src = ndarray | 그림 파일(png/jpg — 한글 경로라 bytes 로 연다) | 영상(t 초 프레임, ffmpeg)."""
    if isinstance(src, np.ndarray):
        return src
    if callable(src):          # 시각 → RGB 함수(render_bench.plan_canvas — 렌더 없는 계획 프레임)
        return src(t)
    from PIL import Image
    p = Path(src)
    if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return np.array(Image.open(io.BytesIO(p.read_bytes())).convert("RGB"))
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{float(t or 0):.3f}", "-i", str(p), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True, stdin=subprocess.DEVNULL).stdout
    if not b:
        raise ValueError(f"프레임 못 뽑음 {p}@{t}")
    return np.array(Image.open(io.BytesIO(b)).convert("RGB"))


def iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / max(1e-9, u)


def _inter_frac(box, other) -> float:
    ix = max(0.0, min(box[2], other[2]) - max(box[0], other[0])); iy = max(0.0, min(box[3], other[3]) - max(box[1], other[1]))
    return ix * iy / max(1e-9, (box[2] - box[0]) * (box[3] - box[1]))


def _in_win(box, win) -> bool:
    if not win:
        return True
    x, y, w, h = win
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return x <= cx <= x + w and y <= cy <= y + h


# ── 얼굴(YuNet — 주인 모델 hybrid/thumb, 같은 축소 여러 크기·배경 얼굴 빼기) ─────────────
def faces(rgb: np.ndarray, win=None) -> list[dict]:
    """얼굴 상자 [{box:[x0,y0,x1,y1](정수리까지 0.35fh 위로), conf}] — 창(win) 안 얼굴만, 큰 것부터."""
    from tools.calcopy.hybrid import thumb as TH
    bgr = np.ascontiguousarray(rgb[:, :, ::-1])
    out = []
    for f in TH.faces_of(TH._detector(), bgr):
        b = [f["x"], f["y"] - 0.35 * f["h"], f["x"] + f["w"], f["y"] + f["h"]]
        if _in_win(b, win):
            out.append({"box": [round(v, 1) for v in b], "conf": f["conf"],
                        "face": [round(v, 1) for v in (f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"])],   # 정수리 늘림 없는 얼굴 상자
                        "lm": [[round(a, 1), round(c, 1)] for a, c in f.get("lm") or []]})                       # 오른눈·왼눈·코·오른입·왼입(YuNet)
    return sorted(out, key=lambda d: -(d["box"][2] - d["box"][0]) * (d["box"][3] - d["box"][1]))


# ── 물건(Claude CLI 판독 — 격자 그림으로 좌표를 읽힌다) ─────────────────────────
GRID = 100


def _grid_jpg(rgb: np.ndarray, win) -> tuple[bytes, tuple[int, int, int, int]]:
    from PIL import Image, ImageDraw, ImageFont
    x, y, w, h = win or (0, 0, rgb.shape[1], rgb.shape[0])
    im = Image.fromarray(rgb[y:y + h, x:x + w]).convert("RGB")
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
    except Exception:  # noqa: BLE001 — 글꼴 없으면 기본(숫자만 읽으면 된다)
        font = ImageFont.load_default()
    for gx in range(0, w, GRID):
        d.line([(gx, 0), (gx, h)], fill=(0, 255, 255), width=1)
        d.text((gx + 3, 3), str(gx), fill=(255, 255, 0), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    for gy in range(0, h, GRID):
        d.line([(0, gy), (w, gy)], fill=(0, 255, 255), width=1)
        d.text((3, gy + 3), str(gy), fill=(255, 255, 0), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=92)
    return buf.getvalue(), (x, y, w, h)


def object_claude(rgb: np.ndarray, what: str, win=None, model: str = "sonnet") -> tuple[list | None, float, str]:
    """(물건 상자) Claude CLI 판독 — 창 그림에 100px 격자·눈금을 그려 픽셀 좌표로 답하게 한다. 반환 (상자 | None, 확신, 까닭)."""
    from tools.calcopy.engine import claude_cli as CC
    jpg, (x, y, w, h) = _grid_jpg(rgb, win)
    prompt = (f"이 그림은 {w}x{h} 픽셀이고 하늘색 선은 {GRID}px 격자, 노란 숫자는 그 선의 픽셀 좌표다. "
              f"그림에서 정확히 이것을 찾아라: \"{what}\". 물건 전체를 빈틈없이 감싸는 상자를 격자 눈금으로 읽어 픽셀 좌표로 답한다. "
              "사람 얼굴은 묻지 않았으면 상자에 넣지 않는다. 확실히 보이지 않으면 found=false. "
              '답 꼴: {"found": true|false, "box": [x0, y0, x1, y1], "label": "상자에 넣은 것 짧게", "confidence": 0~1}')
    d, err = CC.ask([jpg], prompt, tag="fx_target_object", model=model)
    if d is None:
        return None, 0.0, f"Claude 실패 {err}"
    conf = float(d.get("confidence") or 0)
    b = d.get("box")
    if not d.get("found") or not isinstance(b, list) or len(b) != 4:
        return None, conf, f"Claude: 못 찾음 {json.dumps({k: d.get(k) for k in ('found', 'label', 'confidence')}, ensure_ascii=False)}"
    bx = [x + float(b[0]), y + float(b[1]), x + float(b[2]), y + float(b[3])]
    if bx[2] - bx[0] < 12 or bx[3] - bx[1] < 12 or (bx[2] - bx[0]) * (bx[3] - bx[1]) > 0.6 * w * h:
        return None, conf, f"Claude 상자 크기 이상 {bx}"
    return [round(v) for v in bx], conf, f"Claude {model} '{d.get('label')}' 확신 {conf}"


MOUTH_PAD = 1.6       # 입 둘레 상자 한 변 = 입 양끝 거리 × 1.6(입술·이를 감싸는 원 — 손 상수, 벤치 원 크기 실측 전. 판 anchor:"mouth" 일 때만)
ANCHORS = ("face_center", "mouth")


def mouth_box(f: dict) -> list | None:
    """얼굴(faces 한 개)의 입 둘레 상자 [x0,y0,x1,y1] — 중심 = 입 양끝(YuNet lm 3·4) 가운데, 한 변 = 입 폭 × MOUTH_PAD(최소 얼굴 높이 0.2)."""
    lm = f.get("lm") or []
    if len(lm) < 5:
        return None
    (rx, ry), (lx, ly) = lm[3], lm[4]
    cx, cy = (rx + lx) / 2, (ry + ly) / 2
    fh = (f.get("face") or f["box"])[3] - (f.get("face") or f["box"])[1]
    side = max(((rx - lx) ** 2 + (ry - ly) ** 2) ** 0.5 * MOUTH_PAD, 0.2 * fh)
    return [cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2]


def bench_anchor(style: dict) -> list[dict]:
    """벤치 줄판독의 빨간 원(sticker x,y,w) ↔ 그 프레임 얼굴 랜드마크 — 원 중심이 입·얼굴 가운데 중 어디에 가까운가(얼굴 높이로 나눈 거리).
    줄판독 x,y 가 왼위인지 가운데인지 채널마다 달라(샥탬 bench_rings = 가운데, 잇템로그 = 왼위) 두 해석 중 얼굴에 더 가까운 쪽을 쓴다(how 칸).
    판 anchor 칸(07)을 정하는 근거 표 — 원본 영상(판 bench.src_dir)이 있어야 잰다."""
    import glob
    from tools.calcopy.hybrid import thumb as TH
    from tools.calcopy.hybrid.placement import sticker_kind
    B = style.get("bench") or {}
    src, lr = B.get("src_dir"), B.get("line_reads")
    out = []
    for fp in sorted(glob.glob(str(ROOT / lr / "*.json"))) if lr and src else []:
        d = json.loads(Path(fp).read_text(encoding="utf-8"))
        for l in d.get("lines") or []:
            for s in l.get("sticker") or []:
                if not isinstance(s, dict) or sticker_kind(s.get("what", "")) != "circle_arrow" or not isinstance(s.get("x"), (int, float)):
                    continue
                t = float(s.get("t_in", l.get("t0") or 0)) + 0.03
                try:
                    rgb = frame_of(str(Path(src) / f"{d['id']}.mp4"), t)
                except Exception as e:  # noqa: BLE001 — 못 잰 편은 표에 사유로
                    out.append({"id": d["id"], "t": t, "why": f"프레임 없음 {type(e).__name__}"}); continue
                fs = TH.faces_of(TH._detector(), np.ascontiguousarray(rgb[:, :, ::-1]))
                if not fs:
                    out.append({"id": d["id"], "t": round(t, 2), "why": "얼굴 없음(물건 원)"}); continue
                f = max(fs, key=lambda f: f["w"] * f["h"])
                m = ((f["lm"][3][0] + f["lm"][4][0]) / 2, (f["lm"][3][1] + f["lm"][4][1]) / 2)
                c = (f["x"] + f["w"] / 2, f["y"] + f["h"] / 2)
                best = None
                for how, (cx, cy) in (("가운데", (s["x"], s["y"])), ("왼위", (s["x"] + s["w"] / 2, s["y"] + s["w"] / 2))):
                    dm = ((cx - m[0]) ** 2 + (cy - m[1]) ** 2) ** 0.5 / f["h"]
                    dc = ((cx - c[0]) ** 2 + (cy - c[1]) ** 2) ** 0.5 / f["h"]
                    if best is None or min(dm, dc) < min(best[1], best[2]):
                        best = (how, dm, dc)
                how, dm, dc = best
                near = "mouth" if dm < dc else "face_center"
                out.append({"id": d["id"], "t": round(t, 2), "xy": how, "d_mouth": round(dm, 2), "d_center": round(dc, 2),
                            "anchor": near if min(dm, dc) <= 1.0 else None, "what": s.get("what", "")[:30]})
    return out


# ── 자막 옆 ──────────────────────────────────────────────────────────────
def caption_side(size, caption_band, win=None, face_boxes=(), why: list | None = None) -> list | None:
    """자막 띠(y0,y1) 바깥 가장 가까운 빈 자리(가운데 정렬, 띠 위 먼저 → 아래) — 얼굴과 겹치거나 창 밖이면 다음 후보, 다 막히면 None.
    why(목록) 를 주면 후보마다 막힌 까닭을 적는다(조용한 실패 금지 — 07 15a9f46ed 쪽지)."""
    w, h = size
    x, y, ww, wh = win or (0, 0, *CANVAS)
    cx = x + ww / 2
    gap = 12
    up, down = caption_band[0] - gap - h, caption_band[1] + gap
    left, right = x + gap + w / 2, x + ww - gap - w / 2          # 좌우 자리(얼굴이 가운데를 덮는 화면 — ep13 kk_doodle 가운데 둘 다 얼굴 겹침, 15)
    for side, top, ccx in (("위", up, cx), ("아래", down, cx), ("위 왼쪽", up, left), ("위 오른쪽", up, right),
                           ("아래 왼쪽", down, left), ("아래 오른쪽", down, right)):
        b = [ccx - w / 2, top, ccx + w / 2, top + h]
        if b[0] < x or b[2] > x + ww or b[1] < y or b[3] > y + wh:
            if why is not None:
                why.append(f"띠 {side} {[round(v) for v in b]} 창 {[x, y, x + ww, y + wh]} 밖")
            continue
        if any(_inter_frac(b, f) > FACE_OVERLAP for f in face_boxes):
            if why is not None:
                why.append(f"띠 {side} {[round(v) for v in b]} 얼굴 겹침(>{FACE_OVERLAP})")
            continue
        return [round(v) for v in b]
    return None


# ── 찾기(판단 주인) ───────────────────────────────────────────────────────
def find(kind: str, src, t: float | None = None, win=None, avoid=("face",), what: str | None = None, box=None, how: str = "claude",
         size=(160, 160), caption_band=None, detector=None, fail: list | None = None, anchor: str | None = None) -> dict | None:
    """kind = face | object | caption_side → {x,y,w,h(픽셀 상자), box, conf, how, why, face_clear} | None(못 찾음·확신 낮음·얼굴 겹침).
    object: box(손 상자)를 주면 그것, 아니면 detector(rgb, what, win)(시험용 주입) 또는 Claude CLI. avoid 에 'face' 면 얼굴 겹친 상자 = None."""
    rgb = frame_of(src, t)
    fb = [f["box"] for f in faces(rgb, win)] if ("face" in (avoid or ()) or kind in ("face", "caption_side")) else []
    if kind == "face":
        fs = faces(rgb, win)
        if not fs:
            if fail is not None:
                fail.append(f"얼굴 0개(t={t})")
            return None
        b = fs[0]["box"]
        if anchor == "mouth":
            m = mouth_box(fs[0])
            if m is None:
                if fail is not None:
                    fail.append("입 랜드마크 없음(YuNet lm) — 입 둘레 자리 못 잼")
                return None
            return _pack(m, fs[0]["conf"], "yunet", f"얼굴 {len(fs)}개 중 가장 큰 것의 입 둘레(입 양끝 랜드마크)", True)
        return _pack(b, fs[0]["conf"], "yunet", f"얼굴 {len(fs)}개 중 가장 큰 것", True)
    if kind == "caption_side":
        if not caption_band:
            raise ValueError("caption_side 는 caption_band=(y0,y1) 가 필요하다")
        b = caption_side(size, caption_band, win, fb, why=fail)
        return _pack(b, 1.0, "caption_band", f"자막 띠 {caption_band} 바깥", True) if b else None
    if kind != "object":
        raise ValueError(f"모르는 자리 종류 {kind} — face|object|caption_side")
    if box is not None:
        b, conf, why = [float(v) for v in box], 1.0, "손 상자(재료 target)"
    elif detector is not None:
        b, conf, why = detector(rgb, what, win)
    elif how == "claude":
        if not what:
            raise ValueError("object 검출은 what(무엇)이 필요하다 — 눈대중 좌표 금지")
        b, conf, why = object_claude(rgb, what, win)
    else:
        raise ValueError(f"모르는 검출 방법 {how}")
    if b is None or conf < CONF_MIN:
        if fail is not None:
            fail.append(f"물건 '{what}' 못 찾음·확신 {conf}<{CONF_MIN} ({why})")
        return None
    if "face" in (avoid or ()) and any(_inter_frac(b, f) > FACE_OVERLAP for f in fb):
        if fail is not None:
            fail.append(f"물건 상자 {b} 얼굴 겹침(>{FACE_OVERLAP})")
        return None
    return _pack(b, conf, "hand" if box is not None else how, why, True if "face" in (avoid or ()) else None)


def _pack(b, conf, how, why, face_clear) -> dict:
    b = [round(float(v)) for v in b]
    out = {"x": round((b[0] + b[2]) / 2 / CANVAS[0] * 100, 2), "y": round((b[1] + b[3]) / 2 / CANVAS[1] * 100, 2),     # 가운데 = 화면 %(판 스티커 x·y 와 같은 단위)
           "w": b[2] - b[0], "h": b[3] - b[1], "box": b, "conf": round(float(conf), 3), "how": how, "why": why}
    if face_clear is not None:
        out["face_clear"] = face_clear
    return out


# ── 꾸밈 자리(샥탬 on_target 논리 — 채널 규칙 없이) ─────────────────────────────
def on_target(target_box, size=None, canvas=None, caption_band=None, kind: str = "arrow", gap: float = 8.0, pad: float = 1.04) -> dict | None:
    """대상 상자 → 꾸밈 자리. canvas = 창 [x,y,w,h](기본 1080×1920 전체), caption_band = (y0,y1) 덮으면 안 되는 자막 띠.
    circle: 중심 = 상자 가운데, 반지름 = 반대각선×pad(size 주면 max(size)/2) — 창 밖·띠 덮음이면 None.
    arrow : size=(w,h) 그림 — 끝이 상자 가장자리(gap 안쪽)에 닿게 위(↓)→아래(↑)→왼(→)→오른(←) 순, 들어가는 첫 자리. 없으면 None."""
    x0, y0, x1, y1 = [float(v) for v in target_box]
    cx0, cy0, cw, ch = canvas or (0, 0, *CANVAS)

    def ok(b):
        if b[0] < cx0 or b[2] > cx0 + cw or b[1] < cy0 or b[3] > cy0 + ch:
            return "창 밖"
        if caption_band and b[3] > caption_band[0] and b[1] < caption_band[1]:
            return f"자막 띠{tuple(caption_band)}"
        return None
    if kind == "circle":
        r = max(size) / 2 if size else 0.5 * ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 * pad
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        b = [cx - r, cy - r, cx + r, cy + r]
        return None if ok(b) else {"x": round(cx), "y": round(cy), "r": round(r), "box": [round(v) for v in b], "kind": "circle"}
    w, h = size or (140, 180)
    mx = (x0 + x1) / 2; my = (y0 + y1) / 2
    cands = (("above", [mx - w / 2, y0 + gap - h, mx + w / 2, y0 + gap], (mx, y0 + gap)),
             ("below", [mx - w / 2, y1 - gap, mx + w / 2, y1 - gap + h], (mx, y1 - gap)),
             ("left", [x0 + gap - w, my - h / 2, x0 + gap, my + h / 2], (x0 + gap, my)),
             ("right", [x1 - gap, my - h / 2, x1 - gap + w, my + h / 2], (x1 - gap, my)))
    for side, b, tip in cands:
        if not ok(b):
            return {"x": round((b[0] + b[2]) / 2), "y": round((b[1] + b[3]) / 2), "w": w, "h": h, "side": side,
                    "tip": [round(tip[0]), round(tip[1])], "box": [round(v) for v in b], "kind": "arrow"}
    return None


# ── 강조 표시(원·화살표) 대상 좌표·머무는 시간 — 판단 주인(사장님 10-25 "정확히 어디를 강조할지 좌표로, 머무는 시간도 장면에 맞게") ──
#   무엇 = 덩어리 key → 같은 줄 key → 컷 see(재료 장면 설명) · 줄 글 전체를 같이 준다.
#   어디 = 덩어리 시작·가운데·끝 프레임 3장을 오푸스 눈에 한 번에 물어 대상 상자(얼굴 YuNet 상자는 후보로만 보여 준다 — 기계 검출은 후보 제시용).
#   원 = 중심이 대상 상자 가운데, r = 상자 반대각(자막팩 s.r, 1080 폭 %) — 화살표는 원에 붙어 같은 중심을 가리킨다(out/precision20-ui.js renderStickers).
#   머무는 시간 = 덩어리 show(자막팩이 덩어리 동안 그린다) — 한 샷 안 · 3장 모두 대상이 원 중심을 덮음 · 벤치 줄판독 원/화살표 t_out−t_in 실측 자 안. 아니면 안 붙인다.
#   회원 flow 검수도 같은 질문(aim_prompt)을 부른다 — 질문을 두 벌 적지 않는다.
AIM_KINDS = ("circle_arrow",)
AIM_EDGE = 0.05            # 샷 경계 여유(초) — placement._cut_inside 와 같은 값
AIM_R_MIN, AIM_R_MAX = 55.0, 245.0      # 원 반지름 px — 벤치 줄판독 빨간원 지름 w 110~487 실측(ititemlog zOSp 110 · foreignshowshow 487)의 반
AIM_MODEL = "opus"         # 눈 판정 = 오푸스(사장님 10-25)
# 대상 크기별 강조 방식(벤치 실측 — channel/칼카피_제작순서/aim_bench.json, fx_target.py bench-aim, 30개 · 10-25):
#   원(원·원+화살표 12개)은 대상이 화면의 10% 이하일 때만(최대 0.100) · 원 지름 = 대상 긴 변 × 0.85~2.25(중앙 1.4).
#   화살표만(18개)은 대상 0.173 까지 — 우리 자막팩은 원+화살표 한 꼴뿐이라 화살표만 꼴은 아직 못 그린다(남은 것).
#   대상이 속한 전체(사람·물건)가 화면 15% 넘는 13개 중 9개는 전체가 아니라 특징 부위(얼굴·손·틈·젖은 바닥 등, 화면 0.9~10%)를 가리켰다.
#   화면 17.3% 넘는 대상을 통째로 강조한 벤치 표시는 0개 → 큰 대상은 자막이 말하는 성질이 보이는 부위(10% 이하)를 고르고, 없으면 안 붙인다.
AIM_CIRCLE_FRAC_MAX = 0.10        # 원으로 감쌀 대상 상자 넓이 ÷ 화면(1080×1920) 상한 — 벤치 원 대상 최대 0.100
AIM_DIAM_OVER_TARGET = 1.4        # 원 지름 ÷ 대상 긴 변 — 벤치 원 중앙값(0.85~2.25)
_HOLD_CACHE: dict = {}


def hold_rule(channel: str | None) -> dict:
    """벤치 줄판독(channel/*/줄판독/*.json) 원·화살표 스티커 t_out−t_in 실측 → {lo, hi, n, src}. 그 채널 측정 3개↑면 그 채널, 아니면 전 채널."""
    if channel in _HOLD_CACHE:
        return _HOLD_CACHE[channel]
    import glob
    from tools.calcopy.hybrid.placement import sticker_kind
    own, alls = [], []
    for fp in glob.glob(str(ROOT / "channel" / "*" / "줄판독" / "*.json")):
        try:
            d = json.loads(Path(fp).read_text(encoding="utf-8"))
        except (OSError, ValueError):      # 깨진 줄판독은 자에서 뺀다(측정 아님)
            continue
        ch = Path(fp).parent.parent.name
        for l in d.get("lines") or []:
            for s in l.get("sticker") or []:
                if (isinstance(s, dict) and sticker_kind(s.get("what", "")) == "circle_arrow" and isinstance(s.get("t_in"), (int, float))
                        and isinstance(s.get("t_out"), (int, float)) and s["t_out"] > s["t_in"]):
                    v = round(float(s["t_out"]) - float(s["t_in"]), 3)
                    alls.append(v)
                    if ch == channel:
                        own.append(v)
    use, src = (own, f"벤치 {channel} 줄판독 {len(own)}개") if len(own) >= 3 else (alls, f"벤치 전 채널 줄판독 {len(alls)}개")
    out = {"lo": min(use), "hi": max(use), "n": len(use), "src": src} if use else {"lo": None, "hi": None, "n": 0, "src": "벤치 측정 없음"}
    _HOLD_CACHE[channel] = out
    return out


def aim_what(row: dict, line_text: str | None = None, line_keys=(), see: str | None = None) -> dict:
    """무엇을 가리키나(질문 재료) — {key, line, chunk, see}. key = 덩어리 key → 같은 줄 key 첫 것. 대상 결정은 aim_prompt 의 눈이 한다."""
    key = row.get("key") or next((k for k in line_keys if k), None)
    return {"key": key, "line": line_text or row.get("text") or "", "chunk": row.get("text") or "", "see": see or ""}


def aim_prompt(W: dict, n: int, w: int, h: int, cands: list | None = None) -> str:
    """눈 판정 질문(우리 PC Claude · 회원 flow 검수 공용) — 프레임 n장에서 강조 대상 하나와 장마다 상자."""
    c = f" 기계 검출 후보(참고만, 맞지 않으면 무시): {json.dumps(cands, ensure_ascii=False)}." if cands else ""
    return (f"그림 {n}장은 같은 숏폼 장면의 시작·가운데·끝 프레임이다. 각 그림은 {w}x{h} 픽셀, 하늘색 선은 {GRID}px 격자, 노란 숫자는 그 선의 픽셀 좌표다.\n"
            f"이 장면에 빨간 원+화살표 강조를 하나 붙인다. 자막 줄 전체: \"{W['line']}\" / 지금 덩어리: \"{W['chunk']}\""
            + (f" / 강조 낱말: \"{W['key']}\"" if W.get("key") else "") + (f" / 장면 설명: \"{W['see']}\"" if W.get("see") else "") + ".\n"
            "시청자 눈을 끌어야 할 대상 하나를 정하라 — 자막이 말하는 제품·놀라운 변화·핵심 물건(강조 낱말이 있으면 그것)이 우선이고, "
            "그런 것이 화면에 없을 때만 자막이 말하는 사람의 얼굴. 의미 없는 곳(옷깃·빈 배경·아무 얼굴 부위)은 고르지 않는다.\n"
            f"대상이 화면 넓이의 {int(AIM_CIRCLE_FRAC_MAX * 100)}%를 넘게 크면(얼굴 전체에 붙은 마스크팩처럼) 전체를 감싸지 말고, 자막이 말하는 성질이 보이는 특징 부위"
            f"(예: 투명해진 부분·떼는 손끝·틈, 화면 {int(AIM_CIRCLE_FRAC_MAX * 100)}% 이하) 하나를 대상으로 삼는다. 그런 부위가 없으면 confidence 0.\n"
            "그 대상을 빈틈없이 감싸는 상자를 장마다 격자 눈금으로 읽어 픽셀 좌표로 답한다. 그 장에 대상이 안 보이면 그 장 상자 = null. 확실하지 않으면 confidence 를 낮게." + c
            + '\n답 꼴: {"target": "대상 짧게", "why": "왜 이것인가 한 줄", "boxes": [[x0,y0,x1,y1] 또는 null, … 장 순서대로 ' + str(n)
            + '개], "confidence": 0~1}')


def _cut_end(c: dict) -> float:
    return float(c["t1"]) if c.get("t1") is not None else float(c["t0"]) + float(c.get("dur") or 0)


def aim(video, row: dict, cuts: list | None, win=None, caption_band=None, line_text: str | None = None, line_keys=(), channel: str | None = None,
        ask=None, model: str = AIM_MODEL, fail: list | None = None) -> dict | None:
    """원·화살표 하나의 대상 좌표·머무는 시간(판단 주인). 반환 {x,y,r,w,h,box,conf,how,why,aim{…,hold}} | None(fail 에 사유).
    ask(jpgs, prompt) -> (dict|None, err) 를 주면 그것으로 묻는다(시험·회원 flow 주입), 없으면 Claude CLI(오푸스)."""
    fail = fail if fail is not None else []
    a = float(row["t0"])
    b = float((row.get("show") or [None, row["t1"]])[1])
    cut = next((c for c in cuts or [] if float(c["t0"]) - AIM_EDGE <= a < _cut_end(c) - AIM_EDGE), None)
    if cuts and cut is None:
        fail.append(f"덩어리 {a}초가 든 샷 없음"); return None
    if cut is not None and b > _cut_end(cut) + AIM_EDGE:
        fail.append(f"머무는 구간 {a}~{b} 이 샷 경계 {round(_cut_end(cut), 3)} 를 넘음"); return None
    HR = hold_rule(channel)
    if HR["lo"] is not None and not HR["lo"] <= b - a <= HR["hi"]:
        fail.append(f"머무는 길이 {round(b - a, 2)}초 — 벤치 자 {HR['lo']}~{HR['hi']}초({HR['src']}) 밖"); return None
    ts = [round(a + 0.1, 3), round((a + b) / 2, 3), round(max(a + 0.1, b - 0.1), 3)]
    W = aim_what(row, line_text, line_keys, (cut or {}).get("see"))
    jpgs, cands = [], []
    x = y = w = h = 0
    for k, t in enumerate(ts):
        rgb = frame_of(video, t)
        jpg, (x, y, w, h) = _grid_jpg(rgb, win)
        jpgs.append(jpg)
        if k == 0:
            cands = [{"얼굴": [round(f["face"][0] - x), round(f["face"][1] - y), round(f["face"][2] - x), round(f["face"][3] - y)]} for f in faces(rgb, win)][:3]
    if ask is None:
        from tools.calcopy.engine import claude_cli as CC
        ask = lambda parts, pr: CC.ask(parts, pr, tag="fx_target_aim", model=model)   # noqa: E731
    d, err = ask(jpgs, aim_prompt(W, len(ts), w, h, cands))
    if d is None:
        fail.append(f"눈 판정 실패 {err}"); return None
    conf = float(d.get("confidence") or 0)
    bx = d.get("boxes") or []
    if conf < CONF_MIN or len(bx) != len(ts):
        fail.append(f"눈 판정 확신 {conf}<{CONF_MIN} 또는 상자 수 {len(bx)}≠{len(ts)} ('{d.get('target')}')"); return None
    boxes = []
    for t, q in zip(ts, bx):
        if not (isinstance(q, list) and len(q) == 4):
            fail.append(f"대상 '{d.get('target')}' 이 {t}초 프레임에 안 보임 — 머무는 동안 대상이 사라짐"); return None
        boxes.append([x + float(q[0]), y + float(q[1]), x + float(q[2]), y + float(q[3])])
    b0 = boxes[0]
    cx, cy = (b0[0] + b0[2]) / 2, (b0[1] + b0[3]) / 2
    for t, q in zip(ts, boxes):
        if not (q[0] <= cx <= q[2] and q[1] <= cy <= q[3]):
            fail.append(f"대상 '{d.get('target')}' 이 {t}초에 원 중심({round(cx)},{round(cy)}) 밖으로 움직임 {[round(v) for v in q]}"); return None
    frac = (b0[2] - b0[0]) * (b0[3] - b0[1]) / (CANVAS[0] * CANVAS[1])
    if frac > AIM_CIRCLE_FRAC_MAX:
        fail.append(f"대상 '{d.get('target')}' 이 화면 {round(frac * 100, 1)}% — 벤치 원은 {int(AIM_CIRCLE_FRAC_MAX * 100)}% 이하 대상에만(큰 대상은 특징 부위를 못 찾음)"); return None
    r = min(AIM_R_MAX, max(AIM_R_MIN, AIM_DIAM_OVER_TARGET * max(b0[2] - b0[0], b0[3] - b0[1]) / 2))
    if caption_band and cy + r > caption_band[0] and cy - r < caption_band[1]:
        fail.append(f"원(중심 {round(cx)},{round(cy)} r{round(r)})이 자막 띠 {tuple(caption_band)} 를 덮음"); return None
    out = _pack(b0, conf, f"claude-{model}", f"눈 판정 '{d.get('target')}' — {d.get('why')}", None)
    out["r"] = round(r / CANVAS[0] * 100, 2)
    out["aim"] = {"what": d.get("target"), "why": d.get("why"), "asked": W, "box": [round(v) for v in b0], "frac": round(frac, 4),
                  "frames": [{"t": t, "box": [round(v) for v in q]} for t, q in zip(ts, boxes)]}
    out["aim"]["hold"] = {"t0": a, "t1": b, "shot": [float(cut["t0"]), round(_cut_end(cut), 3)] if cut else None, "rule": HR["src"]}
    return out


AIM_BENCH = ROOT / "channel" / "칼카피_제작순서" / "aim_bench.json"      # bench_aim 실측 표(대상 크기별 강조 방식 근거)


def _bench_srcs() -> dict:
    """채널 → 벤치 원본 폴더(판 bench.src_dir)."""
    import glob
    m = {}
    for f in glob.glob(str(ROOT / "tools/calcopy/hybrid/styles/*.json")):
        try:
            b = json.loads(Path(f).read_text(encoding="utf-8")).get("bench") or {}
        except (OSError, ValueError):
            continue
        if b.get("channel") and b.get("src_dir"):
            m[b["channel"]] = b["src_dir"]
    return m


def bench_aim(workers: int = 6) -> list[dict]:
    """벤치 줄판독의 원·화살표마다 원본 프레임(표시가 그려진 채)을 오푸스 눈에 물어 — 표시 모양·표시 상자·가리키는 대상 상자·그 대상이 속한 전체 물건 상자.
    → 대상 넓이 몫(화면 대비)·표시 지름÷대상 긴 변·'부위를 가리켰나'(대상 ≠ 전체 물건). 강조 방식 규칙(aim_mode)의 근거 표."""
    import glob
    from concurrent.futures import ThreadPoolExecutor
    from tools.calcopy.engine import claude_cli as CC
    from tools.calcopy.hybrid.placement import sticker_kind
    srcs = _bench_srcs()
    jobs = []
    for fp in sorted(glob.glob(str(ROOT / "channel" / "*" / "줄판독" / "*.json"))):
        ch = Path(fp).parent.parent.name
        try:
            d = json.loads(Path(fp).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for l in d.get("lines") or []:
            for s in l.get("sticker") or []:
                if not (isinstance(s, dict) and sticker_kind(s.get("what", "")) == "circle_arrow" and isinstance(s.get("t_in"), (int, float))):
                    continue
                vid = next((p for p in glob.glob(str(Path(srcs.get(ch, "")) / f"{d.get('id')}*.mp4"))), None) if srcs.get(ch) else None
                to = s.get("t_out") if isinstance(s.get("t_out"), (int, float)) else s["t_in"] + 0.1
                jobs.append({"ch": ch, "id": d.get("id"), "t": round((float(s["t_in"]) + float(to)) / 2, 3), "dur": round(float(to) - float(s["t_in"]), 3),
                             "what": s.get("what", ""), "text": l.get("text", ""), "src": vid})

    def one(j):
        if not j["src"]:
            return {**j, "skip": "원본 없음"}
        try:
            rgb = frame_of(j["src"], j["t"])
        except ValueError as e:
            return {**j, "skip": str(e)}
        h0, w0 = rgb.shape[:2]
        jpg, _ = _grid_jpg(rgb, None)
        pr = (f"이 그림은 {w0}x{h0} 픽셀 숏폼 프레임이다(하늘색 {GRID}px 격자, 노란 숫자 = 픽셀 좌표). 편집자가 그린 강조 표시(빨간 원·화살표 등, 줄판독 설명: \"{j['what']}\")가 있다. "
              f"그때 자막: \"{j['text']}\".\n"
              "1) mark: 표시 모양 circle|arrow|both|other, mark_box = 표시 전체(원·화살표)를 감싸는 상자. 2) target = 표시가 가리키는 것 짧게, target_box = 그것을 감싸는 상자. "
              "3) whole = 그 대상이 속한 전체 물건·사람(대상이 전체면 같은 것), whole_box. 4) part = 대상이 전체의 한 부위(특징 부분)이면 true. "
              "표시가 안 보이면 found=false.\n"
              '답 꼴: {"found": true, "mark": "circle", "mark_box": [x0,y0,x1,y1], "target": "", "target_box": [..], "whole": "", "whole_box": [..], "part": false, "confidence": 0~1}')
        d, err = CC.ask([jpg], pr, tag="fx_target_bench_aim", model=AIM_MODEL)
        if d is None or not d.get("found"):
            return {**j, "skip": f"판독 실패 {err or d}"}
        out = {**j, **{k: d.get(k) for k in ("mark", "mark_box", "target", "target_box", "whole", "whole_box", "part", "confidence")}, "frame": [w0, h0]}
        try:
            mb, tb, wb = d["mark_box"], d["target_box"], d["whole_box"]
            area = lambda b: max(0, b[2] - b[0]) * max(0, b[3] - b[1])   # noqa: E731
            out["target_frac"] = round(area(tb) / (w0 * h0), 3)
            out["whole_frac"] = round(area(wb) / (w0 * h0), 3)
            out["mark_over_target"] = round(max(mb[2] - mb[0], mb[3] - mb[1]) / max(1, tb[2] - tb[0], tb[3] - tb[1]), 2)
        except (KeyError, TypeError, IndexError):
            out["skip"] = "상자 꼴 이상"
        return out
    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(one, jobs))
    AIM_BENCH.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows


def aim_check(rows: list[dict], cuts: list | None, channel: str | None = None) -> dict:
    """결과물 검사 — 자막표 rows(t0·t1 = show)의 원·화살표마다: 대상(aim) 있음 · 원 중심이 대상 상자(프레임마다) 안 · show 가 한 샷 안 · 길이가 벤치 자 안.
    대상이 무엇인지 계획에 없으면 ×(무엇을 가리키는지 모르는 원 = 의미 없는 원). 반환 {ok, n, bad:[…], rows:[…], hold_rule}."""
    HR = hold_rule(channel)
    res, bad = [], []
    bounds = [float(c["t0"]) for c in (cuts or [])[1:]]
    for r in rows:
        for s in r.get("stickers") or []:
            if s.get("kind") not in AIM_KINDS:
                continue
            a, b = float(r["t0"]), float(r["t1"])
            why = []
            A = s.get("aim") or {}
            if not A.get("box") or not A.get("what"):
                why.append(f"대상 없음 — 무엇을 가리키는지 계획에 없다(자리 how={s.get('how')} site={s.get('site')})")
            elif not all(isinstance(s.get(k), (int, float)) for k in ("x", "y")):
                why.append("원 자리(x·y) 없음")
            else:
                cx, cy = float(s["x"]) / 100 * CANVAS[0], float(s["y"]) / 100 * CANVAS[1]
                for f in A.get("frames") or [{"t": a, "box": A["box"]}]:
                    q = f["box"]
                    if not (q[0] <= cx <= q[2] and q[1] <= cy <= q[3]):
                        why.append(f"원 중심({round(cx)},{round(cy)})이 {f['t']}초 대상 '{A['what']}' 상자 {q} 밖")
            if A.get("box"):
                q = A["box"]
                fr = (q[2] - q[0]) * (q[3] - q[1]) / (CANVAS[0] * CANVAS[1])
                if fr > AIM_CIRCLE_FRAC_MAX:
                    why.append(f"대상 상자가 화면 {round(fr * 100, 1)}% — 벤치 원 대상 상한 {int(AIM_CIRCLE_FRAC_MAX * 100)}% 초과(큰 대상은 특징 부위로)")
            cross = [t for t in bounds if a + AIM_EDGE < t < b - AIM_EDGE]
            if cross:
                why.append(f"머무는 구간 {a}~{b} 안에 샷 경계 {cross}")
            if HR["lo"] is not None and not HR["lo"] <= b - a <= HR["hi"]:
                why.append(f"머무는 길이 {round(b - a, 2)}초 — 벤치 자 {HR['lo']}~{HR['hi']}({HR['src']}) 밖")
            res.append({"line": r.get("line"), "text": r.get("text"), "t": [a, b], "what": A.get("what"), "xy": [s.get("x"), s.get("y")], "ok": not why, "why": why})
            if why:
                bad.append(f"{r.get('line')}「{r.get('text')}」 " + " · ".join(why))
    return {"ok": not bad, "n": len(res), "bad": bad, "rows": res, "hold_rule": HR}


# ── 배치에 꽂기 ──────────────────────────────────────────────────────────
LAST_WHY: str | None = None          # 마지막 locate 실패 사유(placement._site 가 감싼 locate 에 last_why 가 없을 때 읽는다)


def locator(video, win=None, caption_band=None, what_of=None, size_of=None, how: str = "claude", t_of=None, detector=None,
            cuts=None, lines: dict | None = None, channel: str | None = None, ask=None):
    """placement.place(locate=…) 함수를 만든다. video = 완성본 화면을 그린 영상(렌더 전이면 창 바탕 base.mp4),
    what_of(row, sticker) → 물건 이름(대본 key·object 칸), size_of(sticker) → (w,h), t_of(row) → 프레임 시각(기본 덩어리 시작+0.1).
    원·화살표(AIM_KINDS)는 aim()(대상·좌표·머무는 시간) — cuts = 화면 컷, lines = {줄: {text, keys}}, channel = 벤치 자 채널, ask = 눈 판정 주입."""
    def locate(target: dict, row: dict, st: dict):
        global LAST_WHY
        if st.get("kind") in AIM_KINDS:
            why: list = []
            L = (lines or {}).get(row.get("line")) or {}
            got = aim(video, row, cuts, win=win, caption_band=caption_band, line_text=L.get("text"), line_keys=L.get("keys") or (),
                      channel=channel, ask=ask, fail=why)
            locate.last_why = None if got else (" · ".join(why) or "사유 없음")
            LAST_WHY = locate.last_why
            return got
        t = t_of(row) if t_of else float(row["t0"]) + 0.1
        what = what_of(row, st) if what_of else (row.get("key") or st.get("word"))
        size = size_of(st) if size_of else (160, 160)
        av = target.get("avoid")
        why: list = []
        got = find(target["kind"], video, t, win=win, avoid=("face",) if av is None else tuple(av), what=what, how=how,   # 빈 목록 = 피할 것 없음
                   size=size, caption_band=caption_band, detector=detector, fail=why, anchor=target.get("anchor"))
        locate.last_why = None if got else (" · ".join(why) or "사유 없음")      # placement._site 가 로그·자막표에 적는다
        LAST_WHY = locate.last_why          # 렌더러가 locate 를 한 번 더 감싸도(render_bench.make_locate) 사유가 닿게
        return got
    locate.last_why = None
    return locate


# ── 적중 표: 샥탬 손 상자(1차 재료 red_circle target) ↔ 검출 ───────────────────────
def hand_cases() -> list[dict]:
    """channel/foreignshowshow/<편>/재료.json 의 red_circle 손 상자 + 그 컷의 원본·크롭 → 완성본 창 프레임을 다시 그린다(창 [0,434,1080,1052])."""
    out = []
    for mp in sorted((ROOT / "channel/foreignshowshow").glob("*/재료.json")):
        d = json.loads(mp.read_text(encoding="utf-8"))
        ef = next((e for e in d.get("effects") or [] if e.get("kind") == "red_circle" and isinstance(e.get("target"), list)), None)
        if not ef or not d.get("cand_dir"):
            continue
        sh = next((s for s in d.get("shots") or [] if s.get("line") == ef["line"]), None)
        if not sh or not sh.get("src_crop"):
            continue
        out.append({"편": mp.parent.name, "src": str(Path(d["cand_dir"]) / sh["src"]), "ss": float(sh["ss"]) + 0.1, "crop": sh["src_crop"],
                    "hand": ef["target"], "what": ef.get("target_what") or ""})
    return out


def hand_canvas(c: dict) -> np.ndarray:
    from PIL import Image
    x, y, w, h = c["crop"]
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{c['ss']:.3f}", "-i", c["src"], "-frames:v", "1", "-vf", f"crop={w}:{h}:{x}:{y},scale=1080:1052",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    if not b:
        raise ValueError(f"원본 프레임 없음 {c['src']}@{c['ss']}")
    can = Image.new("RGB", CANVAS)
    can.paste(Image.open(io.BytesIO(b)).convert("RGB"), (0, 434))
    return np.array(can)


def bench(only: list[str] | None = None, how: str = "claude") -> list[dict]:
    rows = []
    for c in hand_cases():
        if only and not any(o in c["편"] for o in only):
            continue
        if not Path(c["src"]).exists():
            rows.append({"편": c["편"], "skip": f"원본 없음 {c['src']}"}); continue
        rgb = hand_canvas(c)
        what = c["what"].split("—")[0].split("(")[0].strip() or c["what"]
        r = find("object", rgb, win=(0, 434, 1080, 1052), what=what, how=how)
        rows.append({"편": c["편"], "what": what, "hand": c["hand"], "found": r and r["box"], "conf": r and r["conf"],
                     "iou": round(iou(r["box"], c["hand"]), 3) if r else 0.0, "why": r and r["why"]})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    return rows


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return 2
    if a[0] == "find":
        kind, src = a[1], a[2]
        t = float(a[3]) if len(a) > 3 and not a[3].startswith("--") else None
        opt = lambda k: a[a.index(k) + 1] if k in a else None
        win = tuple(int(v) for v in opt("--win").split(",")) if opt("--win") else None
        band = tuple(int(v) for v in opt("--band").split(",")) if opt("--band") else None
        print(json.dumps(find(kind, src, t, win=win, what=opt("--what"), how=opt("--how") or "claude", caption_band=band), ensure_ascii=False))
        return 0
    if a[0] == "bench":
        rows = bench(a[a.index("--only") + 1].split(",") if "--only" in a else None)
        if "--out" in a:
            Path(a[a.index("--out") + 1]).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        hit = [r for r in rows if r.get("iou", 0) >= 0.5]
        print(f"적중(IoU≥0.5) {len(hit)}/{len([r for r in rows if 'skip' not in r])}")
        return 0
    if a[0] == "anchor":          # fx_target.py anchor <판> — 벤치 빨간 원이 입·얼굴 가운데 중 어디(판 rules.stickers.circle_arrow.anchor 근거, 07)
        sys.path.insert(0, str(ROOT))
        from tools.calcopy.hybrid import styles as ST
        rows = bench_anchor(ST.load(a[1]))
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
        from collections import Counter
        print("anchor 표:", dict(Counter(r.get("anchor") for r in rows if r.get("anchor"))))
        return 0
    if a[0] == "bench-aim":       # fx_target.py bench-aim — 벤치 원·화살표가 대상 크기별로 어떻게 그려졌나(오푸스 눈) → channel/칼카피_제작순서/aim_bench.json
        rows = bench_aim()
        print(f"{len([r for r in rows if 'skip' not in r])}/{len(rows)} 잼 → {AIM_BENCH}")
        return 0
    if a[0] == "aim-check":       # fx_target.py aim-check <편 폴더> [판] — 자막표 원·화살표의 대상 좌표·머무는 시간(결과물 검사, 실패면 rc 1)
        doc = Path(a[1])
        zm = json.loads((doc / "자막표.json").read_text(encoding="utf-8"))
        pf = doc / "plan" / "계획_시간표.json"
        cuts = json.loads(pf.read_text(encoding="utf-8"))["timeline"].get("cuts") if pf.exists() else None
        ch = None
        if len(a) > 2 and not a[2].startswith("--"):
            from tools.calcopy.hybrid import styles as ST
            ch = (ST.load(a[2]).get("bench") or {}).get("channel")
        rows = zm["rows"]
        if "--plan" in a and pf.exists():       # 렌더 전: 계획 배치(show = 화면에 머무는 구간)로
            rows = [{**r, "t0": r["show"][0], "t1": r["show"][1]} for r in json.loads(pf.read_text(encoding="utf-8"))["placement"]["rows"]]
        r = aim_check(rows, cuts, ch)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main() or 0)
