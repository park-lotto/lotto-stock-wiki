# -*- coding: utf-8 -*-
"""스토리 검사 — 사람이 나오나 / 쓰임이 번지나 (2026-09-09).

■ 왜 생겼나 — 사장님: "기존 레퍼런스 채널들 원본이랑 스토리 탄탄한지 비교해봐"

  라이브 DB의 레퍼런스 원본 **630편**을 실측해 우리 대본과 대조했다:

      구체적인 사람이 나온다      299편 (47%)
      겪은 말투(더라고/샀는데)    308편 (49%)

  레퍼런스: "고민만 백만 번 하고 있었는데 **육아선배 언니가** 추천해주는 거예요.
            어릴 땐 낮게 → 크면 높여서 → 길게 늘려서 → 나중엔 **책장이나 행거로**.
            **애들도** 동화 속 오두막집 같다며"
  우리:     "요즘 **사람들** 사이에서 … **초보들은** 수면용이 전부였는데 **고수들은**
            물놀이 귀 보호까지"

  차이가 둘로 모인다 — **얼굴 있는 사람이 없다**, **쓰임이 1단뿐이다**(레퍼런스는 4단).
  그래서 우리 대본은 이야기가 아니라 설명문이 된다.

■ 못박는 계약
  · 익명 집단(사람들·다들·초보들)은 사람이 아니다
  · 쓰임 검사는 재료(targets)가 있을 때만 — 없으면 항목 자체를 안 만든다(회귀 0)
  · 사람 검사는 **기본 꺼짐** — 정보형 스타일까지 강제하면 멀쩡한 대본이 반려된다
  · 재료는 게이트가 **스스로 읽는다** — 호출부 4곳에 인자를 심으면 한 곳이 빠진다(0순위-B)
"""
from shopping_shorts import script_gate as g, insta_facts


# ── 사람 ────────────────────────────────────────────────────────────────
def test_익명_집단은_사람이_아니다():
    """★사장님이 받은 그 대본이다."""
    A = "요즘 사람들 사이에서 엉뚱한 용도로 대박 난 물건 초보들은 수면용이 전부였는데 고수들은 물놀이까지 하더라고"
    assert g.has_person(A) is False


def test_레퍼런스처럼_쓰면_통과():
    R = "고민만 백만 번 하고 있었는데 육아선배 언니가 이걸 추천해주는 거예요 애들도 신나하는데"
    assert g.has_person(R) is True


def test_가족_지인_1인칭_전부_사람으로_센다():
    for t in ("엄마한테 보내드렸더니", "남편이 써보더니", "제가 직접 써봤는데",
              "애들이 아지트라며", "친구가 추천해서", "우리집 화장실에"):
        assert g.has_person(t), t


def test_사람_검사는_기본_꺼짐():
    """★정보형·스펙형까지 사람을 강제하면 회귀가 난다 — 켤 때만 검사한다."""
    style = {"beat_roles": [], "templates": {}}
    names = [c["name"] for c in g.check(style, [{"role": "", "text": "그냥 설명"}])[0]]
    assert "사람이 나온다" not in names
    names_on = [c["name"] for c in
                g.check(style, [{"role": "", "text": "그냥 설명"}], person_required=True)[0]]
    assert "사람이 나온다" in names_on


# ── 쓰임 ────────────────────────────────────────────────────────────────
_FACTS = insta_facts.insta_prompt_block(
    {"targets": ["수면용 귀마개", "물놀이 귀 보호", "공부할 때 소음 차단"]})


def test_재료에서_쓰임을_되찾는다():
    assert len(g._targets_from_facts(_FACTS)) == 3


def test_한_곳만_말하면_반려된다():
    """레퍼런스는 4단인데 우리는 1단이었다."""
    t = g._targets_from_facts(_FACTS)
    A = "초보들은 수면용이 전부였는데 고수들은 물놀이 귀 보호까지 하더라고"
    assert len(g.used_targets(A, t)) < g._USE_MIN


def test_여러_곳으로_번지면_통과():
    t = g._targets_from_facts(_FACTS)
    good = "잘 때도 끼고 물놀이 갈 때 귀 보호로도 쓰고 공부할 때 소음 차단까지 되더라고"
    assert len(g.used_targets(good, t)) >= g._USE_MIN


def test_재료가_없으면_항목_자체가_없다():
    """회귀 0 — 쓰임 재료가 없는 job은 종전대로 나와야 한다."""
    assert g._targets_from_facts("쿠팡 재료만 있음") == []
    style = {"beat_roles": [], "templates": {}}
    names = [c["name"] for c in g.check(style, [{"role": "", "text": "x"}])[0]]
    assert "쓰임이 번진다" not in names


def test_게이트가_재료를_스스로_읽는다():
    """★호출부 4곳에 인자를 심으면 한 곳이 빠지고 검사가 조용히 죽는다(0순위-B)."""
    style = {"beat_roles": [], "templates": {}}
    beats = [{"role": "", "text": "잘 때도 끼고 물놀이 귀 보호로도 쓰고 공부할 때 소음 차단까지"}]
    hit = [c for c in g.check(style, beats, facts_text=_FACTS)[0] if c["name"] == "쓰임이 번진다"]
    assert hit and hit[0]["ok"], "재료를 넘겼는데 검사가 안 생기거나 틀렸다"
