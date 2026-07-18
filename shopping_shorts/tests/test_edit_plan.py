from shopping_shorts import edit_plan as ep


def test_validate_and_ground_preserves_alternate_order_up_to_n():
    seg_map = {
        "A-0": {"video_id": "A", "start": 0.0, "end": 2.0},
        "A-1": {"video_id": "A", "start": 2.0, "end": 4.0},
        "B-0": {"video_id": "B", "start": 0.0, "end": 3.0},
    }
    raw = {"beats": [{
        "role": "hook", "narration": "n", "target_seconds": 4.0,
        "primary": {"seg_id": "A-0"},
        "alternates": [{"seg_id": "A-1"}, {"seg_id": "B-0"}],
    }]}
    grounded = ep._validate_and_ground(raw, seg_map, n_alternates=6)
    alts = grounded["beats"][0]["alternates"]
    # 준 순서대로(A-1 먼저, B-0 다음) 보존 — 조립이 이 순서로 이어붙인다.
    assert [a["seg_id"] for a in alts] == ["A-1", "B-0"]


def test_scripted_n_alt_is_high_enough_to_chain():
    # 회귀 잠금: scripted 모드가 후보를 넉넉히 받도록 상수를 높게 유지.
    assert ep._SCRIPTED_N_ALT >= 4
