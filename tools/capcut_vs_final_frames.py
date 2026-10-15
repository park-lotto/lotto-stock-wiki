# -*- coding: utf-8 -*-
"""캡컷 초안을 **그림으로 합성**해 완성본 프레임과 장면마다 대조한다(관제 191, 2026-10-13, 읽기 전용).

왜: 캡컷 내보내기(app.api_mix_capcut)는 완성본(scene_style.compose)이 영상에 입히는 효과를 따로 흉내 낸다.
  흉내가 빠진 효과는 아무도 모른 채 캡컷에서만 사라졌다(왕혜원님 job 0ddd78a46708: 영상 칸 밖 검은 바탕 = '자막 배경',
  흐림 가림막). 계산끼리 비교하지 않고 **초안 파일이 실제로 그리는 그림**을 완성본 프레임과 픽셀로 맞댄다.

합성 규칙(캡컷 초안 → 그림): 캔버스 1080x1920 검정 → draft 트랙 순서대로(본 영상·컷어웨이·어둡게·장면 겹) 그 시각의 조각을
  그린다. 조각 소재는 캔버스에 맞춰(fit) 놓고 clip.scale 배, 가운데를 (540+x·540, 960−y·960)에 둔다. 키프레임은 무시한다
  (확대 움직임 장면은 영상 칸 안이 조금 다를 수 있다 — 그래서 아래 두 영역만 판정한다).

판정 영역(장면마다):
  band = 영상 칸(layers[i].media top·height) **밖**이면서 장면 겹 그림이 투명한 픽셀 — 완성본은 검정, 초안도 검정이어야 한다.
  blur = 그 장면의 흐림 가림막(fx=blur) 네모 — 완성본은 흐리다. 초안의 같은 자리 선명도(라플라시안 분산)와 차이를 잰다.
  FAIL: band 평균 밝기차 > 25 · blur 선명도비(초안/완성본) > 2.0 이면서 밝기차 > 8

서버: cd /home/ubuntu/lotto-stock-wiki && python3 tools/capcut_vs_final_frames.py <job_id> [더...]
  --rebuild: 지금 코드(PATCH_DIR 수정본)로 초안을 /tmp 에 새로 만들어 잰다(고객 폴더·DB 무변경)
결과: /tmp/capcut_vs_final/<job>/scene_XX.jpg(왼쪽 완성본 · 오른쪽 캡컷 합성) + 표준출력 장면별 한 줄 + `== FAIL n / 장면 m`
"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageStat

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "shopping_shorts" / "data" / "mix_jobs"
DB = ROOT / "shopping_shorts" / "data" / "reference.db"
OUT = Path("/tmp/capcut_vs_final")
W, H = 1080, 1920


def frame(path, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(path), "-frames:v", "1",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if not r.stdout:
        return None
    from io import BytesIO
    return Image.open(BytesIO(r.stdout)).convert("RGB")


def place(canvas, img, seg):
    clip = seg.get("clip") or {}
    s = float((clip.get("scale") or {}).get("x", 1.0))
    tr = clip.get("transform") or {}
    fit = min(W / img.width, H / img.height) * s
    im = img.convert("RGBA").resize((max(1, round(img.width * fit)), max(1, round(img.height * fit))))
    a = float(clip.get("alpha", 1.0))
    if a < 1:
        im.putalpha(im.getchannel("A").point(lambda v: round(v * a)))
    cx, cy = W / 2 + float(tr.get("x", 0)) * W / 2, H / 2 - float(tr.get("y", 0)) * H / 2
    canvas.paste(im, (round(cx - im.width / 2), round(cy - im.height / 2)), im)


def composite(draft_dir, d, t):
    mats = {m["id"]: m for m in d["materials"].get("videos", [])}
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    tracks = [tr for tr in d["tracks"] if tr["type"] == "video"]
    tracks.sort(key=lambda tr: min([s.get("track_render_index", 0) for s in tr["segments"]] or [0]))
    us = round(t * 1e6)
    for tr in tracks:
        for seg in tr["segments"]:
            st, du = seg["target_timerange"]["start"], seg["target_timerange"]["duration"]
            if not (st <= us < st + du):
                continue
            m = mats.get(seg["material_id"])
            if not m:
                continue
            p = draft_dir / Path(m["path"]).name
            if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
                img = Image.open(p)
            else:
                sp = float(seg.get("speed") or 1.0)
                src0 = (seg.get("source_timerange") or {}).get("start", 0) / 1e6
                img = frame(p, src0 + (us - st) / 1e6 * sp)
                if img is None:
                    continue
            place(canvas, img, seg)
    return canvas.convert("RGB")


def sharp(img):
    return ImageStat.Stat(img.convert("L").filter(ImageFilter.FIND_EDGES)).var[0]


def snapshot_of(job):
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = c.execute("select deco_json from mix_jobs where job_id=?", (job,)).fetchone()
    return (json.loads(row[0] or "{}").get("scene_style") or {}) if row else {}


def rebuild(job):
    """캡컷 초안을 **지금 코드로 새로** 만든다 — 라우트(app.api_mix_capcut) 원문 그대로, 쓰는 자리만 /tmp 로(고객 폴더·DB 안 건드림).
    PATCH_DIR 이 있으면 그 모듈(수정본)을 얹는다(capcut_export_audit 와 같은 장치). 반환: 임시 작업 폴더(capcut/·capcut_scene_style/)."""
    import shutil
    sys.path.insert(0, str(ROOT));sys.path.append(str(ROOT / "tools"))   # 관문이 올린 도구(PYTHONPATH)가 먼저
    import capcut_export_audit as cea
    patch = cea.load_patches()
    S = cea.ro_store()
    from shopping_shorts import app, mix_pipeline as mp, clean_base as cb
    cb._write = lambda work, base: None
    wd = OUT / job / "rebuild"
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)

    def _esf(*a, **k):
        k["clip_dir"] = wd / "clips";(wd / "clips").mkdir(exist_ok=True)
        return mp.export_sources_for(*a, **k)
    app_file = str(patch / "app.py") if patch and (patch / "app.py").exists() else None
    f = cea.route_fn(app, "api_mix_capcut", cea._CAPCUT_SUBS,
                     {"_AUDIT_OUT": wd, "Store": S, "mix_pipeline": cea._proxy(mp, export_sources_for=_esf)}, app_file)
    from shopping_shorts import scene_style as ss
    _ctx = ss.context_for

    def _rec(*a, **k):      # 라우트가 계산한 장면 시각을 남긴다 — 단어별 쪼갬 job 도 장면과 짝을 맞추게
        r = _ctx(*a, **k)
        (wd / "scenes.json").write_text(json.dumps([{"start": x["start"], "end": x["end"]} for x in r["scenes"]]), encoding="utf-8")
        return r
    ss.context_for = _rec
    try:
        resp = f(job, base="C:/capcut_check")
    finally:
        ss.context_for = _ctx
    if not (isinstance(resp, dict) and resp.get("ok")):
        raise SystemExit(f"{job} 초안 만들기 실패: {getattr(resp, 'body', resp)}")
    return wd


def audit(job, work=None):
    base = JOBS / job
    work = Path(work) if work else base
    drafts = sorted((work / "capcut").glob("*/draft_content.json"), key=lambda p: p.stat().st_mtime)
    if not drafts:
        print(job, "초안 없음");return None
    dj = drafts[-1];dd = dj.parent;d = json.loads(dj.read_text(encoding="utf-8"))
    final = base / "final.mp4"
    layers = json.loads((work / "capcut_scene_style" / "scene-style-layers.json").read_text(encoding="utf-8"))
    effects = snapshot_of(job).get("effects") or {}
    ov = [tr for tr in d["tracks"] if tr.get("name") == "scene-style-overlay"]
    segs = ov[0]["segments"] if ov else []
    out = OUT / job;out.mkdir(parents=True, exist_ok=True)
    sj = work / "scenes.json"
    if sj.exists():
        spans = [(x["start"], x["end"]) for x in json.loads(sj.read_text(encoding="utf-8"))]
    elif len(segs) == len(layers):
        spans = [(s_["target_timerange"]["start"] / 1e6, (s_["target_timerange"]["start"] + s_["target_timerange"]["duration"]) / 1e6) for s_ in segs]
    else:
        print(job, f"장면 겹 {len(segs)}장 ≠ 장면 {len(layers)} — 단어별 쪼갬 job 은 --rebuild 로 재라");return None
    # 완성본 앞에 인트로(prepend_still)가 붙었으면 그만큼 밀어 읽는다(캡컷엔 인트로가 없다)
    fdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)],
                                capture_output=True, text=True).stdout.strip() or 0)
    shift = fdur - d["duration"] / 1e6
    shift = shift if 0.05 < shift < 3.0 else 0.0
    from shopping_shorts.video_assemble import scene_hl_of
    fails = 0
    for i, ((st, en), layer) in enumerate(zip(spans, layers)):
        t = (st + en) / 2
        F, C = frame(final, t + shift), composite(dd, d, t)
        if F is None:
            continue
        F = F.resize((W, H))
        ink = Image.open(work / "capcut_scene_style" / layer["file"]).convert("RGBA").resize((W, H)).getchannel("A")
        top = round(layer["media"]["top"] * H / 100);hgt = round(layer["media"]["height"] * H / 100)
        band = Image.new("L", (W, H), 255);band.paste(0, (0, top, W, top + hgt))
        band = ImageChops.multiply(band, ink.point(lambda v: 255 if v < 10 else 0))
        diff = ImageChops.difference(F, C).convert("L")
        n = ImageStat.Stat(band).sum[0] / 255
        band_d = (ImageStat.Stat(diff, band).mean[0] if n > 500 else 0.0)
        msg = f"장면{i:02d} t={t:5.2f} 칸밖 {int(n):7d}px 차{band_d:5.1f}"
        bad = band_d > 25
        for m in (effects.get(str(i)) or {}).get("masks") or []:
            if m.get("fx") != "blur":
                continue
            box = (round(m["l"] * W / 100), round(m["t"] * H / 100), round((m["l"] + m["w"]) * W / 100), round((m["t"] + m["h"]) * H / 100))
            fs, cs = sharp(F.crop(box)), sharp(C.crop(box))
            bd = ImageStat.Stat(diff.crop(box)).mean[0]
            ratio = cs / max(fs, 1e-3)
            msg += f" | 흐림 선명도 완성{fs:6.1f} 캡컷{cs:6.1f}(×{ratio:4.1f}) 차{bd:4.1f}"
            bad = bad or (ratio > 2.0 and bd > 8)
        hl = scene_hl_of({"scene_hl": (effects.get(str(i)) or {}).get("highlight")}) or {}
        if hl:     # 장면 강조 — 원 자리(cx·cy·r, 화면 너비 기준) 안팎이 완성본과 같은가
            cx, cy, r = float(hl.get("cx", .5)) * W, float(hl.get("cy", .55)) * H, float(hl.get("r", .22)) * W
            box = (max(0, round(cx - r * 1.3)), max(0, round(cy - r * 1.3)), min(W, round(cx + r * 1.3)), min(H, round(cy + r * 1.3)))
            hd = ImageStat.Stat(diff.crop(box)).mean[0]
            msg += f" | 강조 자리 차{hd:5.1f}"
            bad = bad or hd > 15
        fails += bad
        print(("FAIL " if bad else "ok   ") + msg)
        side = Image.new("RGB", (W * 2 // 3, H // 3));side.paste(F.resize((W // 3, H // 3)), (0, 0));side.paste(C.resize((W // 3, H // 3)), (W // 3, 0))
        side.save(out / f"scene_{i:02d}.jpg", quality=80)
    print(f"== {job} (인트로 {shift:.2f}초 밀어 읽음) FAIL {fails} / 장면 {len(layers)}  (그림: {out})")
    return fails


if __name__ == "__main__":
    rc = 0
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for j in args:
        f = audit(j, rebuild(j) if "--rebuild" in sys.argv else None)
        rc |= bool(f)
    sys.exit(1 if rc else 0)
