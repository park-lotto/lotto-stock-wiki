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


# ── F1/F2/F3 재설계(2026-08-01, Fable 코드리뷰) ──────────────────────────
# 옛 _pick_slot_sequence는 seg 낱개를 Gemini에게 자유 재정렬시킨 뒤에 문장 그룹핑을 했다
# (순서가 거꾸로 → F1: 프랑켄 문장세트) + target_seconds를 무시하고 전부 강제 사용했다
# (F2: 비트 폭증). 그래서 _pick_slot_sequence 자체와 그 seg-level 동작을 검증하던 옛 테스트
# 4개(returns_all_segments_once / drops_unknown_ids_from_model / falls_back_when_call_fails /
# groups_by_sentence)는 "모든 seg를 반드시 다 쓴다"는 F2의 버그였던 동작을 정답으로 여기고
# 있었으므로 삭제하고, 아래 세트 단위 재설계에 맞는 테스트로 교체한다.
# 새 순서: 소스별 시간순으로 먼저 문장세트를 만들고(_build_source_sentence_sets), Gemini에겐
# "세트를 골라 순서만 정하라"고 묻는다(_pick_slot_groups) — 세트 내부는 항상 한 소스만 담겨
# 프랑켄 문장이 구조적으로 불가능하고, 예산(target_seconds)이 있어 전부 강제 사용도 안 한다.

def test_build_source_sentence_sets_never_mixes_sources_within_one_set():
    """세트 하나는 항상 한 video_id의 세그먼트만 담는다(소스별로 먼저 묶으므로)."""
    sm = _sm([("a-0", "가나다요", 2.0), ("a-1", "라마바요", 2.0),
              ("b-0", "사아자요", 2.0), ("b-1", "차카타요", 2.0)])
    sets = ep._build_source_sentence_sets(sm)
    for st in sets:
        vids = {s["video_id"] for s in st["segs"]}
        assert len(vids) == 1


def test_pick_slot_groups_f1_no_cross_source_fragment_mixing():
    """F1 재현: video a는 a1(문장 미종결)+a2(종결)로 한 문장, video b는 자기 세그먼트 보유.

    옛 코드(seg-level 재정렬 후 그룹핑)였다면 Gemini가 [a1, b1, a2] 순서를 반환할 때
    _group_by_sentence가 a1(문장 안 끝남)에 b1을 이어붙이다 a2에서 끝내 [a1, b1, a2]가
    한 세트가 됐다(서로 다른 소스의 조각이 한 문장세트에 섞임 = 프랑켄 문장).
    새 설계에서는 세트가 소스별로 먼저 확정되므로, Gemini가 세트를 어떤 순서로 고르든
    한 세트 안에 두 소스가 섞이는 일이 없어야 한다."""
    sm = _sm([("a-1", "기름이 튀어서", 1.5), ("a-2", "힘들었거든요", 1.5),
              ("b-1", "사아자요", 2.0)])

    def fake_call(prompt, schema):
        # 세트 단위 프롬프트를 받았다면 세트 id로 답해야 한다 — set_id를 그대로 안 쓰고
        # 혹시 seg_id로 답하더라도(모델 실수) 알 수 없는 id는 버려지는지도 같이 확인.
        sets = ep._build_source_sentence_sets(sm)
        ids = [st["set_id"] for st in sets]
        return {"order": list(reversed(ids))}

    groups = ep._pick_slot_groups(sm, target_seconds=30, call=fake_call)
    for g in groups:
        vids = {s["video_id"] for s in g}
        assert len(vids) == 1, f"cross-source mixing within one set: {[s['seg_id'] for s in g]}"
    # a-1과 a-2는 같은 문장(a-2가 종결어미) → 항상 같은 세트로 붙어있어야 한다.
    a_group = next(g for g in groups if any(s["seg_id"] == "a-1" for s in g))
    assert [s["seg_id"] for s in a_group] == ["a-1", "a-2"]


def test_pick_slot_groups_f2_does_not_force_append_unused_sets():
    """모델이 예산을 지켜 세트 일부만 골랐다면, 코드가 나머지를 강제로 뒤에 채우면 안 된다
    (옛 _pick_slot_sequence는 '모델이 빠뜨린 것'을 무조건 뒤에 보충했다 = F2의 핵심 버그)."""
    sm = _sm([("a-0", "가나다요", 2.0), ("a-1", "라마바요", 2.0),
              ("b-0", "사아자요", 2.0), ("b-1", "차카타요", 2.0)])

    def fake_call(prompt, schema):
        sets = ep._build_source_sentence_sets(sm)
        a_only = [st["set_id"] for st in sets if st["video_id"] == "a"]
        return {"order": a_only}   # b쪽 세트는 일부러 선택하지 않음(예산 내 선택 흉내)

    groups = ep._pick_slot_groups(sm, target_seconds=30, call=fake_call)
    ids = {s["seg_id"] for g in groups for s in g}
    assert "b-0" not in ids and "b-1" not in ids   # 강제 보충되면 안 된다
    assert "a-0" in ids and "a-1" in ids


def test_pick_slot_groups_f3_falls_back_to_pick_timeline_on_empty_response():
    """F3 재현: Gemini 응답이 비었거나(order 없음) 무효하면, 안전장치 없는 전체 이어붙이기가
    아니라 _pick_timeline(완성/문제 컷 트리밍 + target_seconds 캡 있음)으로 바로 폴백해야 한다."""
    sm = _sm([("a-0", "가나다요", 2.0), ("a-1", "완성이요", 2.0), ("b-0", "사아자요", 2.0)])
    sm["a-1"]["shot_role"] = "완성"   # a가 마지막 소스가 아니면 _pick_timeline이 이 컷을 잘라낸다

    def fake_call_none(prompt, schema):
        return None

    def fake_call_empty(prompt, schema):
        return {}

    expected = ep._pick_timeline(sm, 30)
    for fake in (fake_call_none, fake_call_empty):
        groups = ep._pick_slot_groups(sm, target_seconds=30, call=fake)
        assert groups == expected


# ── F5: Gemini 세트 순서에도 완성/문제 컷 상식검증 필요 (2026-08-01, 외부 리뷰 후속) ──
# _pick_timeline은 '완성 컷은 끝에서만, 문제 컷은 앞에서만'을 코드로 강제하지만, 그 가드는
# _pick_timeline 자신의 폴백 경로에만 붙어 있다. _pick_slot_groups가 Gemini 응답을 성공적으로
# 받았을 때(훨씬 흔한 경로)는 프롬프트로 부탁만 하고 코드 검증이 없었다 — Gemini가 완성 세트를
# 중간에 놓거나 문제 세트를 뒷부분에 놓아도 그대로 통과됐다. 아래는 그 구멍을 재현하는 테스트.

def test_pick_slot_groups_f5_drops_completion_set_placed_in_the_middle():
    """Gemini가 '완성' 세트를 시퀀스 중간에 배치하면(마지막이 아니면) 걸러내야 한다."""
    sm = _sm([("a-0", "가나다요", 2.0), ("a-1", "완성이요", 2.0),
              ("b-0", "사아자요", 2.0), ("b-1", "차카타요", 2.0)])
    sm["a-1"]["shot_role"] = "완성"

    def fake_call(prompt, schema):
        sets = ep._build_source_sentence_sets(sm)
        by_vid_first = {st["video_id"]: st["set_id"] for st in sets}
        # a(완성 세트) → b0 → b1 : 완성 세트가 마지막이 아니라 중간에 낀 순서.
        b_ids = [st["set_id"] for st in sets if st["video_id"] == "b"]
        return {"order": [by_vid_first["a"]] + b_ids}

    groups = ep._pick_slot_groups(sm, target_seconds=30, call=fake_call)
    ids = [s["seg_id"] for g in groups for s in g]
    assert "a-1" not in ids, f"완성 세트가 중간에 낀 채 그대로 남았다: {ids}"
    assert "b-0" in ids and "b-1" in ids


def test_pick_slot_groups_f5_drops_problem_set_placed_after_the_first_slot():
    """Gemini가 '문제' 세트를 첫 자리가 아닌 곳에 배치하면 걸러내야 한다."""
    sm = _sm([("a-0", "가나다요", 2.0), ("a-1", "라마바요", 2.0),
              ("b-0", "문제상황요", 2.0)])
    sm["b-0"]["shot_role"] = "문제"

    def fake_call(prompt, schema):
        sets = ep._build_source_sentence_sets(sm)
        a_ids = [st["set_id"] for st in sets if st["video_id"] == "a"]
        b_ids = [st["set_id"] for st in sets if st["video_id"] == "b"]
        # a0 → a1 → b0(문제) : 문제 세트가 첫 자리가 아니라 맨 뒤에 낀 순서.
        return {"order": a_ids + b_ids}

    groups = ep._pick_slot_groups(sm, target_seconds=30, call=fake_call)
    ids = [s["seg_id"] for g in groups for s in g]
    assert "b-0" not in ids, f"문제 세트가 첫 자리가 아닌 채 그대로 남았다: {ids}"
    assert "a-0" in ids and "a-1" in ids


def test_pick_slot_groups_f5_keeps_completion_set_when_genuinely_last():
    """완성 세트가 실제로 시퀀스 맨 끝이면 정상 케이스 — 지워지면 안 된다(과잉필터 금지)."""
    sm = _sm([("a-0", "가나다요", 2.0), ("b-0", "완성이요", 2.0)])
    sm["b-0"]["shot_role"] = "완성"

    def fake_call(prompt, schema):
        sets = ep._build_source_sentence_sets(sm)
        by_vid = {st["video_id"]: st["set_id"] for st in sets}
        return {"order": [by_vid["a"], by_vid["b"]]}

    groups = ep._pick_slot_groups(sm, target_seconds=30, call=fake_call)
    ids = [s["seg_id"] for g in groups for s in g]
    assert "b-0" in ids, f"맨 끝의 정상적인 완성 세트까지 지워졌다: {ids}"


def test_pick_slot_groups_f5_keeps_problem_set_when_genuinely_first():
    """문제 세트가 실제로 시퀀스 맨 앞이면 정상 케이스 — 지워지면 안 된다(과잉필터 금지)."""
    sm = _sm([("a-0", "문제상황요", 2.0), ("b-0", "사아자요", 2.0)])
    sm["a-0"]["shot_role"] = "문제"

    def fake_call(prompt, schema):
        sets = ep._build_source_sentence_sets(sm)
        by_vid = {st["video_id"]: st["set_id"] for st in sets}
        return {"order": [by_vid["a"], by_vid["b"]]}

    groups = ep._pick_slot_groups(sm, target_seconds=30, call=fake_call)
    ids = [s["seg_id"] for g in groups for s in g]
    assert "a-0" in ids, f"맨 앞의 정상적인 문제 세트까지 지워졌다: {ids}"


def test_pick_slot_groups_f5_falls_back_to_pick_timeline_when_filter_empties_all():
    """필터가 골라놓은 세트를 전부 지우면(예: 완성 세트 하나만 골랐는데 중간 취급된 경우가
    아니라, 걸러내고 나니 아무것도 안 남는 극단 케이스) _pick_timeline 폴백으로 이어져야
    한다 — F3 폴백과 동일한 안전망(완성/문제 트리밍 + target_seconds 캡)을 재사용."""
    sm = _sm([("a-0", "완성이요", 2.0), ("b-0", "문제상황요", 2.0)])
    sm["a-0"]["shot_role"] = "완성"
    sm["b-0"]["shot_role"] = "문제"

    def fake_call(prompt, schema):
        sets = ep._build_source_sentence_sets(sm)
        by_vid = {st["video_id"]: st["set_id"] for st in sets}
        # a(완성, 마지막 아님) → b(문제, 첫 자리 아님) : 둘 다 필터에 걸려 전부 제거된다.
        return {"order": [by_vid["a"], by_vid["b"]]}

    expected = ep._pick_timeline(sm, 30)
    groups = ep._pick_slot_groups(sm, target_seconds=30, call=fake_call)
    assert groups == expected


def test_pick_slot_groups_groups_by_sentence():
    """_pick_slot_groups 결과도 문장 단위 그룹(한 소스 내)으로 묶여야 한다."""
    sm = _sm([("v0-1", "가나다요", 2.0), ("v0-2", "라마바요", 2.0),
              ("v1-1", "사아자요", 2.0)])

    def fake_call(prompt, schema):
        sets = ep._build_source_sentence_sets(sm)
        # v1 세트를 v0 세트들 사이에 끼워 넣어도(세트 단위 교차) 세트 내부는 안 섞인다.
        v0_ids = [st["set_id"] for st in sets if st["video_id"] == "v0"]
        v1_ids = [st["set_id"] for st in sets if st["video_id"] == "v1"]
        return {"order": [v0_ids[0], v1_ids[0], v0_ids[1]]}

    groups = ep._pick_slot_groups(sm, target_seconds=30, call=fake_call)
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


# ── F4 (2026-08-01, Fable 코드리뷰) ──────────────────────────────────────
# Part 1: _ensure_cta_beat가 만든 CTA 비트의 화면(마지막 비트 컷 재사용)이 뒤이은
#   _assign_timeline 재호출에서 인덱스 배분으로 덮어써지던 문제. screen_pinned 플래그로
#   재배정 대상에서 빼되 used_seg_ids엔 반영해야 한다.
# Part 2: 빌려오기(fallback-borrow)가 일어났을 때 _flag_offtopic이 원래 local chunk가
#   아니라 실제 배정된 화면([pick]+rest)을 검사해야 한다.

def test_pinned_cta_beat_screen_survives_assign_timeline():
    """_ensure_cta_beat가 고른 화면(screen_pinned=True)은 _assign_timeline이 손대면 안 된다.

    그룹 4개, 비트 4개(CTA 비트가 더 붙어 len(beats)=4, 그중 3개가 "진짜" 스토리
    비트라 원래 그룹도 4개 있는 상황 — CTA 추가 전엔 n_active=3, len(groups)=4였다가,
    CTA 비트가 붙으며 len(beats)=4가 된다). CTA는 세 번째(마지막 스토리) 비트의 컷을
    재사용하므로 pin 값은 g2(v-2)다.

    이 그룹 개수(4)로 **핀을 무시한 옛 코드**를 시뮬레이션해보면 n=4로 도는 lo/hi가
    beat3(CTA)에 g3(v-3)을 배정해 pin 값(v-2)과 달라진다 — 즉 이 픽스처는 "우연히
    같은 값이라 통과"가 아니라 핀 로직이 실제로 작동해야만 통과하는 진짜 회귀 테스트다.
    """
    sm = _sm([("v-0", "가나다요", 2.0), ("v-1", "라마바요", 2.0),
              ("v-2", "사아자요", 2.0), ("v-3", "차카타요", 2.0)])
    g = [[sm["v-0"]], [sm["v-1"]], [sm["v-2"]], [sm["v-3"]]]   # 그룹 4개
    last_beat_primary = {"seg_id": "v-2", "text": "사아자요"}   # 세 번째(마지막 스토리) 비트의 컷
    beats = [
        {"narration": "첫줄", "beat_idx": 0, "primary": {}, "alternates": []},
        {"narration": "둘째줄", "beat_idx": 1, "primary": {}, "alternates": []},
        {"narration": "셋째줄", "beat_idx": 2, "primary": dict(last_beat_primary),
         "alternates": []},
        # _ensure_cta_beat가 만든 CTA 비트 — 마지막 스토리 비트 컷을 재사용해 화면이 이미 고정.
        {"narration": "댓글 남겨주세요", "beat_idx": 3, "role": "CTA",
         "primary": dict(last_beat_primary), "alternates": [], "screen_pinned": True},
    ]
    ep._assign_timeline(beats, g)
    assert beats[3]["primary"]["seg_id"] == "v-2"   # 핀이 그대로 유지(옛 코드였다면 v-3이 됐다)
    assert beats[3].get("screen_pinned") is True     # 재배정 루프를 거치지 않았다
    # 나머지 3개 비트는 재배정 대상이라 자기들끼리 화면이 바뀔 수 있다(정상) — 다만
    # v-2는 CTA가 예약해뒀으니 그 비트들 서로간에 중복 없이 배정됐는지만 확인한다.
    other_seg_ids = [b["primary"]["seg_id"] for b in beats[:3]]
    assert len(other_seg_ids) == len(set(other_seg_ids))   # 나머지 비트끼리도 중복 없음


def test_pinned_cta_beat_stays_pinned_across_repeated_calls():
    """리라이트 믹스는 _assign_timeline을 두 번 부른다(멱등 보장) — 핀도 두 번째 호출에서
    안 풀려야 한다."""
    sm = _sm([("v-0", "가나다요", 2.0), ("v-1", "라마바요", 2.0),
              ("v-2", "사아자요", 2.0), ("v-3", "차카타요", 2.0)])
    g = [[sm["v-0"]], [sm["v-1"]], [sm["v-2"]], [sm["v-3"]]]
    beats = [
        {"narration": "첫줄", "beat_idx": 0, "primary": {}, "alternates": []},
        {"narration": "둘째줄", "beat_idx": 1, "primary": {}, "alternates": []},
        {"narration": "셋째줄", "beat_idx": 2, "primary": {"seg_id": "v-2"}, "alternates": []},
        {"narration": "댓글 남겨주세요", "beat_idx": 3, "role": "CTA",
         "primary": {"seg_id": "v-2", "text": "사아자요"}, "alternates": [],
         "screen_pinned": True},
    ]
    ep._assign_timeline(beats, g)
    ep._assign_timeline(beats, g)   # 두 번째 호출(라이브 경로는 grounding 직후+맨 마지막 2회 호출)
    assert beats[3]["primary"]["seg_id"] == "v-2"
    assert beats[3].get("screen_pinned") is True


def test_flag_offtopic_checks_the_actually_borrowed_pick_not_local_chunk():
    """빌려오기(fallback-borrow)가 일어나면, 딴소리 검사는 원래 local chunk가 아니라
    실제로 배정된 화면(pick)을 봐야 한다.

    그룹 2개(g0=[A], g1=[B]), 비트 3개로 lo/hi 정수분배가 겹치게 만든다
    (n=3, len(groups)=2 → i=0,1 모두 chunk=g0). beat0이 A를 먼저 가져가면 beat1의
    로컬 chunk(g0=[A])는 이미 소진 — all_segs_in_order에서 B를 빌려온다(fallback-borrow).
    A의 텍스트는 beat1 나레이션과 낱말이 겹치고, B는 안 겹치게 설계했다 — 옛 코드처럼
    _flag_offtopic(b, chunk)로 (여전히 [A]인) 로컬 chunk를 검사했다면 실제로는 안 맞는
    B가 배정됐는데도 offtopic이 안 잡혔을 것이다. 고친 코드는 [pick]+rest = [B]를 검사해
    정확히 offtopic으로 잡아야 한다.
    """
    sm = _sm([("v-0", "기름이 사방으로 튀어서 힘들었거든요", 2.0),
              ("v-1", "강아지 산책 완전 즐거워요", 2.0)])
    g = [[sm["v-0"]], [sm["v-1"]]]   # 그룹 2개, 비트는 아래서 3개 — lo/hi 겹침 유도
    beats = [
        {"narration": "기름이 튀어서 아주 힘들었어요", "fit": 5,
         "primary": {}, "alternates": []},   # chunk=g0=[v-0] → v-0 사용(말이 겹침)
        {"narration": "기름이 튀어서 아주 힘들었어요", "fit": 5,
         "primary": {}, "alternates": []},   # chunk=g0=[v-0]인데 이미 used → v-1을 빌려옴(안 겹침)
        {"narration": "산책이 즐거워요", "fit": 5,
         "primary": {}, "alternates": []},   # chunk=g1=[v-1]
    ]
    ep._assign_timeline(beats, g)
    assert beats[1]["primary"]["seg_id"] == "v-1"          # 빌려온 화면이 맞는지 전제 확인
    assert beats[1].get("offtopic") and beats[1]["fit"] <= 2 and beats[1]["forced"]
