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


def test_empty_inventory_is_safe():
    assert ep._pick_timeline({}, 30) == []
    assert ep._rewrite_block([]) == ""
    assert ep._assign_timeline([], []) == []
