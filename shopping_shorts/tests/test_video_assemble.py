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
    # 수식어(관형어·부사)가 구절 끝에 홀로 남지 않는다("며칠 안"|"됐는데" 방지).
    segs = va._caption_segments("분명 사온 지 며칠 안 됐는데 물러지고 곰팡이 펴서")
    for s in segs:
        assert s.split()[-1] not in va._CAP_HEAD            # 머리 단어로 안 끝남
    # "며칠 안 됐는데"가 한 덩어리로 붙었는지
    assert any("며칠 안" in s and "됐는데" in s for s in segs)


def test_caption_segments_modifier_leads_next_phrase():
    # 사용자 예시에서 뽑은 원리: 수식어(관형어·부사)는 앞 구절 꼬리에 남지 않고
    # 뒤 단어의 '머리'로 붙는다. 예시 배열들을 회귀 고정.
    cases = [
        ("여러분 오이 절대", ["여러분", "오이 절대"]),
        ("냉장고에 그냥 두지 마세요", ["냉장고에", "그냥 두지 마세요"]),
        ("버리기 일쑤였는데 이 방법은 진짜", ["버리기 일쑤였는데", "이 방법은 진짜"]),
        ("밭에서 딴듯한 식감이 그대로 살아있어요",
         ["밭에서 딴듯한 식감이", "그대로 살아있어요"]),
        ("남겨주시면 자세한 보관비법 바로 알려드릴게요",
         ["남겨주시면", "자세한 보관비법", "바로 알려드릴게요"]),
    ]
    for src, want in cases:
        assert va._caption_segments(src) == want, src


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


# ── 믹스/자막굽기 분리 (VMake 훅) ────────────────────────────────

import inspect


def test_render_mix_and_burn_captions_exist():
    assert callable(getattr(va, "_render_mix", None))
    assert callable(getattr(va, "_burn_captions", None))
    params = inspect.signature(va._render_mix).parameters
    assert "edit_plan" in params and "tts_paths" in params and "source_video_paths" in params


def test_burn_captions_signature():
    params = list(inspect.signature(va._burn_captions).parameters)
    assert params[0] == "in_video"
    assert "edit_plan" in params and "out_path" in params


# ── 반중복탐지 회피(2026-07-14) — 켄번즈 줌(훅·반전) + 기본 크롭줌(나머지) ──

def test_important_beat_indices_picks_hook_and_reversal_roles():
    beats = [
        {"beat_idx": 0, "role": "훅"},
        {"beat_idx": 1, "role": "페인포인트"},
        {"beat_idx": 2, "role": "반전"},
        {"beat_idx": 3, "role": "실용"},
        {"beat_idx": 4, "role": "CTA"},
    ]
    assert va._important_beat_indices(beats) == {0, 2}


def test_important_beat_indices_falls_back_to_first_beat_when_no_role():
    # produce.html 2단계(given_script 모드)는 role이 안 채워짐(edit_plan._SCRIPTED_PROMPT
    # 가 role을 요구하지 않음) — 그때는 첫 비트만 켄번즈 대상으로 폴백.
    beats = [{"beat_idx": 0, "role": ""}, {"beat_idx": 1, "role": ""}]
    assert va._important_beat_indices(beats) == {0}


def test_important_beat_indices_empty_beats():
    assert va._important_beat_indices([]) == set()


def test_base_zoom_vf_targets_output_resolution():
    vf = va._base_zoom_vf()
    assert f"crop={va._OUT_W}:{va._OUT_H}" in vf
    assert "scale=" in vf


def test_kenburns_vf_ramps_zoom_via_output_frame_number():
    # 'zoom+step' self-reference는 비디오 입력에서 상태가 안 이어지는 버그가 있어
    # (2026-07-14 로컬 ffmpeg 실측: 프레임 크기 89px→89px, 안 움직임) 출력 프레임
    # 번호 'on'을 직접 식에 넣는 방식으로 고쳤다 — 그 표현이 살아있는지 회귀 방지.
    vf = va._kenburns_vf(4.0, fps=30)
    assert "zoompan" in vf
    assert "*on" in vf          # 'on' 기반 — 'zoom+' 자기참조 방식으로 되돌아가면 실패
    assert "zoom+" not in vf
    assert f"s={va._OUT_W}x{va._OUT_H}" in vf


def test_kenburns_vf_handles_zero_duration_without_division_error():
    vf = va._kenburns_vf(0.0)
    assert "zoompan" in vf


# ── 단어별 강조(highlight_rules) — 세그먼트 drawtext ──────────

def test_segmented_drawtext_no_rules_single_segment(tmp_path):
    """규칙 없으면 세그먼트 1개(기존 _fixed_drawtext와 동일 산출물 형태)."""
    style = {"font": "", "size": 64, "color": "#FFFFFF", "outline": True,
              "outline_color": "#000000", "outline_w": 6}
    parts = va._segmented_drawtext("안녕하세요", style, tmp_path, "hc", 50, 14)
    assert len(parts) == 1
    assert "drawtext=fontfile=" in parts[0]
    assert "fontcolor=0xFFFFFF" in parts[0]


def test_segmented_drawtext_matches_keyword_splits_segments(tmp_path):
    """키워드 매칭 시 세그먼트가 여러 개로 쪼개지고, x좌표가 증가 순서.
    v1은 정확 단어(공백 분리 토큰) 일치만 지원(설계서 §7 — 부분문자열 매칭은 범위 밖).
    레퍼런스 원본은 "쿠팡꿀템"처럼 붙어있지만, 그 형태는 부분매칭이 필요해 이번엔 다루지 않는다."""
    style = {"font": "", "size": 64, "color": "#FFFFFF"}
    rules = [{"keyword": "쿠팡", "color": "#FF2D2D", "box": True, "box_color": "#FF2D2D"}]
    parts = va._segmented_drawtext("나만 몰랐던 쿠팡 꿀템", style, tmp_path, "hc", 50, 14,
                                     highlight_rules=rules)
    assert len(parts) >= 2
    import re
    xs = [int(m.group(1)) for p in parts for m in [re.search(r"x=(-?\d+)", p)] if m]
    assert xs == sorted(xs)
    assert any("fontcolor=0xFF2D2D" in p and "box=1" in p for p in parts)


def test_segmented_drawtext_no_keyword_match_falls_back_to_one_segment(tmp_path):
    style = {"font": "", "size": 64, "color": "#FFFFFF"}
    rules = [{"keyword": "없는단어", "color": "#FF2D2D"}]
    parts = va._segmented_drawtext("안녕하세요 반갑습니다", style, tmp_path, "hc", 50, 14,
                                     highlight_rules=rules)
    assert len(parts) == 1


def test_segmented_drawtext_two_lines_resets_x_per_line(tmp_path):
    style = {"font": "", "size": 40, "color": "#FFFFFF"}
    rules = [{"keyword": "꿀템", "color": "#FFE100"}]
    parts = va._segmented_drawtext("나만 몰랐던\n쿠팡 꿀템", style, tmp_path, "hc", 50, 14,
                                     highlight_rules=rules)
    assert len(parts) >= 3  # 1줄(1세그먼트) + 2줄(쿠팡/꿀템 최소 2세그먼트)
    import re
    ys = sorted(set(int(m.group(1)) for p in parts for m in [re.search(r"y=(-?\d+)", p)] if m))
    assert len(ys) == 2  # 줄마다 다른 y
