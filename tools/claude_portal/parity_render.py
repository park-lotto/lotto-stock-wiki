# -*- coding: utf-8 -*-
"""사장님 엔진 vs 회원 묶음 엔진 — 같은 재료·대본으로 렌더해 완성본이 똑같은가(11/1 숏템MCP 오픈 전, 사장님 10-29 "똑같이 나오게").

  PYTHONUTF8=1 py tools/claude_portal/parity_render.py --owner <엔진 트랙> --member <묶음 폴더> --job <편 job 폴더> --version <판> --out <비교 폴더>
    <편 job 폴더> = flow 작업 폴더의 job/(doc/<판>/대본.json·재료.json, <판>/render/tts_lines·narr_full.mp3 — 목소리 캐시)
  → <out>/owner/final.mp4 · <out>/member/final.mp4 · <out>/parity.json {frames, psnr_min, psnr_avg, audio_diff_db, same}

판정: 프레임 수 같음 + 모든 프레임 PSNR ≥ 40dB(눈으로 구분 안 되는 인코딩 차) + 소리 차이 신호 ≤ -60dB.
돈 0(SHORTEM_NO_PAID=1): 목소리는 캐시만 — 캐시 없으면 렌더가 멈춘다(그 편은 대조 못 함으로 적는다).
렌더 판단은 엔진 render_bench.render 그대로 부른다(새 판단 없음). 회원 묶음은 판 설정·프리셋을 서버가 빌려주는 것을 흉내 내 <member>/ 에 이미 넣어 둔다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

RUN = r"""
import sys, json
sys.path.insert(0, '.')
from pathlib import Path
from tools.calcopy.hybrid import render_bench as RB
w = Path(sys.argv[2]); out = RB.render(sys.argv[1], w / 'doc' / sys.argv[1], w, log=lambda *a: None)
print('FINAL', json.dumps(str(out) if not isinstance(out, dict) else out.get('final') or '', ensure_ascii=False))
"""


def prep(job: Path, version: str, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    (dst / "doc").mkdir(parents=True)
    shutil.copytree(job / "doc" / version, dst / "doc" / version)
    R0, R = job / version / "render", dst / "render"      # render_bench.render 는 <work>/render 에 굽는다
    R.mkdir(parents=True)
    for p in R0.iterdir():          # 목소리 캐시만(줄 합성·이어 붙인 나레·그 표식) — 영상 조각은 새로 굽는다
        if p.name == "tts_lines" or p.name.startswith("narr_full") or (p.suffix == ".wav" and p.name.startswith("s_")):
            (shutil.copytree if p.is_dir() else shutil.copy2)(p, R / p.name)


def render(engine: Path, version: str, work: Path, log: Path) -> tuple[Path | None, float, str]:
    t = time.time()
    env = {**os.environ, "PYTHONUTF8": "1", "SHORTEM_NO_PAID": "1"}
    r = subprocess.run([sys.executable, "-c", RUN, version, str(work)], cwd=str(engine), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=3600)
    log.write_text(r.stdout + "\n--- stderr ---\n" + r.stderr, encoding="utf-8")
    fin = work / "render" / "final.mp4"
    why = "" if r.returncode == 0 else (r.stderr.strip().splitlines() or ["?"])[-1][:300]
    return (fin if fin.exists() and r.returncode == 0 else None), round(time.time() - t, 1), why


def nframes(p: Path) -> int:
    o = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, timeout=600).stdout.strip()
    return int(o or 0)


def _md5(p: Path, stream: str) -> str:
    return subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-map", f"0:{stream}", "-f", "md5", "-"], capture_output=True, text=True, timeout=900).stdout.strip()


def _channels(p: Path) -> int:
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, timeout=120).stdout.strip()
    return int(o or 1)


def compare(a: Path, b: Path) -> dict:
    # 풀어 낸 화면·소리가 비트까지 같으면 더 잴 것 없이 같다(10-29 잇템로그 2편: 화면·소리 md5 일치)
    if _md5(a, "v") == _md5(b, "v") and _md5(a, "a") == _md5(b, "a"):
        n = nframes(a)
        return {"frames": [n, n], "psnr_min": 99.0, "psnr_avg": 99.0, "worst_frames": [], "audio_diff_max_db": -999.0, "bit_identical": True, "same": True}
    fa, fb = nframes(a), nframes(b)
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(a), "-i", str(b), "-lavfi", "[0:v][1:v]psnr=stats_file=-", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    vals = [float(m) if m != "inf" else 99.0 for m in re.findall(r"psnr_avg:([0-9.]+|inf)", r.stdout)]
    worst = sorted(range(len(vals)), key=lambda i: vals[i])[:3]
    ch = _channels(a)       # 모노 완성본이면 합친 둘째 채널이 c1 — c2 로 빼면 소리 크기 자체를 재게 된다(10-29 첫 판 오판 -1.7dB)
    d = subprocess.run(["ffmpeg", "-v", "info", "-i", str(a), "-i", str(b), "-filter_complex",
                        f"[0:a][1:a]amerge=inputs=2,pan=mono|c0=c0-c{ch},volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    mx = re.search(r"max_volume: (-?[0-9.]+|-inf) dB", d.stderr)
    adiff = -999.0 if not mx or mx.group(1) == "-inf" else float(mx.group(1))
    out = {"frames": [fa, fb], "psnr_min": round(min(vals), 2) if vals else None, "psnr_avg": round(sum(vals) / len(vals), 2) if vals else None,
           "worst_frames": [(i, round(vals[i], 2)) for i in worst], "audio_diff_max_db": adiff}
    out["same"] = fa == fb and bool(vals) and min(vals) >= 40 and adiff <= -60
    return out


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--member", required=True)
    ap.add_argument("--job", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = {"job": a.job, "version": a.version}
    finals = {}
    for side, eng in (("owner", Path(a.owner)), ("member", Path(a.member))):
        w = out / side
        prep(Path(a.job), a.version, w)
        fin, sec, why = render(eng.resolve(), a.version, w, out / f"{side}.log")
        res[side] = {"sec": sec, "ok": bool(fin), "why": why}
        finals[side] = fin
        print(side, "렌더", sec, "초", "완성" if fin else f"실패: {why}", flush=True)
    if finals["owner"] and finals["member"]:
        res["compare"] = compare(finals["owner"], finals["member"])
        res["same"] = res["compare"]["same"]
    else:
        res["same"] = False
    (out / "parity.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res["same"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
