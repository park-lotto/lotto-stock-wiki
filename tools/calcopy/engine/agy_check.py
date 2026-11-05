# -*- coding: utf-8 -*-
"""agy 판독이 프로그램 숫자와 맞는지 여러 편으로 잰다(관제 319 §13-1). 결과 = <out>/agy_check.json · 표 한 줄씩 출력.
    PYTHONUTF8=1 py -m tools.calcopy.engine.agy_check <mp4> [<mp4> …] --out <영문 폴더>
    PYTHONUTF8=1 py -m tools.calcopy.engine.agy_check --synth --out <영문 폴더>   # 5b: 0.2·0.4·1초 색 화면을 보는지(역할 경계 재측정)"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from tools.calcopy.engine import agy, kal_analyze as KA
from tools.calcopy.engine.encoder import venc

SCHEMA = {"type": "object", "properties": {"duration_s": {"type": "number"}, "cut_count": {"type": "integer"},
          "first_caption": {"type": "string"}, "has_narration": {"type": "boolean"}}, "required": ["duration_s", "cut_count"]}

SYNTH_SCHEMA = {"type": "object", "properties": {"flashes": {"type": "array", "items": {"type": "object", "properties": {
    "color": {"type": "string"}, "approx_start_s": {"type": "number"}}}}}, "required": ["flashes"]}
# 검은 화면 4초 위에 빨강 0.2초(t=0.5) · 초록 0.4초(t=1.5) · 파랑 1.0초(t=2.5). agy 가 몇 개를 보는지 잰다.
SYNTH_TRUTH = [("red", 0.5, 0.2), ("green", 1.5, 0.4), ("blue", 2.5, 1.0)]


def to360(src: Path, dst: Path) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "scale=-2:360", *venc(crf=28), "-c:a", "aac", "-b:a", "64k", str(dst)], check=True)
    return dst


def make_synth(dst: Path) -> Path:
    vf = ",".join(f"drawbox=x=0:y=0:w=iw:h=ih:color={c}:t=fill:enable='between(t,{s},{s + d})'" for c, s, d in SYNTH_TRUTH)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=360x640:r=30:d=4", "-vf", vf,
                    *venc(crf=23), "-pix_fmt", "yuv420p", str(dst)], check=True)
    return dst


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("mp4", nargs="*"); ap.add_argument("--out", required=True)
    ap.add_argument("--synth", action="store_true")
    a = ap.parse_args(argv); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows = []
    if a.synth:
        v = make_synth(out / "synth.mp4")
        r = agy.ask_video(v, "검은 화면 위에 잠깐 번쩍이는 색 화면이 있다. 모든 번쩍임의 색과 대략 시작 초를 빠짐없이 적어라.", SYNTH_SCHEMA)
        row = {"truth": SYNTH_TRUTH, "agy": r.get("answer"), "sec": r.get("sec"), "error": r.get("error")}
        rows.append(row); print(json.dumps(row, ensure_ascii=False))
    for i, m in enumerate(a.mp4):
        v = to360(Path(m), out / f"v{i}.mp4")
        md = KA.media_of(str(m))
        r = agy.ask_video(v, "영상 길이(초), 컷 수, 화면에 처음 나오는 자막 글자, 나레이션 유무", SCHEMA)
        ans = r.get("answer") or {}
        row = {"mp4": m, "prog_dur": md.get("duration"), "agy_dur": ans.get("duration_s"), "prog_cuts": md.get("n_cuts"), "agy_cuts": ans.get("cut_count"),
               "first_caption": ans.get("first_caption"), "sec": r.get("sec"), "error": r.get("error")}
        rows.append(row); print(json.dumps(row, ensure_ascii=False))
    (out / "agy_check.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if any(r.get("error") for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
