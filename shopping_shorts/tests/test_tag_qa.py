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


# ── 2026-08-01 리뷰 F1: 커버리지 이중 합산 ────────────────────────

def test_겹친_세그가_중간_공백을_가리지_않는다():
    """★F1: Σ(end-start)로 세면 겹친 만큼 부풀어 공백이 숨는다.

    ★이 fixture를 고르는 데 한 번 실패했다: 처음엔 '앞쪽만 겹치게' 짰더니 **꼬리 검사**가
    먼저 걸려서, 합집합을 단순합으로 되돌려도 테스트가 그대로 통과했다(회귀 주입 실측).
    그래서 **꼬리는 멀쩡하고 중간만 비는** 모양으로 짠다:
      20초 영상 / 세그 0~9, 0~9(겹침), 18~20.
      · 단순합 = 9+9+2 = 20 → 비율 1.0, 마지막 end 20 → **두 검사 다 통과(구멍)**
      · 합집합 = 9+2 = 11 → 비율 0.55 → 커버리지 부족으로 잡힌다.
    9~18초가 통째로 비어 있는데 단순합은 그걸 못 본다."""
    segs = [_seg("v-0", 0.0, 9.0), _seg("v-1", 0.0, 9.0), _seg("v-2", 18.0, 20.0)]
    r = {"segments": segs, "full_text": " ".join(s["text"] for s in segs)}
    score, flags = tag_qa.validate_extract(r, 20.0)
    assert any("커버리지" in f for f in flags), f"중간 공백 9초를 놓쳤다: {flags}"


def test_겹치지_않는_정상_세그는_커버리지_통과():
    """합집합으로 바꿔도 정상 케이스는 그대로 통과해야 한다(과잉 감점 금지)."""
    _, flags = tag_qa.validate_extract(_good_result(n=4, dur=20.0), 20.0)
    assert not any("커버리지" in f for f in flags), flags


def test_맞닿은_세그는_합쳐서_센다():
    """0~10, 10~20은 겹친 게 아니라 이어진 것 — 20초를 다 덮은 것이 맞다."""
    segs = [_seg("v-0", 0.0, 10.0), _seg("v-1", 10.0, 20.0)]
    r = {"segments": segs, "full_text": " ".join(s["text"] for s in segs)}
    _, flags = tag_qa.validate_extract(r, 20.0)
    assert not any("커버리지" in f for f in flags), flags


# ── 2026-08-01 리뷰 F2: role 신호 3개가 한 flag로 뭉개짐 ──────────

def test_role_신호_셋이_각각_flags에_실린다():
    """★F2: 예전엔 첫 신호에서 return이라 나머지가 재시도 프롬프트에 안 실렸고,
    모델이 같은 실수를 반복했다. 셋 다 무너졌으면 셋 다 알려줘야 한다."""
    r = _good_result()
    for s in r["segments"]:
        s["shot_role"], s["change"], s["is_key"] = "기타", "", False
    _, flags = tag_qa.validate_extract(r, 20.0)
    assert any("shot_role" in f for f in flags), flags
    assert any("is_key" in f for f in flags), flags
    assert any("change" in f for f in flags), flags


def test_role_가중치_합은_종전과_같다():
    """총점 스케일을 흔들지 않는다 — 셋 다 무너진 경우가 예전 0.15와 같아야
    옛 점수와 새 점수를 나란히 볼 수 있다."""
    r = _good_result()
    for s in r["segments"]:
        s["shot_role"], s["change"], s["is_key"] = "기타", "", False
    score, _ = tag_qa.validate_extract(r, 20.0)
    assert abs(score - (1.0 - 0.15)) < 1e-9, score


def test_change만_비면_감점이_가장_작다():
    """change는 셋 중 가장 무른 신호다(2026-07-31 신설, 도입·CTA 위주 영상은 비어도 정상).
    이게 shot_role 붕괴와 같은 무게면 옛 영상이 부당하게 깎인다."""
    only_change = _good_result()
    for s in only_change["segments"]:
        s["change"] = ""
    only_shot = _good_result()
    for s in only_shot["segments"]:
        s["shot_role"] = "기타"
    assert tag_qa.validate_extract(only_change, 20.0)[0] > \
           tag_qa.validate_extract(only_shot, 20.0)[0]
