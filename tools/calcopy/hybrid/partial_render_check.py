# -*- coding: utf-8 -*-
"""부분 렌더 결과물 대조(관제 304 · 0순위-C 결과물 검사) — 저장 편 작업 폴더 복사본에서 컷 1개를 바꿔 부분 렌더와 전체 렌더를 프레임·소리로 맞댄다.

  순서  ① 기준 렌더(재사용 씨앗)  ② 재료 컷 1개 시작 초를 옮긴다  ③ 부분 렌더  ④ 전체 렌더(SHORTEM_FULL_RENDER=1)  ⑤ 대조
  대조  프레임 수 · 프레임마다 PSNR(최저·구간 경계 ±3프레임) · 소리 표본 차(최대·상관 최대 지연) · 렌더 시간
  자기 시험  --self = 대조 함수가 정말 어긋남을 잡나: 기준(바꾸기 전) 완성본과 맞대 '바꾼 컷 구간이 달라야' 통과. 못 잡으면 이 도구는 아무것도 안 재는 것이다.

    PYTHONUTF8=1 py tools/calcopy/hybrid/partial_render_check.py <작업폴더 복사본> <판 이름> [--cut 줄:번호] [--move 초] [--line 줄id]
유료 호출 없음: SHORTEM_NO_PAID=1(TTS 는 캐시만) · Claude 호출 없음. 렌더 전 관문은 SHORTEM_WAIVE_GATE=1 로 기록만(옛 편이 새 관문에 걸려도 대조가 목적).
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

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PSNR_SAME = 38.0        # 같은 그림을 두 번 인코딩한 차이는 이 위(실측으로 잰 바닥 — 보고에 원시 값을 같이 적는다)
AUDIO_MAX = 0.02        # 소리 표본 차 최대(풀 스케일 1.0 기준)


def _render(W: Path, v: str, full: bool) -> tuple[float, dict]:
    env = dict(os.environ, SHORTEM_NO_PAID="1", SHORTEM_WAIVE_GATE="1", PYTHONUTF8="1", **({"SHORTEM_FULL_RENDER": "1"} if full else {}))
    if not full:
        env.pop("SHORTEM_FULL_RENDER", None)
    code = ("import sys,json;from pathlib import Path;from tools.calcopy.hybrid import runner_ops as R;"
            "print('@@'+json.dumps(R._c_render(Path(sys.argv[1]),{'version':sys.argv[2],'origin_names':[],'other_faces':False}),ensure_ascii=False))")
    t0 = time.time()
    r = subprocess.run([sys.executable, "-c", code, str(W), v], cwd=str(ROOT), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sec = round(time.time() - t0, 1)
    out = next((x[2:] for x in r.stdout.splitlines() if x.startswith("@@")), None)
    if not out:
        raise SystemExit(f"렌더 실패 rc={r.returncode}: {r.stderr[-1500:]}")
    res = json.loads(out)
    res["log"] = [x for x in (r.stdout + r.stderr).splitlines() if "[부분 렌더]" in x or "[썸네일]" in x]
    return sec, res


def _gray(video: Path) -> tuple[bytes, int, int]:
    w, h = 270, 480
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    return raw, w, h


def frame_psnr(a: Path, b: Path) -> list[float]:
    """프레임마다 PSNR(작은 회색 — 위치·장면 어긋남을 잡는다). 프레임 수가 다르면 짧은 쪽까지."""
    import numpy as np
    ra, w, h = _gray(a)
    rb, _, _ = _gray(b)
    n = min(len(ra), len(rb)) // (w * h)
    x = np.frombuffer(ra[:n * w * h], np.uint8).reshape(n, h, w).astype(float)
    y = np.frombuffer(rb[:n * w * h], np.uint8).reshape(n, h, w).astype(float)
    mse = ((x - y) ** 2).mean(axis=(1, 2))
    return [99.0 if m < 1e-9 else float(10 * np.log10(255 ** 2 / m)) for m in mse]


def frames_of(p: Path) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return int(re.sub(r"\D", "", r.stdout) or 0)


def pcm(p: Path):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(raw, np.float32)


def audio_diff(a: Path, b: Path) -> dict:
    """소리 표본 차와 밀림 — 상관이 가장 큰 지연(표본, 16kHz). 밀리면 0 이 아니다."""
    import numpy as np
    x, y = pcm(a), pcm(b)
    n = min(len(x), len(y))
    d = float(np.abs(x[:n] - y[:n]).max()) if n else 1.0
    win = 800
    best, lag = -2.0, 0
    x2, y2 = x[win:min(n, win + 16000 * 8)], y
    for k in range(-win, win + 1, 8):
        seg = y2[win + k:win + k + len(x2)]
        if len(seg) == len(x2) and x2.std() > 0:
            c = float(np.corrcoef(x2, seg)[0, 1])
            if c > best:
                best, lag = c, k
    return {"samples": [len(x), len(y)], "max_diff": round(d, 5), "lag_samples": lag, "corr": round(best, 5)}


def compare(a: Path, b: Path, cuts: list[dict]) -> dict:
    """a·b 완성본 대조 — 프레임 수·PSNR·경계·소리. cuts = 시간표 컷(경계 ±3프레임을 따로 본다)."""
    p = frame_psnr(a, b)
    edges = sorted({round(float(c["t0"]) * 30) for c in cuts[1:]})
    near = [p[k] for f in edges for k in range(max(0, f - 3), min(len(p), f + 3))]
    srt = sorted(p)
    return {"frames": [frames_of(a), frames_of(b)], "psnr_min": round(srt[0], 2), "psnr_p01": round(srt[len(srt) // 100], 2), "psnr_med": round(srt[len(srt) // 2], 2),
            "edge_min": round(min(near), 2) if near else None, "worst_frame": p.index(srt[0]), "audio": audio_diff(a, b), "n": len(p), "per_frame": p}


def verdict(c: dict) -> list[str]:
    """부분 렌더 = 전체 렌더? 걸린 것 목록(빈 목록 = 통과)."""
    bad = []
    if c["frames"][0] != c["frames"][1]:
        bad.append(f"프레임 수 {c['frames']}")
    if c["psnr_min"] < PSNR_SAME:
        bad.append(f"PSNR 최저 {c['psnr_min']} < {PSNR_SAME}(프레임 {c['worst_frame']})")
    if c["edge_min"] is not None and c["edge_min"] < PSNR_SAME:
        bad.append(f"컷 경계 PSNR {c['edge_min']} < {PSNR_SAME}")
    if abs(c["audio"]["lag_samples"]) > 0:
        bad.append(f"소리 밀림 {c['audio']['lag_samples']}표본")
    if c["audio"]["max_diff"] > AUDIO_MAX:
        bad.append(f"소리 표본 차 {c['audio']['max_diff']} > {AUDIO_MAX}")
    return bad


def move_cut(doc: Path, line: str, k: int, sec: float) -> str:
    p = doc / "재료.json"
    M = json.loads(p.read_text(encoding="utf-8"))
    c = M["cuts"][line][k] if isinstance(M["cuts"][line], list) else M["cuts"][line]
    was = c.get("ss")
    c["ss"] = round(float(was or 0) + sec, 3)
    p.write_text(json.dumps(M, ensure_ascii=False), encoding="utf-8")
    return f"{line}[{k}] {c.get('src')} ss {was} → {c['ss']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work"); ap.add_argument("style")
    ap.add_argument("--cut", default="L2:0", help="줄:그 줄 안 컷 번호")
    ap.add_argument("--move", type=float, default=1.0, help="시작 초를 이만큼 옮긴다")
    ap.add_argument("--out", help="결과 json")
    a = ap.parse_args()
    W, v = Path(a.work), a.style
    R = W / v / "render"
    t = {}
    t["기준 렌더(씨앗)"], r = _render(W, v, False)
    print("기준", t["기준 렌더(씨앗)"], r.get("ok"), r.get("error", "")[:200], r["log"], flush=True)
    T0 = json.loads((R / "timeline.json").read_text(encoding="utf-8"))
    base = R.parent / "_base_final.mp4"
    shutil.copy2(R / "final.mp4", base)
    line, k = a.cut.split(":")
    what = move_cut(W / "doc" / v, line, int(k), a.move)
    print("바꾼 컷:", what, flush=True)
    t["부분 렌더"], r = _render(W, v, False)
    print("부분", t["부분 렌더"], r.get("ok"), r.get("error", "")[:200], r["log"], flush=True)
    part = R.parent / "_part_final.mp4"
    shutil.copy2(R / "final.mp4", part)
    T1 = json.loads((R / "timeline.json").read_text(encoding="utf-8"))
    t["전체 렌더"], r = _render(W, v, True)
    print("전체", t["전체 렌더"], r.get("ok"), r.get("error", "")[:200], r["log"], flush=True)
    full = R.parent / "_full_final.mp4"
    shutil.copy2(R / "final.mp4", full)
    c = compare(part, full, T1["cuts"])
    bad = verdict(c)
    # 자기 시험 — 바꾼 컷 구간은 바꾸기 전 완성본과 달라야 한다(대조가 어긋남을 잡는다는 증거)
    me = compare(part, base, T1["cuts"])
    fp0 = {x["fp"] for x in T0["cuts"]}
    ch = [(float(x["t0"]), float(x["t1"])) for x in T1["cuts"] if x["fp"] not in fp0]
    low = [i for i, x in enumerate(me["per_frame"]) if x < PSNR_SAME]
    inside = [i for i in low if any(a0 * 30 - 20 <= i <= b0 * 30 + 20 for a0, b0 in ch)]
    self_ok = bool(low) and len(inside) == len(low)
    rep = {"changed": what, "changed_cuts": ch, "sec": t, "saved_pct": round((1 - t["부분 렌더"] / t["전체 렌더"]) * 100, 1), "part_vs_full": {k_: v_ for k_, v_ in c.items() if k_ != "per_frame"},
           "verdict": bad or "같음", "self_check": {"part_vs_before_low_frames": len(low), "inside_changed": len(inside), "outside_frames": [i for i in low if i not in inside], "ok": self_ok,
                                                  "psnr_min": me["psnr_min"]}}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    for f in (base, part, full):
        f.unlink(missing_ok=True)
    return 0 if not bad and self_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
