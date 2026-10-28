"""프리셋 견본 300개를 눈으로 훑을 점검 시트로 만든다 (관제 112).

영상마다 자막 띠(세로 1000~1500)만 잘라 7장(0.3~3.3초)을 한 줄로, 20줄씩 한 장.
줄 순서 = P 번호 순서. 출력: D:\\ae_fx_work\\presets_sheets\\sheet_<첫번호>.png
사용: py tools/ae_fx/preset_sheets.py
"""
import subprocess
import sys
from pathlib import Path

SRC = Path(r"D:\ae_fx_work\presets")
OUT = Path(r"D:\ae_fx_work\presets_sheets")
ROWS, N, CW = 20, 7, 220


def main():
    OUT.mkdir(exist_ok=True)
    vids = sorted(SRC.glob("P*.mp4"))
    tmp = OUT / "_rows"
    tmp.mkdir(exist_ok=True)
    for v in vids:
        row = tmp / f"{v.stem}.png"
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", "0.3", "-t", "3.0", "-i", str(v),
               "-vf", f"fps={N}/3.0,crop=1080:500:0:1000,scale={CW}:-1,tile={N}x1", "-frames:v", "1", str(row)]
        if subprocess.run(cmd).returncode:
            print(f"[실패] {v.name}")
            return 1
    for i in range(0, len(vids), ROWS):
        chunk = vids[i:i + ROWS]
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for v in chunk:
            cmd += ["-i", str(tmp / f"{v.stem}.png")]
        out = OUT / f"sheet_{chunk[0].stem}.png"
        cmd += ["-filter_complex", f"vstack=inputs={len(chunk)}", str(out)] if len(chunk) > 1 else ["-c", "copy", str(out)]
        if subprocess.run(cmd).returncode:
            return 1
    print(f"{len(vids)}개 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
