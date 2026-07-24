"""P0-1(훅 로테이션) + P0-2(믹스 경로 은행 배선) — 반복 완화 핵심.

- parts_block이 상위 perf 풀에서 **랜덤 샘플**해 매 호출 다른 훅 조합을 준다(로테이션).
- scene_first(영상 믹스) 프롬프트에 bank_context가 실린다(기본 off·회귀0).
- _plan_and_tts가 bank_enabled 설정일 때만 은행을 조립해 관통한다.
실키 안 씀 — 전부 monkeypatch/가짜 call.
"""
import re

import shopping_shorts.mix_pipeline as mp
from shopping_shorts import bank_assemble as BA
from shopping_shorts import edit_plan
from shopping_shorts.store import Store


# ---- P0-1: 훅 로테이션(상위 perf 풀에서 랜덤 샘플) ----

def test_parts_block_samples_k_from_pool(tmp_path, monkeypatch):
    s = Store(str(tmp_path / "t.db"))
    for i in range(10):
        iid = s.add_pattern_item("hook", f"훅{i}")
        s.set_pattern_item_status(iid, "approved")
    # rng.sample을 제어 → 결정적으로 앞 k개
    monkeypatch.setattr(BA.random, "sample", lambda pop, k: list(pop)[:k])
    block = BA.parts_block(s, k=5)
    got = set(re.findall(r"훅\d", block))
    assert len(got) == 5           # 10개 승인 중 정확히 k=5개만 실림(로테이션 창)


def test_parts_block_rotates_across_calls(tmp_path, monkeypatch):
    """같은 은행이라도 rng가 다르면 다른 훅 조합이 나온다(반복 방지의 근거)."""
    s = Store(str(tmp_path / "t.db"))
    for i in range(10):
        iid = s.add_pattern_item("hook", f"훅{i}")
        s.set_pattern_item_status(iid, "approved")
    monkeypatch.setattr(BA.random, "sample", lambda pop, k: list(pop)[:k])
    first = set(re.findall(r"훅\d", BA.parts_block(s, k=5)))
    monkeypatch.setattr(BA.random, "sample", lambda pop, k: list(pop)[-k:])
    second = set(re.findall(r"훅\d", BA.parts_block(s, k=5)))
    assert first != second


def test_parts_block_small_bank_uses_all(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    for i in range(3):
        iid = s.add_pattern_item("hook", f"훅{i}")
        s.set_pattern_item_status(iid, "approved")
    got = set(re.findall(r"훅\d", BA.parts_block(s, k=5)))
    assert got == {"훅0", "훅1", "훅2"}   # k보다 적으면 전부(샘플 안 함)


# ---- P0-2: scene_first 프롬프트에 은행 주입 ----

def test_scene_first_injects_bank_context():
    box = {}

    def fake_call(prompt, schema, **kw):
        box["prompt"] = prompt
        return {"candidates": []}

    edit_plan._scene_first_candidates("[s0-0] 화면:x", "ref", 20, call=fake_call,
                                      bank_context="[승인된 부품]\n· 훅: 로테이션된새훅")
    assert "로테이션된새훅" in box["prompt"]


def test_scene_first_no_bank_leaves_prompt_clean():
    box = {}

    def fake_call(prompt, schema, **kw):
        box["prompt"] = prompt
        return {"candidates": []}

    edit_plan._scene_first_candidates("[s0-0] 화면:x", "ref", 20, call=fake_call)
    assert "승인된 부품" not in box["prompt"]


def test_build_scene_first_plan_threads_bank(monkeypatch):
    box = {}

    def fake_candidates(inv, ref, secs, n=3, call=None, bank_context="", order_block=""):
        box["bank"] = bank_context
        return []

    monkeypatch.setattr(edit_plan, "_scene_first_candidates", fake_candidates)
    src = [{"video_id": "s0", "full_text": "x", "segments": [
        {"seg_id": "s0-1", "start": 0.0, "end": 1.0, "text": "", "scene_desc": "a"}]}]
    edit_plan.build_scene_first_plan(src, "ref", 20, call=lambda *a, **k: None,
                                     bank_context="[승인된 부품]\n· 훅: 새훅")
    assert box["bank"] == "[승인된 부품]\n· 훅: 새훅"


# ---- P0-2: _plan_and_tts가 설정에 따라 은행 조립·관통 ----

def _wire_plan(monkeypatch, box):
    def fake_sf(source_scripts, reference_text, target_seconds, **kw):
        box["bank"] = kw.get("bank_context")
        return {"candidates": [
            {"plan": {"beats": [{"beat_idx": 0}], "structure": "free",
                      "plagiarism_flags": [], "detected_type": "x", "affiliate_target": ""},
             "story": {}, "score": 0.9, "recommended": True}]}
    monkeypatch.setattr(edit_plan, "build_scene_first_plan", fake_sf)
    monkeypatch.setattr(mp, "_synthesize_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_conform_beats", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_refill_beats_to_tts", lambda *a, **k: None)


def test_plan_and_tts_injects_bank_when_enabled(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "t.db"))
    store.create_mix_job("j", ["u0", "u1"], 20, "free", scene_first=True)
    store.set_setting("bank_enabled", "1")
    iid = store.add_pattern_item("hook", "승인훅하나")
    store.set_pattern_item_status(iid, "approved")
    box = {}
    _wire_plan(monkeypatch, box)
    mp._plan_and_tts(store, "j", [{"full_text": "x"}], 20, "free", None, tmp_path / "w",
                     scene_first=True, reference_text="ref")
    assert box["bank"] and "승인훅하나" in box["bank"]


def test_plan_and_tts_no_bank_when_disabled(tmp_path, monkeypatch):
    store = Store(str(tmp_path / "t.db"))
    store.create_mix_job("j", ["u0", "u1"], 20, "free", scene_first=True)
    iid = store.add_pattern_item("hook", "승인훅하나")
    store.set_pattern_item_status(iid, "approved")
    box = {}
    _wire_plan(monkeypatch, box)
    mp._plan_and_tts(store, "j", [{"full_text": "x"}], 20, "free", None, tmp_path / "w",
                     scene_first=True, reference_text="ref")
    assert box["bank"] == ""   # 설정 off → 회귀0(은행 미주입)
