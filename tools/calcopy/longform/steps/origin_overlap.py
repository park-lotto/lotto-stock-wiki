# 원본 zip 과 우리 코드가 줄 단위로 얼마나 겹치는지 잰다(12자 초과 줄).
# 사용: python -X utf8 origin_overlap.py <원본.zip>
import os, sys, zipfile
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
z = zipfile.ZipFile(sys.argv[1])
theirs = {l.strip() for i in z.infolist() if i.filename.endswith((".py", ".ps1")) for l in z.read(i).decode("utf-8", "replace").splitlines() if len(l.strip()) > 12}
rows = []
for r, ds, fs in os.walk(HERE):
    ds[:] = [d for d in ds if d not in ("__pycache__", "fonts", "media")]
    for f in fs:
        if f.endswith((".py", ".ps1")):
            p = os.path.join(r, f); big = [l.strip() for l in open(p, encoding="utf-8", errors="replace") if len(l.strip()) > 12]
            if big: rows.append((sum(l in theirs for l in big), len(big), os.path.relpath(p, HERE)))
rows.sort(key=lambda x: -x[0] / x[1])
for same, n, name in rows[:12]: print(f"{same / n * 100:5.1f}% {same}/{n} {name}")
s = sum(r[0] for r in rows); a = sum(r[1] for r in rows); print(f"전체 {s}/{a} = {s / a * 100:.1f}%")
