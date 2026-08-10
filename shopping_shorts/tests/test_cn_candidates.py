"""cn_search_candidates — 프레임 비전 → 중국어 후보 검색어 리스트(2026-07-19)."""
import json
import types as _t
from shopping_shorts import video_analysis as va


def test_candidates_empty_without_keys(monkeypatch):
    monkeypatch.setattr(va, "SHORTS_GEMINI_KEYS", [])
    out = va.cn_search_candidates(b"img", "감자칩")
    assert out == {"product": "", "candidates": []}


def test_candidates_empty_without_image(monkeypatch):
    monkeypatch.setattr(va, "SHORTS_GEMINI_KEYS", ["k"])
    out = va.cn_search_candidates(b"", "감자칩")
    assert out == {"product": "", "candidates": []}


def test_candidates_parses_vision_json(monkeypatch):
    monkeypatch.setattr(va, "SHORTS_GEMINI_KEYS", ["k"])
    # 키 조달 함수가 _current_key_and_idx → **_next_live_key_and_idx**로 바뀌었다
    # (키풀 자가복구 작업). 옛 이름을 stub하면 진짜 함수가 돌아 키 없음(None)으로
    # 빠지고, cn_search_candidates가 조용히 빈 결과를 돌려줘 이 테스트가 실패했다.
    monkeypatch.setattr(va.comment_gen, "_next_live_key_and_idx", lambda: ("k", 0))
    payload = {"product": "에어프라이어 감자칩",
               "candidates": [{"ko": "공기튀김 감자칩", "zh": "空气炸锅土豆片"},
                              {"ko": "버블 감자", "zh": "气泡土豆"}]}
    fake_resp = _t.SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))
    fake_client = _t.SimpleNamespace(models=_t.SimpleNamespace(
        generate_content=lambda **kw: fake_resp))
    monkeypatch.setattr(va, "_client_for_key", lambda key: fake_client)
    out = va.cn_search_candidates(b"img", "감자칩 에어프라이어")
    assert out["product"] == "에어프라이어 감자칩"
    assert out["candidates"][0] == {"ko": "공기튀김 감자칩", "zh": "空气炸锅土豆片"}
    assert len(out["candidates"]) == 2
