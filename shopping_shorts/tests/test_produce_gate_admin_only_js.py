"""게이트/생성기 경고는 관리자(cid0=window.IS_ADMIN) 화면에만 뜬다(2026-07-25).
일반 사용자는 기술 경고 대신 최선안을 조용히 받는다(SaaS UX). 백엔드는 gate를 항상 저장하고
표시만 역할로 게이팅한다."""
import re
from pathlib import Path

_HTML = Path("shopping_shorts/static/produce.html").read_text(encoding="utf-8")


def test_gen_warning_gated_by_admin():
    # _genWarn 조립이 window.IS_ADMIN을 조건에 포함해야 함
    m = re.search(r"const _genWarn\s*=\s*\((.*?)\)\s*\n?\s*\?", _HTML)
    assert m, "_genWarn 삼항식을 못 찾음"
    assert "IS_ADMIN" in m.group(1), "_genWarn이 관리자 가드를 안 탐"


def test_gate_warning_gated_by_admin():
    # _gv(게이트 위반 목록)가 관리자일 때만 채워져야 함
    m = re.search(r"const _gv\s*=\s*\((.*?)\)\s*\?", _HTML)
    assert m, "_gv 삼항식을 못 찾음"
    assert "IS_ADMIN" in m.group(1), "_gv가 관리자 가드를 안 탐"
