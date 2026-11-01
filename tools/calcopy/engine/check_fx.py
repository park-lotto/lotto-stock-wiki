"""강조어 자막·모션 효과 결과물 검사(관제 097, 10-24) — 계산이 아니라 나온 영상 프레임으로 잰다.

  py -m tools.calcopy.engine.check_fx fx <효과켠 make 폴더> <효과끈 make 폴더>
      run_log.json fx_placed(line_fx.apply 가 실은 효과)·timeline.json(move 컷)의 시각마다 두 영상 프레임을 떠서
      ① move 컷: 두 시각 평균 픽셀차 ≥ 2.0
      ② 강조 낱말 색: 켠 영상에만 새로 생긴 그 색(노랑 #FFE600·분홍 #FF4FA3 ±40) 픽셀 ≥ 300
      ③ 스티커: 바뀐 픽셀(채널 차 >60) ≥ 300 이고, 그 픽셀이 화면 가운데(가로 20~80%·세로 20~65%) 의 35% 이하
      하나라도 미달이면 rc=1. 효과 칸이 하나도 없으면(fx_placed 없음) 그것도 미달 — 아무것도 안 잰 통과를 막는다.
  py -m tools.calcopy.engine.check_fx same <영상A> <영상B>
      프레임마다 해시(ffmpeg framemd5) 비교 — 효과 칸 없는 옛 편이 새 코드에서 그대로인지. 다르면 rc=1."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

W, H = 540, 960
COLORS = {"#FFE600": (255, 230, 0), "#FF4FA3": (255, 79, 163)}


def frame(video: Path, t: float) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={W}:{H}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(np.int16)


def near(img, rgb, tol=40):
    return (np.abs(img - np.array(rgb)).max(2) <= tol)


def check_fx(on_dir: Path, off_dir: Path) -> list[dict]:
    log = json.loads((on_dir / "run_log.json").read_text(encoding="utf-8"))
    tl = json.loads((on_dir / "timeline.json").read_text(encoding="utf-8"))
    on, off = on_dir / "final.mp4", off_dir / "final.mp4"
    rows = []
    placed = log.get("fx_placed") or []
    if not placed:
        rows.append({"t": None, "kind": "-", "what": "fx_placed 없음(효과가 실리지 않았다)", "val": 0, "ok": False})
    for p in placed:
        t = float(p["t"]) + (0.15 if p["kind"] in ("pop", "flash") else 0.30)   # 등장(150~300ms) 뒤 · 번쩍은 0.4초에 사라져 가운데
        a, b = frame(on, t), frame(off, t)
        diff = float(np.abs(a - b).mean())
        r = {"t": round(t, 2), "kind": p["kind"], "word": p["word"], "diff": round(diff, 2)}
        if p["kind"] == "emph":
            rgb = COLORS.get(p["color"].upper(), (255, 230, 0))
            new = int((near(a, rgb) & ~near(b, rgb)).sum())
            r.update(what=f"새 {p['color']} 픽셀", val=new, ok=new >= 300)
        else:
            ch = np.abs(a - b).max(2) > 60
            c = ch[int(H * .2):int(H * .65), int(W * .2):int(W * .8)].mean()
            n = int(ch.sum())
            r.update(what=f"바뀐 픽셀 {n} · 가운데 가림 비율", val=round(float(c), 3), ok=n >= 300 and c <= 0.35)
        rows.append(r)
    for g in tl["groups"]:
        if not g.get("move"):
            continue
        t0, d = float(g["t0"]), float(g["dur"])
        ts = [t0 + d * 0.25, t0 + d * 0.6]
        fa = [frame(on, t) for t in ts]
        diff = float(np.mean([np.abs(x - frame(off, t)).mean() for x, t in zip(fa, ts)]))
        rows.append({"t": round(t0, 2), "kind": f"move:{g['move'] if isinstance(g['move'], str) else g['move'].get('kind')}",
                     "word": g["src"], "diff": round(diff, 2), "what": "끈 영상과 픽셀차", "val": round(diff, 2), "ok": diff >= 2.0})
    return rows


def same(a: Path, b: Path) -> tuple[int, int]:
    def fm(v):
        out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(v), "-an", "-f", "framemd5", "-"], capture_output=True, text=True, check=True).stdout
        return [l.split(",")[-1].strip() for l in out.splitlines() if l and not l.startswith("#")]
    x, y = fm(a), fm(b)
    return sum(1 for i, j in zip(x, y) if i != j) + abs(len(x) - len(y)), max(len(x), len(y))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    if mode == "same":
        bad, n = same(Path(sys.argv[2]), Path(sys.argv[3]))
        print(f"프레임 {n}장 중 다른 것 {bad}장 → {'같음' if bad == 0 else '다름'}")
        return 0 if bad == 0 else 1
    rows = check_fx(Path(sys.argv[2]), Path(sys.argv[3]))
    print("| 시각 | 종류 | 낱말/소스 | 픽셀차 | 잰 것 | 값 | 판정 |\n|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['t']} | {r['kind']} | {r.get('word', '')} | {r.get('diff', '')} | {r['what']} | {r['val']} | {'통과' if r['ok'] else '미달'} |")
    ok = all(r["ok"] for r in rows)
    print("판정:", "통과" if ok else "미달")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
