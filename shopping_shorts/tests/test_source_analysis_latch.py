# -*- coding: utf-8 -*-
"""소스분석 자동분석 래치 · 진행표시 가드 (2026-08-20)

사장님 제보: "들어가서 새로고침을 한번눌러야 대본들이 아래 분석이 뜬다"
            "그동안에 멈춰있는것처럼 안보이려면 뭔가 진행되고있다는걸 보여줘야한다"

원인: `_autoloadTried`가 **페이지 수명 boolean**이라 한 번 켜지면 새로고침 전까지
      안 풀렸다. 영상을 담으면 refreshStep0()이 다시 도는데 그때는 이미 잠겨 있어
      자동분석을 통째로 건너뛰었다 → 카드도 "분석 중"도 안 뜸(분석을 시작조차 안 함).

★이 테스트는 **옛 코드에서 실패해야** 가드다(reference_재발버그_가드없인_되살아난다).
  옛 코드엔 _autoloadKey·_footageKey·_srcAutoloadRunning이 아예 없으므로 전부 FAIL한다.
"""
import pathlib
import re

import pytest

HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
SRC = HTML.read_text(encoding="utf-8")


def test_래치가_묶음지문으로_판정된다():
    """boolean 래치만으로 판정하면 새 영상을 담아도 분석이 안 돈다."""
    assert "function _footageKey()" in SRC, "담긴 영상 묶음의 지문 함수가 없다"
    # 래치 분기가 지문 비교를 쓰는지 — boolean만 보면 이번 버그가 그대로 재발한다.
    assert re.search(r"_autoloadKey\s*!==\s*_fkey", SRC), \
        "자동분석 분기가 묶음 지문(_autoloadKey)으로 판정하지 않는다"


def test_지문은_담긴것만_정렬해_만든다():
    """담기 해제한 영상이 섞이거나 순서만 바뀌어 재분석이 돌면 크레딧이 샌다."""
    m = re.search(r"function _footageKey\(\)\{(.*?)\n\}", SRC, re.S)
    assert m, "_footageKey 본문을 못 찾았다"
    body = m.group(1)
    assert "useFootage" in body, "담긴 영상(useFootage)만 세야 한다"
    assert ".sort()" in body, "순서만 바뀐 것을 다른 묶음으로 보면 안 된다"


def test_담자마자_진행표시를_먼저_올린다():
    """네트워크 왕복 전에 표시가 떠야 '멈춘 것처럼' 안 보인다."""
    m = re.search(r"async function refreshStep0\(\)\{(.*?)\n  try\{", SRC, re.S)
    assert m, "refreshStep0 앞부분을 못 찾았다"
    head = m.group(1)
    # aipick fetch·_pushWork보다 먼저 _SRC_BUSY를 세우고 그려야 한다.
    assert "_SRC_BUSY = pending" in head, "선제 진행표시가 없다(빈 화면 구간이 남는다)"
    assert "renderSourceAnalysis()" in head, "선제 표시를 그리지 않는다"


def test_분석을_건너뛰면_진행표시를_내린다():
    """도는 게 없는데 회전표시가 남으면 빈 화면보다 나쁜 거짓말이 된다."""
    assert "let _srcAutoloadRunning" in SRC, "실제 실행 여부 플래그가 없다"
    assert re.search(r"if\(_SRC_BUSY && !_SRC_QUEUED && !_srcAutoloadRunning\)", SRC), \
        "자동분석 분기를 건너뛴 경로에서 진행표시를 내리지 않는다"


def test_자동분석_실패해도_표시가_풀린다():
    """예외가 나면 회전표시가 영영 남는다 — finally로 반드시 내린다."""
    m = re.search(r"_srcAutoloadRunning = true;(.*?)_SRC_BUSY = 0;", SRC, re.S)
    assert m, "자동분석 실행 구간을 못 찾았다"
    assert "finally" in m.group(1), "autoloadAllFootage를 finally로 감싸지 않았다"


def _refresh_step0_body():
    """refreshStep0 본문을 **중괄호 짝을 세어** 잘라낸다.

    ⚠️ 정규식 `(.*?)\\n\\}`로 자르면 안 된다 — 본문 안 템플릿 리터럴·중첩 블록 때문에
       엉뚱한 곳에서 끊기거나 뒤 함수까지 삼킨다(이 테스트를 처음 쓸 때 실제로 그랬다).
    """
    i = SRC.index("async function refreshStep0()")
    depth, started = 0, False
    for j in range(i, len(SRC)):
        if SRC[j] == "{":
            depth += 1
            started = True
        elif SRC[j] == "}":
            depth -= 1
            if started and depth == 0:
                return SRC[i:j]
    raise AssertionError("refreshStep0 본문의 끝을 못 찾았다")


def test_재귀호출_방지선은_그대로다():
    """2026-07-26 무한루프·크레딧 소진 사고의 방지선을 지운 게 아닌지 확인.

    refreshStep0 안에서 자기 자신을 다시 부르면 그 사고가 재발한다.
    선언부와 주석은 호출이 아니므로 **실제 호출 형태**만 센다.
    """
    body = _refresh_step0_body()
    # 주석 줄을 걷어낸 뒤 호출부만 본다(주석 속 "refreshStep0()를 부르지 마라"는 무해).
    code = "\n".join(
        ln for ln in body.splitlines() if not ln.lstrip().startswith("//")
    )
    calls = re.findall(r"(?<!function )\brefreshStep0\s*\(", code)
    assert not calls, f"refreshStep0이 자기 자신을 다시 부른다(무한루프 위험): {calls}"
