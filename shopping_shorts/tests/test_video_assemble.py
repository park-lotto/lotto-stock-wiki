from shopping_shorts import video_assemble as va


class _FakeFont:
    """글자당 10px 고정 — 폰트 무관하게 줄바꿈 경계를 결정적으로 검증."""
    def getlength(self, s):
        return 10 * len(s)


def test_wrap_keeps_short_line_and_empty():
    f = _FakeFont()
    assert va._wrap_to_width("hi", f, 100) == ["hi"]
    assert va._wrap_to_width("", f, 100) == [""]


def test_wrap_breaks_at_word_boundary():
    f = _FakeFont()
    # "ab cd ef" (per-char 10): max_w=55 → "ab cd"(50) 들어가고 " ef"에서 넘침
    assert va._wrap_to_width("ab cd ef", f, 55) == ["ab cd", "ef"]


def test_wrap_char_splits_long_spaceless_word():
    f = _FakeFont()
    # 공백 없는 한글 같은 긴 단어: max_w=45 → 4글자(40)씩
    assert va._wrap_to_width("abcdef", f, 45) == ["abcd", "ef"]


def test_wrap_preserves_explicit_newline_via_segmented():
    # 수동 줄바꿈(\n)은 각 줄로 유지되고, 긴 줄만 추가로 자동 줄바꿈된다.
    f = _FakeFont()
    lines = [seg for ln in "짧은줄\n".split("\n") for seg in va._wrap_to_width(ln, f, 100)]
    assert lines == ["짧은줄", ""]


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


def test_segmented_drawtext_base_color_not_clobbered_to_default(tmp_path):
    """비강조 단어는 default_color가 아니라 style의 실제 색으로 렌더돼야 한다
    (base_color_hex를 미리 _hex_to_ff 변환해 넘기면 drawtext 빌드 시 2중 변환되어
    '0x...' 문자열이 6-hex 판정에서 탈락 → default_color로 새는 회귀 버그)."""
    style = {"font": "", "size": 60, "color": "#00FF00"}  # 초록, default(주황)와 다름
    parts = va._segmented_drawtext("안녕 세상", style, tmp_path, "hc", 50, 14,
                                     highlight_rules=None, default_color="0xFF8800")
    assert len(parts) == 1
    assert "fontcolor=0x00FF00" in parts[0]
    assert "0xFF8800" not in parts[0]


def test_segmented_drawtext_base_color_kept_alongside_highlight(tmp_path):
    """강조 규칙과 비강조 base 색이 함께 있을 때도 base가 default로 새면 안 된다."""
    style = {"font": "", "size": 60, "color": "#FFFFFF"}  # 흰색 base
    rules = [{"keyword": "쿠팡", "color": "#FF2D2D"}]
    parts = va._segmented_drawtext("나만 몰랐던 쿠팡", style, tmp_path, "hc", 50, 14,
                                     highlight_rules=rules, default_color="0xFF8800")
    joined = " ".join(parts)
    assert "fontcolor=0xFFFFFF" in joined   # 비강조 단어 = 흰색(주황 아님)
    assert "fontcolor=0xFF2D2D" in joined   # 강조 단어 = 규칙색
    assert "fontcolor=0xFF8800" not in joined  # default로 새면 안 됨


# ── Task 2: _headcopy_drawtext_parts/_caption_drawtexts 리팩터 회귀 가드 ──

def test_headcopy_drawtext_no_highlight_matches_single_block(tmp_path):
    """highlight_rules 없는 hc는 세그먼트 1개(폭측정 x좌표 무관하게 fontcolor/폰트 등 필드는 기존과 동일)."""
    hc = {"text": "테스트 문구", "font": "", "color": "#FF8800", "size": 60,
          "x": 50, "y": 14, "outline": True, "outline_color": "#000000", "outline_w": 7}
    dt = va._headcopy_drawtext_parts(hc, tmp_path)[0]
    assert dt is not None
    assert "fontcolor=0xFF8800" in dt
    assert "borderw=7" in dt
    assert "bordercolor=0x000000" in dt


def test_caption_drawtexts_no_style_still_renders_bar_and_text(tmp_path):
    parts = va._caption_drawtexts("여러분 안녕하세요 반갑습니다", 2.0, tmp_path, 0)
    assert any("drawbox" in p for p in parts)  # 하단 바 유지


# ── Critical 버그 픽스: deco.highlight_rules → headcopy/caption_style 병합 ──
# UI는 강조단어 규칙을 deco에 저장하지만 렌더는 headcopy/caption_style에서 읽는다.
# _merge_highlight_rules가 _burn_captions 진입부에서 이 둘을 잇는 다리 역할.

def test_merge_highlight_rules_injects_into_both():
    rules = [{"keyword": "쿠팡", "color": "#FF2D2D"}]
    hc, cap = va._merge_highlight_rules({"text": "x"}, None, {"highlight_rules": rules})
    assert hc["highlight_rules"] == rules            # 헤드카피에 주입
    assert cap["highlight_rules"] == rules            # 자막(None이었어도) 주입


def test_merge_highlight_rules_no_rules_passthrough():
    hc, cap = va._merge_highlight_rules({"text": "x"}, None, {"extra_texts": []})
    assert "highlight_rules" not in hc               # 규칙 없으면 무변경
    assert cap is None                                # caption_style None 유지


def test_merge_highlight_rules_does_not_override_existing():
    own = [{"keyword": "자체", "color": "#000000"}]
    deco_rules = [{"keyword": "덮지마", "color": "#FFFFFF"}]
    hc, cap = va._merge_highlight_rules({"highlight_rules": own}, {"highlight_rules": own}, {"highlight_rules": deco_rules})
    assert hc["highlight_rules"] == own              # 기존 우선
    assert cap["highlight_rules"] == own


def test_merge_highlight_rules_reaches_headcopy_drawtext(tmp_path):
    # 통합: deco에만 규칙이 있어도 병합 후 _headcopy_drawtext_parts가 규칙색을 낸다.
    hc0 = {"text": "나만 몰랐던 쿠팡", "font": "", "color": "#FFFFFF", "size": 60, "x": 50, "y": 20}
    rules = [{"keyword": "쿠팡", "color": "#FF2D2D", "box": True, "box_color": "#FFE100"}]
    hc, _ = va._merge_highlight_rules(hc0, None, {"highlight_rules": rules})
    parts = va._headcopy_drawtext_parts(hc, tmp_path)
    joined = " ".join(parts)
    assert "fontcolor=0xFF2D2D" in joined            # 강조 단어 규칙색이 실제 필터에 나온다
    assert any("drawtext=fontfile=" in p for p in parts)


# ── 비트당 다중 클립 계획(_plan_beat_clips) ────────────────────────
def _seg(v, s, e):
    return {"video_id": v, "start": s, "end": e}


def _total_out(clips):
    return sum(c["out_dur"] for c in clips)


def test_plan_single_long_segment_no_slowmo():
    # 구간(0~10, 길이10)이 나레이션(4)보다 길다 → 앞 4초만 1배속, 유출·슬로모 없음.
    clips = va._plan_beat_clips([_seg("A", 0.0, 10.0)], tts_dur=4.0)
    assert len(clips) == 1
    c = clips[0]
    assert c["video_id"] == "A" and c["start"] == 0.0
    assert abs(c["src_dur"] - 4.0) < 1e-6 and abs(c["out_dur"] - 4.0) < 1e-6
    assert c["start"] + c["src_dur"] <= 10.0  # 유출 0


def test_plan_chains_multiple_segments_to_fill():
    # 2.2 + 2.2 = 4.4 ≥ 4.0 → 첫 구간 통째(2.2) + 둘째 구간 앞 1.8초. 슬로모 없음.
    segs = [_seg("A", 0.0, 2.2), _seg("B", 5.0, 7.2)]
    clips = va._plan_beat_clips(segs, tts_dur=4.0)
    assert len(clips) == 2
    assert abs(clips[0]["out_dur"] - 2.2) < 1e-6
    assert abs(clips[1]["out_dur"] - 1.8) < 1e-6
    # 각 클립 구간 밖으로 안 나감
    for c, s in zip(clips, segs):
        assert c["start"] + c["src_dur"] <= s["end"] + 1e-9
    assert abs(_total_out(clips) - 4.0) < 0.05
    # 소스 충분 → 슬로모 0
    assert all(abs(c["out_dur"] - c["src_dur"]) < 1e-6 for c in clips)


def test_plan_slows_last_clip_when_short():
    # 2.2 + 2.2 = 4.4 < 4.9 → 부족분 0.5는 마지막 클립을 슬로모로 늘림.
    segs = [_seg("A", 0.0, 2.2), _seg("B", 5.0, 7.2)]
    clips = va._plan_beat_clips(segs, tts_dur=4.9)
    assert abs(_total_out(clips) - 4.9) < 0.05
    # 마지막 클립만 슬로모(out_dur > src_dur), 나머진 1배속
    assert clips[-1]["out_dur"] > clips[-1]["src_dur"] + 1e-6
    assert all(abs(c["out_dur"] - c["src_dur"]) < 1e-6 for c in clips[:-1])
    # 유출 0: src_dur는 구간 길이 이내
    for c, s in zip(clips, segs):
        assert c["src_dur"] <= (s["end"] - s["start"]) + 1e-9


def test_plan_absorbs_tiny_remainder_into_previous():
    # 2.0 + 2.0, tts 4.3 → 앞 2.0 + 뒤 2.0 = 4.0, 남은 0.3(<0.8)은 새 클립 안 만들고
    # 직전(마지막) 클립을 슬로모로 늘려 흡수. 0.8초 미만 독립 클립 없음.
    segs = [_seg("A", 0.0, 2.0), _seg("B", 0.0, 2.0)]
    clips = va._plan_beat_clips(segs, tts_dur=4.3)
    assert abs(_total_out(clips) - 4.3) < 0.05
    assert all(c["out_dur"] >= 0.8 - 1e-9 for c in clips)
    # 마지막 클립이 0.3만큼 슬로모로 늘어남(src 2.0 → out 2.3)
    assert clips[-1]["out_dur"] > clips[-1]["src_dur"] + 1e-6


def test_plan_never_overflows_segment_end():
    # 어떤 조합이든 start+src_dur는 end를 안 넘는다(유출 0의 직접 검증).
    segs = [_seg("A", 3.0, 4.0), _seg("B", 10.0, 10.5)]
    clips = va._plan_beat_clips(segs, tts_dur=6.0)  # 합계 1.5 << 6.0
    for c, s in zip(clips, segs):
        assert c["start"] + c["src_dur"] <= s["end"] + 1e-9
    assert abs(_total_out(clips) - 6.0) < 0.05


def test_plan_absorbs_short_leading_segment():
    # 선두 구간이 0.8초 미만(0.3s)이고 통째 소비돼도 독립 클립으로 안 남는다.
    segs = [_seg("A", 0.0, 0.3), _seg("B", 0.0, 5.0)]
    clips = va._plan_beat_clips(segs, tts_dur=5.3)
    assert all(c["out_dur"] >= 0.8 - 1e-9 for c in clips)   # 깜빡임 없음
    assert abs(_total_out(clips) - 5.3) < 0.05
    for c, s in [(c, s) for c in clips for s in segs if s["video_id"] == c["video_id"]]:
        assert c["start"] + c["src_dur"] <= s["end"] + 1e-9   # 유출 0 유지


def test_plan_absorbs_short_middle_segment():
    # 중간 구간이 짧아도(0.3s) 최종에 0.8초 미만 독립 클립이 남지 않는다.
    segs = [_seg("A", 0.0, 5.0), _seg("B", 0.0, 0.3), _seg("C", 0.0, 5.0)]
    clips = va._plan_beat_clips(segs, tts_dur=5.3)
    assert all(c["out_dur"] >= 0.8 - 1e-9 for c in clips)
    assert abs(_total_out(clips) - 5.3) < 0.05


# ── _render_mix 실렌더 grounding (유출 0 + 길이 일치) ──────────────

import re
import shutil
import subprocess
import pytest

_HAS_FF = shutil.which("ffmpeg") and shutil.which("ffprobe")


# stdin=DEVNULL 필수(Windows): pytest 캡처 중 부모 stdin 핸들이 무효라 명시 안 하면
# subprocess가 상속하려다 OSError([WinError 6] 핸들이 잘못되었습니다)로 죽는다
# (2026-07-18 실측 — video_assemble._run_ffmpeg에도 동일 원인으로 동일하게 추가함).
def _make_color_source(path, colors, seconds_each=1.0, fps=30):
    """colors=['red','green',...] 각 색을 seconds_each초씩 이어붙인 720x1280 소스."""
    parts = []
    for i, col in enumerate(colors):
        seg = path.parent / f"src_seg_{i}.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        f"color=c={col}:s=720x1280:d={seconds_each}:r={fps}",
                        "-pix_fmt", "yuv420p", str(seg)], check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        parts.append(seg)
    lst = path.parent / "src_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(path)], check=True, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _make_silence(path, dur):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    f"anullsrc=r=44100:cl=stereo", "-t", str(dur),
                    "-c:a", "aac", str(path)], check=True, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _avg_color(video, at_sec):
    """video의 at_sec 지점 1프레임을 뽑아 평균 YUV(signalstats) 텍스트를 반환한다.
    ⚠️ 브리프 원안은 nested `movie=` 필터 + seek_point였으나 이 환경(Windows)에서
    실측 2건 모두 실패해 -ss(입력시크)+실디코드 방식으로 교체했다(2026-07-18):
    ①경로의 드라이브 콜론('C:\\...')이 movie= 필터 자신의 옵션 구분자 콜론과 충돌해
    항상 빈 출력(ffprobe: "Failed to avformat_open_input 'C'")이 났다. `C\\:/...`처럼
    콜론을 이스케이프하면 파싱 에러는 없어지지만, ②그 상태에서도 seek_point가 항상
    frame:0(pts_time≈0.02)만 반환해(재인코딩된 mix_raw.mp4처럼 키프레임이 드문 짧은
    클립에서 seek_point가 forward-decode를 안 함) at_sec와 무관하게 같은 프레임이
    나왔다(실측: t=0.2~1.8 전부 VAVG=240 동일). 반면 `-ss <t> -i <video>`(입력 옵션
    시크)는 ffmpeg가 자동으로 accurate seek(키프레임에서 목표시각까지 디코드)를 하므로
    같은 소스에서 t=0.2/0.7→VAVG=240(red), t=1.2/1.5/1.8→VAVG=81(green)로 실제
    시간에 따라 값이 달라짐을 확인했다(구버전 코드의 유출 재현). 이 방식으로 교체."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at_sec), "-i", str(video),
                        "-frames:v", "1", "-vf", "signalstats,metadata=print:file=-",
                        "-f", "null", "-"], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True)
    return r.stdout


def _vavg(stats):
    """_avg_color가 반환한 metadata=print 텍스트에서 첫 VAVG 값을 뽑는다(없으면 None)."""
    m = re.search(r"VAVG=(-?\d+)", stats)
    return int(m.group(1)) if m else None


@pytest.mark.skipif(not _HAS_FF, reason="ffmpeg/ffprobe 없음")
def test_render_mix_no_overflow_and_exact_length(tmp_path):
    # 소스 A: 0~1s=red, 1~2s=green, 2~3s=blue. 매칭 구간은 [0,1](red)뿐인데 나레이션은 2초.
    # 옛 코드면 1s 이후 green이 샜다(유출). 새 코드는 red를 슬로모로 2초 채운다.
    src = tmp_path / "A.mp4"
    _make_color_source(src, ["red", "green", "blue"])
    tts = tmp_path / "tts0.wav"
    _make_silence(tts, 2.0)
    edit_plan = {"beats": [{
        "beat_idx": 0, "role": "hook", "narration": "x",
        "primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 1.0},
        "alternates": [],
    }]}
    out = va._render_mix(edit_plan, {0: str(tts)}, {"A": str(src)}, tmp_path)

    assert abs(va._probe_duration(out) - 2.0) < 0.15   # 길이 == 나레이션
    # 유출 0: 1.5초 지점(옛 코드면 green이 나올 자리)이 red 계열이어야 한다.
    # signalstats YUV: red는 V(빨강) 크고(실측 240), green은 낮다(실측 81). 150을 경계로
    # red/green을 가른다(blue=110도 150 미만이라 같이 걸러지지만 이 테스트 소스엔 안 나옴).
    stats = _avg_color(out, 1.5)
    vavg = _vavg(stats)
    assert vavg is not None  # 프레임을 실제로 뽑았다(빈 출력 아님)
    assert vavg > 150, f"1.5초 지점이 red가 아님(VAVG={vavg}) — 유출 의심"


@pytest.mark.skipif(not _HAS_FF, reason="ffmpeg/ffprobe 없음")
def test_render_mix_chains_two_segments(tmp_path):
    # 소스 A: red,green,blue 각 2초(6초). 구간 [0,2](red)+[2,4](green) 이어붙여 나레이션 3.5초.
    src = tmp_path / "A.mp4"
    _make_color_source(src, ["red", "green", "blue"], seconds_each=2.0)
    tts = tmp_path / "tts0.wav"
    _make_silence(tts, 3.5)
    edit_plan = {"beats": [{
        "beat_idx": 0, "role": "hook", "narration": "x",
        "primary": {"video_id": "A", "seg_id": "A-0", "start": 0.0, "end": 2.0},
        "alternates": [{"video_id": "A", "seg_id": "A-1", "start": 2.0, "end": 4.0}],
    }]}
    out = va._render_mix(edit_plan, {0: str(tts)}, {"A": str(src)}, tmp_path)
    assert abs(va._probe_duration(out) - 3.5) < 0.2
