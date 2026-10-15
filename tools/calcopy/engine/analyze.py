# -*- coding: utf-8 -*-
"""칼카피 엔진 ① 뜯기 1판 — 영상 1편 → 외관·소리·제작법을 숫자와 사전 후보로.

    PYTHONUTF8=1 py tools/calcopy/engine/analyze.py <mp4> --out <폴더>

설계: docs/superpowers/specs/2026-10-15-칼카피엔진-design.md §3 ①뜯기
출력(폴더 안): 뜯기.json · 뜯기.md · sheet.jpg(컷마다 가운데 프레임) · captions/(자막 크롭) · fonts/(글꼴 대조 그리드)

재는 자는 전부 남의 것을 부른다(같은 판단 두 벌 금지):
  배치·자막·컷·소리 = shopping_shorts.channelkit.bench (편 하나 창 = layout.measure_video·window_vote, 자막 띠 = captions.choose_caption; layout1 은 부르기만)
  글꼴 = fontmatch(hotpeople font.py·font4.py 원리) · 말투 = tools/calcopy/script_text_stats.tone
  글자 읽기·제작법·받아쓰기 = 무료 제미나이(gemini_free.ask, 버텍스·유료 금지). 시험은 llm= 로 가짜를 끼운다.
항목마다 ok / failed:이유 와 method(잰 함수 이름)를 남긴다. 실패는 멈추지 않고 표에 적는다.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("BRAINBULB_VERTEX", "0")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from shopping_shorts.channelkit.bench import probe, layout, captions, cuts as bcuts, audio as baudio  # noqa: E402
from tools.calcopy.engine import layout1, fontmatch, gemini_free, audio_comp, rules  # noqa: E402
from tools.calcopy.script_text_stats import tone  # noqa: E402

ENGINE_VERSION = "뜯기 1판 2026-10-15"
MATERIAL_KINDS = ["남의영상재편집", "스톡영상", "사진+움직임", "기사·화면캡처", "AI그림", "AI영상", "짤·밈",
                  "역할극·인물컷", "화면녹화", "글자만", "직접촬영", "모름"]
FONT_CROPS = 6          # 글꼴 대조 자막 크롭 최대 수
MOTION_STARTS = 3       # 등장 곡선 잴 자막 시작 수
MOTION_HALF = 9         # ±9프레임(원 fps)
BATCH = 10              # 제미나이 한 번에 보낼 그림 수(큰 시트 한 번에 주면 번호를 순서대로 찍는다 — 메모리)


def _jpeg(img: np.ndarray, w: int | None = None, q: int = 85) -> bytes:
    im = Image.fromarray(img)
    if w and im.width != w:
        im = im.resize((w, int(im.height * w / im.width)))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q)
    return b.getvalue()


def _batched(llm, items: list[tuple[str, bytes]], prompt: str, tag: str) -> tuple[dict, list[str]]:
    """[(라벨, jpeg)] → {라벨: 답 dict}. 묶음마다 [라벨 글, 그림] 순서로 보낸다. 실패 묶음은 이유 목록."""
    got, errs = {}, []
    for k in range(0, len(items), BATCH):
        part = []
        for lab, jpg in items[k:k + BATCH]:
            part += [lab, jpg]
        d, err = llm(part, prompt, f"{tag}{k // BATCH}")
        if err:
            errs.append(err)
            continue
        for it in (d or {}).get("items", []):
            if isinstance(it, dict) and it.get("label"):
                got[str(it["label"]).strip()] = it
    return got, errs


# ── 3. 자막 글자(OCR) ─────────────────────────────────────────────────────
OCR_PROMPT = ('각 그림은 숏폼 영상의 자막 띠를 잘라낸 것이다. 그림마다 앞의 라벨이 붙어 있다. '
              '화면에 얹은 자막 글자만 줄 단위로 **보이는 그대로** 옮겨라(띄어쓰기·문장부호·이모티콘 글자 그대로, 고치지 마라). '
              '영상 속 간판·물건의 글자는 빼라. 자막이 없으면 lines 는 빈 목록.\n'
              'JSON만: {"items":[{"label":"자막 0","lines":["첫 줄","둘째 줄"]}]}')


def ocr_captions(path, vl, cap, out_dir, llm) -> dict:
    reg = captions.caption_region(vl)
    W = vl["canvas"][0]
    y0, y1 = reg
    cdir = Path(out_dir) / "captions"
    cdir.mkdir(exist_ok=True)
    crops, items = {}, []
    for it in cap["items"]:
        t = (it["t0"] + it["t1"]) / 2
        img = probe.grab(path, t, f"crop={W}:{y1 - y0}:0:{y0}", W, y1 - y0)
        if img is None:
            continue
        crops[it["i"]] = img
        Image.fromarray(img).save(cdir / f"c{it['i']:02d}_{it['t0']:.2f}s.png")
        if it.get("lines", 0) > 0:
            items.append((f"자막 {it['i']} ({it['t0']:.2f}~{it['t1']:.2f}s)", _jpeg(img, 720)))
    got, errs = _batched(llm, items, OCR_PROMPT, "ocr")
    texts = {}
    for lab, _ in items:
        i = int(lab.split()[1])
        g = got.get(lab) or got.get(f"자막 {i}")
        if g is not None:
            texts[i] = [str(x) for x in (g.get("lines") or [])]
    return {"crops": crops, "texts": texts, "asked": len(items), "read": len(texts), "errors": errs}


# ── 4·5. 글꼴 · 글자 효과 ─────────────────────────────────────────────────
def _pick_even(xs: list, n: int) -> list:
    if len(xs) <= n:
        return xs
    return [xs[int(round(k))] for k in np.linspace(0, len(xs) - 1, n)]


def _cdist(a, b) -> float:
    return float(np.abs(np.array(a, float) - np.array(b, float)).max())


def text_fx_one(img: np.ndarray, pol: str, canvas_bg: list[int]) -> dict | None:
    """채움색·외곽선(두께·색)·글자 상자. 잉크 = bench layout.ink_mask(티끌 제거)."""
    ink = fontmatch.glyph_mask(img, pol)
    if ink.sum() < 50:
        return None
    fill = [int(v) for v in np.median(img[ink], axis=0)]
    rings, prev = [], ink
    for r in range(1, 19):
        d = cv2.dilate(ink.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0
        ring = d & ~prev
        rings.append([int(v) for v in np.median(img[ring], axis=0)] if ring.any() else None)
        prev = d
    local_bg = rings[15] or rings[-1]
    thick = 0
    if rings[0] and _cdist(rings[0], fill) > 60 and local_bg and _cdist(rings[0], local_bg) > 40:
        for rc in rings[:12]:
            if rc and _cdist(rc, fill) > 60 and _cdist(rc, rings[0]) < 60:
                thick += 1
            else:
                break
    ys, xs = np.where(ink)
    pad = 24
    a0, a1 = max(0, ys.min() - pad), min(img.shape[0], ys.max() + pad)
    b0, b1 = max(0, xs.min() - pad), min(img.shape[1], xs.max() + pad)
    k = 2 * (thick + 6) + 1
    away = ~(cv2.dilate(ink.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) > 0)
    reg = img[a0:a1, b0:b1][away[a0:a1, b0:b1]]
    box = None
    if len(reg) > 200:
        lum = reg.astype(float) @ np.array([0.299, 0.587, 0.114])
        med = [int(v) for v in np.median(reg, axis=0)]
        if lum.std() < 15:
            box = {"color": med} if _cdist(med, canvas_bg) > 40 else {"color": med, "note": "화면 배경과 같은 색(상자 아님)"}
    return {"fill_rgb": fill, "outline": {"px": thick, "rgb": rings[0]} if thick else None,
            "box": box if box and "note" not in box else None, "box_note": box.get("note") if box else None}


def fonts_and_fx(cap, ocr, vl, out_dir) -> tuple[dict, dict]:
    pol = vl["caption"]["ink"]
    fdir = Path(out_dir) / "fonts"
    fdir.mkdir(exist_ok=True)
    usable = []
    for it in cap["items"]:
        i = it["i"]
        lines = [x for x in ocr["texts"].get(i, []) if x.strip()]
        if i not in ocr["crops"] or not lines:
            continue
        masks = fontmatch.line_masks(ocr["crops"][i], pol)
        if len(masks) != len(lines):
            continue
        usable.append((i, lines, masks))
    picks = _pick_even(usable, FONT_CROPS)
    per, totals, fx = [], {}, []
    for i, lines, masks in picks:
        j = max(range(len(lines)), key=lambda q: len(lines[q].replace(" ", "")))
        r = fontmatch.rank(masks[j], lines[j])
        png = fdir / f"c{i:02d}.png"
        fontmatch.grid(masks[j], lines[j], r[:5], str(png))
        per.append({"caption": i, "text": lines[j], "top5": [{"font": x["font"], "score": x["score"]} for x in r[:5]],
                    "grid": str(png.relative_to(out_dir)).replace("\\", "/"), "_ref": masks[j],
                    "failed_fonts": [{"font": x["font"], "why": x.get("failed") or "글자 빠짐 " + x["missing"]}
                                     for x in r if x.get("failed") or x.get("missing")]})
        for x in r:
            totals.setdefault(x["font"], []).append(x["score"])
        f = text_fx_one(ocr["crops"][i], pol, vl["bg_rgb"])
        if f:
            fx.append({"caption": i, **f})
    if not per:
        why = "OCR 글자가 없음" if not ocr["texts"] else "OCR 줄 수와 잉크 줄 수가 맞는 자막이 없음"
        fonts = {"failed": why, "method": fontmatch.METHOD, "usable": 0}
    else:
        tot = sorted(({"font": k, "score": round(float(np.mean(v)), 4)} for k, v in totals.items()), key=lambda r: -r["score"])
        if tot[0]["score"] <= 0:
            errs = sorted({x["why"] for x in per[0]["failed_fonts"]}) or ["점수 0(실패 표시 없음)"]
            for p in per:
                p.pop("_ref", None)
            return {"failed": f"모든 후보 점수 0: {errs[:3]}", "method": fontmatch.METHOD, "per_crop": per}, fx
        for p in per:
            p.pop("_ref", None)
        fonts = {"ok": True, "method": f"fontmatch.rank ({fontmatch.METHOD}), 합산 = 크롭별 점수 평균",
                 "n_fonts": len(fontmatch.font_paths()), "usable": len(usable), "per_crop": per, "top3": tot[:3]}
    return fonts, fx


# ── 6. 등장 곡선 ─────────────────────────────────────────────────────────
def caption_motion(path, vl, cap, meta) -> dict:
    reg = captions.caption_region(vl)
    y0, y1 = reg
    W = vl["canvas"][0]
    fps = meta["fps"]
    pol = vl["caption"]["ink"]
    starts = [it for it in cap["items"] if it["t0"] > 0 and it["t1"] - it["t0"] >= 0.5]
    out = []
    for it in _pick_even(starts, MOTION_STARTS):
        t0 = it["t0"]
        ss = max(0.0, t0 - MOTION_HALF / fps)
        curve = []
        for k, f in enumerate(probe.frames(path, f"crop={W}:{y1 - y0}:0:{y0}", W, y1 - y0, ss=ss,
                                           dur=(2 * MOTION_HALF + 1) / fps)):
            m = layout.ink_mask(f, pol)
            ys, xs = np.where(m)
            bb = [int(xs.min()), int(ys.min() + y0), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)] if len(ys) else None
            curve.append({"t": round(ss + k / fps, 3), "bbox": bb, "ink": int(m.sum())})
        out.append({"caption": it["i"], "t0": t0, "anim": captions.caption_anim(path, vl, t0 + 0.03, fps), "curve": curve})
    return {"ok": True, "method": "layout.ink_mask bbox·잉크량 (원 fps ±9프레임) + captions.caption_anim", "starts": out} if out \
        else {"failed": "0.5초 넘는 자막 시작이 없음"}


# ── 7·8. 컷 · 제작법 ─────────────────────────────────────────────────────
MAT_PROMPT = ('각 그림은 세로 숏폼 영상의 한 컷 가운데 프레임(화면 전체 — 위아래 글자 띠 포함)이다. 그림마다 앞에 라벨이 있다. '
              '영상 창 안의 그림이 **어떻게 만들어졌는지(제작법)**를 아래 사전에서 정확히 하나 고르고 한 줄로 근거를 적어라. '
              '확신이 없으면 "모름". 사전: ' + " | ".join(MATERIAL_KINDS) + '\n'
              '뜻: 남의영상재편집=다른 채널·방송·릴스 영상을 가져와 자른 것 / 스톡영상=스톡 사이트 풍 일반 영상 / '
              '사진+움직임=정지 사진에 확대·이동 / 기사·화면캡처=기사·SNS·웹 화면 캡처 / AI그림=생성 이미지 / AI영상=생성 영상 / '
              '짤·밈=유행 짤·밈 이미지 / 역할극·인물컷=사람이 연기·대화하는 연출 컷 / 화면녹화=폰·PC 화면 녹화 / '
              '글자만=그림 없이 글자 화면 / 직접촬영=채널 주인이 직접 찍은 영상(같은 사람·장소가 이어지고 채널 나레가 그 사람 목소리일 때만). '
              '외국인·원본 언어 소리·서로 다른 장소/인물의 영상을 채널 틀(위아래 글자 띠) 안에 넣은 것은 남의영상재편집이다.\n'
              'JSON만: {"items":[{"label":"컷 0","kind":"사전 항목","why":"한 줄"}]}')


def shots_and_materials(path, vl, meta, cap, out_dir, llm, want_materials=True, context: str = "") -> tuple[dict, dict]:
    if not vl.get("window"):
        return {"failed": "영상 창을 못 찾음(layout)"}, {"failed": "컷이 없음"}
    cu = bcuts.measure_video(path, vl, meta, cap["changes"] if cap else [], zoom=True)
    dur = meta["duration"]
    bounds = [0.0] + list(cu["cuts"]) + [dur]
    segs = bcuts.shot_lengths(list(cu["cuts"]), dur)
    a = np.array(segs)
    cuts = {"ok": True, "method": "bench.cuts.measure_video (scene_detect+merge_close+cut_verify)", "times": cu["cuts"],
            "shots": len(segs), "shot_len": {"median": round(float(np.median(a)), 2), "p10": round(float(np.percentile(a, 10)), 2),
                                            "p90": round(float(np.percentile(a, 90)), 2)},
            "first_cut": cu["first_cut"], "cut_per_min": cu["cut_per_min"],
            "cut_eq_sub": cu["cut_eq_sub"], "cut_eq_sub_rate": round(cu["cut_eq_sub"][0] / max(1, cu["cut_eq_sub"][1]), 3)
            if cu.get("cut_eq_sub") else None, "zoom": cu.get("zoom"), "bench": cu}
    W, H = meta["width"], meta["height"]
    cw = 180
    chh = int(round(H * cw / W))
    frames = []
    for k, (s, e) in enumerate(zip(bounds, bounds[1:])):
        img = probe.grab(path, (s + e) / 2, f"scale={cw * 2}:{chh * 2}", cw * 2, chh * 2)
        frames.append((k, s, e, img))
    cols = 6
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (chh + 18)), "white")
    d = ImageDraw.Draw(sheet)
    for k, s, e, img in frames:
        x, y = k % cols * cw, k // cols * (chh + 18)
        if img is not None:
            sheet.paste(Image.fromarray(img).resize((cw, chh)), (x, y + 18))
        d.text((x + 3, y + 3), f"#{k} {s:.1f}-{e:.1f}s", fill=(220, 0, 0))
    sheet.save(Path(out_dir) / "sheet.jpg", quality=82)
    if not want_materials:
        return cuts, {"failed": "건너뜀(--no-materials)"}
    items = [(f"컷 {k} ({s:.2f}~{e:.2f}s)", _jpeg(img, 360)) for k, s, e, img in frames if img is not None]
    got, errs = _batched(llm, items, (f"영상 맥락(판독 참고용): {context}" + chr(10) if context else "") + MAT_PROMPT, "mat")
    per, cnt = [], {}
    for k, s, e, img in frames:
        g = got.get(f"컷 {k} ({s:.2f}~{e:.2f}s)") or got.get(f"컷 {k}")
        kind = str(g.get("kind", "")).strip() if g else None
        row = {"shot": k, "t": [round(s, 2), round(e, 2)], "kind": kind, "why": g.get("why") if g else None}
        if g is None:
            row["failed"] = errs[0] if errs else "답 없음"
        elif kind not in MATERIAL_KINDS:
            row["off_dict"] = True
        per.append(row)
        if kind:
            cnt[kind] = cnt.get(kind, 0) + (e - s)
    tot = sum(cnt.values())
    mats = {"method": "gemini_free.ask (컷 가운데 프레임 → 제작법 사전 분류)", "dict": MATERIAL_KINDS, "per_shot": per,
            "share_by_time": {k: round(v / tot, 3) for k, v in sorted(cnt.items(), key=lambda x: -x[1])} if tot else {},
            "share_by_count": {k: sum(1 for r in per if r["kind"] == k) for k in cnt}}
    if got:
        mats["ok"] = True
    else:
        mats["failed"] = errs[0] if errs else "답 없음"
    if errs:
        mats["errors"] = errs
    return cuts, mats


# ── 9·10. 소리 · 말투 ────────────────────────────────────────────────────
ASR_PROMPT = ('이 오디오의 말소리를 들리는 그대로(원래 언어 그대로) 받아써라. 구절(쉼 단위)마다 시작·끝 초, 화자 라벨(S1,S2…), '
              '언어 코드(ko/en/ja…), 종류 kind(narration=영상 위에 얹은 해설 목소리 / dialog=연기·대화 / source=원본 영상 속 현장 말소리). '
              '화자마다 성별 gender(male/female/unknown)와 합성음성(TTS)처럼 들리는지 voice(tts/human/unknown). '
              '노래 가사·배경음은 빼라. 현장음(박수·환호·물소리 등)이 깔려 있으면 ambient 에 짧게. 말이 없으면 빈 목록.\n'
              '또 효과음(편집으로 넣은 짧은 소리)마다 시각 t 와 종류 kind(띵|휙|펑|웃음|탄성|기타), '
              '배경음악 bgm = {present: 있나, mood: 분위기 태그 3개 이내, start: 시작 초, fade_out: 끝에서 줄어드나}, '
              'voice_tone = 주 목소리 톤 한 줄(예: 빠르고 들뜬 20대 여성 수다체).\n'
              'JSON만: {"speakers":[{"id":"S1","gender":"female","voice":"tts"}],'
              '"segments":[{"start":0.0,"end":0.0,"speaker":"S1","lang":"ko","kind":"narration","text":""}],"ambient":"",'
              '"sfx":[{"t":0.0,"kind":"띵"}],"bgm":{"present":true,"mood":["경쾌"],"start":0.0,"fade_out":false},"voice_tone":""}')


def audio_and_tone(path, meta, llm, R: dict | None = None) -> tuple[dict, dict]:
    au = baudio.measure_video(path, meta)
    res = {"method": "bench.audio.measure_video + gemini_free.ask 받아쓰기 + audio_comp.composition", "bench": au}
    if not au.get("has_audio"):
        res["failed"] = "소리 없음"
        res["composition"] = {"failed": "소리 없음", "kind": "나레 없음"}
        return res, {"failed": "받아쓰기 없음(소리 없음)"}
    mp3 = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", "-f", "mp3", "-"],
                         capture_output=True).stdout
    d, err = llm([(mp3, "audio/mp3")], ASR_PROMPT, "asr")
    res["ok"] = True
    if err:
        res["transcript"] = {"failed": err}
        res["composition"] = {"failed": f"받아쓰기 실패({err})"}
        return res, {"failed": f"받아쓰기 실패({err})"}
    seg = [s for s in ((d or {}).get("segments") or (d or {}).get("items") or []) if isinstance(s, dict) and str(s.get("text", "")).strip()]
    try:
        seg = sorted(({"start": float(s["start"]), "end": float(s["end"]), "text": str(s["text"]).strip(),
                       "speaker": str(s.get("speaker") or "S?"), "lang": str(s.get("lang") or "").strip().lower(),
                       "kind": str(s.get("kind") or "unknown").strip().lower()} for s in seg), key=lambda s: s["start"])
    except (KeyError, TypeError, ValueError) as e:
        res["transcript"] = {"failed": f"받아쓰기 모양 이상: {e}"}
        res["composition"] = {"failed": "받아쓰기 모양 이상"}
        return res, {"failed": "받아쓰기 모양 이상"}
    ko = [s for s in seg if s["lang"] == "ko"]
    speak = sum(max(0.0, s["end"] - s["start"]) for s in ko)
    chars = sum(len(s["text"].replace(" ", "")) for s in ko)
    gaps = [b["start"] - a["end"] for a, b in zip(ko, ko[1:]) if b["start"] - a["end"] > 0.05]
    langs = sorted({s["lang"] for s in seg if s["lang"]})
    res["asr_extra"] = {k: (d or {}).get(k) for k in ("sfx", "bgm", "voice_tone", "speakers")}
    res["transcript"] = {"segments": seg, "n": len(seg), "langs": langs, "ambient": (d or {}).get("ambient") or "",
                         "speech_sec_all": round(sum(max(0.0, s["end"] - s["start"]) for s in seg), 2),
                         "ko_speech_sec": round(speak, 2), "speech_share_ko": round(speak / meta["duration"], 3) if meta["duration"] else None,
                         "chars_nospace_ko": chars, "cps": round(chars / speak, 2) if speak > 0 else None,
                         "pause_median": round(st.median(gaps), 2) if gaps else None, "pauses": len(gaps),
                         "narration": "한국어 말소리 있음" if ko else ("한국어 말소리 없음(외국어 원음만)" if seg else "말소리 없음"),
                         "method": "한국어 구절만: cps = 공백 뺀 글자 ÷ 구절 길이 합, 쉼 = 이웃 구절 사이 >0.05s"}
    ocr = [" ".join(it["text"]) for it in ((R or {}).get("captions") or {}).get("items", []) if it.get("text")]
    try:
        res["composition"] = audio_comp.composition(path, meta, {**(d or {}), "segments": seg}, ocr)
    except Exception as e:  # noqa: BLE001 — 구성 재기 실패는 항목에 남기고 계속
        res["composition"] = {"failed": f"{type(e).__name__}: {str(e)[:100]}"}
    t = tone([s["text"] for s in ko])
    return res, ({"ok": True, "method": "tools/calcopy/script_text_stats.tone (한국어 받아쓰기 구절 단위)", **t} if t.get("n")
                 else {"failed": "한국어 받아쓰기 구절 없음"})


def _context(R: dict) -> str:
    """제작법 판독에 같이 주는 맥락: 자막 글자 전문 + 받아쓰기 언어·앞부분."""
    caps = " / ".join(" ".join(it["text"]) for it in (R.get("captions") or {}).get("items", []) if it.get("text"))
    tr = (R.get("audio") or {}).get("transcript") or {}
    say = " ".join(s["text"] for s in tr.get("segments", []))[:200]
    return f"화면 자막: {caps[:400]} | 말소리 언어: {', '.join(tr.get('langs') or []) or '없음'} | 말소리: {say}"


# ── 묶기 ─────────────────────────────────────────────────────────────────
def analyze(mp4: str, out_dir: str, llm=None, materials: bool = True) -> dict:
    llm = llm or gemini_free.ask
    os.makedirs(out_dir, exist_ok=True)
    gemini_free.CALLS.clear()
    T = {}
    t_all = time.time()
    R: dict = {"engine": ENGINE_VERSION, "source": str(mp4), "measured_at": time.strftime("%Y-%m-%d %H:%M")}
    unknown: list[str] = []

    t = time.time()
    meta = probe.info(mp4)
    R["probe"] = {"ok": True, "method": "bench.probe.info", "w": meta["width"], "h": meta["height"], "fps": meta["fps"],
                  "duration": meta["duration"], "has_audio": meta["has_audio"], "raw": meta}
    T["probe"] = time.time() - t

    t = time.time()
    lay = layout1.measure(mp4, meta)
    vl = lay["vl"]
    R["layout"] = {"ok": bool(vl.get("window")), "method": "bench.layout.measure_video(+window_vote) + bench.captions.choose_caption (입구 layout1.measure)",
                   "window": vl.get("window"), "window_method": lay["window"]["method"], "bg_rgb": vl.get("bg_rgb"),
                   "ink_polarity": (vl.get("caption") or {}).get("ink"), "caption_pos": (vl.get("caption") or {}).get("pos"),
                   "caption_band": (vl.get("caption") or {}).get("band"),
                   "other_frame_segments": lay["window"].get("other_frame_segments", []),
                   "above_bands": lay["bench_full"].get("above_bands"), "bench_full_single": lay["bench_full"],
                   "chunks": lay["window"].get("chunks", []), "caption_candidates": lay["caption_candidates"]}
    if not vl.get("window"):
        R["layout"]["failed"] = "영상 창을 못 찾음"
    if R["layout"]["other_frame_segments"]:
        unknown.append(f"틀이 다른 구간(엔딩·전체화면 등): {R['layout']['other_frame_segments']} — 창 다수결에서 뺌")
    T["layout"] = time.time() - t

    t = time.time()
    cap = lay["caption"]
    if cap is None and vl.get("caption", {}).get("band") and vl.get("window"):
        cap = captions.measure_video(mp4, vl, meta)
    ocr = None
    if cap and cap.get("region"):
        ocr = ocr_captions(mp4, vl, cap, out_dir, llm)
        items = [{**it, "text": ocr["texts"].get(it["i"])} for it in cap["items"]]
        R["captions"] = {"ok": True, "method": "bench.captions.measure_video + gemini_free.ask(OCR)", "region": cap["region"],
                         "changes": cap["changes"], "spans": cap["spans"], "n_spans": len(cap["spans"]), "items": items,
                         "glyph": cap["glyph"], "unstable": cap.get("unstable", []), "ocr": {"asked": ocr["asked"], "read": ocr["read"], "errors": ocr["errors"]}}
        if ocr["errors"]:
            R["captions"]["ocr"]["failed"] = ocr["errors"][0]
            unknown.append(f"자막 OCR 일부 실패: {ocr['errors']}")
        if ocr["asked"] > ocr["read"]:
            unknown.append(f"자막 글자 못 읽음 {ocr['asked'] - ocr['read']}/{ocr['asked']}개")
    else:
        R["captions"] = {"failed": "자막 띠를 못 찾음(후보 점수 0)", "method": "bench.captions.caption_score"}
    T["captions"] = time.time() - t

    t = time.time()
    if ocr:
        R["fonts"], fx = fonts_and_fx(cap, ocr, vl, out_dir)
        if R["fonts"].get("failed"):
            unknown.append(f"글꼴: {R['fonts']['failed']}")
        elif R["fonts"]["top3"][0]["score"] < 0.5:
            unknown.append(f"글꼴 1위 점수 {R['fonts']['top3'][0]['score']} < 0.5 — 창고에 없는 글꼴일 수 있음")
        other = R["layout"]["other_frame_segments"]
        gl_all = cap.get("glyph") or []
        span_t0 = {it["i"]: it["t0"] for it in cap["items"]}
        gl = [g for g in gl_all if not any(a <= span_t0.get(g["i"], -1) < b for a, b in other)] or gl_all
        R["text_fx"] = {"method": "engine.text_fx_one(링 색) + bench captions.glyph_style(획·외곽선·그림자)",
                        "per_crop": fx, "glyph": gl_all, "glyph_used_for_summary": [g["i"] for g in gl]}
        if fx:
            R["text_fx"]["ok"] = True
            R["text_fx"]["summary"] = {
                "fill_rgb": [int(np.median([f["fill_rgb"][k] for f in fx])) for k in range(3)],
                "outline_px": int(np.median([(f["outline"] or {}).get("px", 0) for f in fx])),
                "outline_rgb": next((f["outline"]["rgb"] for f in fx if f["outline"]), None),
                "box": next((f["box"] for f in fx if f["box"]), None),
                "shadow": [g["shadow"] for g in gl if g.get("shadow")][:1] or None,
                "stroke_px": st.median([g["stroke"] for g in gl if g.get("stroke")]) if any(g.get("stroke") for g in gl) else None,
                "line_h_px": st.median([g["line_h"] for g in gl]) if gl else None}
        else:
            R["text_fx"]["failed"] = "글꼴 대조에 쓴 크롭이 없음(OCR·줄 수 불일치)"
    else:
        R["fonts"] = {"failed": "자막이 없어 글꼴 대조 못 함"}
        R["text_fx"] = {"failed": "자막이 없어 글자 효과 못 잼"}
    T["fonts_fx"] = time.time() - t

    t = time.time()
    R["caption_motion"] = caption_motion(mp4, vl, cap, meta) if cap and cap.get("region") else {"failed": "자막 없음"}
    for s in R["caption_motion"].get("starts", []):
        if s["anim"] == "판정불가":
            unknown.append(f"등장효과 판정불가: 자막 {s['caption']} ({s['t0']}s)")
    T["caption_motion"] = time.time() - t

    t = time.time()
    R["audio"], R["script_tone"] = audio_and_tone(mp4, meta, llm, R)
    if (R["audio"].get("transcript") or {}).get("failed"):
        unknown.append(f"받아쓰기 실패: {R['audio']['transcript']['failed']}")
    comp = R["audio"].get("composition") or {}
    if comp.get("failed"):
        unknown.append(f"소리 구성 실패: {comp['failed']}")
    else:
        for k in ("duck_db", "caption_eq_narration", "sfx_per_sec"):
            if isinstance(comp.get(k), dict) and comp[k].get("failed"):
                unknown.append(f"소리 구성 {k}: {comp[k]['failed']}")
        if comp.get("narration") == "unknown":
            unknown.append("나레 TTS/사람 판정 못 함(unknown)")
        unknown.append("효과음 솟음·피치 지표 문턱은 미검증(참고값)")
    T["audio_tone"] = time.time() - t

    t = time.time()
    R["cuts"], R["materials"] = shots_and_materials(mp4, vl, meta, cap, out_dir, llm, materials,
                                                     context=_context(R))
    for r in R["materials"].get("per_shot", []):
        if r.get("off_dict"):
            unknown.append(f"제작법 사전 밖: 컷 {r['shot']} '{r['kind']}'")
        elif r.get("kind") == "모름":
            unknown.append(f"제작법 모름: 컷 {r['shot']} ({r.get('why')})")
        elif r.get("failed"):
            unknown.append(f"제작법 판독 실패: 컷 {r['shot']} ({r['failed']})")
    T["cuts_materials"] = time.time() - t

    t = time.time()
    comp = R["audio"].get("composition") or {}
    extra = R["audio"].get("asr_extra") or {}
    sub_ch = (R.get("captions") or {}).get("changes") or []
    cut_t = (R.get("cuts") or {}).get("times") or []
    jobs = {"sfx_rules": lambda: rules.sfx_rules(comp, sub_ch, cut_t, meta["duration"], extra),
            "bgm_rules": lambda: rules.bgm_rules(extra, comp, mp4, meta["duration"]) if R["audio"].get("ok") else {"failed": "소리 없음"},
            "voice_rules": lambda: rules.voice_rules(comp, (R["audio"].get("transcript") or {}), extra),
            "overlay_rules": lambda: rules.overlay_rules(mp4, meta, (R.get("captions") or {}).get("items", []), llm, _jpeg)
            if materials else {"failed": "건너뜀(--no-materials)"}}
    for k, f in jobs.items():
        try:
            R[k] = f()
        except Exception as e:  # noqa: BLE001 — 규칙 하나가 죽어도 나머지 뜯기는 남긴다(항목에 이유)
            R[k] = {"failed": f"{type(e).__name__}: {str(e)[:120]}"}
    for k in ("sfx_rules", "bgm_rules", "voice_rules", "overlay_rules"):
        if R[k].get("failed"):
            unknown.append(f"{k}: {R[k]['failed']}")
    T["rules"] = time.time() - t

    R["unknown"] = unknown
    R["llm_calls"] = list(gemini_free.CALLS)
    R["timing_sec"] = {k: round(v, 1) for k, v in T.items()} | {"total": round(time.time() - t_all, 1)}
    with open(Path(out_dir) / "뜯기.json", "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    (Path(out_dir) / "뜯기.md").write_text(to_md(R), encoding="utf-8")
    return R


# ── 사람이 읽는 보고 ──────────────────────────────────────────────────────
KEYS = [("probe", "1 기본(probe)"), ("layout", "2 배치(layout)"), ("captions", "3 자막(captions)"), ("fonts", "4 글꼴(fonts)"),
        ("text_fx", "5 글자 효과(text_fx)"), ("caption_motion", "6 등장 곡선(caption_motion)"), ("cuts", "7 컷(cuts)"),
        ("materials", "8 제작법(materials)"), ("audio", "9 소리(audio)"), ("script_tone", "10 말투(script_tone)"),
        ("sfx_rules", "12 효과음 규칙"), ("bgm_rules", "13 배경음악 규칙"), ("overlay_rules", "14 짤 규칙"), ("voice_rules", "15 목소리 규칙")]


def _st(x: dict) -> str:
    return "확인됨" if x.get("ok") and not x.get("failed") else f"실패: {x.get('failed', '?')}"


def to_md(R: dict) -> str:
    ok = [n for k, n in KEYS if R[k].get("ok") and not R[k].get("failed")]
    bad = [f"{n} ({R[k].get('failed')})" for k, n in KEYS if not (R[k].get("ok") and not R[k].get("failed"))]
    P, L = R["probe"], R["layout"]
    o = [f"# 뜯기 — {Path(R['source']).stem}", "",
         f"- **확인됨**: {', '.join(ok) or '없음'}",
         f"- **실패·미확인**: {', '.join(bad) or '없음'} / 미확인 목록 {len(R['unknown'])}건(맨 아래 11)",
         f"- 엔진: {R['engine']} · 잰 시각 {R['measured_at']} · 걸린 시간 {R['timing_sec']['total']}초 · 제미나이 호출 {len(R['llm_calls'])}회",
         "", "## 1 기본", "| 항목 | 값 |", "|---|---|",
         f"| 크기 | {P['w']}×{P['h']} |", f"| fps | {P['fps']} |", f"| 길이 | {P['duration']}초 |", f"| 소리 | {P['has_audio']} |",
         "", f"## 2 배치 — {_st(L)}", "| 항목 | 값 |", "|---|---|",
         f"| 영상 창 [x,y,w,h] | {L.get('window')} |", f"| 창 찾은 법 | {L.get('window_method')} |", f"| 배경색 | {L.get('bg_rgb')} |",
         f"| 자막 자리 | {L.get('caption_pos')} 띠 {L.get('caption_band')} 잉크 {L.get('ink_polarity')} |",
         f"| 창 위 고정 글자 띠 | {L.get('above_bands')} |", f"| 틀이 다른 구간 | {L.get('other_frame_segments') or '없음'} |", ""]
    if L.get("caption_candidates"):
        o += ["자막 띠 후보 채점(score = 자막다운 구간 수 × 잉크 지속도 × 잉크 보이는 비율):", "",
              "| 자리 | 띠 | 잉크 | 구간 | 지속도 | 보임 | 점수 |", "|---|---|---|---|---|---|---|"]
        o += [f"| {c['pos']} | {c['band']} | {c['ink']} | {c.get('spans')} | {c.get('persist')} | {c.get('coverage')} | {c.get('score')} |"
              for c in L["caption_candidates"]]
    Cp = R["captions"]
    o += ["", f"## 3 자막 — {_st(Cp)}"]
    if Cp.get("ok"):
        o += [f"자막 {Cp['n_spans']}개 · 띠 {Cp['region']} · OCR {Cp['ocr']['read']}/{Cp['ocr']['asked']}", "",
              "| # | 시작~끝(초) | 줄 | 폭(px) | 글자(OCR) |", "|---|---|---|---|---|"]
        o += [f"| {it['i']} | {it['t0']}~{it['t1']} | {it.get('lines', 0)} | {it.get('widths', '')} | {' / '.join(it['text']) if it.get('text') else '—'} |"
              for it in Cp["items"]]
        o += ["", "획·외곽선·그림자·등장(bench glyph):", "", "| 자막 | 줄높이 | 획 | 외곽선 | 그림자[dx,dy] | 등장 |", "|---|---|---|---|---|---|"]
        o += [f"| {g['i']} | {g['line_h']} | {g['stroke']} | {g['outline']} | {g['shadow']} | {g['anim']} |" for g in Cp["glyph"]]
    F = R["fonts"]
    o += ["", f"## 4 글꼴 — {_st(F)}"]
    if F.get("ok"):
        o += [f"방법: {F['method']} · 후보 {F['n_fonts']}개 · 대조 크롭 {len(F['per_crop'])}개(쓸 수 있던 것 {F['usable']})", "",
              "**합산 top3**: " + " · ".join(f"{x['font']} ({x['score']})" for x in F["top3"]), "",
              "| 자막 | 대조 글자 | top5 | 그리드 |", "|---|---|---|---|"]
        o += [f"| {p['caption']} | {p['text']} | {', '.join(f'{x['font']} {x['score']}' for x in p['top5'])} | {p['grid']} |"
              for p in F["per_crop"]]
    X = R["text_fx"]
    o += ["", f"## 5 글자 효과 — {_st(X)}"]
    if X.get("ok"):
        s = X["summary"]
        o += ["| 항목 | 값 |", "|---|---|", f"| 채움색 RGB | {s['fill_rgb']} |", f"| 외곽선 | {s['outline_px']}px {s['outline_rgb'] or ''} |",
              f"| 그림자 [dx,dy] | {s['shadow']} |", f"| 글자 상자 | {s['box'] or '없음'} |", f"| 획 폭 | {s['stroke_px']}px |",
              f"| 첫 줄 높이 | {s['line_h_px']}px |"]
    M = R["caption_motion"]
    o += ["", f"## 6 등장 곡선 — {_st(M)}"]
    for s0 in M.get("starts", []):
        ink = [c["ink"] for c in s0["curve"]]
        bw = [c["bbox"][2] if c["bbox"] else 0 for c in s0["curve"]]
        o += [f"- 자막 {s0['caption']} 시작 {s0['t0']}s · bench 등장 = **{s0['anim']}** · 잉크량 {ink[0]}→{max(ink) if ink else 0}→{ink[-1] if ink else 0} "
              f"· 폭 {bw[0] if bw else 0}→{bw[-1] if bw else 0} ({len(ink)}프레임)"]
    K = R["cuts"]
    o += ["", f"## 7 컷 — {_st(K)}"]
    if K.get("ok"):
        o += ["| 항목 | 값 |", "|---|---|", f"| 샷 수 | {K['shots']} |", f"| 컷 시각 | {K['times']} |",
              f"| 샷 길이 중앙/p10/p90 | {K['shot_len']['median']} / {K['shot_len']['p10']} / {K['shot_len']['p90']}초 |",
              f"| 첫 컷 | {K['first_cut']}초 |", f"| 분당 컷 | {K['cut_per_min']} |",
              f"| 컷=자막교체 | {K['cut_eq_sub']} ({K['cut_eq_sub_rate']}) |", f"| 줌 | {K['zoom']} |"]
    Mt = R["materials"]
    o += ["", f"## 8 제작법 — {_st(Mt)}", "시트: sheet.jpg (컷마다 가운데 프레임, #번호 시작-끝초)"]
    if Mt.get("per_shot"):
        o += ["", f"시간 비율: {Mt.get('share_by_time')}", "", "| 컷 | 시각 | 제작법 | 근거 |", "|---|---|---|---|"]
        o += [f"| {r['shot']} | {r['t'][0]}~{r['t'][1]} | {r['kind'] or '실패'}{' (사전 밖)' if r.get('off_dict') else ''} | {r.get('why') or r.get('failed', '')} |"
              for r in Mt["per_shot"]]
    A = R["audio"]
    o += ["", f"## 9 소리 — {_st(A)}"]
    b = A.get("bench") or {}
    if b.get("has_audio"):
        o += ["| 항목 | 값 |", "|---|---|", f"| LUFS(I) | {b.get('I')} |", f"| TP | {b.get('TP')} |", f"| LRA | {b.get('LRA')} |",
              f"| 단기 폭 S | {b.get('S_spread')} |", f"| 8~16k | {b.get('hf_8k16k_dbfs')} dBFS |", f"| 오프닝 | {b.get('openvoice')} |"]
        tr = A.get("transcript") or {}
        if tr.get("failed"):
            o += [f"| 받아쓰기 | 실패: {tr['failed']} |"]
        else:
            o += [f"| 말소리 | {tr['narration']} · 언어 {tr['langs']} |", f"| 말속도(한국어) | {tr['cps']} 자/초(공백 제외) |",
                  f"| 쉼 중앙(한국어) | {tr['pause_median']}초 ({tr['pauses']}번) |", f"| 한국어 말 차지 비율 | {tr['speech_share_ko']} |",
                  f"| 현장음 | {tr.get('ambient') or '—'} |"]
        Cm = A.get("composition") or {}
        o += ["", f"**소리 구성** — {('실패: ' + Cm['failed']) if Cm.get('failed') else Cm.get('kind')}"]
        if not Cm.get("failed"):
            def _v(k):
                v = Cm.get(k)
                return f"실패: {v['failed']}" if isinstance(v, dict) and v.get("failed") else v
            o += ["", "| 항목 | 값 |", "|---|---|",
                  f"| 화자 | {'; '.join(f'{s['n']} {s['gender']} {round(s['share'] * 100)}% {s['kinds']} {s['langs']} 목소리추정 {s['voice_guess']}' for s in Cm.get('speakers', [])) or '없음'} |",
                  f"| 나레 종류 | {Cm.get('narration')} {(Cm.get('narration_metrics') or {}).get('pitch', '')} |",
                  f"| 원음 깔림 | {Cm.get('source_audio_kept')} {Cm.get('source_evidence')} |",
                  f"| 덕킹(나레−무말 dB) | {_v('duck_db')} |", f"| 자막=나레 겹침 | {_v('caption_eq_narration')} |",
                  f"| 효과음 솟음/초 | {_v('sfx_per_sec')} (말 밖 {(Cm.get('sfx') or {}).get('outside_per_sec')}/초) |"]
        if tr.get("segments"):
            o += ["", "받아쓰기:", ""]
            o += [f"- [{s['start']:.1f}~{s['end']:.1f}] {s.get('speaker', '')} {s.get('lang', '')} {s.get('kind', '')}: {s['text']}" for s in tr["segments"]]
    S = R["script_tone"]
    o += ["", f"## 10 말투 — {_st(S)}"]
    if S.get("ok"):
        o += [f"구절 {S['n']}개 · 존댓말 비율 {S['polite_ratio']} · 전언 표지 {S['hearsay']} · 1인칭 {S['person_1st']} · 2인칭 {S['person_2nd']}",
              f"끝 꼴: {S['endings']}"]
    Sf, Bg, Ov, Vo = R["sfx_rules"], R["bgm_rules"], R["overlay_rules"], R["voice_rules"]
    o += ["", f"## 12 효과음 규칙 — {_st(Sf)}"]
    if Sf.get("ok"):
        o += [f"- {Sf['per_sec']}발/초 ({Sf['count']}발) · 자리 {Sf['position']} · 종류 {Sf.get('kinds', '판독 없음')}", f"- 방법: {Sf['method']}"]
    o += ["", f"## 13 배경음악 규칙 — {_st(Bg)}"]
    if Bg.get("ok"):
        o += [f"- 있음 {Bg['present']} · 분위기 {Bg['mood']} · 시작 {Bg['start_s']}초 · 덕킹 {Bg['duck_db']} · 끝 {Bg['end']}"]
    o += ["", f"## 14 짤 규칙 — {_st(Ov)}"]
    if Ov.get("ok"):
        o += [f"편당 {Ov['count']}개 ({Ov['per_min']}/분) · 종류 {Ov['kind_share']} · 자리 {Ov['slot_share']}", "",
              "| 종류 | 무엇 | 시각(초) | 편 % | 길이 | 자리 | 전체화면 | 크기 % | 상자[x,y,w,h] |", "|---|---|---|---|---|---|---|---|---|"]
        o += [f"| {a['kind']} | {a['what']} | {a['t']} | {a['t_pct']} | {a['len_s']} | {a['slot']} | {a['full']} | {a['size_pct']} | {a['box']} |"
              for a in Ov["appearances"]]
    o += ["", f"## 15 목소리 규칙 — {_st(Vo)}"]
    if Vo.get("ok"):
        o += [f"- 성별 {Vo['genders']} · 역할(한국어 화자) {Vo['roles']} · 전체 화자 {Vo['speakers_all']} · 말속도 {Vo['cps']} · 나레 {Vo['narration']} · 톤: {Vo['tone']}"]
    o += ["", "## 11 미확인·사전 밖", ""] + ([f"- {u}" for u in R["unknown"]] or ["- 없음"])
    o += ["", f"걸린 시간(초): {R['timing_sec']}", ""]
    return "\n".join(o)


def main() -> None:
    ap = argparse.ArgumentParser(description="칼카피 엔진 ① 뜯기 — 영상 1편 분석")
    ap.add_argument("mp4")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-materials", action="store_true", help="제작법 판독(제미나이) 건너뛰기")
    a = ap.parse_args()
    R = analyze(a.mp4, a.out, materials=not a.no_materials)
    print(f"뜯기 끝: {a.out}  ({R['timing_sec']['total']}초, 제미나이 {len(R['llm_calls'])}회)")
    print("\n".join(l for l in to_md(R).splitlines()[:5]))


if __name__ == "__main__":
    main()
