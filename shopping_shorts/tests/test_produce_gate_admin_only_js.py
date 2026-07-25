"""게이트/생성기 경고는 관리자(cid0=window.IS_ADMIN) 화면에만 뜬다(2026-07-25).
일반 사용자는 기술 경고 대신 최선안을 조용히 받는다(SaaS UX). 백엔드는 gate를 항상 저장하고
표시만 역할로 게이팅한다. ★window 참조는 node 테스트에서도 안전하게 typeof 가드."""
import re
from pathlib import Path

_HTML = Path("shopping_shorts/static/produce.html").read_text(encoding="utf-8")


def test_admin_flag_is_typeof_guarded():
    # _isAdmin은 typeof window 가드 + window.IS_ADMIN 에서 나와야 함(node ReferenceError 방지)
    m = re.search(r"const _isAdmin\s*=\s*(.+);", _HTML)
    assert m, "_isAdmin 정의를 못 찾음"
    assert "typeof window" in m.group(1)
    assert "IS_ADMIN" in m.group(1)


def test_gen_warning_gated_by_admin():
    m = re.search(r"const _genWarn\s*=\s*\((.*?)\)\s*\n?\s*\?", _HTML)
    assert m, "_genWarn 삼항식을 못 찾음"
    assert "_isAdmin" in m.group(1), "_genWarn이 관리자 가드를 안 탐"


def test_gate_warning_gated_by_admin():
    m = re.search(r"const _gv\s*=\s*\((.*?)\)\s*\?", _HTML)
    assert m, "_gv 삼항식을 못 찾음"
    assert "_isAdmin" in m.group(1), "_gv가 관리자 가드를 안 탐"
