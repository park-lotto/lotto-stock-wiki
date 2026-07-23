from shopping_shorts.store import Store


def test_append_bank_usage_caps_and_persists(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    for i in range(55):
        lst = store.append_bank_usage({"i": i}, cap=50)
    assert len(lst) == 50
    assert lst[0]["i"] == 5        # 앞 5개 밀려남
    assert lst[-1]["i"] == 54
    # 재조회로 영속 확인
    import json
    saved = json.loads(store.get_setting("bank_usage_recent"))
    assert len(saved) == 50


import json
from shopping_shorts import mix_pipeline


def test_record_bank_usage_writes_audit_and_samples(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    snap = {"empty": False, "spine_present": True, "spine_beats": 3, "parts_total": 8}
    rec = {"recommended": True, "score": 0.8,
           "plan": {"beats": [{"narration": "이거 대박인데요?"}] + [{"narration": str(i)} for i in range(5)],
                    "plagiarism_flags": []},
           "story": {"cta_line": "프로필 확인"},
           "judge": {"script_quality": 4, "scene_sync": 4, "storyline": 4, "total": 0.8}}
    calls = {"n": 0}

    def fake_call(prompt, schema):
        calls["n"] += 1
        return {"arc_follow": 4, "flavor_follow": 3, "verbatim_copy": False}

    # counter가 1이 되는 첫 호출 → 샘플됨(N=10, %N==1)
    mix_pipeline._record_bank_usage(store, snap, "ctx", rec, [rec], sample_n=10, call=fake_call)
    audit = json.loads(store.get_setting("bank_usage_audit_last"))
    assert audit["n"] == 1
    assert audit["bank_used_rate"] == 1.0
    assert audit["conformance_pass_rate"] == 1.0
    assert calls["n"] == 1                          # 첫 job 샘플됨
    assert audit["compliance"]["arc_avg"] == 4.0


def test_record_bank_usage_skips_llm_between_samples(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    snap = {"empty": False, "spine_present": True, "spine_beats": 3, "parts_total": 8}
    rec = {"recommended": True, "score": 0.5,
           "plan": {"beats": [{"narration": "b"}], "plagiarism_flags": []},
           "story": {"cta_line": ""}}
    calls = {"n": 0}

    def fake_call(prompt, schema):
        calls["n"] += 1
        return {"arc_follow": 3, "flavor_follow": 3, "verbatim_copy": False}

    for _ in range(5):
        mix_pipeline._record_bank_usage(store, snap, "ctx", rec, [rec], sample_n=10, call=fake_call)
    assert calls["n"] == 1                          # 1번째만 샘플(%10==1), 2~5는 스킵
    audit = json.loads(store.get_setting("bank_usage_audit_last"))
    assert audit["n"] == 5
