"""프레임 태깅 추출전환 B1 (2026-07-29): 영상 통째 업로드 대신 파이썬이 컷+프레임+오디오전사,
제미니는 프레임만 태깅. 순수 병합 로직부터 검증.
설계: docs/superpowers/specs/2026-07-29-프레임태깅-추출전환-design.md
"""
from shopping_shorts import frame_script as fs


# ── ① 컷 경계 + 워드 타임스탬프 → 세그먼트(start/end/text) ──────────────────
def test_segments_from_cuts_and_words_basic():
    cuts = [0.0, 3.0, 6.0]          # 두 구간: [0,3), [3,6)
    words = [{"word": "우유", "start": 0.5, "end": 1.0},
             {"word": "안먹는", "start": 1.0, "end": 1.8},
             {"word": "완성됐어요", "start": 3.2, "end": 4.0}]
    segs = fs.segments_from_cuts_and_words(cuts, words)
    assert len(segs) == 2
    assert segs[0]["start"] == 0.0 and segs[0]["end"] == 3.0
    assert segs[0]["text"] == "우유 안먹는"
    assert segs[1]["text"] == "완성됐어요"


def test_segments_word_on_boundary_goes_to_earlier():
    """경계에 걸친 워드(start==경계)는 그 구간이 시작하는 세그먼트에 담는다(누락 방지)."""
    cuts = [0.0, 2.0, 4.0]
    words = [{"word": "딱", "start": 2.0, "end": 2.3}]
    segs = fs.segments_from_cuts_and_words(cuts, words)
    assert segs[1]["text"] == "딱"     # start==2.0 → 두번째 구간[2,4)


def test_segments_no_words_text_blank_fail_open():
    """오디오 전사가 없으면(무자막·키없음) text는 빈칸 — 크래시 금지, 프레임 태깅만."""
    segs = fs.segments_from_cuts_and_words([0.0, 2.0], None)
    assert len(segs) == 1
    assert segs[0]["text"] == ""


def test_segments_single_cut_returns_empty():
    """컷 경계가 1개 이하면 구간을 못 만든다 → 빈 리스트(호출부가 폴백)."""
    assert fs.segments_from_cuts_and_words([0.0], []) == []
    assert fs.segments_from_cuts_and_words([], []) == []


# ── ② 제미니 프레임 태그를 세그먼트에 병합 ──────────────────────────────────
def test_merge_tags_into_segments():
    segs = [{"start": 0.0, "end": 3.0, "text": "우유 안먹는"},
            {"start": 3.0, "end": 6.0, "text": "완성됐어요"}]
    tags = [{"scene_desc": "우유 붓기", "shot_role": "사용중", "is_key": False},
            {"scene_desc": "완성 모찌", "shot_role": "완성", "is_key": True,
             "product_benefits": ["쫀득한 식감"]}]
    out = fs.merge_frame_tags(segs, tags)
    assert out[1]["scene_desc"] == "완성 모찌" and out[1]["shot_role"] == "완성"
    assert out[1]["is_key"] is True
    assert out[1]["product_benefits"] == ["쫀득한 식감"]
    # 태그 없는(모자란) 세그먼트는 fail-open 기본값
    assert out[0]["shot_role"] == "사용중"


def test_merge_tags_fewer_tags_fail_open():
    """태그가 세그먼트보다 적어도 크래시 없이 기본값으로 채운다."""
    segs = [{"start": 0, "end": 1, "text": "a"}, {"start": 1, "end": 2, "text": "b"}]
    out = fs.merge_frame_tags(segs, [{"scene_desc": "x", "shot_role": "완성"}])
    assert out[0]["scene_desc"] == "x"
    assert out[1]["scene_desc"] == "" and out[1]["shot_role"] == "기타"  # 기본값


def test_full_text_joins_segment_texts():
    segs = [{"text": "우유 안먹는"}, {"text": "완성됐어요"}]
    assert fs.full_text_of(segs) == "우유 안먹는 완성됐어요"
