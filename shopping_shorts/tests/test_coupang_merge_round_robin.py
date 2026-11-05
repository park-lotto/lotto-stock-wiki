# -*- coding: utf-8 -*-
"""11-05 숏템리폿 회원 편(체스넛 무브): 쿠팡 검색어 결과를 순서대로 이어 붙이고 앞 12개만 판정에 보내,
첫 검색어(한글 음역 '체스넛 무브' → 신발 12개)가 자리를 다 차지했다. 둘째 검색어 1위였던 같은 제품(9771196745 — PC 34편 납품 제품)이
판정에 안 실려 '같은 제품 없음'으로 소재를 버렸다. 검색어마다 1위·2위…를 번갈아 넣는다(runner_ops.merge_items)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import runner_ops as R  # noqa: E402


def _r(prefix, n):
    return {"ok": True, "items": [{"product_id": f"{prefix}{i}", "name": f"{prefix}{i}"} for i in range(n)]}


def test_second_query_top_is_in_first_12():
    shoes, same = _r("shoe", 12), {"ok": True, "items": [{"product_id": "9771196745", "name": "Chessnut Move 로봇 체스보드"}]}
    top12 = [x["product_id"] for x in R.merge_items([shoes, same, _r("chess", 12)])[:12]]
    assert "9771196745" in top12[:3]
    assert top12[0] == "shoe0"                          # 첫 검색어 1위도 그대로 앞


def test_same_product_once_and_empty_ok():
    a = {"ok": True, "items": [{"product_id": "1"}, {"product_id": "2"}]}
    b = {"ok": True, "items": [{"product_id": "2"}, {"product_id": "3"}]}
    assert [x["product_id"] for x in R.merge_items([a, b, {}, None])] == ["1", "2", "3"]
    assert R.merge_items([]) == []
