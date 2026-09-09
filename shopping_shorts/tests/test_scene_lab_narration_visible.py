# -*- coding: utf-8 -*-
"""3단계 영상대본MIX에서 **대본이 잘리면 안 된다** — 2026-09-06 고객 제보 회귀 방지.

고객: "대본이 끝까지 안 나오네요. 영상대본mix 단계에서요. 대본도 씹히는 거 같고요"

원인은 데이터가 아니라 **CSS**였다(DB는 7줄 전부 멀쩡했다):
`body.tight`(촘촘히 = **기본 켜짐**)가 대본 칸을 한 줄로 잘랐다.
    body.tight .tbsay{max-height:1.9em; -webkit-line-clamp:1}
실측(고객 잡 3ec9df659411): 67자 문장이 실제 45px인데 20px만 보여 **25px이 잘렸다**.
게다가 1.9em은 한 줄(1.5em)보다 커서 **둘째 줄이 반쯤 걸쳐** 글자가 가로로 잘린 채
보인다 = 고객이 말한 "씹힌다".

★대본은 화면 장식이 아니라 고객이 확인하러 온 것이다 — 촘촘히가 접을 대상이 아니다.

이 테스트는 CSS 파일에서 규칙을 **직접 읽어** 판정한다(기억으로 쓰지 않는다).
"""
import re
import pathlib

import pytest

SCENE_LAB = (pathlib.Path(__file__).resolve().parents[1] / "static" / "scene_lab.html")


def _css():
    html = SCENE_LAB.read_text(encoding="utf-8")
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))


def _tight_tbsay_rules(css):
    """`body.tight .tbsay{...}` 규칙 본문만 모은다(.open 등 다른 선택자는 뺀다)."""
    out = []
    for m in re.finditer(r"body\.tight\s+\.tbsay([^{,]*)\{([^}]*)\}", css):
        suffix, body = m.group(1).strip(), m.group(2)
        if suffix == "":          # 순수 `body.tight .tbsay` 만 (`.open`·`.editing` 제외)
            out.append(body)
    return out


def test_tight_mode_does_not_clamp_narration():
    """촘촘히에서 대본 칸을 한 줄로 자르지 않는다."""
    rules = _tight_tbsay_rules(_css())
    for body in rules:
        flat = body.replace(" ", "").replace("\n", "")
        assert "-webkit-line-clamp:1" not in flat, (
            "촘촘히가 대본을 한 줄로 자른다 — 고객 '대본이 씹힌다'가 재발한다: %s" % body)
        m = re.search(r"max-height:\s*([\d.]+)em", body)
        if m:
            assert float(m.group(1)) >= 4.0, (
                "촘촘히 대본 칸 max-height가 %sem — 한 줄짜리라 문장이 잘린다" % m.group(1))


def test_default_narration_box_can_show_multiple_lines():
    """기본 `.tbsay`는 여러 줄을 보여주고, 넘치면 잘라 없애지 말고 스크롤한다."""
    css = _css()
    m = re.search(r"(?<!body\.tight )\.tbsay\{([^}]*)\}", css)
    assert m, ".tbsay 기본 규칙을 못 찾았다"
    body = m.group(1)
    mh = re.search(r"max-height:\s*([\d.]+)em", body)
    assert mh and float(mh.group(1)) >= 4.0, "기본 대본 칸이 너무 낮다: %s" % body
    assert "overflow-y:auto" in body.replace(" ", ""), (
        "넘칠 때 스크롤이 없으면 글자가 잘려 사라진다: %s" % body)


def test_saymore_toggle_still_exists():
    """긴 문장을 통째로 펼치는 ⌄ 버튼은 살아 있어야 한다(회귀 방지)."""
    html = SCENE_LAB.read_text(encoding="utf-8")
    assert "saymore" in html, "대본 펼치기 버튼이 사라졌다"
    assert "classList.toggle('open')" in html, "펼치기 토글 배선이 끊겼다"
