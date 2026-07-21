from shopping_shorts import script_extract, action_dict, edit_plan


def test_schema_has_action_enum():
    props = script_extract._RESPONSE_SCHEMA["properties"]["segments"]["items"]["properties"]
    assert "action" in props
    assert props["action"]["enum"] == action_dict.ACTION_VOCAB + ["없음"]


def test_assign_seg_ids_fills_action_fallback():
    raw = [{"start": 0, "end": 2, "text": "뚜껑을 당겨서 뜯어요", "scene_desc": "손이 포장을 뜯는다"}]
    segs = script_extract._assign_seg_ids("VID", raw)
    assert segs[0]["action"] == "당기다"


def test_assign_seg_ids_keeps_gemini_action():
    raw = [{"start": 0, "end": 2, "text": "물을 붓는다", "scene_desc": "", "action": "붓다"}]
    segs = script_extract._assign_seg_ids("VID", raw)
    assert segs[0]["action"] == "붓다"


def test_assign_seg_ids_none_action_becomes_none():
    raw = [{"start": 0, "end": 2, "text": "가격은 삼천원", "scene_desc": "", "action": "없음"}]
    segs = script_extract._assign_seg_ids("VID", raw)
    assert segs[0]["action"] is None


def test_inventory_line_includes_action():
    sources = [{"video_id": "V", "segments": [
        {"seg_id": "V-1", "start": 0, "end": 3, "text": "당겨요", "scene_desc": "뜯기", "action": "당기다"}]}]
    seg_map, prompt_block = edit_plan._build_inventory(sources)
    assert "행위:당기다" in prompt_block
    assert seg_map["V-1"]["action"] == "당기다"
