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


def _show_body():
    """화면을 켜는 **한 곳** — 보호는 여기 있어야 한다."""
    i = JS.index("function showVid(")
    return JS[i:JS.index("\n}", i)]


def test_settled_is_judged_by_value_not_flag():
    """구멍① — 플래그가 아니라 **실제 시각**으로 판정해야 한다."""
    assert "function _seekSettled(" in JS
    body = JS[JS.index("function _seekSettled("):]
    body = body[:body.index("\n}")]
    assert "currentTime" in body          # 값을 본다
    assert "_SEEK_EPS" in body            # 허용 오차로 비교
    assert "v.seeking" in body or "!v.seeking" in body   # 플래그는 보조로만


def test_protection_lives_in_show_vid_not_in_callers():
    """★보호는 **화면을 켜는 한 곳**에 있어야 한다(2026-09-20 사장님 "6곳중에 2곳 고친거면 또 그런다").

    처음엔 되감기(seekTo) 자리에만 넣었다. 그런데 showVid 호출처가 6곳이고, 그중 재생 중
    컷 갈아끼우기는 `v.currentTime = …` 하고 **곧바로** 켜는 같은 모양이라 거기서 또 샌다.
    한 곳씩 막으면 새 경로가 생길 때마다 또 새므로, 보호를 showVid 안으로 옮겼다.
    """
    body = _show_body()
    assert "visibility = 'hidden'" in body          # 아직 안 왔으면 가린다
    assert "_seekSettled(" in body                  # 값(또는 시크중)으로 판정
    assert "_pinHidden(" in body                    # 드러내는 일은 한 곳에서만


def test_every_caller_passes_the_target_time():
    """켤 때 **어디로 보냈는지**를 넘겨야 값으로 판정할 수 있다.

    안 넘기면 '시크 중인가'로만 보게 되는데, 그건 브라우저가 플래그를 세우기 전 틈을 못 막는다
    (9/18판이 그래서 샜다). 목표를 아는 호출처는 반드시 넘긴다.
    """
    calls = [ln.strip() for ln in JS.splitlines()
             if "showVid(" in ln and "function showVid" not in ln]
    assert len(calls) >= 5, "호출처를 못 찾았다(리팩터링으로 모양이 바뀌었나)"
    # 목표를 모르는 곳은 '썸네일 잡기' 한 곳뿐 — 거긴 멈춘 상태라 showVid 가 시크중만 봐도 된다
    bare = [c for c in calls if "showVid(v)" in c]
    assert len(bare) <= 1, "목표 시각을 안 넘기는 호출처가 남았다: %s" % bare


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
    assert "_unhidePinned()" in _show_body()                    # 자리에 왔으면 앞선 것을 정리


def test_stop_play_unhides():
    """재생을 멈출 때도 되돌린다 — 멈춘 화면이 빈 채로 남으면 안 된다."""
    body = JS[JS.index("function stopPlay()"):]
    body = body[:body.index("\n}")]
    assert "_unhidePinned()" in body


@pytest.mark.parametrize("fn", ["_seekSettled", "_unhidePinned", "_pinHidden"])
def test_helpers_defined_once(fn):
    """같은 이름을 두 번 만들면 나중 것이 앞 것을 조용히 덮는다(이 저장소가 데인 함정)."""
    assert JS.count("function %s(" % fn) == 1


def test_pin_releases_the_previous_one_first():
    """★가린 재생기를 **버리고 새로 가리면** 그것은 영영 안 드러난다(2026-09-20 실측).

    칸0(컷 9개)처럼 연달아 전환하면 _hidePin 이 덮어써지고, 앞서 가려둔 재생기는
    visibility:hidden 인 채로 남는다. 3초를 기다려도 화면이 안 그려지는 판이 나왔다
    (3회 중 1회). 가리는 쪽에 **되돌리는 책임**을 같이 둔다.
    """
    body = _pin_body()
    head = body[:body.index("let waited")]
    assert "_unhidePinned()" in head, "앞서 가려둔 재생기를 먼저 되돌리지 않는다"
    # reveal 은 자기 재생기를 조건 없이 되돌려야 한다(다른 전환이 맡았어도 화면은 되살린다)
    rv = body[body.index("const reveal"):body.index("const tick")]
    assert "visibility = ''" in rv
    assert "if (!_hidePin || _hidePin.v !== v) return;" not in rv, \
        "다른 전환이 끼면 되돌리지 않고 빠져나간다(가린 채 남는다)"
