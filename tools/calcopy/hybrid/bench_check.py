# -*- coding: utf-8 -*-
"""벤치 판(renderer=bench) 렌더 뒤 자동 검사 — **호출만 남긴 호환 입구** (관제 097 2026-10-19 → 관제 263 지시서 04, 2026-10-24).

    PYTHONUTF8=1 py tools/calcopy/hybrid/bench_check.py <판> <doc_dir> <work_dir>

판정 주인은 `tools/calcopy/hybrid/quality_gate.py` 한 곳이다(관문 두 벌 금지 — 표준 §3-3 B4). 이 파일은
옛 10항목(길이·화면=시간표·음량·최고점·0초 얼굴·컷 조각 프레임·멈춤·번쩍임·썸네일 2프레임·배치)만 quality_gate.gate(only="legacy10") 로
불러 <doc>/자동검사.json 을 예전 꼴로 남긴다 — run.py·runner_ops(회원 경로)가 이 함수를 부른다. 전체 관문은 quality_gate.py gate.
측정 조각(vdur·part_frames·part_slivers·thumb_stamped·freezes·FREEZE_SEC)은 quality_gate 에 있고 여기서는 이름만 이어 준다(옛 import 호환).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.quality_gate import (  # noqa: E402,F401 — 옛 import 호환(05 업그레이드 자가 bench_check.freezes 를 부른다)
    FREEZE_SEC, freezes, gate, part_frames, part_slivers, thumb_stamped, vdur)


def check(style_name: str, doc: Path, work: Path, log=print) -> dict:
    r = gate(style_name, Path(doc), Path(work), only="legacy10", log=log)
    return {"ok": r["ok"], "report": r["report"]}


if __name__ == "__main__":
    r = check(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))
    sys.exit(0 if r["ok"] else 1)
