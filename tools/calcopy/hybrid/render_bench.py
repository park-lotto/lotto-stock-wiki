# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 — **벤치 판 공용 렌더러**(키치잇판·꿀템노트판·스타픽룸판 …). 판 설정(styles/<판>.json)만 보고 그린다 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py tools/calcopy/hybrid/render_bench.py <판> <doc_dir> <work_dir> [--plan]
    (보통은 run.py <연예인> render --version <판>)

편 전용 렌더 3벌(channel/kitchit/…/render_kitchit.py · channel/kkultemnote/…/render_kkt.py · channel/starpickroom/hybrid/render_spr.py)의 공통을 뽑았다.
같은 판단 두 벌 금지:
  · 시각 = timeline() 한 곳(줄 이어 붙이기·자막 덩어리 시각·컷)            · 나레 = render_itssum.tts_once/make_sentences(Typecast·미나 서버 합성 캐시)
  · 자막·효과 배치 = placement.place() 한 곳(벤치 줄판독 빈도)              · 자막 그리기 = scene_style.compose(자막팩 길) — PNG 자막 없음
  · 자막표 → 비트 = tools/caption_pack/check_bench_packs.rows_to_timeline(자막팩 쪽 견본 그대로)
  · 틀 그림 = frame_png() 한 곳(판 설정 frame 칸) · 마스터 = −14 LUFS 2단 loudnorm(판 설정 loudness)

대본.json: slug · title_lines [[[글, 'hi'|null|'#hex'], …], …] · source_label · (comment{text,likes,from,to}) ·
  lines[{id, kind:'tts', tts, caps[{text, key?, key_color?, object_src?} | 글]} | {id, kind:'orig', src, spans[[a,b]…] | span, caps_rel[[글, s0, s1, key?]…]}]
재료.json: cand_dir · cuts{줄 id: [{src, ss?, crop[x,y,w,h] | 'face', w?, at?, max?, move?, see}]} · blur{src: [[x,y,w,h(,a,b)]…]}(원본에 박힌 글 흐림 — 잘라서 피하지 말고)
  tts 줄 = w(무게) 비례로 줄 칸 [시작, 다음 줄 시작) 을 나눔 · orig 줄 = at(줄 시작부터 초), ss 를 안 적으면 원음 구간에 입을 맞춘 초 · 비어 있으면 구간마다 얼굴 크롭 한 컷
출력(work/render/): final.mp4 · timeline.json · 자막표.json(배치 결과) · render_info.json · (doc) final_sheet_1s.jpg
"""
from __future__ import annotations

import json
import math
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import FACE_MODEL, FPS, ROOT, SR, StageError, dur_of, jload, jsave, lufs, nchar, probe, run  # noqa: E402

W, H = 1080, 1920
FONTS = ROOT / "shopping_shorts/static/fonts"
SFX_DIR = ROOT / "shopping_shorts/assets/sfx_packs"
BGM_DIR = ROOT / "shopping_shorts/assets/bgm_lib"
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
CAP_EXTRA = ("key", "key_color", "object_src", "aside", "append", "sound", "small")   # 대본 caps 덩어리 칸 → 배치(placement)가 읽는다


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) if isinstance(c, str) else tuple(c)


def _font(name, px):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / name), int(px))


def caps_of(L: dict) -> list[dict]:
    """줄 자막 덩어리 → [{text, key?, …}] (글만 적은 꼴도 받는다)."""
    if L["kind"] == "orig":
        out = []
        for c in L.get("caps_rel") or []:
            d = {"text": c[0], "s0": float(c[1]), "s1": float(c[2])}
            if len(c) > 3 and c[3]:
                d["key"] = c[3]
            out.append(d)
        return out
    return [c if isinstance(c, dict) else {"text": c} for c in L.get("caps") or []]


def spans_of(L: dict) -> list[list[float]]:
    return [list(s) for s in (L.get("spans") or [L["span"]])]


# ── 시간표(판단 주인) ───────────────────────────────────────────────────
def gap_between(st: dict, prev: str | None, cur: str) -> float:
    T = st.get("timing") or {}
    if prev is None:
        return 0.0
    if prev == "orig" and cur == "orig" and "gap_oo" in T:
        return T["gap_oo"]
    key = "gap_after_tts" if prev == "tts" else "gap_after_orig"
    return T.get(key, T.get("gap", 0.1))


def narr_cap_starts(L: dict, sent: dict | None, align: dict | None, tts_char0: int) -> list[float]:
    """나레 덩어리 시작(줄 시작부터 초). 글자 시각(align)이 있으면 그 덩어리 첫 글자의 소리 시각(배속·앞자르기 갚음),
    없으면 글자 수 비례. 자막 글(숫자 표기)과 tts 글(한글 읽기)이 다르면 덩어리 비율로 tts 글자 자리를 잡는다."""
    caps = caps_of(L)
    w = [max(1, nchar(c["text"])) for c in caps]
    dur = sent["dur"] if sent else sum(w) / 7.0
    if not (sent and align):
        acc, out = 0, []
        for x in w:
            out.append(round(dur * acc / sum(w), 3)); acc += x
        return out
    ch, st = align["characters"], align["character_start_times_seconds"]
    idx = [i for i, c in enumerate(ch) if re.match(r"[가-힣A-Za-z0-9]", c)]
    n_line = nchar(L["tts"])
    out, acc = [], 0
    for j, x in enumerate(w):
        if j == 0:
            out.append(0.0)
        else:
            k = tts_char0 + round(acc / sum(w) * n_line)
            k = min(k, len(idx) - 1)
            t_raw = float(st[idx[k]])
            x0 = max(0.0, sent["raw"][0] - 0.02)
            out.append(round(max(0.0, min(dur - 0.15, (t_raw - x0) / sent["tempo"])), 3))
        acc += x
    return out


def timeline(S: dict, M: dict, st: dict, sent: dict | None, align: dict | None) -> dict:
    """sent = {줄 id: {dur, raw, tempo}} (None 이면 글자÷cps 어림). 반환 = lines(줄 시각)·rows(자막 덩어리)·cuts(화면)·opos(원음 조각)·end."""
    t, prev, lines, rows, opos, char0 = 0.0, None, {}, [], [], 0
    est = st.get("cps_target", 7.0)
    for L in S["lines"]:
        t += gap_between(st, prev, L["kind"])
        if L["kind"] == "orig":
            t0 = t
            for k, (a, b) in enumerate(spans_of(L)):
                opos.append({"line": L["id"], "k": k, "src": L["src"], "span": [a, b], "t0": round(t, 3), "t1": round(t + b - a, 3)})
                t += b - a
            lines[L["id"]] = [round(t0, 3), round(t, 3)]
            for j, c in enumerate(caps_of(L)):
                rows.append({"line": L["id"], "j": j, "speaker": "orig", "text": c["text"], "t0": round(t0 + c["s0"], 3), "t1": round(t0 + c["s1"], 3),
                             **{k: c[k] for k in CAP_EXTRA if c.get(k)}})
        else:
            s = (sent or {}).get(L["id"])
            d = s["dur"] if s else round(nchar(L["tts"]) / est, 3)
            lines[L["id"]] = [round(t, 3), round(t + d, 3)]
            starts = narr_cap_starts(L, s, align, char0)
            caps = caps_of(L)
            for j, c in enumerate(caps):
                a = t + starts[j]
                b = t + (starts[j + 1] if j + 1 < len(caps) else d)
                rows.append({"line": L["id"], "j": j, "speaker": "narr", "text": c["text"], "t0": round(a, 3), "t1": round(b, 3),
                             **{k: c[k] for k in CAP_EXTRA if c.get(k)}})
            char0 += nchar(L["tts"])
            t += d
        prev = L["kind"]
    end = round(t + (st.get("timing") or {}).get("tail", 0.35), 3)
    end = round(round(end * FPS) / FPS, 4)
    order = [L["id"] for L in S["lines"]]
    Lm = {L["id"]: L for L in S["lines"]}
    cuts = []
    for i, lid in enumerate(order):
        a = lines[lid][0]
        nxt = lines[order[i + 1]][0] if i + 1 < len(order) else end
        L = Lm[lid]
        cs = (M.get("cuts") or {}).get(lid)
        if L["kind"] == "orig":
            if not cs:
                cs = [{"at": round(p["t0"] - a, 3), "src": p["src"], "ss": p["span"][0], "crop": "face", "see": "원음 구간(자동 얼굴 크롭)"}
                      for p in opos if p["line"] == lid]
            for c in cs:
                c0 = a + float(c.get("at", 0.0))
                ss = c.get("ss")
                if ss is None:      # 입 맞춤: 그 시각에 들리는 원음 조각의 원본 초
                    p = next((p for p in opos if p["line"] == lid and p["t0"] - 1e-3 <= c0 < p["t1"]), None)
                    if not p:
                        raise StageError(f"{lid} 컷 at {c.get('at')} 가 원음 조각 밖")
                    ss = round(p["span"][0] + (c0 - p["t0"]), 3)
                cuts.append({**c, "line": lid, "ss": ss, "src": c.get("src", L["src"]), "t0": round(c0, 3), "kind": "orig"})
        else:
            if not cs:
                raise StageError(f"재료.json cuts 에 나레 줄 {lid} 컷이 없다")
            ws = [float(c.get("w", 1)) for c in cs]
            acc = 0.0
            for c, w in zip(cs, ws):
                c0 = a + float(c["at"]) if "at" in c else a + (nxt - a) * acc / sum(ws)
                cuts.append({**c, "line": lid, "t0": round(c0, 3), "kind": "tts"})
                acc += w
    cuts[0]["t0"] = 0.0
    src_dir = Path(M["cand_dir"]) if M.get("cand_dir") else None
    for i, c in enumerate(cuts):
        c["t1"] = cuts[i + 1]["t0"] if i + 1 < len(cuts) else end
        c["dur"] = round(c["t1"] - c["t0"], 3)
        c["over"] = round(c["dur"] - c["max"], 3) if c.get("max") is not None and c["dur"] > c["max"] else 0.0
        if src_dir and c["kind"] == "tts" and c.get("ss") is not None and not c.get("no_snap"):
            s2 = snap_ss(src_dir / c["src"], float(c["ss"]), (round(c["t1"] * FPS) - round(c["t0"] * FPS)) / FPS)   # 실제 뽑을 프레임 길이로      # 원음 컷은 입 맞춤이라 옮기지 않는다(검사만)
            if s2 != float(c["ss"]):
                c["ss_planned"], c["ss"] = c["ss"], s2
        if src_dir:
            left = src_left(src_dir / c["src"], float(c.get("ss") or 0.0))
            if left is not None and c["dur"] > left:
                c["src_left"] = left
                c["over"] = max(c["over"], round(c["dur"] - left, 3))
    for i, r in enumerate(rows):      # 자막은 다음 덩어리 시작까지(줄 사이 틈도 앞 자막이 덮는다 — 벤치: 자막 없는 틈 거의 없음)
        r["show"] = [r["t0"], round(rows[i + 1]["t0"] if i + 1 < len(rows) else end, 3)]
    return {"lines": lines, "rows": rows, "cuts": cuts, "opos": opos, "end": end}


# ── 틀 그림(판단 주인: 판 설정 frame) ─────────────────────────────────────
def frame_png(S: dict, st: dict, out: Path) -> Path:
    """검정 바탕 + 제목 줄들(낱말 색·기울임·박스) + 로고 + 출처 + 워터마크, 창 자리는 투명."""
    from PIL import Image, ImageDraw
    F = st["frame"]
    im = Image.new("RGBA", (W, H), _rgb(F.get("bg", [0, 0, 0])) + (255,))
    x, y, w, h = F["window"]
    im.paste((0, 0, 0, 0), (x, y, x + w, y + h))
    d = ImageDraw.Draw(im)
    for spec, segs in zip(F["title"], S["title_lines"]):
        segs = [(s, None) if isinstance(s, str) else (s[0], s[1] if len(s) > 1 else None) for s in segs]
        col = lambda c: _rgb(spec["hi"]) if c == "hi" else (_rgb(c) if c else _rgb(spec["color"]))
        px = spec["px"]
        while True:
            f = _font(spec["font"], px)
            tw = sum(f.getlength(t) for t, _ in segs)
            if tw <= spec.get("max_w", 1000) or px <= 50:
                break
            px -= 2
        asc, desc = f.getmetrics()
        pad = int(px * 0.5)
        sh = float(spec.get("shear") or 0)
        lay = Image.new("RGBA", (int(tw) + 2 * pad + int((asc + desc) * sh), asc + desc + 2 * pad), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        xx = pad + int((asc + desc) * sh * 0.5)
        for t, c in segs:
            dl.text((xx, pad), t, font=f, fill=col(c) + (255,))
            xx += f.getlength(t)
        if sh:
            lay = lay.transform(lay.size, Image.AFFINE, (1, sh, -sh * lay.size[1] * 0.5, 0, 1, 0), resample=Image.BICUBIC)
        bb = lay.getbbox()
        lay = lay.crop(bb)
        if spec.get("box"):
            bx = spec["box"]
            d.rectangle(bx, fill=_rgb(spec["box_color"]) + (255,))
            top = (bx[1] + bx[3]) // 2 - lay.size[1] // 2
        elif "center" in spec:
            top = spec["center"] - lay.size[1] // 2
        else:
            top = spec["ink_top"]
        im.alpha_composite(lay, (W // 2 - lay.size[0] // 2, int(top)))
    C = F.get("credit")
    if C and S.get("source_label"):
        f = _font(C["font"], C["px"])
        bb = d.textbbox((0, 0), S["source_label"], font=f)
        top = C["ink_top"] - bb[1] if "ink_top" in C else C["center"] - (bb[1] + bb[3]) // 2
        d.text((W // 2 - (bb[2] - bb[0]) // 2 - bb[0], top), S["source_label"], font=f, fill=_rgb(C["color"]))
    WM = F.get("watermark")
    if WM:
        f = _font(WM["font"], WM["px"])
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        bb = f.getbbox(WM["text"])
        dl.text((WM["x1"] - f.getlength(WM["text"]), WM["cy"] - (bb[1] + bb[3]) // 2), WM["text"], font=f, fill=(255, 255, 255, WM["alpha"]))
        im.alpha_composite(lay)
    LG = F.get("logo")
    if LG and LG.get("kind") == "spr_gold":
        sys.path.insert(0, str(ROOT / "channel/starpickroom/_tools"))
        import spr_overlay
        spr_overlay.logo_layer(im, LG["text"])
    elif LG:
        f = _font(LG["font"], LG["px"])
        lay = Image.new("RGBA", (W, 160), (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((LG["x"], 10), LG["text"], font=f, fill=tuple(LG["rgba"]), stroke_width=LG.get("stroke", 0), stroke_fill=tuple(LG.get("stroke_rgba", [0, 0, 0, 255])))
        im.alpha_composite(lay, (0, LG["y"] - 10))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def comment_png(C: dict, px: int, out: Path) -> tuple[int, int]:
    """유튜브 댓글 카드(꿀템노트 벤치 m0Ex·KCx 실측: 흰 상자, 글 검정, 아래 줄 엄지·숫자·'답글')."""
    from PIL import Image, ImageDraw
    f, fs = _font("Pretendard-Regular.otf", px), _font("Pretendard-Regular.otf", 28)
    try:
        from PIL import ImageFont
        sym = ImageFont.truetype("C:/Windows/Fonts/segmdl2.ttf", 32)
    except OSError:
        sym = fs
    w = int(min(980, f.getlength(C["text"]) + 44)); h = 142
    im = Image.new("RGBA", (w, h), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
    d.text((20, 14), C["text"], font=f, fill=(15, 15, 15))
    d.text((20, 86), "\ue8e1", font=sym, fill=(30, 30, 30))
    d.text((66, 88), str(C.get("likes", "")), font=fs, fill=(96, 96, 96))
    d.text((130, 86), "\ue8e0", font=sym, fill=(30, 30, 30))
    d.text((210, 88), "답글", font=fs, fill=(30, 30, 30))
    im.save(out)
    return w, h


# ── 화면 ────────────────────────────────────────────────────────────────
_det = None


def face_crop(src: Path, t: float, ar: float) -> list[int]:
    """그 프레임의 가장 큰 얼굴을 가운데로 둔 ar(가로/세로) 크롭 — 높이는 원본 전체."""
    import cv2
    global _det
    sw, sh, _ = probe(src)
    ch = sh; cw = int(round(ch * ar)); cw = min(cw, sw)
    if cw == sw:
        ch = int(round(sw / ar))
    cap = cv2.VideoCapture(str(src)); cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, f = cap.read(); cap.release()
    cx = sw / 2
    if ok:
        if _det is None:
            _det = cv2.FaceDetectorYN.create(FACE_MODEL, "", (320, 320), 0.6, 0.3, 50)
        _det.setInputSize((f.shape[1], f.shape[0]))
        _, faces = _det.detect(f)
        if faces is not None and len(faces):
            fx, fy, fw, fh = max(faces, key=lambda z: z[2] * z[3])[:4]
            cx = fx + fw / 2
    x = int(min(max(cx - cw / 2, 0), sw - cw))
    return [x, 0, cw, ch]


BLUR_SIGMA = 25.0     # 가림 흐림 세기 = 제품 가림막 흐림의 최저값(deco_frame.blur_sigma 25~80)과 같은 gblur


def blur_vf(regs, ss: float, dur: float, sigma: float = BLUR_SIGMA) -> str:
    """원본에 박힌 자막·글 자리를 흐린다(원본 픽셀 좌표, 잘라 내기 전). regs = [[x, y, w, h(, a, b)], …], a~b = 원본 초(없으면 늘).
    10-22 사장님 "자막을 가리려고 확대를 많이 해서 너무 커지거나 가운데로 안 간다 → 가림막 흐림으로": 잘라서 피하던 걸 흐림으로 바꾼다.
    흐림은 제품 렌더(video_assemble)와 같은 gblur — 다만 여기는 원본 좌표라 마스크 그림 대신 사각 영역(crop→gblur→overlay)."""
    out = []
    for r in regs or []:
        x, y, w, h = (int(v) for v in r[:4])
        a, b = (float(r[4]), float(r[5])) if len(r) >= 6 else (None, None)
        if a is not None and (b <= ss or a >= ss + dur):
            continue                                           # 이 컷 구간과 안 겹침
        en = f":enable='between(t,{max(0.0, a - ss):.3f},{b - ss:.3f})'" if a is not None else ""
        out.append(f"split[bo][bi];[bi]crop={w}:{h}:{x}:{y},gblur=sigma={sigma}[bb];[bo][bb]overlay={x}:{y}{en}")
    return ",".join(out)


_src_len: dict[str, float] = {}


def src_left(src: Path, ss: float) -> float | None:
    """원본 영상에서 ss 뒤로 남은 화면 초(마지막 프레임 하나 뺌). 사진은 None(얼마든 늘린다).
    10-23 사장님 "뒤에 멈추거나 중간중간 튄다": 컷이 원본 끝을 넘으면 clip 이 n프레임보다 적게 뽑고, 뒤 컷이 전부 앞당겨져
    (09 딸기라떼 27프레임 = 0.9초 어긋남) 끝 화면이 멈췄다. 그때까지 아무 검사도 안 걸렸다(05·08·09·11 네 편)."""
    if src.suffix.lower() in IMG_EXT or not src.exists():
        return None
    k = str(src)
    if k not in _src_len:
        out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration:format=duration", "-of", "json", src]).stdout
        j = json.loads(out)
        d = (j.get("streams") or [{}])[0].get("duration") or (j.get("format") or {}).get("duration")
        _src_len[k] = float(d)
    return round(_src_len[k] - ss - 1 / FPS, 3)


SLIVER_SEC = 0.2      # 컷 처음·끝 이 안에 장면 경계가 있으면 '번쩍임'(앞뒤 샷이 몇 프레임 끼어 튀어 보인다)
_shots: dict[str, list] = {}


def shot_starts(video: Path) -> list[float]:
    """영상의 장면 경계(새 샷이 시작하는 초, 30fps 격자). 프레임 차(108폭 회색 평균) > max(25, 중앙값×4).
    10-23 사장님 "중간중간 튄다": 원본이 1초 안팎 잘린 쇼츠라 컷 끝에 이웃 샷 1~5프레임이 끼었다(02 c09 웹페이지 3프레임 등)."""
    import subprocess
    import numpy as np
    k = str(video)
    if k not in _shots:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", k, "-vf", f"fps={FPS},scale=108:192,format=gray", "-f", "rawvideo", "-"],
                             capture_output=True, stdin=subprocess.DEVNULL).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, 192, 108).astype(np.int16)
        d = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2)) if len(fr) > 1 else np.zeros(0)
        lim = max(25.0, 4 * float(np.median(d))) if len(d) else 25.0
        _shots[k] = [round((i + 1) / FPS, 4) for i, x in enumerate(d) if x > lim]
    return _shots[k]


def slivers(starts: list[float], a: float, b: float, edge: float = SLIVER_SEC) -> list[float]:
    """구간 [a,b) 안 경계 중 처음·끝 edge 안에 있는 것."""
    return [s for s in starts if a + 1e-3 < s < b - 1e-3 and (s - a < edge - 1e-3 or b - s < edge - 1e-3)]      # 딱 0.2초(6프레임)는 통과


def snap_ss(src: Path, ss: float, dur: float, reach: float = 0.4) -> float:
    """나레 컷 시작 초를 ±reach 안에서 가장 덜 움직여 번쩍임 없는 자리로(원본 끝도 넘지 않게). 못 찾으면 그대로(검사가 잡는다)."""
    if src.suffix.lower() in IMG_EXT or not src.exists():
        return ss
    st = shot_starts(src)
    if not slivers(st, ss, ss + dur):
        return ss
    for k in range(1, int(reach * FPS) + 1):
        for s in (ss + k / FPS, ss - k / FPS):
            left = src_left(src, s)
            if s >= 0 and (left is None or dur <= left) and not slivers(st, s, s + dur):
                return round(s, 3)
    return ss


def count_frames(p: Path) -> int:
    return int(run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                    "-of", "csv=p=0", p]).stdout.strip() or 0)


def clip(src: Path, ss: float, n: int, crop, win: tuple[int, int], out: Path, push: float = 0.0, move=None, blur=None):
    ww, wh = win
    if src.suffix.lower() in IMG_EXT:
        from tools.calcopy import narr_video as nv
        x, y, cw, ch = crop
        mv = nv.still_move(src, crop, ww / wh, n / FPS, move or "in")
        # 사진(JPG)은 yuvj420p·pc·bt470bg 로 나온다 → 영상 조각(yuv420p·tv·bt709)과 이어 붙이면 render_base 가 그 경계에서
        # 필터를 다시 세우며 틀(제목·로고·출처 줄)을 2~4프레임 빠뜨린다(10-21 장윤주 실측: 쿠팡 사진 컷 앞뒤 2+4프레임 → 고친 뒤 0.
        # 최화정_피부 완성본에도 제목 빠짐 2+2프레임이 있었다 — 원인 대조는 안 함). 영상 조각과 같은 꼴로 맞춘다.
        vf = (f"crop={cw}:{ch}:{x}:{y},{mv}scale={ww}:{wh}:flags=lanczos:out_range=tv:out_color_matrix=bt709,"
              f"format=yuv420p,setsar=1")
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", src, "-vf", vf, "-frames:v", n, "-r", FPS, "-c:v", "libx264", "-crf", "16",
             "-preset", "veryfast", "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", out])
        return
    x, y, cw, ch = crop
    bl = blur_vf(blur, ss, n / FPS)
    pre = bl + "," if bl else ""
    vf = f"{pre}crop={cw}:{ch}:{x}:{y},scale={ww}:{wh}:flags=lanczos,setsar=1,fps={FPS}"
    if push:
        vf = (f"{pre}crop={cw}:{ch}:{x}:{y},scale={ww * 2}:{wh * 2}:flags=lanczos,fps={FPS},"
              f"zoompan=z='1+{push}*on/{max(1, n)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={ww}x{wh}:fps={FPS},setsar=1")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ss:.3f}", "-i", src, "-an", "-vf", vf, "-frames:v", n, "-c:v", "libx264", "-crf", "16",
         "-preset", "veryfast", "-pix_fmt", "yuv420p", out])


def render_window(T: dict, M: dict, st: dict, R: Path) -> Path:
    src_dir = Path(M["cand_dir"])
    x, y, ww, wh = st["frame"]["window"]
    parts = R / "parts"; shutil.rmtree(parts, ignore_errors=True); parts.mkdir(parents=True)
    lst = []
    for k, c in enumerate(T["cuts"]):
        n = round(c["t1"] * FPS) - round(c["t0"] * FPS)
        c["frames"] = n
        src = src_dir / c["src"]
        crop = c.get("crop", "face")
        if src.suffix.lower() in IMG_EXT and not (isinstance(crop, list) and len(crop) == 4):
            # 사진 재료(쿠팡 상품 사진)는 얼굴 크롭·시작 초가 없다 — 창 비율로 가운데를 자른다(10-22 강주은: 사진 컷에 ss·crop 없음 → KeyError 'ss' 로 렌더 멈춤)
            iw, ih = probe(src)[:2]
            cw = min(iw, round(ih * ww / wh)); chh = min(ih, round(cw * wh / ww))
            crop = [(iw - cw) // 2, (ih - chh) // 2, cw, chh]
            c["crop_used"] = crop
        elif crop == "face":
            crop = face_crop(src, float(c.get("ss") or 0.0) + min(0.5, c["dur"] / 2), ww / wh)
            c["crop_used"] = crop
        push = (st.get("cuts") or {}).get("push_orig" if c["kind"] == "orig" else "push_tts", 0.0)
        p = parts / f"c{k:02d}.mp4"
        clip(src, float(c.get("ss", 0.0)), n, crop, (ww, wh), p, push=float(c.get("push", push)), move=c.get("move"),
             blur=(M.get("blur") or {}).get(c["src"]))
        got = count_frames(p)
        if got != n:      # 모자라면 뒤 컷이 전부 앞당겨지고 끝이 멈춘다 — 조용히 넘기지 않는다
            raise StageError(f"컷 조각 프레임 모자람: {c['line']} {c['src']}@{c.get('ss')} 계획 {n} · 실제 {got}")
        lst.append(f"file '{p.as_posix()}'")
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    win = R / "window.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", parts / "list.txt", "-c", "copy", win])
    return win


def render_base(S: dict, T: dict, st: dict, placed: dict, R: Path, win: Path) -> Path:
    """틀 + 창 + 댓글 카드 + 번쩍임(자막 없는 바탕)."""
    F = st["frame"]
    x, y, ww, wh = F["window"]
    png = frame_png(S, st, R / "frame.png")
    n = sum(c["frames"] for c in T["cuts"])
    end = n / FPS
    ins = ["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={end:.3f}", "-i", win, "-loop", "1", "-t", f"{end:.3f}", "-i", png]
    fc = f"[0:v][1:v]overlay={x}:{y}:shortest=0[a];[a][2:v]overlay=0:0[b]"
    last = "b"
    C = placed.get("comment")
    if C:
        cw, ch = comment_png(C, F["comment"]["px"], R / "comment.png")
        ins += ["-loop", "1", "-t", f"{end:.3f}", "-i", R / "comment.png"]
        fc += f";[b][3:v]overlay={(W - cw) // 2}:{F['comment']['bottom'] - ch}:enable='between(t,{C['t0']:.3f},{C['t1']:.3f})'[c]"
        last = "c"
    fl = placed.get("flashes") or []
    if fl:
        dsec = F.get("flash_sec", 0.1)
        e = "+".join(f"between(T,{t:.3f},{t + dsec:.3f})*(1-(T-{t:.3f})/{dsec})" for t in fl)
        fc += f";[{last}]geq=lum='min(255,lum(X,Y)+255*({e}))':cb='cb(X,Y)':cr='cr(X,Y)'[f]"
        last = "f"
    out = R / "base.mp4"
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", fc + f";[{last}]format=yuv420p[v]", "-map", "[v]", "-frames:v", n, "-r", FPS,
         "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", out])
    return out


# ── 자막(자막팩 길) ──────────────────────────────────────────────────────
def caption_rows(placed: dict, st: dict) -> list[dict]:
    """배치 결과 → 자막팩 견본(check_bench_packs.rows_to_timeline) 공통 줄 꼴. 타이핑 덩어리는 글자 시각(판 caption.typing_cps)."""
    cps = float(st["caption"].get("typing_cps", 10.0))
    out = []
    for r in placed["rows"]:
        a, b = r["show"]
        row = {"line": r["line"], "t0": a, "t1": b, "text": r["text"], "speaker": r["speaker"], "variant": r.get("variant") or "",
               "emph": r.get("emph") or [], "sticker": "", "stickers": []}
        for s in r.get("stickers") or []:
            if s["kind"] == "heart":
                row["sticker"] = "heart"
            elif s["kind"] != "comment_card":
                row["stickers"].append({k: v for k, v in s.items() if k != "follow"})
        if r["enter"] == "typing":
            n = len(r["text"].replace(" ", ""))
            step = min(1.0 / cps, (b - a) * 0.85 / max(1, n))
            row["chars"] = [round(a + k * step, 3) for k in range(n)]
        out.append(row)
    return out


def snapshot(pack: str) -> dict:
    from shopping_shorts import scene_style
    return scene_style.validate_snapshot({"version": 1, "mode": "story", "plainCaption": 2, "presetId": "plain", "sceneIndex": 0, "frameKind": "body",
                                          "frameRule": "body_all", "text": {"channel": "", "hook1": "", "hook2": "", "bodyTitle": ""},
                                          "captionPack": pack, "motionPack": "off", "wordFx": {"style": "mark", "color": "", "grow": ""}})


def burn_captions(base: Path, rows: list[dict], st: dict, R: Path, end: float) -> Path:
    from shopping_shorts import scene_style
    from tools.caption_pack.check_bench_packs import rows_to_timeline
    tts = R / "silence.wav"
    if not tts.exists():
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", "1", tts])
    tl = rows_to_timeline(rows, tts, end)
    jsave(R / "caption_timeline.json", tl)
    out = R / "captioned.mp4"
    shutil.rmtree(R / "cw", ignore_errors=True)
    scene_style.compose(str(base), tl, snapshot(st["caption"]["pack"]), str(out), R / "cw", {"text": ""})
    return out


# ── 소리 ────────────────────────────────────────────────────────────────
def audio(S: dict, M: dict, st: dict, T: dict, sent: list[dict], placed: dict, R: Path) -> tuple[Path, dict]:
    src_dir = Path(M["cand_dir"])
    end = T["end"]
    pieces = []
    for s in sent:
        pieces.append((s["wav"], T["lines"][s["id"]][0], "narr"))
    for k, p in enumerate(T["opos"]):
        a, b = p["span"]
        w = R / f"o_{k}.wav"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src_dir / p["src"], "-vn", "-ac", "1", "-ar", SR,
             "-af", f"highpass=f=90,afade=t=in:d=0.015,afade=t=out:st={max(0, b - a - 0.02):.3f}:d=0.02", w])
        pieces.append((str(w), p["t0"], "orig"))

    def cat(kind):
        ps = [p for p in pieces if p[2] == kind]
        if not ps:
            return None, float("nan")
        o = R / f"cat_{kind}.wav"
        run(["ffmpeg", "-y", "-v", "error", *[x for p in ps for x in ("-i", p[0])], "-filter_complex",
             "".join(f"[{i}:a]" for i in range(len(ps))) + f"concat=n={len(ps)}:v=0:a=1[o]", "-map", "[o]", "-ar", SR, o])
        return o, lufs(o)[0]
    _, nI = cat("narr")
    _, oI = cat("orig")
    og = round(nI - oI, 2) if not math.isnan(oI) and not math.isnan(nI) else 0.0      # 원음 = 나레와 같은 크기
    ins, fc = [], []
    for k, (p, t, kind) in enumerate(pieces):
        ins += ["-i", p]
        fc.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=mono,volume={og if kind == 'orig' else 0}dB,adelay={int(round(t * 1000))}[p{k}]")
    fc.append("".join(f"[p{k}]" for k in range(len(pieces))) + f"amix=inputs={len(pieces)}:normalize=0,apad,atrim=0:{end:.3f}[n]")
    voice = R / "voice.wav"
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[n]", "-ar", SR, voice])
    B = st["bgm"]
    bgm = BGM_DIR / f"{S.get('bgm', {}).get('id') or B['id']}.mp3"
    bI = lufs(bgm)[0]
    g = round((nI - B["db_below_voice"]) - bI, 2)
    k = 10 ** (float(B.get("duck_orig_db", 0.0)) / 20)
    duck = "+".join(f"between(t,{p['t0']:.3f},{p['t1']:.3f})" for p in T["opos"]) or "0"
    ins2 = ["-i", voice, "-stream_loop", "-1", "-i", bgm]
    fc2 = [f"[1:a]aresample={SR},aformat=channel_layouts=mono,atrim=0:{end:.3f},asetpts=PTS-STARTPTS,volume={g}dB,"
           f"volume='if({duck},{k:.4f},1)':eval=frame,afade=t=out:st={end - B.get('fade_out', 0.4):.3f}:d={B.get('fade_out', 0.4)}[b]"]
    mix_in = "[0:a][b]"
    SF = st.get("sfx_files") or {}
    for j, e in enumerate(placed.get("sfx") or []):
        f = SFX_DIR / SF.get(e["kind"], f"팩01/{e['kind']}.wav")
        ins2 += ["-i", f]
        fc2.append(f"[{j + 2}:a]aresample={SR},aformat=channel_layouts=mono,volume={SF.get('gain_db', -8)}dB,adelay={int(round(e['t'] * 1000))}[s{j}]")
        mix_in += f"[s{j}]"
    n_in = 2 + len(placed.get("sfx") or [])
    fc2.append(f"{mix_in}amix=inputs={n_in}:normalize=0:duration=first[o]")
    raw = R / "mix_raw.wav"
    run(["ffmpeg", "-y", "-v", "error", *ins2, "-filter_complex", ";".join(fc2), "-map", "[o]", "-ar", SR, raw])
    mix = R / "mix.wav"
    loud(raw, mix, st["loudness"])
    return mix, {"narr_lufs": nI, "orig_lufs": oI, "orig_gain": og, "bgm_gain": g, "mix": lufs(mix)}


def loud(src: Path, dst: Path, L: dict):
    """2단 loudnorm(측정 → 선형 맞춤) — 판 설정 loudness(−14 LUFS · TP).
    올릴 양만큼 최고점이 TP 를 넘으면 ffmpeg 가 선형을 버리고 동적으로 가 목표에 못 미친다(김나영 꿀템노트판 −21.6/−0.8 → −15.2).
    그때는 먼저 올리고 리미터로 최고점을 눌러 둔 뒤 선형 맞춤."""
    import json as _j
    I, TP = L["lufs"], L["tp"]
    pi, ptp = lufs(src)
    if ptp + (I - pi) > TP:
        pre = Path(dst).with_name(Path(dst).stem + "_lim.wav")
        run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af",
             f"volume={I - pi:.2f}dB,alimiter=limit={10 ** ((TP - 1.0) / 20):.4f}:attack=2:release=50:level=disabled", "-ar", SR, pre])
        src = pre
    m = run(["ffmpeg", "-hide_banner", "-i", src, "-af", f"loudnorm=I={I}:TP={TP}:LRA=11:print_format=json", "-f", "null", "-"], check=False).stderr
    j = _j.loads(m[m.rindex("{"):m.rindex("}") + 1])
    af = (f"loudnorm=I={I}:TP={TP}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample={SR}")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af", af, "-ar", SR, dst])


# ── 전체 ────────────────────────────────────────────────────────────────
def plan_rows(S: dict, T: dict, st: dict) -> dict:
    """배치(placement.place) — 씨앗 = 편 slug(같은 편은 늘 같은 배치)."""
    from tools.calcopy.hybrid import placement as PL
    placed = PL.place(T["rows"], st, S.get("slug") or "x")
    for r, t in zip(placed["rows"], T["rows"]):
        r["show"] = t["show"]
    # 댓글 카드 = 배치가 고르고(벤치 편 비율) 대본에 원본 댓글이 있을 때만
    C = S.get("comment")
    rule = (st["placement"]["rules"].get("stickers") or {}).get("comment_card")
    cnt = (st["placement"].get("counted") or {}).get("stickers", {}).get("comment_card", {})
    if C and rule and PL._chance(S.get("slug") or "x", "sticker:comment_card") < float(cnt.get("videos", rule.get("share", 0.6))):
        t0 = T["lines"][C["from"]][0] if C.get("from") in T["lines"] else T["end"] / 2
        t1 = T["end"] if C.get("to", "end") == "end" else T["lines"][C["to"]][0]
        placed["comment"] = {**C, "t0": t0, "t1": t1}
        placed["log"].append(f"댓글 카드 {t0:.2f}~{t1:.2f}")
    return placed


def render(style_name: str, doc: Path, work: Path, plan_only: bool = False, log=print, tts: bool = False) -> dict:
    from tools.calcopy.hybrid import render_itssum as RI
    from tools.calcopy.hybrid import styles as ST
    st = ST.load(style_name)
    doc, work = Path(doc), Path(work)
    S, M = jload(doc / "대본.json"), jload(doc / "재료.json")
    S.setdefault("voice", {k: st["voice"][k] for k in ("name", "voice_id") if k in st["voice"]})
    S.setdefault("cps_target", st.get("cps_target", 7.0))
    R = work / "render"; R.mkdir(parents=True, exist_ok=True)
    if plan_only:
        sm = align = None
        if tts:      # 계획 때 진짜 목소리 길이로(10-22 선우용여: 어림으로 통과 → 렌더에서 '컷이 원본 샷보다 길다' 2번·완성본 길이 넘침으로 렌더 3번). 합성은 캐시 — 렌더가 그대로 쓴다
            tts_S = {**S, "lines": [l for l in S["lines"] if l["kind"] == "tts"]}
            full, align = RI.tts_once(tts_S, R, log)
            sent, _, _ = RI.make_sentences(tts_S, full, R, log, align=align)
            sm = {x["id"]: x for x in sent}
        T = timeline(S, M, st, sm, align)
        placed = plan_rows(S, T, st)
        jsave(doc / "plan/계획_시간표.json", {"timeline": T, "placement": placed})
        over = [c for c in T["cuts"] if c["over"] > 0]
        for c in T["cuts"]:
            log(f"  {c['line']:4s} {c['t0']:6.2f}~{c['t1']:6.2f} {c['dur']:.2f}s max {c.get('max')} {c['src']}@{c.get('ss')}")
        LD = st["length"]
        length = {"sec": round(T["end"], 2), "min": LD["min"], "max": LD["max"], "measured": bool(sm),
                  "ok": LD["min"] - 0.5 <= T["end"] <= LD["max"] + 0.5}      # 판정 = bench_check '길이'와 같은 범위(±0.5)
        log(f"{'목소리 실측' if sm else '어림'} 길이 {T['end']}초 · 배치 {placed['log']}")
        msg = ("계획에서 컷이 원본 샷보다 길다" + ("" if sm else "(어림)") + ": " + str([(c["line"], c["src"], c.get("ss"), c["dur"], c.get("max"), {"원본 남음": c["src_left"]} if "src_left" in c else None) for c in over])) if over else ""
        if over and not tts:
            raise StageError(msg)
        return {"timeline": T, "placement": placed, "length": length, "over": msg}
    tts_S = {**S, "lines": [l for l in S["lines"] if l["kind"] == "tts"]}
    full, align = RI.tts_once(tts_S, R, log)
    sent, tempo, _ = RI.make_sentences(tts_S, full, R, log, align=align)
    sm = {s["id"]: s for s in sent}
    T = timeline(S, M, st, sm, align)
    over = [c for c in T["cuts"] if c["over"] > 0]
    if over:
        raise StageError("컷이 원본 샷보다 길다: " + str([(c["line"], c["src"], c.get("ss"), c["dur"], c.get("max"), {"원본 남음": c["src_left"]} if "src_left" in c else None) for c in over]))
    placed = plan_rows(S, T, st)
    from tools.calcopy.hybrid import placement as PL
    chk = PL.check_place(placed, st)
    win = render_window(T, M, st, R)
    base = render_base(S, T, st, placed, R, win)
    T["end"] = round(sum(c["frames"] for c in T["cuts"]) / FPS, 4)
    rows = caption_rows(placed, st)
    cap = burn_captions(base, rows, st, R, T["end"])
    mix, A = audio(S, M, st, T, sent, placed, R)
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", cap, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{T['end']:.3f}", final])
    from tools.calcopy.engine import ad_mark
    ad_mark.apply_inplace(final, log=log)
    jsave(R / "timeline.json", T)      # 썸네일 카드가 이 시간표로 장면(줄·몇 번째 컷)을 찾는다 — 카드보다 먼저 저장(10-24 09: 옛 시간표로 찾아 실패)
    if (doc / "썸네일.json").exists():      # 맨 앞 2프레임 = 썸네일 카드(주인 thumb.card · 10-23 사장님 "맨 앞에 썸네일 아주 잠깐") — 카드에 '광고' 같이 찍힘
        from tools.calcopy.hybrid import thumb as TH
        tc = TH.cards(style_name, doc, work, log=log)
        TH.stamp_video(final, Path(tc["pick_jpg"]))
        log(f"썸네일 {tc['pick']} → 맨 앞 {TH.THUMB_FRAMES}프레임")      # 오른쪽 위 '광고' 표시 — 주인 = engine/ad_mark(사장님 10-22 모든 렌더)
    jsave(R / "timeline.json", T)
    tab = {"_note": f"배치 결과 — placement.place(판 설정 {style_name}) · 시각은 final.mp4 기준 초", "pack": st["caption"]["pack"], "rows": rows,
           "sfx": placed["sfx"], "flashes": placed["flashes"], "comment": placed.get("comment"), "log": placed["log"], "check": chk}
    jsave(R / "자막표.json", tab)
    jsave(doc / "자막표.json", tab)
    info = {"made_by": "tools/calcopy/hybrid/render_bench.py", "version": style_name, "tempo": tempo, "final": str(final), "final_dur": dur_of(final),
            "final_lufs": lufs(final), "audio": A, "placement_check": chk, "n_cuts": len(T["cuts"]),
            "cuts_flat": [{k: c.get(k) for k in ("line", "src", "ss", "t0", "t1", "dur", "see")} for c in T["cuts"]]}
    jsave(R / "render_info.json", info)
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, doc / "final_sheet_1s.jpg")
    log(f"final {final} {info['final_dur']:.2f}초 LUFS/TP {info['final_lufs']} · 배치 {placed['log']}")
    return info


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("style"); ap.add_argument("doc"); ap.add_argument("work"); ap.add_argument("--plan", action="store_true")
    a = ap.parse_args()
    render(a.style, Path(a.doc), Path(a.work), plan_only=a.plan)
