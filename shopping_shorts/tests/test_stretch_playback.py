# -*- coding: utf-8 -*-
"""[전체 늘리기]가 **미리보기에서도 실제로 느리게** 재생된다.

★왜(2026-09-06 사장님 "켜도 적용이 안 되고 있는데? 속도가 같음"):
  종전 미리보기는 컷 길이(dur) 숫자만 늘리고 재생은 늘 1배속이었다
  (`playbackRate`가 코드에 **한 군데도 없었다**). 그래서 소스가 먼저 끝나고
  남은 시간은 마지막 프레임에서 멈춘 채 흘렀다 — 느려지는 게 아니라 **멈췄다**.
  렌더(video_assemble)는 ffmpeg setpts로 진짜 느리게 만드니 둘이 어긋났다.

규칙: 컷에 실제 소스 길이(src_dur)가 있고 화면 시간(dur)이 그보다 길면
      playbackRate = src_dur / dur (상한 MAX_SLOWMO 안에서만).
"""
import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "static" / "scene_play.js"


def _code():
    """주석을 걷어낸 본문 — 내 설명 주석에 단언이 걸리지 않게(전례 있음)."""
    return "\n".join(re.sub(r"//.*$", "", ln)
                     for ln in JS.read_text(encoding="utf-8").splitlines())


def test_미리보기가_재생속도를_바꾼다():
    assert "playbackRate" in _code(), \
        "미리보기가 playbackRate를 전혀 안 쓴다 — 늘려도 1배속이라 멈춤만 생긴다"


def test_속도계산이_상한을_지킨다():
    code = _code()
    i = code.index("playbackRate")
    around = code[max(0, i - 400):i + 400]
    assert "MAX_SLOWMO" in around, "재생 속도가 상한(MAX_SLOWMO)을 안 본다"


def test_컷을_틀_때_속도가_적용된다():
    """★정의만 있으면 안 된다 — **실제로 컷을 트는 자리**(v.play() 옆)에서 불려야 한다.
    처음엔 파일 전체에서 applyRate를 찾았는데, 그러면 함수 정의부에 걸려
    호출부를 통째로 지워도 통과했다(사보타주로 잡은 가짜 단언)."""
    code = _code()
    i = code.index("v.play().catch")
    around = code[max(0, i - 300):i]
    assert re.search(r"\bapplyRate\s*\(\s*v\s*,", around), \
        "컷을 트는 자리에서 applyRate를 안 부른다 — 정의만 있고 배선이 없다"


def test_applyRate_정의가_상한과_속도를_다룬다():
    code = _code()
    body = code[code.index("function applyRate("):]
    body = body[:body.index("\n}")]
    assert "playbackRate" in body and "MAX_SLOWMO" in body
