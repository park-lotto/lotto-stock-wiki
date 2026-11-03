# -*- coding: utf-8 -*-
"""프리셋 정본(frame.json·manifest.json) → 읽기용 프리셋.md·CLAUDE.md (관제 319 D4). 렌더는 이 md 를 읽지 않는다.
머리 첫 줄 표식 = 두 파일의 md5. 서버 bm_make 가 표식이 다르면 다시 그리게 지시한다(D10)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from shopping_shorts.calcopy_frame.per_video import flat  # 칸 이름 짓기는 여기 한 곳(preset_save.variables 와 같은 이름)

MARK = "<!-- manifest_sha: {} -->"


def sha(preset_dir: Path) -> str:
    h = hashlib.md5()
    for n in ("frame.json", "manifest.json"):
        h.update((Path(preset_dir) / n).read_bytes())
    return h.hexdigest()


def _cell(v: object) -> str:
    t = json.dumps(v, ensure_ascii=False)[:60]
    return t.replace("|", "\\|").replace("\\n", "⏎").replace("\\r", "")


def render(preset_dir: Path, out_dir: Path, name: str) -> dict:
    preset_dir, out_dir = Path(preset_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = json.loads((preset_dir / "frame.json").read_text(encoding="utf-8"))
    man = json.loads((preset_dir / "manifest.json").read_text(encoding="utf-8"))
    var = set(man.get("variables") or [])
    s = sha(preset_dir)
    lines = [MARK.format(s), f"# 내 프리셋 — {name}", "", f"쟀던 벤치 편: {len(man.get('sources') or [])}편", "",
             "| 칸 | 값 | 어떻게 |", "|---|---|---|"]
    for k, v in flat(frame).items():
        lines.append(f"| {k} | {_cell(v)} | {'편마다 소재에 맞춰 정함' if k in var else '고정'} |")
    md = out_dir / "프리셋.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cm = out_dir / "CLAUDE.md"
    cm.write_text(MARK.format(s) + f"\n# {name} 프리셋으로 만들 때 지킬 것\n\n- 만들기 전에 프리셋.md 를 끝까지 읽는다.\n"
                  "- '고정' 칸은 바꾸지 않는다. '편마다' 칸만 이 소재에 맞춰 정한다.\n- 프리셋.md 에 없는 규칙은 지어내지 않는다.\n", encoding="utf-8")
    return {"md": str(md), "claude_md": str(cm), "sha": s}


def stale(md_path: Path, preset_dir: Path) -> bool:
    first = Path(md_path).read_text(encoding="utf-8").splitlines()[:1]
    return not first or first[0] != MARK.format(sha(preset_dir))
