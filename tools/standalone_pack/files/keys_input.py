# -*- coding: utf-8 -*-
"""키 입력. 메모장에 붙여넣고 저장·닫기만 하면 된다. 값은 대화나 화면에 나오지 않는다."""
import subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
KEYS = Path(__file__).resolve().parent / "data" / "keys"
KEYS.mkdir(parents=True, exist_ok=True)
FORM = KEYS / "입력.txt"
ITEMS = [("typecast", "필수", "타입캐스트", "typecast.ai > 개발자 > API 키"),
         ("vmake", "권장", "VMake (app_key:secret 꼴)", "VMake 개발자 화면. 없으면 원본 자막을 흐림으로 가립니다"),
         ("speechmatics", "선택", "스피치매틱스", "speechmatics.com > Settings > API Keys. 없으면 위스퍼로 진행"),
         ("coupang_access", "선택", "쿠팡 파트너스 Access Key", "쿠팡 파트너스 > 추가기능 > 오픈API. 없으면 크롬으로 찾습니다"),
         ("coupang_secret", "선택", "쿠팡 파트너스 Secret Key", "위와 같은 곳")]
lines = ["# 각 줄의 = 뒤에 키를 붙여넣고 저장한 뒤 메모장을 닫아 주세요.", ""]
for k, need, label, where in ITEMS:
    if (KEYS / k).exists(): continue
    lines += [f"# [{need}] {label} — {where}", f"{k}=", ""]
if len(lines) == 2:
    print("키 입력 끝"); sys.exit(0)
FORM.write_text("\n".join(lines), encoding="utf-8-sig")
subprocess.run(["notepad.exe", str(FORM)])
n = 0
for ln in FORM.read_text(encoding="utf-8-sig").splitlines():
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1)
        if v.strip() and k.strip() in {x[0] for x in ITEMS}:
            (KEYS / k.strip()).write_text(v.strip(), encoding="utf-8"); n += 1
FORM.unlink()
print(f"키 {n}개 저장")
print("타입캐스트 키가 필요합니다" if not (KEYS / "typecast").exists() else "필수 키 있음")
