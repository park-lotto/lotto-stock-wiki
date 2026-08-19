# -*- coding: utf-8 -*-
"""장면 편집(iframe) 크기가 '무슨 작업만 하면' 바뀌던 것을 막는다 (2026-08-19 사장님 제보).

증상: 미리보기/편집 화면 크기가 계속 달라진다.

★근본 원인(코드 실측) — 같은 판단이 두 곳에 **다르게** 적혀 있었다(CLAUDE.md 0순위-B):
    · produce.html 마크업        : height:150vh · min-height:1100px
    · toggleSceneLabWide() 복귀부: height:88vh  (min-height 는 아예 안 씀)
  [⛶ 넓게 보기]를 켰다 끄면 원래 크기로 안 돌아오고 **88vh로 쪼그라든다**.
  min-height도 사라져 창이 짧으면 더 작아진다 = "작업만 하면 크기가 변한다".

계약: 크기 기준값은 **한 곳(_SL_FRAME_H/_SL_FRAME_MINH)** 에만 둔다.
      마크업도 복귀부도 그 값을 쓴다 → 두 벌이 어긋날 수 없다.
"""
import re
from pathlib import Path

PROD = Path(__file__).resolve().parents[1] / "static" / "produce.html"
SRC = PROD.read_text(encoding="utf-8")


def test_크기_기준값이_한_곳에만_있다():
    """상수가 없으면 또 두 곳에 손으로 적게 된다 — 그게 이 사고의 원인이었다."""
    assert re.search(r"const\s+_SL_FRAME_H\s*=", SRC), "_SL_FRAME_H 상수가 없다"
    assert re.search(r"const\s+_SL_FRAME_MINH\s*=", SRC), "_SL_FRAME_MINH 상수가 없다"


def test_넓게보기_토글이_높이를_손으로_적지_않는다():
    """88vh 같은 리터럴이 되살아나면 다시 어긋난다(회귀 방지)."""
    m = re.search(r"function toggleSceneLabWide\(\)\{.*?\n\}", SRC, re.S)
    assert m, "toggleSceneLabWide 를 못 찾았다"
    body = m.group(0)
    assert "88vh" not in body, "복귀부가 아직 88vh를 손으로 적고 있다"
    assert "150vh" not in body, "복귀부가 높이를 손으로 적고 있다"
    # 크기는 반드시 한 곳(_applySceneLabFrameSize)을 통해서만 입힌다.
    assert "_applySceneLabFrameSize" in body, \
        "토글이 크기 함수를 안 쓴다 — 또 두 벌로 갈린다"


def test_크기함수가_두_상태_모두_height와_minHeight를_정한다():
    """한쪽만 정하면 반대 상태의 값이 남아 '작업만 하면 크기가 변한다'가 재발한다."""
    m = re.search(r"function _applySceneLabFrameSize\([^)]*\)\{.*?\n\}", SRC, re.S)
    assert m, "_applySceneLabFrameSize 를 못 찾았다"
    body = m.group(0)
    assert body.count("minHeight") >= 2, "두 상태 모두 min-height를 정해야 한다"
    assert body.count("style.height") >= 2, "두 상태 모두 height를 정해야 한다"
    assert "_SL_FRAME_H" in body and "_SL_FRAME_MINH" in body


def test_마크업_iframe에는_높이를_적지_않는다():
    """마크업에 숫자가 남으면 상수를 고쳐도 첫 화면만 옛 값으로 남는다."""
    m = re.search(r'<iframe id="sceneLabFrame".*?>', SRC, re.S)
    assert m, "sceneLabFrame iframe 을 못 찾았다"
    tag = m.group(0)
    assert "height:" not in tag, f"iframe 마크업이 아직 높이를 적고 있다: {tag}"


def test_마크업_iframe도_같은_기준값을_쓴다():
    """마크업에만 숫자가 남아 있으면 상수를 고쳐도 첫 화면은 안 바뀐다."""
    m = re.search(r"function _applySceneLabFrameSize\(", SRC)
    assert m, "_applySceneLabFrameSize(크기를 실제로 입히는 한 곳)가 없다"
