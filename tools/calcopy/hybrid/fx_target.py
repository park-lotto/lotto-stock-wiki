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
            out.append({"box": [round(v, 1) for v in b], "conf": f["conf"]})
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


# ── 자막 옆 ──────────────────────────────────────────────────────────────
def caption_side(size, caption_band, win=None, face_boxes=(), why: list | None = None) -> list | None:
    """자막 띠(y0,y1) 바깥 가장 가까운 빈 자리(가운데 정렬, 띠 위 먼저 → 아래) — 얼굴과 겹치거나 창 밖이면 다음 후보, 다 막히면 None.
    why(목록) 를 주면 후보마다 막힌 까닭을 적는다(조용한 실패 금지 — 07 15a9f46ed 쪽지)."""
    w, h = size
    x, y, ww, wh = win or (0, 0, *CANVAS)
    cx = x + ww / 2
    gap = 12
    for side, top in (("위", caption_band[0] - gap - h), ("아래", caption_band[1] + gap)):
        b = [cx - w / 2, top, cx + w / 2, top + h]
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
         size=(160, 160), caption_band=None, detector=None, fail: list | None = None) -> dict | None:
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


# ── 배치에 꽂기 ──────────────────────────────────────────────────────────
LAST_WHY: str | None = None          # 마지막 locate 실패 사유(placement._site 가 감싼 locate 에 last_why 가 없을 때 읽는다)


def locator(video, win=None, caption_band=None, what_of=None, size_of=None, how: str = "claude", t_of=None, detector=None):
    """placement.place(locate=…) 함수를 만든다. video = 완성본 화면을 그린 영상(렌더 전이면 창 바탕 base.mp4),
    what_of(row, sticker) → 물건 이름(대본 key·object 칸), size_of(sticker) → (w,h), t_of(row) → 프레임 시각(기본 덩어리 시작+0.1)."""
    def locate(target: dict, row: dict, st: dict):
        t = t_of(row) if t_of else float(row["t0"]) + 0.1
        what = what_of(row, st) if what_of else (row.get("key") or st.get("word"))
        size = size_of(st) if size_of else (160, 160)
        av = target.get("avoid")
        why: list = []
        got = find(target["kind"], video, t, win=win, avoid=("face",) if av is None else tuple(av), what=what, how=how,   # 빈 목록 = 피할 것 없음
                   size=size, caption_band=caption_band, detector=detector, fail=why)
        locate.last_why = None if got else (" · ".join(why) or "사유 없음")      # placement._site 가 로그·자막표에 적는다
        global LAST_WHY
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
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main() or 0)
