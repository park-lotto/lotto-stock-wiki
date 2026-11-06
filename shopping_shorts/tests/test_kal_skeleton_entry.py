# -*- coding: utf-8 -*-
"""kal 흐름 뼈대 입구 한 길(11-06 감시 적발 ① · Jev 해결 0.80 나안).
kal 흐름 뼈대 = kal.py step_skeleton(kal=True · loud 열) 한 곳. 낮은 층 CLI `kal_analyze skeleton` 은 kal 칸 없는 옛 모양이라
지침서·표준작업지시가 kal 흐름 단계로 그 CLI 를 안내하면 #5 `_jimun`·#8 `_kind_draft` 가 꺼진 뼈대가 나온다(같은 --out 이면 덮어씀).
고치기 전 판: 지침서 85줄 ③·06:15 가 CLI 를 안내 → 문서 시험 실패 / CLI 가 경보 없이 조용히 옛 모양 → 경보 시험 실패."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import kal_analyze as K  # noqa: E402

DOCS = [ROOT / "tools/calcopy/칼카피_분석지침서.md", ROOT / "tools/calcopy/표준작업지시/06_줄판독_규칙빈도.md"]


def test_docs_point_kal_flow_skeleton_to_kal_py():
    """kal 흐름 문서에서 `kal_analyze skeleton` 을 말하는 줄은 kal.py 길(step_skeleton)을 함께 말해야 한다 — CLI 를 kal 단계로 안내 금지."""
    bad = []
    for p in DOCS:
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"kal_analyze skeleton", ln) and "--spec" not in ln and "kal.py" not in ln:
                bad.append(f"{p.name}:{i}")
    assert not bad, bad
    g = DOCS[0].read_text(encoding="utf-8").splitlines()
    sec = next(ln for ln in g if ln.startswith("- 들어가는 것: src mp4·vtt"))
    assert "step_skeleton" in sec, "지침서 §2-2 ③ 은 kal.py step_skeleton 을 정본으로 적는다"


def test_cli_skeleton_warns_not_kal_flow(tmp_path, capsys):
    """CLI 는 그대로 옛 모양(회원 실행기와 같음)이되 'kal 흐름 뼈대가 아님' 경보를 한 줄 낸다 — 조용히 꺼지지 않게."""
    tt = {"probe": {"duration": 4.0, "fps": 30, "w": 1080, "h": 1920},
          "layout": {"window": [0, 483, 1080, 1058], "caption_band": [1103, 1179]},
          "captions": {"items": [{"t0": 0.0, "t1": 1.0, "text": ["(바로 퀵 전화해봄)"], "top_y": 1110}]},
          "cuts": {"times": []}}
    src = tmp_path / "vid9" / "뜯기.json"
    src.parent.mkdir()
    src.write_text(json.dumps(tt, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out.json"
    assert K.main(["skeleton", str(src), "--out", str(out)]) == 0
    o = capsys.readouterr().out
    assert "[경보]" in o and "kal.py" in o, o
    d = json.loads(out.read_text(encoding="utf-8"))
    assert all("_jimun" not in l and "_kind_draft" not in l for l in d["lines"])   # CLI 모양은 그대로(회원 옛 판)
