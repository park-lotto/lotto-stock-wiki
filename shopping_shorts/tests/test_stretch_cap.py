# -*- coding: utf-8 -*-
"""[전체 늘리기]는 미리보기도 렌더와 **같은 상한(1.15배)**을 지킨다.

★왜(2026-09-06): 미리보기(scene_play.js)는 부족분을 무제한으로 늘려 보여줬는데
  렌더(video_assemble._MAX_SLOWMO)는 1.15배까지만 늘리고 나머지를 정지 프레임으로
  떠안는다. 그래서 "미리보기는 부드러운데 결과물엔 멈춤이 생긴다"가 됐다.
  실측 사례(칸 2.8초·재료 1.7초): 미리보기 1.65배 vs 렌더 1.15배 + 정지 0.85초.
  같은 판단이 두 군데에서 다른 값을 쓰는 것 자체가 0순위-B 위반이다.
"""
import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "static" / "scene_play.js"


def test_미리보기_상한이_렌더와_같다():
    from shopping_shorts.video_assemble import _MAX_SLOWMO
    src = JS.read_text(encoding="utf-8")
    m = re.search(r"const\s+MAX_SLOWMO\s*=\s*([\d.]+)", src)
    assert m, "미리보기에 MAX_SLOWMO 상한이 없다 — 무제한으로 늘리고 있다"
    assert float(m.group(1)) == _MAX_SLOWMO, \
        f"미리보기 {m.group(1)} vs 렌더 {_MAX_SLOWMO} — 두 값이 어긋나면 결과물이 다르다"


def test_늘리기_분기가_상한을_실제로_쓴다():
    """상수만 두고 안 쓰면 아무 소용이 없다 — spread 분기 안에서 쓰여야 한다."""
    src = JS.read_text(encoding="utf-8")
    i = src.index("if (spread && filled > EPS)")
    body = src[i:i + 700]
    code = "\n".join(re.sub(r"//.*$", "", ln) for ln in body.splitlines())
    assert "MAX_SLOWMO" in code, "spread 분기가 상한을 안 쓴다"
