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


def test_empty_inventory_is_safe():
    assert ep._pick_timeline({}, 30) == []
    assert ep._rewrite_block([]) == ""
    assert ep._assign_timeline([], []) == []
