"""finish.py FINAL DESK SHEET [FRAME] — 1초 시트 + 바탕화면 복사(MD5) + check_seams(render/check_seams.txt) + 0.1초 프레임."""
import hashlib, shutil, subprocess, sys, os
from pathlib import Path
ROOT = Path("C:/Users/CH/Desktop/로또의 주식/.tracks/칼카피숏템엔진")
sys.path.insert(0, str(ROOT))
final, desk, sheet = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
frame = sys.argv[4] if len(sys.argv) > 4 else None
from tools.calcopy.engine.remake import sheet_1s
sheet_1s(final, sheet)
if final.resolve() != desk.resolve():
    shutil.copy(final, desk)
md5 = [hashlib.md5(Path(p).read_bytes()).hexdigest() for p in (final, desk)]
print("md5", md5, "same" if md5[0] == md5[1] else "DIFF")
if frame:
    env = dict(os.environ, PYTHONUTF8="1")
    r = subprocess.run(["py", "tools/calcopy/engine/check_seams.py", str(final), "--frame", frame], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    (final.parent / "check_seams.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
    print("check_seams rc", r.returncode, [l for l in r.stdout.splitlines() if "통과" in l or "실패" in l][:2])
d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)], capture_output=True, text=True).stdout.strip()
print("dur", d)
