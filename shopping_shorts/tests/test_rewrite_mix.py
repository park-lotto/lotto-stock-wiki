"""리라이트 믹스 — 원본 타임라인을 뼈대로 두고 문장만 갈아끼운다(2026-07-31).

레퍼런스 프로그램 역분석: 자기 자막이 그 순간 원본 자막을 바꿔 말한 것이었다
("변하는데"→"말랑말랑 젤리 같아요"). 화면을 새로 찾을 필요가 없다.
사장님 정의: "대사의 시작과 끝 장면까지가 한 세트."
"""
from shopping_shorts import edit_plan as ep


def _sm(spec):
    m, t = {}, 0.0
    for sid, text, dur in spec:
        m[sid] = {"video_id": sid.rsplit("-", 1)[0], "seg_id": sid, "start": t, "end": t + dur,
                  "text": text, "scene_desc": f"{sid} 화면", "change": "", "is_key": False,
                  "shot_role": "사용중"}
        t += dur
    return m


def test_pick_slot_sequence_returns_all_segments_once():
    """Gemini가 고른 순서가 무엇이든, 입력된 seg_id 전부가 정확히 한 번씩 나와야 한다."""
    sm = _sm([("v0-1", "가나다요", 2.0), ("v0-2", "라마바요", 2.0),
              ("v1-1", "사아자요", 2.0), ("v1-2", "차카타요", 2.0)])

    def fake_call(prompt, schema):
        # Gemini 응답 흉내: 소스를 교차하는 순서
        return {"order": ["v1-1", "v0-1", "v1-2", "v0-2"]}

    seq = ep._pick_slot_sequence(sm, call=fake_call)
    ids = [s["seg_id"] for s in seq]
    assert sorted(ids) == sorted(sm.keys())
    assert ids == ["v1-1", "v0-1", "v1-2", "v0-2"]


def test_pick_slot_sequence_drops_unknown_ids_from_model():
    """모델이 없는 seg_id를 지어내면 그 항목만 버리고 나머지는 순서 유지."""
    sm = _sm([("v0-1", "가나다요", 2.0), ("v0-2", "라마바요", 2.0)])

    def fake_call(prompt, schema):
        return {"order": ["v0-1", "v9-99", "v0-2"]}

    seq = ep._pick_slot_sequence(sm, call=fake_call)
    assert [s["seg_id"] for s in seq] == ["v0-1", "v0-2"]


def test_pick_slot_sequence_falls_back_when_call_fails():
    """Gemini 호출이 실패(None 반환)하면 _pick_timeline과 동등한 폴백(시간순 이어붙이기)으로."""
    sm = _sm([("v0-1", "가나다요", 2.0), ("v0-2", "라마바요", 2.0)])

    def fake_call(prompt, schema):
        return None

    seq = ep._pick_slot_sequence(sm, call=fake_call)
    assert [s["seg_id"] for s in seq] == ["v0-1", "v0-2"]


def test_pick_slot_sequence_groups_by_sentence():
    """_pick_slot_sequence 결과도 _pick_timeline과 같은 문장 단위 그룹으로 묶여야 한다."""
    sm = _sm([("v0-1", "가나다요", 2.0), ("v0-2", "라마바요", 2.0),
              ("v1-1", "사아자요", 2.0)])

    def fake_call(prompt, schema):
        return {"order": ["v0-1", "v1-1", "v0-2"]}

    groups = ep._pick_slot_groups(sm, call=fake_call)
    ids = [[s["seg_id"] for s in g] for g in groups]
    assert ids == [["v0-1"], ["v1-1"], ["v0-2"]]   # 각자 "요"로 끝나는 문장 → 세트 하나씩


def test_ends_sentence_uses_korean_endings():
    assert ep._ends_sentence("잔소리 들었는데 설치해놨더라고요")
    assert ep._ends_sentence("확 줄어든 거 있죠?")
    assert not ep._ends_sentence("이게 방탄아크릴 소재라")
    assert not ep._ends_sentence("")


def test_set_breaks_at_sentence_end_not_by_time():
    """한 세트 = 원본 문장 하나가 시작해서 끝나는 장면까지."""
    sm = _sm([("v-0", "요리할 때마다 기름이", 1.5), ("v-1", "튀어서 힘들었거든요", 1.5),
              ("v-2", "이걸 세웠더니", 1.5), ("v-3", "싹 막아주네요", 1.5)])
    g = ep._pick_timeline(sm, 30)
    assert len(g) == 2
    assert [s["seg_id"] for s in g[0]] == ["v-0", "v-1"]
    assert [s["seg_id"] for s in g[1]] == ["v-2", "v-3"]


def test_short_segment_does_not_become_its_own_set():
    sm = _sm([("v-0", "네요", 0.3), ("v-1", "이렇게 하니까 되더라고요", 2.0)])
    g = ep._pick_timeline(sm, 30)
    assert len(g) == 1


def test_prompt_shows_original_line_and_budget():
    sm = _sm([("v-0", "기름이 튀어서 힘들었거든요", 2.0)])
    txt = ep._rewrite_block(ep._pick_timeline(sm, 30))
    assert "원본이 한 말: 기름이 튀어서 힘들었거든요" in txt
    assert "자 이내" in txt
    assert "그대로 베끼지 마라" in txt


def test_assign_timeline_puts_screens_in_source_order():
    """말과 화면이 어긋날 수 없다 — 순서가 곧 원본 순서다."""
    sm = _sm([("v-0", "가나다라마바사요", 2.0), ("v-1", "아자차카타파하요", 2.0)])
    g = ep._pick_timeline(sm, 30)
    beats = [{"narration": "첫줄", "primary": {"seg_id": "v-1"}, "alternates": []},
             {"narration": "둘째줄", "primary": {"seg_id": "v-0"}, "alternates": []}]
    ep._assign_timeline(beats, g)
    assert beats[0]["primary"]["seg_id"] == "v-0"
    assert beats[1]["primary"]["seg_id"] == "v-1"


def test_beat_count_mismatch_is_safe():
    sm = _sm([("v-0", "가나다요", 2.0), ("v-1", "라마바요", 2.0), ("v-2", "사아자요", 2.0)])
    g = ep._pick_timeline(sm, 30)
    beats = [{"narration": "한 줄뿐", "primary": {"seg_id": "v-2"}, "alternates": []}]
    ep._assign_timeline(beats, g)
    assert beats[0]["primary"]["seg_id"] == "v-0"      # 앞에서부터 순서대로


def test_source_order_is_preserved_within_a_source():
    """소스 안에서는 원본 시간순 그대로 — CTA 화면이 앞으로 튈 수 없다."""
    sm = _sm([("v-0", "가나다요", 2.0), ("v-1", "라마바요", 2.0), ("v-2", "사아자요", 2.0)])
    ids = [s["seg_id"] for g in ep._pick_timeline(sm, 30) for s in g]
    assert ids == ["v-0", "v-1", "v-2"]


def test_trailing_ending_shots_of_non_final_source_are_dropped():
    """A를 다 쓰고 B를 붙이면 A의 마무리 화면이 한가운데 온다 → 꼬리의 완성컷은 잘라낸다."""
    sm = _sm([("a-0", "가나다요", 2.0), ("a-1", "라마바요", 2.0), ("a-2", "완성이요", 2.0),
              ("b-0", "사아자요", 2.0)])
    sm["a-2"]["shot_role"] = "완성"
    ids = [s["seg_id"] for g in ep._pick_timeline(sm, 30) for s in g]
    assert "a-2" not in ids and "b-0" in ids


def test_final_source_keeps_its_ending_shot():
    """마지막 소스의 완성컷은 남긴다 — 마무리는 끝에서 나와야 한다."""
    sm = _sm([("a-0", "가나다요", 2.0), ("a-1", "완성이요", 2.0)])
    sm["a-1"]["shot_role"] = "완성"
    ids = [s["seg_id"] for g in ep._pick_timeline(sm, 30) for s in g]
    assert "a-1" in ids


def test_offtopic_line_is_flagged():
    """그 자리의 결과 한 낱말도 안 겹치면 딴소리로 표시한다(fit↓·forced)."""
    sm = _sm([("v-0", "기름이 사방으로 튀어서 힘들었거든요", 2.0)])
    g = ep._pick_timeline(sm, 30)
    beats = [{"narration": "강아지 산책 정말 즐거워요", "fit": 5,
              "primary": {"seg_id": "v-0"}, "alternates": []}]
    ep._assign_timeline(beats, g)
    assert beats[0].get("offtopic") and beats[0]["fit"] <= 2 and beats[0]["forced"]


def test_reworded_line_is_not_flagged():
    """표현을 바꿔 쓰라고 했으니 많이 겹칠 필요는 없다 — 결만 이어지면 통과."""
    sm = _sm([("v-0", "기름이 사방으로 튀어서 힘들었거든요", 2.0)])
    g = ep._pick_timeline(sm, 30)
    beats = [{"narration": "요리할 때마다 기름 때문에 스트레스였죠", "fit": 5,
              "primary": {"seg_id": "v-0"}, "alternates": []}]
    ep._assign_timeline(beats, g)
    assert not beats[0].get("offtopic")


def test_reassign_is_idempotent_and_restores_order():
    """핑퐁 후처리가 화면을 뒤섞어도 마지막에 다시 걸면 원본 순서로 돌아온다(멱등).

    실측(job e288f2f0c387): grounding 직후에만 걸었더니 order_by_backbone·dedup_*·
    swap_hook_cta가 화면을 다시 섞어 한 비트에 s0-1·s1-7·s1-13이 뒤엉켰다.
    """
    sm = _sm([("v-0", "가나다요", 2.0), ("v-1", "라마바요", 2.0), ("v-2", "사아자요", 2.0)])
    g = ep._pick_timeline(sm, 30)
    beats = [{"narration": "첫줄", "primary": {"seg_id": "v-0"}, "alternates": []},
             {"narration": "둘째줄", "primary": {"seg_id": "v-1"}, "alternates": []},
             {"narration": "셋째줄", "primary": {"seg_id": "v-2"}, "alternates": []}]
    ep._assign_timeline(beats, g)
    first = [b["primary"]["seg_id"] for b in beats]
    # 후처리가 화면을 뒤섞은 상황을 흉내
    beats[0]["primary"], beats[2]["primary"] = beats[2]["primary"], beats[0]["primary"]
    ep._assign_timeline(beats, g)
    assert [b["primary"]["seg_id"] for b in beats] == first


def test_rewrite_mix_runs_even_when_backbone_is_on():
    """★라이브는 backbone_base_enabled=1이다(2026-07-31 서버 실조회).

    처음엔 backbone_base가 꺼진 분기에만 넣어서 라이브에서 리라이트 믹스가 아예 안 돌았다
    (실측 job 52f64c62b3ef: 훅에 s1-13·s1-4·s1-14가 뒤엉키고 s0-5가 두 비트에 중복).
    """
    seen = {}

    def _cap(prompt, schema):
        seen["p"] = prompt
        return {"candidates": [{"hook": "h", "beats": [
            {"role": "훅", "narration": "새 문장", "seg_ids": ["v-0"], "fit": 5}]}]}

    sources = [{"video_id": "v", "full_text": "본문", "segments": [
        {"seg_id": f"v-{i}", "start": i * 2, "end": i * 2 + 2, "text": "기름이 튀었거든요",
         "scene_desc": "주방", "change": "기름이 튄다", "shot_role": "사용중"} for i in range(5)]}]
    ep.build_scene_first_plan(sources, "ref", 20, n_candidates=1, call=_cap,
                              backbone_base=True)
    assert "원본이 하던 말을 우리 말로 바꿔 쓴다" in seen["p"]


def test_build_scene_first_plan_uses_gemini_slot_order_with_no_duplicate_screens():
    """build_scene_first_plan이 _pick_timeline이 아니라 _pick_slot_groups를 쓰는지 확인한다
    (Task5: 화면 순서를 소스순서+시간순 강제가 아니라 Gemini 판단으로 정한다).

    fake_call이 스키마로 분기한다 — order 스키마(_SLOT_SEQ_SCHEMA)로 물으면 두 소스를
    교차하는 순서(order 응답)를, 대본/후보 스키마로 물으면 후보 candidates 응답을 준다.
    _pick_timeline이었다면 소스 a 전부 → 소스 b 전부 순서로 강제됐을 것이나, 여기서는
    order 응답이 b-0을 a-1보다 앞에 오도록 일부러 교차시켜, 실제로 그 순서가 tl_groups에
    반영됐는지(=_pick_timeline이 아니라 _pick_slot_groups가 쓰였는지)를 간접 확인한다.

    핵심 검증은 사장님이 실측한 화면중복 버그의 재발 방지: 최종 plan['beats']의
    primary.seg_id에 중복이 없어야 한다.
    """
    calls = {"order": 0, "script": 0}

    def fake_call(prompt, schema):
        if schema.get("required") == ["order"]:
            calls["order"] += 1
            # 소스를 교차하는 순서(단순 a전부→b전부가 아님) — 실제로 반영되는지 확인용.
            return {"order": ["b-0", "a-0", "a-1", "b-1"]}
        calls["script"] += 1
        return {"candidates": [{"hook": "h", "beats": [
            {"role": "훅", "narration": "첫 줄", "seg_ids": ["a-0"], "fit": 5},
            {"role": "스토리", "narration": "둘째 줄", "seg_ids": ["a-0"], "fit": 5},
            {"role": "CTA", "narration": "셋째 줄", "seg_ids": ["a-0"], "fit": 5},
        ]}]}

    sources = [
        {"video_id": "a", "full_text": "본문A", "segments": [
            {"seg_id": "a-0", "start": 0, "end": 2, "text": "가나다요",
             "scene_desc": "주방A1", "change": "가나다", "shot_role": "사용중"},
            {"seg_id": "a-1", "start": 2, "end": 4, "text": "라마바요",
             "scene_desc": "주방A2", "change": "라마바", "shot_role": "사용중"},
        ]},
        {"video_id": "b", "full_text": "본문B", "segments": [
            {"seg_id": "b-0", "start": 0, "end": 2, "text": "사아자요",
             "scene_desc": "주방B1", "change": "사아자", "shot_role": "사용중"},
            {"seg_id": "b-1", "start": 2, "end": 4, "text": "차카타요",
             "scene_desc": "주방B2", "change": "차카타", "shot_role": "사용중"},
        ]},
    ]

    result = ep.build_scene_first_plan(sources, "ref", 8, n_candidates=1, call=fake_call)

    assert calls["order"] >= 1     # _pick_slot_groups가 실제로 _call을 order 스키마로 불렀다
    plan = result["candidates"][0]["plan"]
    seg_ids = [b["primary"]["seg_id"] for b in plan["beats"]]
    assert len(seg_ids) == len(set(seg_ids))          # 핵심: 화면 중복 없음
    assert set(seg_ids) <= {"a-0", "a-1", "b-0", "b-1"}


def test_clip_matching_the_words_comes_first():
    """말에 맞는 컷을 비트 안에서 앞으로 올린다(사장님: 태깅이 맞으면 가져오면 되잖아)."""
    sm = _sm([("v-0", "", 2.0), ("v-1", "", 2.0)])
    sm["v-0"]["change"] = "가림막을 벽에 설치한다"
    sm["v-1"]["change"] = "물티슈로 표면을 닦아낸다"
    got = ep._order_clips_by_words("물티슈로 쓱 닦아도 끝이에요",
                                   [sm["v-0"], sm["v-1"]])
    assert got[0]["seg_id"] == "v-1"


def test_clip_order_kept_when_nothing_matches():
    sm = _sm([("v-0", "", 2.0), ("v-1", "", 2.0)])
    got = ep._order_clips_by_words("전혀 다른 이야기", [sm["v-0"], sm["v-1"]])
    assert [s["seg_id"] for s in got] == ["v-0", "v-1"]


def test_later_source_intro_problem_shots_are_dropped():
    """두 번째 소스의 도입부(문제·before=더러운 상태)가 후반에 끼면 안 된다."""
    sm = _sm([("a-0", "가나다요", 2.0), ("a-1", "라마바요", 2.0),
              ("b-0", "사아자요", 2.0), ("b-1", "차카타요", 2.0)])
    sm["b-0"]["shot_role"] = "문제"
    ids = [s["seg_id"] for g in ep._pick_timeline(sm, 30) for s in g]
    assert "b-0" not in ids and "b-1" in ids


def test_first_source_keeps_its_intro():
    sm = _sm([("a-0", "가나다요", 2.0), ("a-1", "라마바요", 2.0)])
    sm["a-0"]["shot_role"] = "문제"
    ids = [s["seg_id"] for g in ep._pick_timeline(sm, 30) for s in g]
    assert "a-0" in ids


def test_rewrite_mix_does_not_prepend_hook_again():
    """★후킹 중복 차단(2026-07-31 사장님). 리라이트 믹스는 첫 세트가 이미 훅 자리라
    hook 필드를 덧붙이면 같은 말이 두 번 나온다(실측 B안: '카페에 두면 다들 어디서
    샀냐고 물어봐요' 뒤에 같은 문장이 그대로 이어짐)."""
    sm = _sm([("v-0", "카페에 두면 다들 어디서 샀냐고 물어봐요", 2.0)])
    cand = {"hook": "이거 카페에 두면 다들 어디서 샀냐고 물어봐요",
            "beats": [{"role": "훅", "narration": "다들 어디서 샀냐고 물어보더라고요",
                       "seg_ids": ["v-0"], "fit": 5}]}
    plan = ep._ground_candidate(cand, sm, lead_hook=False)
    assert plan["beats"][0]["narration"] == "다들 어디서 샀냐고 물어보더라고요"


def test_legacy_path_still_leads_with_hook():
    sm = _sm([("v-0", "본문", 2.0)])
    cand = {"hook": "이거 진짜 물건이에요",
            "beats": [{"role": "훅", "narration": "그래서 써봤는데요",
                       "seg_ids": ["v-0"], "fit": 5}]}
    plan = ep._ground_candidate(cand, sm, lead_hook=True)
    assert plan["beats"][0]["narration"].startswith("이거 진짜 물건이에요")


def test_prompt_forbids_repeating_the_hook():
    sm = _sm([("v-0", "기름이 튀었거든요", 2.0)])
    txt = ep._rewrite_block(ep._pick_timeline(sm, 30))
    assert "한 문장으로" in txt and "두 번 말하지 마라" in txt


def test_empty_inventory_is_safe():
    assert ep._pick_timeline({}, 30) == []
    assert ep._rewrite_block([]) == ""


def test_assign_timeline_called_once_never_duplicates():
    """_assign_timeline이 grounding 직후 딱 한 번만 불리면(재호출 없음), n==len(groups)가
    항상 성립하므로 화면 중복이 구조적으로 생길 수 없다 — split이 비트를 늘리지 않는지 검증.

    group idx 2(v-2, v-3)는 v-2 텍스트가 문장을 안 끝내(_ends_sentence False) 다음 컷과
    한 세트로 묶인다 — 이래야 _assign_timeline이 그 비트에 real alternates(v-3)를 채워
    (구)_split_long_beats의 분할 조건("컷이 2개 이상")을 실제로 태운다."""
    sm = _sm([("v-0", "가나다요", 2.0), ("v-1", "라마바요", 2.0),
              ("v-2", "사이참깨", 1.5), ("v-3", "사아자요", 2.0),
              ("v-4", "차카타요", 2.0)])
    g = ep._pick_timeline(sm, 30)
    assert len(g) == 4
    long_narr = ("이 냄비는 정말 놀라울 정도로 열전도가 빠르고 코팅이 오래 가서 만족스럽습니다. "
                 "게다가 손잡이까지 안 뜨거워서 요리할 때 진짜 편하더라고요.")
    beats = [
        {"narration": "첫줄", "beat_idx": 0, "primary": {"seg_id": "v-0"}, "alternates": []},
        {"narration": "둘째줄", "beat_idx": 1, "primary": {"seg_id": "v-1"}, "alternates": []},
        {"narration": long_narr, "beat_idx": 2, "primary": {"seg_id": "v-2"},
         "alternates": [{"seg_id": "v-2b"}]},
        {"narration": "넷째줄", "beat_idx": 3, "primary": {"seg_id": "v-4"}, "alternates": []},
    ]
    ep._assign_timeline(beats, g)
    beats = ep._fix_beat_structure(beats)   # split이 더는 개수를 안 늘려야 한다
    assert len(beats) == 4                  # 불변식: 그룹 개수와 항상 같다
    seg_ids = [b["primary"]["seg_id"] for b in beats]
    assert len(seg_ids) == len(set(seg_ids))
    assert ep._assign_timeline([], []) == []


def test_assign_timeline_never_duplicates_even_when_counts_mismatch():
    """n(beats) != len(groups) 여도, 안 쓴 seg가 남아있는 한 같은 seg_id가 두 비트에
    배정되면 안 된다.

    실측(job 8226822c5b09, ping_pong=True 라이브 설정): n_beats=6, n_groups=5일 때
    정수분배 lo/hi가 겹쳐 비트 0과 1이 둘 다 groups[0]을 받고, 그 안의 같은 첫 클립을
    골라 화면이 중복됐다. groups(세트) 하나에 세그먼트가 2개 있어(v-0, v-0b) 6개 비트에
    돌아갈 안 쓴 화면이 총 6개 있는 상황을 재현한다 — 이 경우 중복 없이 다 배정돼야 한다.
    """
    sm = _sm([("v-0", "가나다요", 1.0), ("v-0b", "라마바요", 1.0),
              ("v-1", "사아자요", 2.0), ("v-2", "차카타요", 2.0),
              ("v-3", "파하가요", 2.0), ("v-4", "나다라요", 2.0)])
    g = [[sm["v-0"], sm["v-0b"]], [sm["v-1"]], [sm["v-2"]], [sm["v-3"]], [sm["v-4"]]]
    assert len(g) == 5   # 세트 5개, 세그먼트는 총 6개
    beats = [{"narration": f"문장{i}", "beat_idx": i, "primary": {}, "alternates": []}
             for i in range(6)]   # 비트 6개 — 일부러 그룹(5)보다 많게
    ep._assign_timeline(beats, g)
    seg_ids = [b["primary"]["seg_id"] for b in beats]
    assert len(seg_ids) == len(set(seg_ids)), f"duplicate seg_ids: {seg_ids}"
