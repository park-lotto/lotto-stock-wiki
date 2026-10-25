# -*- coding: utf-8 -*-
"""대체(비슷한) 제품 밝히기 — script_audit.alt_disclosed(사장님 10-25, 제작순서 03).
product_mode 'alt' 대본에 '같은 제품이 아니라 비슷한 제품' 이라고 말하는 나레 줄이 없으면 audit 가 반려한다. alt 가 아니면 안 잰다."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import script_audit as SA  # noqa: E402

PARK = ROOT / "channel/yanshottem/하이브리드_박정수_썬크림/키치잇판/대본.json"


def _d(mode, *says):
    return {"product_mode": mode, "lines": [{"id": f"N{i}", "kind": "tts", "text": s, "tts": s} for i, s in enumerate(says, 1)]}


def test_alt_needs_line():
    assert SA.alt_disclosed(_d("alt", "강주은이 산 가디건이에요.", "저도 하나 사 봤는데 좋더라고요."))["rule"] == "alt_say"


def test_alt_said_passes():
    for s in ("영상 보고 쿠팡에서 찾아봤는데 똑같은 건 없어서 후기 많은 걸로 사 봤어요.",
              "같은 제품은 아니고 비슷한 걸로 골라 봤어요.",
              "쿠팡엔 없어서 비슷한 흑백 가디건으로 사 봤는데요."):
        assert SA.alt_disclosed(_d("alt", "가디건 이야기.", s)) is None, s


def test_not_alt_not_judged():
    for m in ("exact", "named", None):
        assert SA.alt_disclosed(_d(m, "그 제품이에요.")) is None


def test_orig_line_does_not_count():
    d = _d("alt", "가디건이에요.")
    d["lines"].append({"id": "O1", "kind": "orig", "text": "똑같은 건 없어"})
    assert SA.alt_disclosed(d) is not None


def test_audit_rejects_alt_without_line(tmp_path):
    """실물 대본(박정수 키치잇판 — 같은 제품이라 밝힘 줄 없음): exact 면 audit 결과 그대로, alt 로 바꾸면 product:alt_say 로 반려."""
    raw = json.loads(PARK.read_text(encoding="utf-8"))
    base = SA.audit(PARK, "키치잇판")
    p = tmp_path / "대본.json"
    p.write_text(json.dumps({**raw, "product_mode": "alt"}, ensure_ascii=False), encoding="utf-8")
    a = SA.audit(p, "키치잇판")
    assert not a["ok"] and any(r["kind"] == "product:alt_say" for r in a["rules"])
    assert not any(r["kind"].startswith("product:") for r in base["rules"])
