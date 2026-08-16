"""최초 배치의 코드 자동보충(_fill_beat_screen_time)이 **같아 보이는 화면**을 뒤로 미는가.

소스를 여러 개 올리면 같은 장면이 소스마다 있고 seg_id가 달라, 종전의 `sid in used`
검사로는 못 걸렀다(2026-08-16 사장님 "왜 같은데 2장이 붙지").
★막지 않고 순서만 민다 — 막으면 재료가 동나 '같은 컷 그대로 재사용' 폴백으로 떨어져
  오히려 나빠지기 때문. 그래서 "다른 화면이 있으면 그게 먼저"만 확인한다.
"""
from shopping_shorts import edit_plan


def _seg(sid, vid, start, desc, label="", change=""):
    return {"seg_id": sid, "video_id": vid, "start": start, "end": start + 2.0,
            "scene_desc": desc, "label": label, "change": change,
            "text": "", "shot_role": "기타", "is_key": False,
            "action": "", "product_benefits": []}


# s1-1 = 이미 쓰는 화면 / s2-9 = 다른 소스의 **같은 장면** / s1-5 = 전혀 다른 장면
SEGS = {
    "s1-1": _seg("s1-1", "v1", 0.0, "에스프레소가 하트 모양 노즐 틈새로 솟구치며 크레마가 오른다",
                 label="추출 순간"),
    "s2-9": _seg("s2-9", "v2", 0.0, "에스프레소가 하트 모양 노즐 틈새로 솟구치며 크레마가 오른다",
                 label="추출 순간"),
    "s1-5": _seg("s1-5", "v1", 8.0, "원목 스쿱을 거치대에 가지런히 올려 둔다", label="스쿱 정리"),
}


def _beats():
    return [{
        "beat_idx": 0, "role": "훅", "narration": "커피가 올라옵니다",
        "target_seconds": 6.0,
        "primary": {"seg_id": "s1-1", "video_id": "v1", "start": 0.0, "end": 2.0},
        "alternates": [],
    }]


def _alt_ids(beats):
    return [a["seg_id"] for a in beats[0]["alternates"]]


def test_같아보이는_화면보다_다른_화면을_먼저_붙인다():
    out = edit_plan._fill_beat_screen_time(_beats(), SEGS)
    ids = _alt_ids(out)
    assert ids, "화면이 모자라면 뭔가는 붙어야 한다"
    # 전혀 다른 장면(s1-5)이 같은 장면(s2-9)보다 먼저 와야 한다
    assert ids.index("s1-5") < ids.index("s2-9"), ids


def test_다른_화면이_없으면_그래도_붙인다_회귀0():
    """같아 보이는 것뿐이면 막지 않고 쓴다 — 빈 화면보다 낫다(종전 동작 유지)."""
    segs = {"s1-1": SEGS["s1-1"], "s2-9": SEGS["s2-9"]}
    out = edit_plan._fill_beat_screen_time(_beats(), segs)
    assert "s2-9" in _alt_ids(out)


def test_설명이_비면_안_터진다():
    segs = {
        "s1-1": _seg("s1-1", "v1", 0.0, ""),
        "s9-9": _seg("s9-9", "v9", 0.0, ""),
        "s1-5": SEGS["s1-5"],
    }
    out = edit_plan._fill_beat_screen_time(_beats(), segs)
    assert isinstance(out, list)
