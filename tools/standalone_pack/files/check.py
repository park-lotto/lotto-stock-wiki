# -*- coding: utf-8 -*-
"""시작 검수. 판이 실제로 쓰는 도구·키·로그인을 엔진 판단(need_list) 그대로 잰다. 빈 목록이면 시작 가능."""
import json, os, shutil, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import run as R   # 환경을 같이 쓴다
from tools.calcopy.hybrid import runner_ops as OPS

fails = []
try:
    for x in OPS.need_list(R.VERSION, "", R.json.loads((R.ROOT / "pack.json").read_text(encoding="utf-8")).get("fmt", "")):
        fails.append(x["label"])
except Exception as e:  # noqa: BLE001
    fails.append("점검 실패: " + str(e)[:160])
gb = shutil.disk_usage(R.ROOT).free / 1e9
if gb < 5: fails.append(f"디스크 여유 {gb:.1f}GB — 5GB 이상 비워 주세요")
if fails:
    print("시작 불가:")
    for f in fails: print(" -", f)
    print("setup 을 다시 실행하거나 위 항목을 채워 주세요.")
    sys.exit(1)
print("시작 가능")
