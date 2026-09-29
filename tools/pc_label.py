"""이 PC 이름(집/회사) — 창 이름·보고 머리말이 쓰는 한 곳 (카드 046).

`%USERPROFILE%\\.claude-pc.json` 의 {"label": "집"} 을 읽는다. 없거나 깨졌으면 컴퓨터 이름.
PC 마다 다른 값이라 저장소 밖에 둔다 — 설치는 tools/pc_setup.ps1.
"""
import json
import os
from pathlib import Path


def label(home=None, computer=None):
    home = Path(home or Path.home())
    computer = computer or os.environ.get("COMPUTERNAME", "PC")
    try:
        data = json.loads((home / ".claude-pc.json").read_text(encoding="utf-8"))
        return str(data.get("label") or computer)
    except (OSError, ValueError, AttributeError):
        return computer
