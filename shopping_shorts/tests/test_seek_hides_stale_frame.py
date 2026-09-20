# -*- coding: utf-8 -*-
"""되감기 때 '다음다음 컷'이 스치는 것 — 9/18 수정의 구멍 두 개를 막았는지 지킨다.

배경(2026-09-18 이윤정님 → 2026-09-20 전 회원 실측):
  컷2를 보는 중에 컷1 재생기(슬롯0)는 seat()가 **컷3 시작점**에 미리 앉혀 둔다
  (슬롯은 `k % 2`라 컷0·컷2가 같은 재생기를 쓴다). 여기서 컷1로 되감으면 시크가
  끝나기 전 그 재생기의 현재 프레임 = **컷3**이 먼저 보인다.

  최근 14일 실측: 작업 1,068건 중 872건(81.6%)·회원 58명 중 56명에게 이 구조가 있다.
  즉 한 줄이 뚫리면 거의 전 회원이 겪는다 — 그래서 테스트로 박는다.

9/18 수정에 남아 있던 구멍:
  ① `v.seeking` 플래그로만 판정 → 브라우저가 아직 플래그를 안 세운 틈에 곧장 showVid.
  ② 안전핀 400ms가 터지면 그냥 showVid → 느린 PC에서 **고치려던 그 프레임**을 노출.
"""
import re
from pathlib import Path

import pytest

JS = (Path(__file__).resolve().parents[1] / "static" / "scene_play.js").read_text(encoding="utf-8")


def _seek_block():
    """seekTo 안에서 재생기를 바꾸는 대목만 떼어낸다."""
    i = JS.index("const _want = v.currentTime;")
    return JS[i:i + 1200]


def test_settled_is_judged_by_value_not_flag():
    """구멍① — 플래그가 아니라 **실제 시각**으로 판정해야 한다."""
    assert "function _seekSettled(" in JS
    body = JS[JS.index("function _seekSettled("):]
    body = body[:body.index("\n}")]
    assert "currentTime" in body          # 값을 본다
    assert "_SEEK_EPS" in body            # 허용 오차로 비교
    assert "v.seeking" in body or "!v.seeking" in body   # 플래그는 보조로만


def test_transfer_hides_until_seek_lands():
    """구멍② — 못 기다릴 땐 **가린 채** 넘긴다. 옛 프레임을 그냥 보여주지 않는다."""
    blk = _seek_block()
    assert "visibility = 'hidden'" in blk          # 가리고 전환
    assert "_seekSettled(" in blk                  # 값으로 판정해 진입
    assert "_pinHidden(" in blk                    # 드러내는 일은 한 곳에서만 한다


def _pin_body():
    i = JS.index("function _pinHidden(")
    return JS[i:JS.index("\n}", i)]


def test_reveal_requires_the_seek_to_have_landed():
    """★시간이 아니라 **자리에 왔는지**로 드러낸다(2026-09-20 진짜 크롬 실측으로 잡은 결함).

    처음엔 seeked + 안전핀 1500ms 였는데, 실제 크롬에서 **안전핀이 터지는 순간 아직 시크
    중이면 컷3이 그대로 드러났다**(프레임 1장 노출: black → YELLOW → red). 시간으로 찍으면
    느린 환경에서 반드시 샌다 — 9/18판이 400ms로 샌 것과 같은 구조다.
    """
    body = _pin_body()
    assert "_seekSettled(v, want)" in body, "자리에 왔는지 확인하지 않고 드러낸다"
    # seeked 로 곧바로 드러낼 때도 확인을 거쳐야 한다(이벤트가 와도 값이 안 맞을 수 있다)
    assert body.count("_seekSettled(v, want)") >= 2, "빠른 경로에서 확인을 건너뛴다"
    assert "_PIN_MAX_MS" in body, "한도가 없으면 영영 가려질 수 있다"


def test_pin_reveals_and_cleans_up():
    """가려둔 화면은 반드시 다시 드러난다 — 안 그러면 빈 화면이 남는다."""
    body = _pin_body()
    assert "visibility = ''" in body                            # 드러내기
    assert re.search(r"setTimeout\(tick,\s*_PIN_STEP_MS\)", body)  # 못 왔으면 다시 본다
    assert "_unhidePinned()" in _seek_block()                   # 다음 전환 전에 앞선 것을 정리


def test_stop_play_unhides():
    """재생을 멈출 때도 되돌린다 — 멈춘 화면이 빈 채로 남으면 안 된다."""
    body = JS[JS.index("function stopPlay()"):]
    body = body[:body.index("\n}")]
    assert "_unhidePinned()" in body


@pytest.mark.parametrize("fn", ["_seekSettled", "_unhidePinned", "_pinHidden"])
def test_helpers_defined_once(fn):
    """같은 이름을 두 번 만들면 나중 것이 앞 것을 조용히 덮는다(이 저장소가 데인 함정)."""
    assert JS.count("function %s(" % fn) == 1
