# -*- coding: utf-8 -*-
"""지식롱폼 꾸러미 만들기. 사용: python -X utf8 build_longform.py <엔진 폴더(tools.lock 출처)> <출력 zip>"""
import fnmatch, re, shutil, sys, tempfile, zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "calcopy" / "longform"
LOCK, ZP = Path(sys.argv[1]) / "installer/common/tools.lock.json", Path(sys.argv[2])
DROP = ("*/__pycache__/*", "*.pyc", "fonts/Pretendard-Regular.otf.bak")
SECRETS = (r"3\.35\.251\.172", r"LightsailDefaultKey", r"AIza[0-9A-Za-z_-]{30,}", r"apikey_[0-9a-f]{20,}", r"parklotto12", r"\.volcano", r"지식한입", r"Chris", r"일레븐랩스")
names = []
with zipfile.ZipFile(ZP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    def put(p, arc):
        z.write(p, "shorcl_long/" + arc); names.append(arc)
    for p in SRC.rglob("*"):
        rel = p.relative_to(SRC).as_posix()
        if p.is_file() and not any(fnmatch.fnmatch(rel, d) for d in DROP): put(p, rel)
    F = HERE / "longform_files"
    for n in ("CLAUDE.md", "setup.ps1", "requirements.txt"): put(F / n, n)
    put(F / "keys_input.py", "steps/keys_input.py")
    put(LOCK, "tools.lock.json")
bad = []
for p in SRC.rglob("*"):
    if p.suffix in (".py", ".md", ".json", ".txt"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        bad += [(p.relative_to(SRC).as_posix(), s) for s in SECRETS if re.search(s, t)]
print(len(names), "파일", ZP.stat().st_size // 1000000, "MB", "금지 글자", len(bad))
for b in bad[:14]: print(" ", b)
sys.exit(1 if bad else 0)
