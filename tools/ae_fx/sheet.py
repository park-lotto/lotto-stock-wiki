"""견본 영상을 눈으로 점검할 프레임 시트로 만든다 (관제 112).

영상마다 한 줄(균등 간격 N장), 여러 영상을 세로로 쌓아 PNG 한 장.
사용: py tools/ae_fx/sheet.py <출력.png> <영상> [<영상> ...] [--n 10] [--w 190] [--from 0] [--to 4]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--w", type=int, default=190)
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=4.0)
    a = ap.parse_args()
    rows = []
    tmp = Path(tempfile.mkdtemp(prefix="fxsheet_"))
    for i, v in enumerate(a.videos):
        row = tmp / f"row{i}.png"
        fps = a.n / (a.t1 - a.t0)
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(a.t0), "-t", str(a.t1 - a.t0), "-i", v,
               "-vf", f"fps={fps},scale={a.w}:-1,tile={a.n}x1", "-frames:v", "1", str(row)]
        if subprocess.run(cmd).returncode:
            print(f"[실패] {v}")
            return 1
        rows.append(row)
    if len(rows) == 1:
        Path(a.out).write_bytes(rows[0].read_bytes())
    else:
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for r in rows:
            cmd += ["-i", str(r)]
        cmd += ["-filter_complex", f"vstack=inputs={len(rows)}", str(a.out)]
        if subprocess.run(cmd).returncode:
            return 1
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
