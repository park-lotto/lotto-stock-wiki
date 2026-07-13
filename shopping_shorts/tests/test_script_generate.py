import json

from shopping_shorts import script_generate, comment_gen

_STRUCT = {"characters": [{"who": "농원 언니", "role": "정보원"}], "twist": "관상용→가전",
           "development": "문제→해결", "hook": "언니네 집은 왜 안 습해?", "appeal": "편리함",
           "tone": "친근한 수다체"}


def _wire(mp, text):
    mp.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    mp.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    def gen(model, contents, config):
        return type("R", (), {"text": text})()
    models = type("M", (), {"generate_content": staticmethod(gen)})()
    mp.setattr(comment_gen, "_client_for_key", lambda key: type("C", (), {"models": models})())


def test_generate_ok(monkeypatch):
    _wire(monkeypatch, json.dumps({"drafts": [{"hook": "h", "script": "s", "applied": "a"}]}))
    out = script_generate.generate_variations(_STRUCT, "원본 대본", {"characters": "keep"}, {}, "A")
    assert out[0]["script"] == "s"


def test_generate_no_keys(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [])
    assert script_generate.generate_variations(_STRUCT, "t", {}, {}, "A") == []


def test_generate_empty_text_is_noop(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", ["k"])
    assert script_generate.generate_variations(_STRUCT, "   ", {}, {}, "A") == []


def test_generate_bad_json(monkeypatch):
    _wire(monkeypatch, "not json")
    assert script_generate.generate_variations(_STRUCT, "t", {}, {}, "A") == []


def test_elem_lines_keep_mode():
    lines = script_generate._elem_lines(_STRUCT, {"characters": "keep", "twist": "keep"}, {})
    assert "유지" in lines
    assert "농원 언니" in lines  # characters를 사람이 읽을 형태로 펼침


def test_elem_lines_free_mode():
    lines = script_generate._elem_lines(_STRUCT, {"twist": "free"}, {})
    assert "변형" in lines and "자유" in lines


def test_elem_lines_category_mode_uses_lookup_description():
    lookup = {"characters": [{"label": "전문가", "description": "직업 전문가 등장"}]}
    lines = script_generate._elem_lines(
        _STRUCT, {"characters": "category:전문가"}, lookup)
    assert "전문가" in lines and "직업 전문가 등장" in lines


def test_elem_lines_random_mode_picks_from_lookup(monkeypatch):
    lookup = {"tone": [{"label": "정중체", "description": "존댓말"}]}
    monkeypatch.setattr(script_generate.random, "choice", lambda seq: seq[0])
    lines = script_generate._elem_lines(_STRUCT, {"tone": "random"}, lookup)
    assert "정중체" in lines


def test_elem_lines_hook_uses_hook_type_field():
    # hook 요소는 structure의 실제 필드명이 hook_type(analyze_structure 출력 기준) —
    # _elem_lines가 "hook"이 아니라 "hook_type"을 읽는지 확인(버그 수정, 2026-07-13).
    struct = dict(_STRUCT)
    struct["hook_type"] = "경고형"
    lines = script_generate._elem_lines(struct, {"hook": "keep"}, {})
    assert "경고형" in lines


def test_refine_draft_rewrite_returns_new_script(monkeypatch):
    _wire(monkeypatch, json.dumps({"script": "더 유머러스한 새 대본"}))
    out = script_generate.refine_draft_rewrite("원본 대본", "더 유머러스하게")
    assert out == "더 유머러스한 새 대본"


def test_refine_draft_rewrite_empty_on_failure(monkeypatch):
    _wire(monkeypatch, "not json")
    assert script_generate.refine_draft_rewrite("원본", "지시") == ""


def test_refine_draft_partial_returns_new_script(monkeypatch):
    _wire(monkeypatch, json.dumps({"script": "앞부분 그대로. 바뀐 뒷부분."}))
    out = script_generate.refine_draft_partial("앞부분 그대로. 원래 뒷부분.", "원래 뒷부분.", "더 재밌게")
    assert out == "앞부분 그대로. 바뀐 뒷부분."


def test_refine_draft_no_keys_returns_empty(monkeypatch):
    monkeypatch.setattr(comment_gen, "SHORTS_GEMINI_KEYS", [])
    assert script_generate.refine_draft_rewrite("원본", "지시") == ""
    assert script_generate.refine_draft_partial("원본", "부분", "지시") == ""


def test_elem_lines_devices_keep_mode_joins_list():
    struct = {"devices": ["권위자인용", "구체적숫자"]}
    lines = script_generate._elem_lines(struct, {"devices": "keep"}, {})
    assert "설득장치" in lines
    assert "권위자인용" in lines and "구체적숫자" in lines


def test_elem_lines_devices_in_elem_keys():
    assert "devices" in script_generate.ELEM_KEYS
    assert script_generate.ELEM_LABELS["devices"] == "설득장치"
