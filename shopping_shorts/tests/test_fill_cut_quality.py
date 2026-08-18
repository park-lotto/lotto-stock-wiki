"""채울 때 '어디서 가져오는가'를 따진다(2026-08-18).

사장님: "짧은 거 여기저기서 붙여서 하면 눈이 아프더라고 / 짧은 건 2개 정도 이어서,
영상당 2장면+2장면."

실측(job 790bdd6dfe32): 컷 24개 평균 1.8초, **1초 미만 4개**, 8비트 중 5비트가
2~3개 소스 혼합. 비트2는 s3(1.3초)→s1(2.4초)→s0(1.1초)로 1~2초마다 영상이 바뀌었다.
원인은 _fill_beat_screen_time이 '부족분을 채우기'만 하고 출처를 안 따진 것.
"""
import copy

from shopping_shorts import edit_plan


def _seg(vid, i, dur, desc):
    return {"seg_id": "%s-%d" % (vid, i), "video_id": vid,
            "start": i * 10.0, "end": i * 10.0 + dur, "scene_desc": desc}


def _beat(primary, narration="손톱 광택이 살아나요", need=9.0):
    return [{"role": "hook", "narration": narration, "target_seconds": need,
             "primary": dict(primary), "alternates": []}]


def _clips(b):
    return [b["primary"]] + list(b.get("alternates") or [])


def test_같은_영상에서_이어_붙인다():
    """다른 소스의 짧은 조각이 '대사와 더 어울려' 보여도, 같은 영상을 먼저 쓴다."""
    seg = {}
    for i in range(5):
        s = _seg("A", i, 3.0, "네일 작업 장면")
        seg[s["seg_id"]] = s
    for i in range(5):
        s = _seg("B", i, 0.9, "손톱 광택")      # 대사와 단어가 겹치지만 0.9초짜리
        seg[s["seg_id"]] = s
    out = edit_plan._fill_beat_screen_time(copy.deepcopy(_beat(seg["A-0"])), seg)
    cl = _clips(out[0])
    assert len({c["video_id"] for c in cl}) == 1, "한 비트 안에서 영상이 튀면 산만하다"
    assert all(edit_plan._seg_secs(c) >= edit_plan._MIN_CUT_SECONDS for c in cl), \
        "1초 미만 조각이 붙었다 — 사장님이 '눈 아프다'고 한 그 모양"


def test_재고가_없으면_짧은_것도_쓴다():
    """막지는 않는다 — 막으면 채울 게 동나 재사용 폴백(같은 컷 반복)으로 떨어진다.
    그게 더 나쁘다는 판단은 이 함수의 기존 주석과 같다."""
    seg = {}
    p = _seg("A", 0, 2.0, "시작")
    seg[p["seg_id"]] = p
    for i in range(1, 6):
        s = _seg("A", i, 0.9, "짧은 조각")
        seg[s["seg_id"]] = s
    out = edit_plan._fill_beat_screen_time(copy.deepcopy(_beat(p, need=6.0)), seg)
    got = sum(edit_plan._seg_secs(c) for c in _clips(out[0]))
    assert got >= 6.0, "짧은 것밖에 없을 때도 화면은 채워야 한다(불변식 우선)"


def test_최소길이_기준이_상수로_한곳에_있다():
    """숫자를 코드 여기저기 흩으면 다음 사람이 한쪽만 고친다(0순위-B)."""
    assert edit_plan._MIN_CUT_SECONDS == 1.5
