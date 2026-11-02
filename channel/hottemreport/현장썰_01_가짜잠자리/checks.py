# -*- coding: utf-8 -*-
"""현장썰 1편 완성본 자동 검사(숫자) — make_render.py 뒤에 돈다 (관제 097, 2026-10-18).
    PYTHONUTF8=1 py channel/hottemreport/현장썰_01_가짜잠자리/checks.py [<mp4>]
재는 것: 길이·LUFS·최고점 / 원음 창 안 나레 겹침(narr_gapped 소리 > −45dB 칸 비율) / 원음−나레 크기(구간 LUFS) /
  완성본 구간 받아쓰기(나레 줄·원음 창, 무료 제미나이 gemini_free) / check_seams / 1초 시트·0.5초 앞 5초 시트 / 컷 목록(B13 같은 소스 ±3초).
결과 = render/checks.json + plan 폴더 시트. 판정은 숫자로만, 눈 판독(시트 줄별 대조)은 사람이 근거.md 에 적는다.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ["BRAINBULB_VERTEX"] = "0"
from tools.calcopy import hottem_audio as ha  # noqa: E402

D = Path(__file__).resolve().parent
R = Path("C:/숏템_칼카피/hottemreport/현장썰_01_가짜잠자리/render")


def sh(cmd):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")


def ebur(p, a=None, b=None):
    cmd = ["ffmpeg", "-hide_banner"] + (["-ss", f"{a:.3f}", "-to", f"{b:.3f}"] if a is not None else []) + ["-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"]
    e = sh(cmd).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])
    pk = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)
    return I, (float(pk[-1]) if pk else None)


def overlap(win):
    """원음 창 안에서 나레(narr_gapped.wav)가 소리 내는 50ms 칸 비율(> −45dBFS)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(R / "narr_gapped.wav"), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(float) / 32768
    n = 800
    out = []
    for a, b in win:
        cells = [x[i:i + n] for i in range(int(a * 16000), int(b * 16000) - n + 1, n)]
        db = [20 * np.log10(np.sqrt((c ** 2).mean()) + 1e-9) for c in cells]
        out.append({"win": [a, b], "cells": len(db), "narr_cells": int(sum(d > -45 for d in db)), "ratio": round(sum(d > -45 for d in db) / max(1, len(db)), 3)})
    return out


def asr(mp4, spans):
    from tools.calcopy.engine.gemini_free import ask_many
    P = '이 오디오의 말을 들리는 그대로 받아써라(한국어는 한국어, 영어는 영어). 배경음악은 빼라. JSON만: {"text":""}'
    jobs = []
    for k, (a, b) in enumerate(spans):
        o = R / f"look/chk_{k}.mp3"
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", o])
        jobs.append(([(o.read_bytes(), "audio/mp3")], P, "final_chk"))
    return [((d or {}).get("text"), e) for d, e in ask_many(jobs)]


def norm(s):
    return re.sub(r"[^가-힣a-z0-9]", "", (s or "").lower())


def main():
    mp4 = Path(sys.argv[1]) if len(sys.argv) > 1 else R / "final.mp4"
    S = json.loads((D / "대본_render.json").read_text(encoding="utf-8"))
    rend = S["render"]
    blocks, win, dur = rend["blocks"], [tuple(w) for w in rend["windows"]], rend["dur"]
    res = {"mp4": str(mp4)}
    res["dur"] = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]).stdout.strip())
    res["lufs_I"], res["peak_dbfs"] = ebur(mp4)
    res["overlap"] = overlap(win)
    nspan = [(b["n0"], b["n1"]) for b in blocks if b["kind"] == "나레"]
    res["narr_lufs"] = [round(ebur(mp4, a, b)[0], 1) for a, b in nspan]
    res["orig_lufs"] = [round(ebur(mp4, a, b)[0], 1) for a, b in win]
    nmed = sorted(res["narr_lufs"])[len(nspan) // 2]
    res["orig_minus_narr_db"] = [round(o - nmed, 1) for o in res["orig_lufs"]]
    lines = {l["id"]: l for l in json.loads((D / "대본.json").read_text(encoding="utf-8"))["final"]["lines"]}
    O = {o["id"]: o for o in json.loads((D / "대본.json").read_text(encoding="utf-8"))["final"]["orig_audio"]}
    spans = [(b["n0"] - 0.05, b["n1"] + 0.1) if b["kind"] == "나레" else (b["a0"] - 0.05, b["a1"] + 0.05) for b in blocks]
    got = asr(mp4, spans)
    rows = []
    for b, (txt, err) in zip(blocks, got):
        want = lines[b["id"]]["text"] if b["kind"] == "나레" else O[b["id"]]["en"]
        w, g = norm(want), norm(txt)
        import difflib
        rows.append({"id": b["id"], "want": want, "got": txt, "err": err, "sim": round(difflib.SequenceMatcher(None, w, g).ratio(), 3)})
    res["asr"] = rows
    r = sh(["py", ROOT / "tools/calcopy/engine/check_seams.py", mp4, "--frame", D / "frame_render.json", "--json", R / "seams.json"])
    res["check_seams"] = {"rc": r.returncode, "tail": (r.stdout or "")[-1500:]}
    (D / "plan").mkdir(exist_ok=True)
    n = int(res["dur"]) + 1
    cols = 9
    sh(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vf", f"fps=1,scale=240:427,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='%{{pts\\:hms}}':x=6:y=6:fontsize=22:fontcolor=yellow:box=1:boxcolor=black,"
        f"tile={cols}x{(n + cols - 1) // cols}", "-frames:v", "1", "-q:v", "3", D / "final_sheet_1s.jpg"])
    sh(["ffmpeg", "-v", "error", "-y", "-t", "6", "-i", mp4, "-vf", "fps=2,scale=270:480,tile=6x2", "-frames:v", "1", "-q:v", "3", R / "look/head_0.5s.jpg"])
    # B13: 같은 소스 겹침·±3초
    pcs = rend["pieces"]
    b13 = []
    for i in range(len(pcs)):
        for j in range(i + 1, len(pcs)):
            p, q = pcs[i], pcs[j]
            if p["src"] != q["src"]:
                continue
            gap = max(q["ss"] - p["src_end"], p["ss"] - q["src_end"])
            if gap < 3.0:
                b13.append({"a": [p["block"], p["ss"], p["src_end"]], "b": [q["block"], q["ss"], q["src_end"]], "gap_s": round(gap, 2)})
    res["b13_same_src_within_3s"] = b13
    res["cuts"] = len(pcs)
    (R / "checks.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
