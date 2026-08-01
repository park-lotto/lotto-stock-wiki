"""태깅 QA 게이트 Layer 1 — validate_extract 검증 테스트.

설계: scratchpad/태깅QA게이트_솔루션설계_2026-08-01.md
원칙: QA는 **기록 장치**지 차단 장치가 아니다(빈 대본 금지). 점수와 flags만 낸다.
"""
from shopping_shorts import tag_qa


def _seg(seg_id, start, end, text="맛있게 구워집니다요", scene_desc="프라이팬에 생선을 굽는 모습",
         shot_role="사용중", change="생선 껍질이 노릇하게 익는다", is_key=True):
    return {"seg_id": seg_id, "start": start, "end": end, "text": text,
            "scene_desc": scene_desc, "shot_role": shot_role, "change": change,
            "is_key": is_key}


def _good_result(n=4, dur=20.0):
    """지침을 다 지킨 정상 추출 결과 — 이 위에 결함을 하나씩 얹어 테스트한다."""
    step = dur / n
    segs = [_seg(f"v-{i}", round(i * step, 1), round((i + 1) * step, 1),
                 text=f"{i}번째 구간 나레이션입니다요",
                 scene_desc=f"{i}번째 화면 — 서로 다른 묘사가 들어간다")
            for i in range(n)]
    return {"segments": segs,
            "full_text": " ".join(s["text"] for s in segs),
            "product_benefits": ["기름이 튀지 않는다"]}


def test_good_extract_scores_high_with_no_flags():
    score, flags = tag_qa.validate_extract(_good_result(), 20.0)
    assert flags == [], f"정상 결과에 flags가 붙으면 안 된다: {flags}"
    assert score >= 0.9


def test_flags_missing_hook_when_first_segment_starts_late():
    """★최우선 규칙: 첫 세그는 0초부터. 3초부터 시작 = 훅 누락."""
    r = _good_result()
    r["segments"][0]["start"] = 3.0
    score, flags = tag_qa.validate_extract(r, 20.0)
    assert any("훅" in f for f in flags), flags
    assert score < 1.0


def test_flags_low_coverage_when_segments_miss_most_of_video():
    """20초 영상인데 세그가 6초만 덮으면 대부분을 놓친 것."""
    r = _good_result(n=2, dur=6.0)
    score, flags = tag_qa.validate_extract(r, 20.0)
    assert any("커버리지" in f for f in flags), flags


def test_flags_time_inconsistency_on_overlap_and_reversal():
    r = _good_result()
    r["segments"][1]["end"] = r["segments"][1]["start"] - 1.0   # start > end 역전
    score, flags = tag_qa.validate_extract(r, 20.0)
    assert any("시간" in f for f in flags), flags


def test_flags_when_all_shot_roles_collapsed_to_기타():
    """분포 붕괴 = 대충 태깅 신호(스파인 슬롯 배치가 무의미해진다)."""
    r = _good_result()
    for s in r["segments"]:
        s["shot_role"] = "기타"
    score, flags = tag_qa.validate_extract(r, 20.0)
    assert any("shot_role" in f for f in flags), flags


def test_flags_duplicated_scene_desc():
    """같은 묘사를 복붙하면 화면 구분이 사라진다."""
    r = _good_result()
    for s in r["segments"]:
        s["scene_desc"] = "요리하는 모습"
    score, flags = tag_qa.validate_extract(r, 20.0)
    assert any("scene_desc" in f for f in flags), flags


def test_silent_video_with_benefits_is_exempt_from_empty_text_penalty():
    """무자막 영상: text가 전부 비어도 product_benefits가 있으면 감점하지 않는다.
    (프롬프트가 '자막 없어도 benefits는 반드시 채워라'라고 요구하는 경로)"""
    r = _good_result()
    for s in r["segments"]:
        s["text"] = ""
    r["full_text"] = ""
    r["product_benefits"] = ["터치 한 번에 자동으로 열린다"]
    score, flags = tag_qa.validate_extract(r, 20.0)
    assert not any("나레이션" in f for f in flags), f"무자막 면제가 안 걸렸다: {flags}"


def test_empty_text_without_benefits_is_flagged():
    """무자막 면제의 반대 경우 — benefits도 없으면 그냥 받아쓰기 실패다."""
    r = _good_result()
    for s in r["segments"]:
        s["text"] = ""
    r["full_text"] = ""
    r["product_benefits"] = []
    score, flags = tag_qa.validate_extract(r, 20.0)
    assert any("나레이션" in f for f in flags), flags


def test_duration_none_skips_duration_checks_without_crashing():
    """ffprobe 실패로 duration을 모르면 커버리지 검사는 건너뛴다(fail-open)."""
    score, flags = tag_qa.validate_extract(_good_result(n=2, dur=6.0), None)
    assert not any("커버리지" in f for f in flags), flags
    assert score > 0.0


def test_empty_segments_scores_zero_but_does_not_raise():
    score, flags = tag_qa.validate_extract({"segments": [], "full_text": ""}, 20.0)
    assert score == 0.0
    assert flags, "빈 결과엔 이유가 남아야 한다"
