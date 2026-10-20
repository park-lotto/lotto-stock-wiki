# -*- coding: utf-8 -*-
"""작업물 비평 도구(관제 244, 2026-10-20) — 렌더 mp4 → 0.5초 프레임 시트 + 지시서 QUALITY_CHECK 중 잴 수 있는 것 자동 + 레퍼런스와 나란히 비교 그림.
사용:
  py tools/mograph/critique.py --work work-298bdc5dc0 --ref 2103918792845963545 --out out/모션그래픽엔진/작업물2
  py tools/mograph/critique.py --mp4 <파일> --out <폴더>                      (장부 밖 영상도 된다)
산출물: <out>/frames_0.5s.png(시트) · <out>/compare_ref_vs_work.png(레퍼런스 띠 위·작업물 띠 아래) · <out>/critique.json(자동 측정)
자동으로 재는 것(지시서 QUALITY_CHECK 에서 숫자로 잴 수 있는 것만 — 글자 겹침·촌스러움은 눈이 판정):
  빈 프레임(전경 1% 미만) 0.3초 이상 연속 없음 · 바탕색 통째 전환 횟수 · 장면 수(실측 검출) · 강조색(채도 높은 색) 종류 수 · 마지막 1초 정지(프레임차 < 2)
★점수는 사람이 매긴다 — 이 도구는 근거 숫자와 그림만 만든다(0xMovez 8점 비평 루프의 자료)."""
import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shopping_shorts.mograph import reverse as rv, render as rd      # noqa: E402

STEP = 0.5


def frames_sheet(mp4, png, duration, step=STEP, cols=6, width=200):
    tiles = int(duration / step) + 1
    rows = -(-tiles // cols)
    vf = "fps=1/%.3f,scale=%d:-1,tile=%dx%d:padding=4:margin=4:color=0x202020" % (step, width, cols, rows)
    r = rv._run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vf", vf, "-frames:v", "1", str(png)], 180)
    return png.exists(), (r.stderr or "")[-200:]


def accent_colors(series_frames_dir):
    """장면 대표 프레임들에서 채도 높은(HSV s>0.45, v>0.35) 픽셀의 색상(hue 30도 단위) 종류 수."""
    import numpy as np
    from PIL import Image
    hues = set()
    for p in sorted(Path(series_frames_dir).glob("s[0-9][0-9].png")):
        im = Image.open(p).convert("HSV").resize((120, 68))
        a = np.asarray(im)
        m = (a[:, :, 1] > 115) & (a[:, :, 2] > 90)
        if m.sum() < 60:
            continue
        h = a[:, :, 0][m]
        for b in np.unique(h // 21):      # 255/12 ≈ 21 → 12칸
            if (h // 21 == b).sum() > 40:
                hues.add(int(b))
    return sorted(hues)


def measure_work(mp4, d):
    m = rv.measure(mp4, d)
    ser = m["series"]
    # 빈 프레임: 바탕색이 화면의 99% 이상인 표본이 0.3초 이상 연속
    blank_runs, run = [], 0
    for x in ser:
        if x["bg_share"] >= 0.99:
            run += 1
        else:
            if run * (1 / rv.SAMPLE_FPS) >= 0.3:
                blank_runs.append(round(run / rv.SAMPLE_FPS, 2))
            run = 0
    if run * (1 / rv.SAMPLE_FPS) >= 0.3:
        blank_runs.append(round(run / rv.SAMPLE_FPS, 2))
    last = [x["diff"] for x in ser if x["t"] >= m["probe"]["duration"] - 1.0]
    return {"scene_count": m["scene_count"], "bg_flips": m["bg_flips"], "bg_sequence": m["bg_sequence"], "cuts_per_s": m["cuts_per_s"],
            "scene_dur": m["scene_dur"], "blank_runs_s": blank_runs, "accent_hues": accent_colors(d / "scenes"),
            "last_1s_max_diff": round(max(last), 2) if last else None, "duration": m["probe"]["duration"], "size": [m["probe"]["w"], m["probe"]["h"]]}


def compare_image(ref_strip, work_strip, out_png, title_ref, title_work):
    from PIL import Image, ImageDraw
    a = Image.open(ref_strip).convert("RGB")
    b = Image.open(work_strip).convert("RGB")
    W = max(a.width, b.width)
    canvas = Image.new("RGB", (W, a.height + b.height + 80), (18, 18, 18))
    dr = ImageDraw.Draw(canvas)
    dr.text((8, 8), title_ref, fill=(240, 240, 240))
    canvas.paste(a, (0, 34))
    dr.text((8, a.height + 46), title_work, fill=(240, 240, 240))
    canvas.paste(b, (0, a.height + 72))
    canvas.save(out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work")
    ap.add_argument("--mp4")
    ap.add_argument("--ref", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    mp4 = Path(a.mp4) if a.mp4 else rd.out_dir(a.work) / "out.mp4"
    if not mp4.exists():
        print("mp4 없음:", mp4); sys.exit(2)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    pr = rv.probe(mp4)
    ok, err = frames_sheet(mp4, out / "frames_0.5s.png", pr["duration"])
    if not ok:
        print("시트 실패:", err); sys.exit(2)
    mdir = out / "_measure"; mdir.mkdir(exist_ok=True)
    met = measure_work(mp4, mdir)
    rv.scene_strip(mdir, json.loads((mdir / "measure.json").read_text(encoding="utf-8")), out / "strip.png")
    res = {"mp4": str(mp4), "label": a.label or a.work or mp4.name, "probe": pr, "auto": met, "sheet": str(out / "frames_0.5s.png")}
    if a.ref:
        rd_ = rv.out_dir(a.ref)
        if (rd_ / "strip.png").exists():
            compare_image(rd_ / "strip.png", out / "strip.png", out / "compare_ref_vs_work.png", "REF " + a.ref, "WORK " + res["label"])
            res["compare"] = str(out / "compare_ref_vs_work.png")
            rec = rv.find_ref(a.ref) or {}
            res["ref_measure"] = rec.get("measure")
    (out / "critique.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("label", "auto", "sheet") if k in res} | ({"compare": res["compare"]} if "compare" in res else {}), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
