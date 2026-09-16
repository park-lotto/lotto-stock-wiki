# -*- coding: utf-8 -*-
"""경로 정리 3단계 — "장면을 먼저 고르고 그 장면에 대해 쓴다"를 고정한다(2026-09-16).

배경(실측 job c393b1c7c2f9 / mix 26698eb0a362, 팬케이크): 2단계가 10줄 전부에 장면 번호를 붙였는데
사람이 보면 5줄이 화면과 무관했다("친구네 집 갔다가"에 팬케이크 들어올리는 컷, "단백질까지"에
반으로 가르는 컷). 게이트는 번호가 목록에 **있는지**만 봤고 3단계는 그대로 상속했다 — 의미를 보는
곳이 어디에도 없었다.

처방 셋(검사 추가가 아니라 구조 + 최소 검사):
  1. 출력 칸 순서 role → needs_scene → src_seg → text (propertyOrdering). 장면을 고른 뒤 문장을 쓴다.
  2. 규칙 문구: "장면을 먼저 고르고, 그 장면에 보이는 것을 말로 옮겨라 / 화면에 없는 이야기는 억지로
     장면을 붙이지 마라".
  3. 유일한 의미 검사 `_shares_word`: 문장과 대표 장면 설명이 2글자 어간을 하나도 안 나누면
     '장면과 무관한 문장'으로 되돌린다(치명 아님, 모델 0회).

★3번은 실데이터로 채점한 뒤 남겼다: 맞는 줄 5개 오탐 0 · 무관한 줄 5개 중 3개 검출(8·9번은 못 잡음).
  "맞는 줄을 절대 잘못 잡지 않는다"가 이 검사의 존재 조건이다 — 그게 깨지면 검사를 빼야 한다.
"""
import json
from pathlib import Path

from shopping_shorts import script_gate as G, script_generate as SG

_FIX = Path(__file__).parent / "fixtures" / "pancake_c393b1c7c2f9.json"


def _fixture():
    return json.loads(_FIX.read_text(encoding="utf-8"))


def test_출력_칸_순서는_장면_먼저_문장_나중():
    items = SG._STYLE_SCHEMA["properties"]["beats"]["items"]
    assert items["propertyOrdering"] == ["role", "needs_scene", "src_seg", "text"]
    assert list(items["properties"].keys()) == ["role", "needs_scene", "src_seg", "text"]
    assert set(items["required"]) == {"role", "src_seg", "text"}


def test_규칙_문구가_장면_먼저를_말한다():
    assert "장면을 먼저 고르고" in SG._GROUNDED_RULE
    assert "억지로 장면을 붙이지 마라" in SG._GROUNDED_RULE
    assert "반려된다" not in SG._GROUNDED_RULE      # 09-14식 위협 문구는 빠졌다


def test_shares_word_는_2글자_어간_겹침만_본다():
    assert G._shares_word("프라이팬에 굽기만 하면 끝이라는데", "반죽을 프라이팬 위로 짜내는 모습")
    assert G._shares_word("알고 보니 수플레 팬케이크였다", "노릇하게 익은 팬케이크들을 보여줌")
    # 알려진 한계: '팬에'와 '프라이팬'은 2글자 어간을 안 나눈다. 그래서 scene_descs_of가 scene_desc뿐
    # 아니라 change·action·use_point까지 이어 붙인다 — 실데이터 6번("팬에 굽기만")은 그 덕에 잡히지 않았다.
    assert not G._shares_word("팬에 굽기만 하면", "반죽을 프라이팬 위로 짜내는 모습")
    assert not G._shares_word("저 친구네 집 갔다가 충격 받았어요", "익은 팬케이크를 들어 올리며 보여줌")
    assert not G._shares_word("", "아무 설명")
    assert G._shares_word("54개 부품이 들어있음", "카드 한 장에 54개 부품")   # 숫자도 낱말


def test_scene_descs_없이_부르면_옛_동작_그대로():
    beats = [{"role": "hook", "text": "저 친구네 집 갔다가", "src_seg": "s0-0", "needs_scene": True},
             {"role": "use", "text": "팬에 굽기만", "src_seg": "s0-1", "needs_scene": True},
             {"role": "cta", "text": "댓글 남겨요", "src_seg": "", "needs_scene": False}]
    ok, det = G.scene_grounding_check(beats, {"s0-0", "s0-1"})
    assert ok and "무관" not in det


def test_팬케이크_실데이터_맞는_줄은_절대_안_잡고_무관한_줄을_잡는다():
    d = _fixture()
    descs = SG.scene_descs_of(d["sources"])
    ids = SG.scene_ids_of(d["sources"])
    assert len(d["beats"]) == 10 and len(ids) >= 40
    ok, det = G.scene_grounding_check(d["beats"], ids, scene_descs=descs, source_count=4)
    assert not ok and "장면과 무관한 문장" in det
    # 사람이 판정한 정답(앞 세션 표): 맞는 줄 2·4·5·6·7 — 이 줄들은 무관 목록에 **절대** 없어야 한다
    for i in (2, 4, 5, 6, 7):
        assert f"{i}번 '" not in det.split("장면과 무관한 문장")[1].split(" — ")[0], (i, det)
    # 무관한 줄 1·3·10은 잡힌다(8·9는 '폭신'·'부드러' 같은 낱말이 겹쳐 못 잡는다 — 알려진 한계)
    flagged = det.split("장면과 무관한 문장: ")[1].split(" — ")[0]
    for i in (1, 3, 10):
        assert f"{i}번 '" in flagged, (i, flagged)


def test_무관_판정은_치명이_아니다():
    """되돌리기(재작성 1회)까지만 — 안을 버리지 않는다. 치명은 소재 셋뿐(FATAL_CHECKS)."""
    assert "장면 근거" not in G.FATAL_CHECKS
    assert G.fatal_fail([{"name": "장면 근거", "ok": False, "detail": "장면과 무관한 문장: 1번"}]) == ""
