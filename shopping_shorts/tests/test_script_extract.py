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


def test_assign_seg_ids_accepts_motion_map(monkeypatch):
    from shopping_shorts import script_extract as se
    raw_segments = [
        {"start": 0.0, "end": 1.0, "text": "훅", "scene_desc": "손이 상자를 연다"},
        {"start": 1.0, "end": 3.0, "text": "본문", "scene_desc": "제품을 든다"},
    ]
    motion_map = {"vid-0": "PEAK", "vid-1": None}
    out = se._assign_seg_ids("vid", raw_segments, motion_map=motion_map)
    assert out[0]["motion_level"] == "PEAK"
    assert out[1]["motion_level"] is None


def test_assign_seg_ids_motion_map_optional_defaults_none():
    from shopping_shorts import script_extract as se
    raw_segments = [{"start": 0.0, "end": 1.0, "text": "", "scene_desc": ""}]
    out = se._assign_seg_ids("vid", raw_segments)
    assert out[0]["motion_level"] is None


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
    hint, cuts, fps = script_extract._boundary_hint("dummy.mp4")
    assert "3.6" in hint and "8.5" in hint   # 108/30=3.6, 255/30=8.5
    assert cuts == [(0, 108), (108, 255), (255, 363)]
    assert fps == 30.0


def test_boundary_hint_fail_open(monkeypatch):
    from shopping_shorts import script_extract
    def boom(*a, **k): raise RuntimeError("ffmpeg 없음")
    monkeypatch.setattr(script_extract.scene_cut, "detect_cuts", boom)
    hint, cuts, fps = script_extract._boundary_hint("dummy.mp4")
    assert hint == "" and cuts == [] and fps == 0.0


def test_extract_script_computes_motion_map(monkeypatch):
    from shopping_shorts import script_extract

    class FakeResp:
        text = ('{"segments": [{"start": 0, "end": 1, "text": "훅", "scene_desc": "손"}, '
                '{"start": 1, "end": 3, "text": "본문", "scene_desc": "제품"}], '
                '"full_text": "훅본문"}')

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

    # scene_cut(ffmpeg) 3함수 모킹: 컷 2개(0~30프레임 LOW, 30~90프레임 PEAK), fps=30
    monkeypatch.setattr(script_extract.scene_cut, "video_fps", lambda p: 30.0)
    monkeypatch.setattr(script_extract.scene_cut, "detect_cuts", lambda p, **kw: [(0, 30), (30, 90)])
    monkeypatch.setattr(script_extract.scene_cut, "frame_motion", lambda p, **kw: {0: 1.0, 30: 99.0, 60: 40.0})

    out = script_extract.extract_script("/fake.mp4", "vidX", caption="cap")
    # seg0[0,1)→프레임0~30 → 컷(0,30) 전체겹침 vs 컷(30,90) 0겹침 → LOW
    assert out["segments"][0]["motion_level"] == "LOW"
    # seg1[1,3)→프레임30~90 → 컷(30,90)과 전체겹침 → PEAK
    assert out["segments"][1]["motion_level"] == "PEAK"


def test_prompt_scene_desc_accuracy_guard():
    from shopping_shorts import script_extract
    p = script_extract._PROMPT
    assert "주 대상" in p and "정확" in p


def test_prompt_main_product_vs_background_prop_guard():
    """배경 소품·동물에 낚여 주 제품을 오인하는 것을 막는 지시가 프롬프트에 있는지(2026-07-29 실사고)."""
    from shopping_shorts import script_extract
    p = script_extract._PROMPT
    assert "배경 소품" in p
    assert "동물" in p
