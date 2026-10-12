# -*- coding: utf-8 -*-
"""자막 줄을 쪼개도 **맞춰 둔 장면은 그 말에 붙어 있다**(2026-09-21 박세현님 job fe21f8a5dc71).

사고: 믹스에서 3줄↔3장면을 맞춘 뒤, 자막 단계에서 **마지막 줄**을 읽기 좋게 둘로 나눴다.
종전 규칙 `(k*조각수)//구절수`는 어느 줄을 나눴는지 안 보고 앞에서부터 고르게 다시 나눠
**2번째 줄 「기름때 낀 프라이팬을」의 닦는 장면(s5)이 행주 장면(s2) 반복으로** 바뀌었다.
완성본 프레임으로 확인한 실제 사고 모양을 그대로 테스트로 옮긴다.

규칙(한 곳 = video_assemble.phrase_owners):
  R1 구절 수 == 조각 수 → 순서대로 1:1 (그리고 그 짝을 새로 얼린다)
  R2 수가 다르고 얼린 짝(clip_anchor)이 유효 → 조각은 **자기가 덮던 글자 위치**를 계속 덮는다
  R3 얼린 짝이 없으면 종전 식(옛 job 동작 그대로)
"""
import pytest

from shopping_shorts import video_assemble as va

# 박세현님 칸1 실물(서버 스냅샷 final_clean_05b2….plan.json / …7b11….plan.json)
NARR = "웬 키친타월인가 했더니, 기름때 낀 프라이팬을 쓱 닦아내는 항균 행주더라고요."
L3 = ["웬 키친타월인가 했더니", "기름때 낀 프라이팬을", "쓱 닦아내는 항균 행주더라고요"]
L4 = ["웬 키친타월인가 했더니", "기름때 낀 프라이팬을", "쓱 닦아내는", "항균 행주더라고요"]
SEGS = [{"video_id": "s2", "seg_id": "film_s2_30.23_31.63", "start": 30.23, "end": 31.63},
        {"video_id": "s5", "seg_id": "film_s5_3.55_4.85", "start": 3.55, "end": 4.85},
        {"video_id": "s2", "seg_id": "film_s2_33.76_34.80", "start": 33.76, "end": 34.80}]


def _beat(lines, **kw):
    b = {"narration": NARR, "caption_lines": list(lines), "phrase_sync": True,
         "scene_override": [dict(s) for s in SEGS]}
    b.update(kw)
    return b


def test_사고재현_마지막줄을_나눠도_둘째줄_장면은_그대로():
    """믹스에서 3줄·3장면을 맞춤(얼림) → 자막 단계에서 마지막 줄을 나눔 → 렌더."""
    b = _beat(L3)
    va.ensure_clip_anchor(b)                 # 믹스 저장(apply) 시점 = 보이는 짝을 얼린다
    b["caption_lines"] = list(L4)            # 자막 단계에서 마지막 줄을 둘로
    b["cap_durs"] = [1.395, 1.299, 0.5756, 1.1944]      # 렌더 #2 스냅샷의 실제 구절 시간
    b["cap_lead"] = 0.0
    assert va.phrase_owners(b, 3) == [0, 1, 2, 2]
    plan = va._plan_phrase_clips(b, va._beat_material(b), 4.46)
    vids = [c["video_id"] for c in plan]
    assert vids == ["s2", "s5", "s2", "s2"], vids       # 종전: s2,s2,s5,s2 (닦는 장면이 밀림)
    assert plan[1]["start"] == pytest.approx(3.55)       # 닦는 장면이 제 줄에서 처음부터
    assert plan[2]["start"] == pytest.approx(33.76)      # 나눈 두 줄은 같은 롤 장면이
    assert plan[3]["start"] == pytest.approx(plan[2]["start"] + plan[2]["out_dur"], abs=1e-6)  # 이어서


def test_칸3_실물_둘째줄을_나누면_둘째장면이_이어_덮는다():
    """칸3 실물: 종전엔 첫 장면(s0)이 두 번 나오고 2.2초로 맞춘 s8이 1.24초로 잘렸다."""
    b = {"narration": "흡수력도 좋아서 싱크대 물기까지 한 번에 정리돼요.", "phrase_sync": True,
         "caption_lines": ["흡수력도 좋아서", "싱크대 물기까지 한 번에 정리돼요"],
         "scene_override": [{"video_id": "s0", "start": 21.32, "end": 22.44},
                            {"video_id": "s8", "start": 8.76, "end": 10.96}]}
    va.ensure_clip_anchor(b)
    b["caption_lines"] = ["흡수력도 좋아서", "싱크대 물기까지", "한 번에 정리돼요"]
    b["cap_durs"] = [0.94, 0.96, 1.244]
    plan = va._plan_phrase_clips(b, va._beat_material(b), 3.144)
    assert [c["video_id"] for c in plan] == ["s0", "s8", "s8"]
    assert plan[1]["out_dur"] + plan[2]["out_dur"] == pytest.approx(2.204, abs=1e-3)   # s8이 2.2초 그대로


def test_R1_수가_같아지면_순서대로_그리고_다시_나눠도_유지():
    """잘못 얼려진 옛 상태에서 빠져나오는 길: 줄을 합쳐 수를 맞추면 1:1, 다시 나눠도 안 밀린다."""
    b = _beat(L4)                            # 옛 job: 4줄·3장면, 얼린 짝 없음
    assert va.phrase_owners(b, 3) == [0, 0, 1, 2]        # R3 — 옛 동작 그대로
    va.ensure_clip_anchor(b)                 # 그 (틀린) 짝이 얼어도
    b["caption_lines"] = list(L3)            # 줄을 합쳐 3줄 = 3장면
    assert va.phrase_owners(b, 3) == [0, 1, 2]           # R1
    va.ensure_clip_anchor(b)                 # 수가 같으면 1:1로 **다시 얼린다**
    b["caption_lines"] = list(L4)
    assert va.phrase_owners(b, 3) == [0, 1, 2, 2]


def test_앞줄을_합쳐도_뒷줄_장면은_그대로():
    """A+B를 합치면 구절 2·조각 3 — 뒤 C의 장면이 조각2에서 조각1로 밀리면 안 된다."""
    b = _beat(L3)
    va.ensure_clip_anchor(b)
    b["caption_lines"] = ["웬 키친타월인가 했더니 기름때 낀 프라이팬을", "쓱 닦아내는 항균 행주더라고요"]
    assert va.phrase_owners(b, 3) == [0, 2]


def test_대사가_바뀌면_얼린짝은_무효():
    b = _beat(L3)
    va.ensure_clip_anchor(b)
    b["narration"] = "전혀 다른 문장입니다 정말로 다릅니다 그렇죠"
    b["caption_lines"] = ["전혀 다른 문장입니다", "정말로", "다릅니다", "그렇죠"]
    assert va.phrase_owners(b, 3) == [0, 0, 1, 2]        # 옛 글자 위치를 새 문장에 들이대지 않는다


def test_조각수가_바뀌면_얼린짝은_무효():
    b = _beat(L3)
    va.ensure_clip_anchor(b)
    b["caption_lines"] = list(L4)
    assert va.phrase_owners(b, 2) == [0, 0, 1, 1]        # 조각 2개 = 종전 식


def test_얼린짝_없는_옛_job은_장면_배정이_종전_그대로():
    """배정(어느 줄에 어느 장면)은 옛 식 그대로다. ★달라지는 것 하나: 같은 장면이 바로 다음 줄로
    이어질 때 재료가 모자라면 종전엔 처음부터 **되감았고** 이제는 끝 프레임에서 버틴다(의도한 변경)."""
    b = _beat(L4)
    plan = va._plan_phrase_clips(b, va._beat_material(b), 4.46)
    assert [c["video_id"] for c in plan] == ["s2", "s2", "s5", "s2"]
