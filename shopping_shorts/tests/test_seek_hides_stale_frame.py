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
    # 안전핀이 터져도 showVid를 새로 하지 않는다(이미 전환했고, 드러내기만 한다).
    # ★범위를 콜백 본문으로 정확히 자른다 — 넓게 자르면 아래 else의 showVid를 잘못 잡는다.
    i = blk.index("const go = () => {")
    go_body = blk[i:blk.index("};", i)]
    assert "showVid" not in go_body, "안전핀이 옛 프레임을 노출한다(9/18 구멍 재발)"
    assert "visibility = ''" in go_body, "안전핀이 화면을 드러내지 않는다"


def test_pin_reveals_and_cleans_up():
    """가려둔 화면은 반드시 다시 드러난다 — 안 그러면 빈 화면이 남는다."""
    blk = _seek_block()
    assert "visibility = ''" in blk                 # 드러내기
    assert re.search(r"setTimeout\(go,\s*\d+\)", blk), "안전핀이 없으면 영영 가려질 수 있다"
    assert "_unhidePinned()" in blk                 # 다음 전환 전에 앞선 것을 정리


def test_stop_play_unhides():
    """재생을 멈출 때도 되돌린다 — 멈춘 화면이 빈 채로 남으면 안 된다."""
    body = JS[JS.index("function stopPlay()"):]
    body = body[:body.index("\n}")]
    assert "_unhidePinned()" in body


@pytest.mark.parametrize("fn", ["_seekSettled", "_unhidePinned"])
def test_helpers_defined_once(fn):
    """같은 이름을 두 번 만들면 나중 것이 앞 것을 조용히 덮는다(이 저장소가 데인 함정)."""
    assert JS.count("function %s(" % fn) == 1
