# -*- coding: utf-8 -*-
"""화면이 '조립본'임을 말하는가(2026-08-19).

★조용한 폴백이 쳇바퀴의 뿌리였다(memory: reference_silent_fallback_pipeline_undo).
  경로가 갈리면 화면이 어느 쪽인지 말해야, "왜 결과가 달라졌지"를 사장님이 알 수 있다.
문자열 검사로 끝내는 이유: 이 표시는 렌더 함수 안 한 줄이라 JS 하네스로 띄우는 비용이
검사 가치보다 크다. 최소한 **사라지면 깨지게** 못 박는다.
"""
import io
import pathlib

HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _src():
    return io.open(HTML, encoding="utf-8").read()


def test_재료줄에_틀조립_표시가_있다():
    s = _src()
    assert "m.assembled" in s, "materials.assembled를 화면이 안 읽는다"
    assert "틀 조립 " in s


def test_안_탭에_조립_배지가_있다():
    assert "dr.made_by==='조립'" in _src()
