import io
from shopping_shorts import script_extract


def test_assign_seg_ids_pure():
    raw = [
        {"start": 0, "end": 1.5, "text": "안녕", "scene_desc": "인물 등장"},
        {"start": 1.5, "end": 3, "text": "이거 보세요", "scene_desc": "제품 클로즈업"},
    ]
    out = script_extract._assign_seg_ids("vidA", raw)
    assert out[0]["seg_id"] == "vidA-0"
    assert out[1]["seg_id"] == "vidA-1"
    assert out[0]["start"] == 0.0 and isinstance(out[0]["start"], float)
    assert out[1]["end"] == 3.0


def test_assign_seg_ids_tolerates_missing_fields():
    out = script_extract._assign_seg_ids("v", [{"text": "x"}])
    assert out[0]["seg_id"] == "v-0"
    assert out[0]["start"] == 0.0
    assert out[0]["end"] == 0.0
    assert out[0]["scene_desc"] == ""


def test_extract_script_maps_gemini_response(monkeypatch):
    # Gemini 업로드/생성 전체를 가짜로 대체
    class FakeResp:
        text = ('{"segments": [{"start": 0, "end": 2, "text": "훅 문장", '
                '"scene_desc": "손에 든 컵"}], "full_text": "훅 문장"}')

    class FakeFiles:
        def upload(self, **k): return object()
        def get(self, **k):
            class S: name = "ACTIVE"
            class F:
                state = S()
                name = "f"
            return F()
        def delete(self, **k): pass

    class FakeModels:
        def generate_content(self, **k): return FakeResp()

    class FakeClient:
        files = FakeFiles()
        models = FakeModels()

    monkeypatch.setattr(script_extract, "SHORTS_GEMINI_KEYS", ["dummy"])
    monkeypatch.setattr(script_extract.comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(script_extract.comment_gen, "_client_for_key", lambda key: FakeClient())
    monkeypatch.setattr(script_extract, "_wait_until_active", lambda c, f: f)
    monkeypatch.setattr("builtins.open", lambda *a, **k: io.BytesIO(b"fake"))

    out = script_extract.extract_script("/fake.mp4", "vidX", caption="cap")
    assert out["full_text"] == "훅 문장"
    assert out["segments"][0]["seg_id"] == "vidX-0"
    assert out["segments"][0]["scene_desc"] == "손에 든 컵"


def test_extract_script_exhausted_pool_returns_empty(monkeypatch):
    monkeypatch.setattr(script_extract, "SHORTS_GEMINI_KEYS", ["dummy"])
    monkeypatch.setattr(script_extract.comment_gen, "_current_key_and_idx", lambda: (None, None))
    out = script_extract.extract_script("/fake.mp4", "vidX")
    assert out == {"segments": [], "full_text": ""}


def test_boundary_hint_formats_seconds(monkeypatch):
    from shopping_shorts import script_extract
    # detect_cuts가 프레임(30fps 가정) 튜플을 주면 초 경계 문자열로 변환.
    monkeypatch.setattr(script_extract.scene_cut, "video_fps", lambda p: 30.0)
    monkeypatch.setattr(script_extract.scene_cut, "detect_cuts",
                        lambda p, threshold=0.3: [(0, 108), (108, 255), (255, 363)])
    hint = script_extract._boundary_hint("dummy.mp4")
    assert "3.6" in hint and "8.5" in hint   # 108/30=3.6, 255/30=8.5


def test_boundary_hint_fail_open(monkeypatch):
    from shopping_shorts import script_extract
    def boom(*a, **k): raise RuntimeError("ffmpeg 없음")
    monkeypatch.setattr(script_extract.scene_cut, "detect_cuts", boom)
    assert script_extract._boundary_hint("dummy.mp4") == ""   # 실패=빈 문자열


def test_prompt_scene_desc_accuracy_guard():
    from shopping_shorts import script_extract
    p = script_extract._PROMPT
    assert "주 대상" in p and "정확" in p
