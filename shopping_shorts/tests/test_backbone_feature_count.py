# -*- coding: utf-8 -*-
"""특징 묶음 3~4개 + 장면별 특징·용처가 재료에 실린다 (2026-09-21 사장님).

사장님: "특징은 4개까지 가야 되고" / "장면의 특징효과등을 태깅잘해서 넣자는거야
        장면에 딱맞게 말은 바꿔서"
종전: 묶음 최소 5·최대 7 → 25초에 7줄이면 줄당 2.5초로 밋밋했다.
     재료 블록엔 영상 단위 특징만 있고 **장면별** 특징·용처가 없어,
     모델이 "이 장면이 무슨 장점을 보여주는가"를 장면 단위로 못 봤다.
"""
from shopping_shorts import backbone_assemble as ba


def test_특징_상한이_4개다():
    assert ba.MAX_GROUPS == 4, "사장님 확정: 특징은 4개까지"
    assert ba.MIN_GROUPS == 3


def test_프롬프트가_3에서4개를_요구한다():
    src = [{"video_id": "s0", "segments": [], "product_benefits": []}]
    import inspect
    body = inspect.getsource(ba.build_groups)
    assert "MIN_GROUPS}~{MAX_GROUPS}" in body or "3~4" in body
    # 잘게 쪼개라는 옛 지시가 남아 있으면 상한과 싸운다
    assert "너무 뭉치지 마라" not in body


def test_장면별_특징과_용처가_재료에_실린다():
    s = {"video_id": "s0", "product_benefits": ["전체특징"], "segments": [
        {"seg_id": "s0-1", "start": 0, "end": 2, "scene_desc": "손이 빗을 든다",
         "text": "이거 보세요", "change": "앰플이 채워짐",
         "product_benefits": ["손에 묻히지 않고 바른다"],
         "use_point": "사용법을 보여주는 대목에 쓰기 좋습니다"},
    ]}
    block = ba._source_block(s, True)
    assert "손에 묻히지 않고 바른다" in block, "장면별 특징이 재료에 없다"
    assert "사용법을 보여주는 대목" in block, "장면별 용처가 재료에 없다"
    assert "손이 빗을 든다" in block and "앰플이 채워짐" in block


def test_장면_특징이_없어도_안_깨진다():
    s = {"video_id": "s0", "segments": [
        {"seg_id": "s0-1", "start": 0, "end": 1, "scene_desc": "화면"},
    ]}
    block = ba._source_block(s, False)
    assert "s0-1" in block and "특징:" not in block
