# -*- coding: utf-8 -*-
"""자막제거 실패 사유 분류 — 새어나가면 '다시 시도해 주세요'라는 거짓 안내가 나간다.

★왜 이 테스트가 생겼나(2026-08-26): 08-25에 no_credit을 가르고도, 08-26에
  **우리 포인트 부족**이 unknown으로 새어 같은 사고가 재발했다(cid 57, 6회 재시도).
  분류가 늘 때마다 여기 한 줄씩 늘려라.
"""
import io
import os
import re

import pytest

from shopping_shorts.app import clean_failure_kind

# 전부 서버 clean_error에서 실제로 나온 원문이다(추정 문구 금지).
CASES = [
    ("포인트가 부족합니다 (필요 5P, 보유 2.1P)", "no_points"),
    ("[60002] You don't have enough credits for this API. Purchase a subscription", "no_credit"),
    ("서버 재시작으로 중단되었습니다", "interrupted"),
    ("vmake code 10101 right reduce error", "unsupported"),
    ("알 수 없는 오류", "unknown"),
    ("", "unknown"),
    (None, "unknown"),
]


@pytest.mark.parametrize("err,kind", CASES)
def test_clean_failure_kind(err, kind):
    assert clean_failure_kind(err) == kind


def test_ui_has_branch_for_every_kind():
    """화면(cleanFailHtml)에 분기가 없는 kind가 있으면 기본 문구로 새어
    '잠시 후 다시 시도'라는 거짓 안내가 나간다 — 그게 두 번 난 사고의 모양이다."""
    p = os.path.join(os.path.dirname(__file__), "..", "static", "produce.html")
    html = io.open(p, encoding="utf-8").read()
    body = html[html.index("function cleanFailHtml("):]
    body = body[:body.index("\n}")]
    for kind in {k for _e, k in CASES} - {"unknown"}:
        assert re.search(r"kind\s*===\s*['\"]%s['\"]" % kind, body), kind


def test_no_points_does_not_offer_retry():
    """포인트 부족은 다시 눌러도 같은 결과라 재시도 버튼을 주면 안 된다."""
    p = os.path.join(os.path.dirname(__file__), "..", "static", "produce.html")
    html = io.open(p, encoding="utf-8").read()
    start = html.index("if(kind === 'no_points')")
    block = html[start:html.index("if(kind === 'no_credit')", start)]
    assert "+ redo" not in block
