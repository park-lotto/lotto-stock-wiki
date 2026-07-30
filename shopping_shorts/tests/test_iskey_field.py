"""script_extract가 is_key·shot_role를 스키마·출력에 담되 required는 아님(기존 추출본 호환)."""
from shopping_shorts import script_extract


def test_schema_has_iskey_shotrole_optional():
    props = script_extract._RESPONSE_SCHEMA["properties"]["segments"]["items"]["properties"]
    assert props["is_key"]["type"] == "boolean"
    assert props["shot_role"]["type"] == "string"
    req = script_extract._RESPONSE_SCHEMA["properties"]["segments"]["items"]["required"]
    assert "is_key" not in req and "shot_role" not in req


def test_assign_seg_ids_defaults_faillopen():
    raw = [{"start": 0, "end": 2, "text": "a", "scene_desc": "s"}]  # is_key 없음
    out = script_extract._assign_seg_ids("vid", raw)
    assert out[0]["is_key"] is False        # fail-open 기본
    assert out[0]["shot_role"] == "기타"    # fail-open 기본


def test_assign_seg_ids_preserves_iskey():
    raw = [{"start": 0, "end": 2, "text": "a", "scene_desc": "s",
            "is_key": True, "shot_role": "완성"}]
    out = script_extract._assign_seg_ids("vid", raw)
    assert out[0]["is_key"] is True
    assert out[0]["shot_role"] == "완성"
    # 장면스파인 재설계: 옛 값 '조리'는 새 어휘 '사용중'으로 마이그레이션된다(fail-open).
    out2 = script_extract._assign_seg_ids("vid", [{"start": 0, "end": 2, "text": "a",
                                                   "scene_desc": "s", "shot_role": "조리"}])
    assert out2[0]["shot_role"] == "사용중"


def test_prompt_mentions_iskey():
    assert "is_key" in script_extract._PROMPT
    assert "shot_role" in script_extract._PROMPT
