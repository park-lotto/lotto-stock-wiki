# -*- coding: utf-8 -*-
"""통과한 칼카피 프리셋을 장면꾸미기 고정형 목록(out/continuous20-data.js)에 **관리자 전용**으로 등록.

    PYTHONUTF8=1 py tools/calcopy/engine/template_register.py channel/sseolpulda/preset/A_흰바탕창/창아래_검정 --name "칼카피 썰풀다 A"

행 모양의 주인 = calcopy_frame.to_snapshot.build_row(customFrame 과 같은 함수 — 같은 설명서면 같은 번호 custom_<sha1>).
프리셋의 변수 자리는 첫 출처 편 값으로 채운다(목록 카드의 보기용 — 고객 작업에서는 그 편 제목·자막이 들어간다).
표식: admin_only=true · calcopy_preset=<프리셋 폴더>. 같은 프리셋을 다시 등록하면 그 행을 바꾼다(번호가 바뀌면 새 번호로).
고객 노출: precision20-ui.js 목록 필터(rowVisible — 판정 한 곳)가 관리자(context.adminView)에게만 보인다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.calcopy_frame import to_snapshot  # noqa: E402
from tools.calcopy.engine import preset_save as PS  # noqa: E402

DATA = ROOT / "out" / "continuous20-data.js"
PREFIX = "window.CONTINUOUS20= "


def read_rows(path: Path = DATA) -> list:
    raw = path.read_text(encoding="utf-8-sig").strip()
    return json.loads(raw.split("=", 1)[1].rstrip(";\r\n "))


def write_rows(rows: list, path: Path = DATA) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:      # 저장소는 LF(.gitattributes) — 윈도 text 모드면 CRLF 로 바뀐다
        f.write(PREFIX + json.dumps(rows, ensure_ascii=False, indent=1) + ";\n")


def preset_spec(preset_dir: Path) -> dict:
    pre, M = PS.load(preset_dir)
    first = json.loads((preset_dir / "sources" / f"{M['sources'][0]['id']}.json").read_text(encoding="utf-8"))
    return PS.apply(pre, first)


def register(preset_dir: Path, name: str, path: Path = DATA) -> dict:
    spec = preset_spec(preset_dir)
    row = to_snapshot.build_row(spec)
    rel = str(preset_dir.resolve().relative_to(ROOT)).replace("\\", "/")
    row.update(name=name, admin_only=True, calcopy_preset=rel)
    rows = [r for r in read_rows(path) if r.get("calcopy_preset") != rel]
    rows.append(row)
    write_rows(rows, path)
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("preset"); ap.add_argument("--name", required=True)
    a = ap.parse_args(argv)
    row = register(Path(a.preset), a.name)
    print("등록", row["id"], row["name"], "admin_only", row["admin_only"], "←", row["calcopy_preset"])


if __name__ == "__main__":
    main()
