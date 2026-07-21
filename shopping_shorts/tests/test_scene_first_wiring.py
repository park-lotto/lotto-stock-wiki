"""Task6: 장면 우선 대본 모드 배선 — 후보 저장/조회 store 왕복 + _plan_and_tts 분기 검증.

실키(Gemini 등)는 전혀 쓰지 않는다 — build_scene_first_plan·build_edit_plan·TTS는 모두 monkeypatch.
"""
import shopping_shorts.mix_pipeline as mp
from shopping_shorts import edit_plan as _edit_plan
from shopping_shorts.store import Store


def test_mix_candidates_roundtrip(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.create_mix_job("j", ["u"], 20, "free")
    st.set_mix_candidates("j", [{"score": 0.9, "recommended": True}])
    got = st.get_mix_candidates("j")
    assert got[0]["recommended"] is True


def test_get_mix_candidates_없으면_빈리스트(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.create_mix_job("j0", ["u"], 20, "free")
    assert st.get_mix_candidates("j0") == []
    assert st.get_mix_candidates("존재안함") == []


def test_create_mix_job_scene_first_플래그_왕복(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.create_mix_job("j1", ["u0", "u1"], 20, "free", scene_first=True)
    job = st.get_mix_job("j1")
    assert job["scene_first"] is True

    st.create_mix_job("j1b", ["u0", "u1"], 20, "free")
    assert st.get_mix_job("j1b")["scene_first"] is False


def test_scene_first_후보있으면_저장하고_추천후보를_edit_plan으로(tmp_path, monkeypatch):
    """_plan_and_tts(scene_first=True)가 build_scene_first_plan을 호출해 후보 전체를
    store에 저장하고, recommended=True인 후보의 plan을 그대로 edit_plan에 세팅하는지."""
    db = tmp_path / "t.db"
    store = Store(str(db))
    store.create_mix_job("j2", ["u0", "u1"], 20, "free", scene_first=True)

    candidates = [
        {"plan": {"beats": [{"beat_idx": 0}], "structure": "free",
                  "plagiarism_flags": [], "detected_type": "unbox", "affiliate_target": ""},
         "story": {}, "score": 0.4, "recommended": False},
        {"plan": {"beats": [{"beat_idx": 0}, {"beat_idx": 1}], "structure": "free",
                  "plagiarism_flags": [], "detected_type": "unbox", "affiliate_target": ""},
         "story": {}, "score": 0.9, "recommended": True},
    ]

    def fake_build_scene_first_plan(source_scripts, reference_text, target_seconds,
                                    n_candidates=3, video_type=None, call=None, ping_pong=False):
        assert reference_text == "ref text"
        return {"candidates": candidates, "detected_type": "unbox"}

    monkeypatch.setattr(_edit_plan, "build_scene_first_plan", fake_build_scene_first_plan)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_conform_beats", lambda *a, **k: None)

    work = tmp_path / "work"
    mp._plan_and_tts(store, "j2", [{"full_text": "x"}], 20, "free", None, work,
                     scene_first=True, reference_text="ref text")

    saved = store.get_mix_candidates("j2")
    assert len(saved) == 2

    job = store.get_mix_job("j2")
    assert job["edit_plan"]["beats"] == candidates[1]["plan"]["beats"]
    assert job["status"] == "ready_for_review"


def test_scene_first_후보없으면_build_edit_plan_폴백(tmp_path, monkeypatch):
    """build_scene_first_plan이 candidates=[]를 돌려주면(grounding 전멸 등) 후보를 저장하지
    않고 기존 build_edit_plan 경로로 조용히 폴백하는지."""
    db = tmp_path / "t.db"
    store = Store(str(db))
    store.create_mix_job("j3", ["u0", "u1"], 20, "free", scene_first=True)

    fallback_plan = {"beats": [{"beat_idx": 0}], "structure": "free",
                     "plagiarism_flags": [], "detected_type": "unbox", "affiliate_target": ""}

    def fake_build_scene_first_plan(*a, **k):
        return {"candidates": [], "detected_type": "unbox"}

    monkeypatch.setattr(_edit_plan, "build_scene_first_plan", fake_build_scene_first_plan)
    monkeypatch.setattr(mp, "build_edit_plan", lambda *a, **k: fallback_plan)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_conform_beats", lambda *a, **k: None)

    work = tmp_path / "work"
    mp._plan_and_tts(store, "j3", [{"full_text": "x"}], 20, "free", None, work,
                     scene_first=True, reference_text="ref text")

    assert store.get_mix_candidates("j3") == []
    job = store.get_mix_job("j3")
    assert job["edit_plan"]["beats"] == fallback_plan["beats"]


def test_scene_first_false면_기존_build_edit_plan_그대로(tmp_path, monkeypatch):
    """scene_first 기본값(False)일 때 build_scene_first_plan은 아예 호출되지 않고
    기존 build_edit_plan 흐름이 무변경으로 동작하는지(하위호환 회귀)."""
    db = tmp_path / "t.db"
    store = Store(str(db))
    store.create_mix_job("j4", ["u0", "u1"], 20, "free")

    called = {"scene_first_plan": False}

    def fake_build_scene_first_plan(*a, **k):
        called["scene_first_plan"] = True
        return {"candidates": [], "detected_type": "unbox"}

    plan = {"beats": [{"beat_idx": 0}], "structure": "free",
            "plagiarism_flags": [], "detected_type": "unbox", "affiliate_target": ""}

    monkeypatch.setattr(_edit_plan, "build_scene_first_plan", fake_build_scene_first_plan)
    monkeypatch.setattr(mp, "build_edit_plan", lambda *a, **k: plan)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_conform_beats", lambda *a, **k: None)

    work = tmp_path / "work"
    mp._plan_and_tts(store, "j4", [{"full_text": "x"}], 20, "free", None, work)

    assert called["scene_first_plan"] is False
    job = store.get_mix_job("j4")
    assert job["edit_plan"]["beats"] == plan["beats"]
