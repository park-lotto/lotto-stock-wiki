# -*- coding: utf-8 -*-
"""키 입력. 메모장에 붙여넣고 저장·닫기만 하면 된다."""
import subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
KEYS = Path(__file__).resolve().parent.parent / "data" / "keys"
KEYS.mkdir(parents=True, exist_ok=True)
FORM = KEYS / "입력.txt"
ITEMS = [("typecast", "타입캐스트", "typecast.ai > 개발자 > API 키"), ("pixabay", "Pixabay", "pixabay.com/api/docs"),
         ("gemini", "제미나이", "aistudio.google.com > Get API key. 결제 등록이 필요합니다"), ("typesafe", "TypeSafe", "console.typesafe.ai/keys")]
lines = ["# 각 줄의 = 뒤에 키를 붙여넣고 저장한 뒤 메모장을 닫아 주세요.", ""]
for k, label, where in ITEMS:
    if not (KEYS / k).exists(): lines += [f"# {label} — {where}", f"{k}=", ""]
if len(lines) == 2:
    print("키 입력 끝"); sys.exit(0)
FORM.write_text("\n".join(lines), encoding="utf-8-sig")
subprocess.run(["notepad.exe", str(FORM)])
n = 0
for ln in FORM.read_text(encoding="utf-8-sig").splitlines():
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1)
        if v.strip(): (KEYS / k.strip()).write_text(v.strip(), encoding="utf-8"); n += 1
FORM.unlink()
print(f"키 {n}개 저장")
