from shopping_shorts import edit_plan


def _scripts():
    return [
        {"video_id": "A", "full_text": "가방 속이 흥건해진 적",
         "segments": [
             {"seg_id": "A-0", "start": 0.0, "end": 2.0, "text": "훅", "scene_desc": "컵"},
             {"seg_id": "A-1", "start": 2.0, "end": 5.0, "text": "페인", "scene_desc": "젖은 가방"},
         ]},
        {"video_id": "B", "full_text": "거꾸로 흔들어도 안 흘러요",
         "segments": [
             {"seg_id": "B-0", "start": 0.0, "end": 3.0, "text": "반전", "scene_desc": "뒤집기"},
         ]},
    ]


def test_build_inventory_maps_all_segments():
    seg_map, block = edit_plan._build_inventory(_scripts())
    assert set(seg_map) == {"A-0", "A-1", "B-0"}
    assert seg_map["A-1"]["start"] == 2.0
    assert "A-0" in block and "B-0" in block  # 프롬프트 블록에 seg_id 노출


def test_ground_ref_returns_real_timecode():
    seg_map, _ = edit_plan._build_inventory(_scripts())
    # 모델이 엉뚱한 start/end를 줘도 인벤토리 값으로 되붙인다
    grounded = edit_plan._ground_ref({"seg_id": "A-1", "start": 999, "end": 999}, seg_map)
    assert grounded == {"video_id": "A", "seg_id": "A-1", "start": 2.0, "end": 5.0,
                        "scene_desc": "젖은 가방",  # scene_desc 실림(Task 4 ①: 얼굴정렬용)
                        "change": "",  # 2026-07-31 신설(사물 주어 변화) — 없는 소스는 빈 문자열
                        "is_key": False, "shot_role": "기타"}  # 앵커 판별용(fail-open 기본)


def test_ground_ref_unknown_seg_id_none():
    seg_map, _ = edit_plan._build_inventory(_scripts())
    assert edit_plan._ground_ref({"seg_id": "ZZ-9"}, seg_map) is None


def test_validate_and_ground_drops_invalid_and_grounds():
    seg_map, _ = edit_plan._build_inventory(_scripts())
    raw = {"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "새 훅", "target_seconds": 2,
         "primary": {"seg_id": "A-0", "start": 111}, "effect": "cut",
         "alternates": [{"seg_id": "B-0"}, {"seg_id": "BAD-1"}]},
        {"beat_idx": 1, "role": "x", "narration": "무효", "target_seconds": 2,
         "primary": {"seg_id": "NOPE"}, "alternates": []},
    ]}
    out = edit_plan._validate_and_ground(raw, seg_map, n_alternates=2)
    assert len(out["beats"]) == 1  # primary 무효인 beat 드롭
    b = out["beats"][0]
    assert b["primary"] == {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 2.0,
                            "scene_desc": "컵", "change": "", "is_key": False, "shot_role": "기타"}
    assert b["alternates"] == [{"video_id": "B", "seg_id": "B-0", "start": 0.0, "end": 3.0,
                                "scene_desc": "뒤집기", "change": "", "is_key": False,
                                "shot_role": "기타"}]  # BAD-1 제거
    assert b["visual_verb"] is False  # 스키마에 없으면 False 폴백(fail-open)


def test_ngram_overlap_identical_is_high():
    assert edit_plan._ngram_overlap("거꾸로 흔들어도 안 흘러요", "거꾸로 흔들어도 안 흘러요") > 0.9


def test_ngram_overlap_different_is_low():
    assert edit_plan._ngram_overlap("완전 새로운 표현입니다", "거꾸로 흔들어도 안 흘러요") < 0.2


def test_plagiarism_flags_detects_copy():
    beats = [
        {"beat_idx": 0, "narration": "거꾸로 흔들어도 안 흘러요"},  # B의 원문 그대로
        {"beat_idx": 1, "narration": "전혀 다른 새 문장이에요"},
    ]
    flags = edit_plan._plagiarism_flags(beats, ["가방 속이 흥건해진 적", "거꾸로 흔들어도 안 흘러요"], threshold=0.5)
    assert [f["beat_idx"] for f in flags] == [0]


def test_build_inventory_exposes_motion_level_without_touching_scene_desc():
    from shopping_shorts.edit_plan import _build_inventory
    source_scripts = [{
        "video_id": "v1",
        # _build_inventory는 첫·마지막 세그먼트를 CTA·썸네일 박제 차단용으로 잘라낸다
        # (len(segs)>=3일 때 segs[1:-1]) — 그래서 앞뒤에 버림용 세그를 하나씩 더 둬서
        # 실제로 검사할 v1-0/v1-1을 중간 자리로 밀어넣는다.
        "segments": [
            {"seg_id": "v1-lead", "start": -1.0, "end": 0.0, "text": "lead", "scene_desc": "리드", "motion_level": None},
            {"seg_id": "v1-0", "start": 0.0, "end": 1.0, "text": "a", "scene_desc": "손이 상자를 연다", "motion_level": None},
            {"seg_id": "v1-1", "start": 1.0, "end": 2.0, "text": "b", "scene_desc": "제품을 든다", "motion_level": "PEAK"},
            {"seg_id": "v1-2", "start": 2.0, "end": 3.0, "text": "c", "scene_desc": "마무리", "motion_level": "LOW"},
            {"seg_id": "v1-tail", "start": 3.0, "end": 4.0, "text": "tail", "scene_desc": "테일", "motion_level": None},
        ],
    }]
    seg_map, inventory = _build_inventory(source_scripts)
    # scene_desc 자체는 불변 — dedup 키(_claim_key)가 이걸 토큰화하므로 오염 금지
    assert seg_map["v1-1"]["scene_desc"] == "제품을 든다"
    assert seg_map["v1-1"]["motion_level"] == "PEAK"
    # 프롬프트 라인에는 모션 정보가 별도로 노출(있을 때만)
    assert "모션:PEAK" in inventory
    # None인 경우 라인에 모션 표기 없음(잡음 최소화)
    line0 = [l for l in inventory.split("\n") if "[v1-0]" in l][0]
    assert "모션:" not in line0
