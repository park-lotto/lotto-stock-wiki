# -*- coding: utf-8 -*-
"""마이페이지가 보여주는 하루 한도가 **사실인지** (2026-08-23 발견).

★무엇이 잘못됐었나
   /api/me가 한도를 두 벌 실어 보냈다 —
     usage_limits : plan을 보고 계산한 **진짜** 값 (관리자=무제한)
     limits       : plan을 안 보고 하드코딩한 무료 등급 값 (5/2/10)
   그런데 화면(settings.html)은 **limits**를 읽었다. 그래서 관리자 계정으로
   들어가도 "영상 제작 2회"가 떴다(라이브 실측). Pro를 결제한 고객이
   같은 화면을 보면 "돈 냈는데 2회냐"가 된다.

   같은 값을 두 곳에서 따로 정하면 반드시 어긋난다(0순위-B) → 하나로 합쳤다.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
APP = (SRC / "app.py").read_text(encoding="utf-8")
SETTINGS = (SRC / "static" / "settings.html").read_text(encoding="utf-8")


def test_me_does_not_hardcode_limits():
    """★한도를 다시 계산하지 않는다 — 위에서 정한 값을 그대로 쓴다."""
    assert '"limits": {"lens": _lim(' not in APP, (
        "/api/me가 한도를 또 계산한다 — plan을 무시한 값이 화면에 나간다")
    assert '"usage_limits": limits, "limits": limits' in APP, (
        "limits와 usage_limits가 같은 값이어야 한다")


def test_settings_page_reads_limits():
    """화면이 읽는 필드가 실제로 서버가 채우는 필드인지."""
    assert "d.limits" in SETTINGS, "settings.html이 limits를 안 읽는다"


def test_unlimited_is_shown_as_words_not_dash():
    """★관리자는 한도가 없다(None). 그걸 '–'로 보여주면 '못 쓴다'로 읽힌다."""
    assert '"무제한"' in SETTINGS, "무제한 표시가 없다"
    m = re.search(r"function lim\(v\)\{[^}]*\}", SETTINGS)
    assert m, "lim() 헬퍼가 없다"
    assert "null" in m.group(0), "null(무제한)을 따로 처리해야 한다"


def test_unit_is_not_duplicated():
    """'무제한 회'가 되지 않게 단위를 따로 감춘다."""
    assert "limRenderUnit" in SETTINGS, "단위를 따로 제어할 수 없다"
    assert 'display = (v == null) ? "none" : ""' in SETTINGS, (
        "무제한일 때 단위를 감추는 처리가 없다")


def test_global_vmake_key_ui_is_admin_only():
    """★mix.html의 vmake 키 칸은 **회사 전역 키**다 — 고객에게 보이면
    자기 키인 줄 알고 넣어 회사 키를 덮어쓴다(그래도 포인트는 깎인다)."""
    mix = (SRC / "static" / "mix.html").read_text(encoding="utf-8")
    assert 'id="vmakeKeyRow"' in mix and "display:none" in mix, (
        "회사 전역 키 칸이 기본으로 보인다")
    assert "is_admin" in mix, "관리자 판정 없이 노출 여부를 정하고 있다"
