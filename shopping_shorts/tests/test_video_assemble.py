from shopping_shorts import video_assemble as va


def test_pick_segment_primary_covers_narration():
    # primary 구간 3초, tts 2.4초 → primary가 1배속으로 담을 수 있으므로 primary 선택
    beat = {"primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 3.0}, "alternates": []}
    ref = va._pick_segment(beat, tts_dur=2.4, source_video_paths={"A": "a.mp4"})
    assert ref["seg_id"] == "A-0"


def test_pick_segment_prefers_alternate_that_covers_when_primary_too_short():
    # primary 1초로 tts 2.4초를 못 담음 → 2.4초를 담을 수 있는 alternate(3초) 선택
    beat = {
        "primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 1.0},
        "alternates": [{"video_id": "B", "seg_id": "B-0", "start": 0.0, "end": 3.0}],
    }
    ref = va._pick_segment(beat, tts_dur=2.4, source_video_paths={"A": "a.mp4", "B": "b.mp4"})
    assert ref["seg_id"] == "B-0"


def test_pick_segment_picks_longest_when_none_cover():
    # 아무 후보도 tts를 못 담으면 가장 긴 후보 선택(부족분은 루프로 채움)
    beat = {
        "primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 1.0},
        "alternates": [{"video_id": "B", "seg_id": "B-0", "start": 0.0, "end": 2.0}],
    }
    ref = va._pick_segment(beat, tts_dur=5.0, source_video_paths={"A": "a.mp4", "B": "b.mp4"})
    assert ref["seg_id"] == "B-0"  # 2초 > 1초


def test_pick_segment_skips_missing_source():
    # primary 소스가 없으면 존재하는 alternate로
    beat = {
        "primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 5.0},
        "alternates": [{"video_id": "B", "seg_id": "B-0", "start": 0.0, "end": 3.0}],
    }
    ref = va._pick_segment(beat, tts_dur=2.0, source_video_paths={"B": "b.mp4"})
    assert ref["seg_id"] == "B-0"


# ── 자막 구절 분할 ──────────────────────────────────────────────

def test_caption_segments_empty():
    assert va._caption_segments("") == []
    assert va._caption_segments(None) == []
    assert va._caption_segments("   ") == []


def test_caption_segments_splits_into_short_phrases():
    # 어절 기준 짧은 구절. 각 구절은 공백 제외 글자수가 목표 근처(1줄), 줄바꿈 없음.
    segs = va._caption_segments("오이 사자마자 냉장고에 넣으셨나요?")
    assert len(segs) >= 2                       # 한 덩어리로 안 뭉침
    assert " ".join(segs) == "오이 사자마자 냉장고에 넣으셨나요?"  # 어절 순서·내용 보존
    for s in segs:
        assert "\n" not in s                    # 짧은 1줄
        assert len(s.replace(" ", "")) <= va._CAP_WRAP  # 화면 밖으로 안 나감


def test_caption_segments_irregular_lengths():
    # 어절 길이가 제각각이라 구절 길이도 불규칙(규칙적으로 안 잘림).
    segs = va._caption_segments("이 오이는 사자마자 바로 냉장고에 넣어야 신선하게 오래 먹어요")
    lengths = {len(s.replace(" ", "")) for s in segs}
    assert len(lengths) > 1                     # 전부 같은 길이가 아님


def test_caption_segments_long_single_word_wrapped():
    # 목표를 크게 넘는 초장문 단일 어절은 _CAP_WRAP로 방어 줄바꿈.
    long_word = "가" * (va._CAP_WRAP * 2 + 3)
    segs = va._caption_segments(long_word)
    assert all(len(s.replace("\n", "")) <= va._CAP_WRAP for s in segs)


def test_caption_segments_max_words_cap():
    # 아주 짧은 어절이 여러 개여도 한 구절이 _CAP_MAX_WORDS 어절을 넘지 않는다.
    # (레퍼런스 리듬: 1~3어절 단위로 빠르게 전환)
    segs = va._caption_segments("가 나 다 라 마 바 사 아")   # 1글자 어절 8개
    assert all(len(s.split()) <= va._CAP_MAX_WORDS for s in segs)
    assert " ".join(segs) == "가 나 다 라 마 바 사 아"        # 내용 보존


def test_caption_segments_ref_rhythm_2to3_words():
    # 레퍼런스 리듬: 2~3어절 단위(너무 잘게 쪼개지 않음). 어절 상한은 지킨다.
    segs = va._caption_segments("저도 오이를 냉장고에 넣어도 꼭 두 세개씩 물러서 버렸거든요")
    assert 3 <= len(segs) <= 5                               # 적당히 뭉침(잘게X)
    assert all(len(s.split()) <= va._CAP_MAX_WORDS for s in segs)


def test_caption_segments_no_dangling_modifier():
    # 관형어·부사로 구절이 끝나지 않는다("며칠 안"|"됐는데" 같은 어색한 끊김 방지).
    segs = va._caption_segments("분명 사온 지 며칠 안 됐는데 물러지고 곰팡이 펴서")
    for s in segs:
        assert s.split()[-1] not in va._CAP_NO_TAIL         # 매달리는 말로 안 끝남
    # "며칠 안 됐는데"가 한 덩어리로 붙었는지
    assert any("며칠 안" in s and "됐는데" in s for s in segs)


def test_caption_segments_han_modifier_stays_with_noun():
    # "한 스푼", "한 달" 등 관형사 "한"이 뒤 명사와 분리되지 않는다.
    segs = va._caption_segments("이것 한 스푼이면 아삭함이 한 달넘게 마법의 가루!")
    assert any("한 스푼이면" in s for s in segs)
    assert any("한 달넘게" in s for s in segs)


def test_caption_segments_breaks_after_sentence_end():
    # 문장부호(? .)로 끝난 뒤엔 문장 경계에서 끊는다(다음 문장이 앞에 안 붙음).
    segs = va._caption_segments("오이 사서 냉장고에 넣으셨나요? 그럼 지금 바로 버리셔야 합니다.")
    # 물음표로 끝나는 구절이 있고, 그 구절 뒤로 새 문장이 분리됨
    q_idx = [i for i, s in enumerate(segs) if s.endswith("?")]
    assert q_idx                                             # ?로 끝나는 구절 존재
    for i in q_idx:
        if i + 1 < len(segs):
            assert not segs[i].endswith("? 그럼")            # 다음 문장이 안 붙음


# ── 자막 시간 배분 ──────────────────────────────────────────────

def test_caption_durations_sum_not_exceed_dur():
    segs = va._caption_segments("오이 사자마자 냉장고에 넣으셨나요?")
    durs = va._caption_durations(segs, dur=6.0)
    assert len(durs) == len(segs)
    assert sum(durs) <= 6.0 + 1e-6              # 총합이 나레이션 길이를 안 넘음


def test_caption_durations_min_floor_applied():
    # 아주 짧은 구절이라도 최소 표시시간 하한을 받는다(시간 여유가 있을 때).
    segs = ["가", "매우매우긴구절이야여기"]
    durs = va._caption_durations(segs, dur=6.0)
    assert min(durs) >= va._CAP_MIN_DUR - 1e-6
    assert sum(durs) <= 6.0 + 1e-6


def test_caption_durations_equal_fallback_when_too_tight():
    # 하한들의 합이 dur를 넘으면 균등분할로 폴백(총합 = dur).
    segs = ["가", "나", "다", "라"]
    durs = va._caption_durations(segs, dur=1.0)   # 4 * 0.5 = 2.0 > 1.0
    assert sum(durs) == 1.0
    assert durs == [0.25, 0.25, 0.25, 0.25]
