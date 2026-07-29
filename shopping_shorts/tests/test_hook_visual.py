"""P1 훅 비주얼(2026-07-29): 인벤토리가 shot_role/is_key를 프롬프트에 노출하되 scene_desc는 불변.
훅 규칙이 완성/실증 장면을 첫 화면으로 당기고 준비동작을 금지하는지."""
import inspect
from shopping_shorts import edit_plan as ep


def _script():
    return [{"video_id": "v1", "segments": [
        {"seg_id": "v1-0", "start": 0, "end": 2, "text": "훅", "scene_desc": "인트로"},
        {"seg_id": "v1-1", "start": 2, "end": 4, "text": "재료 붓기", "scene_desc": "우유를 붓는다",
         "shot_role": "조리", "is_key": False},
        {"seg_id": "v1-2", "start": 4, "end": 6, "text": "완성", "scene_desc": "완성된 모찌",
         "shot_role": "완성", "is_key": True},
        {"seg_id": "v1-3", "start": 6, "end": 8, "text": "끝", "scene_desc": "인사"},
    ]}]


def test_inventory_exposes_shot_role_and_is_key():
    seg_map, block = ep._build_inventory(_script())
    assert "역할:조리" in block and "역할:완성" in block
    assert "실증:Y" in block            # v1-2 is_key=True
    assert "실증:N" in block            # v1-1 is_key=False
    # scene_desc 문자열엔 역할/실증이 안 섞였다(_claim_key 오염 방지)
    assert seg_map["v1-2"]["scene_desc"] == "완성된 모찌"
    assert "역할" not in seg_map["v1-2"]["scene_desc"]


def test_prompt_has_hook_visual_rule():
    src = inspect.getsource(ep._scene_first_candidates)
    assert "역할:완성" in src
    assert "준비동작" in src
    assert "시간순" in src
