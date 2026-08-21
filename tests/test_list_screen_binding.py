# -*- coding: utf-8 -*-
"""나열형: 항목의 말과 화면이 **같은 영상**에서 나오는가 (2026-08-21).

실측으로 드러난 사고를 고정한다 — `_assign_timeline`은 비트를 그룹에 위치순으로
나눠 주는데, 나열형은 항목마다 다른 제품이라 intro·cta가 자리를 밀면 말과 화면이
어긋난다(실측 3항목 중 2항목이 남의 제품 화면).
"""
from shopping_shorts import edit_plan as ep

PRODUCTS = ["신발건조기", "세정제", "3단우산", "미니제습기"]


def _groups():
    return [[{"seg_id": "v%d-%d" % (i, k), "video_id": "v%d" % i,
              "start": k * 2.0, "end": k * 2.0 + 2.0,
              "scene_desc": "%s 쓰는 장면" % p, "text": p} for k in range(2)]
            for i, p in enumerate(PRODUCTS)]


def _beats(with_src):
    # 재료가 모자란 편(v1)을 건너뛴 상태 — 항목 순번은 연속인데 영상은 v0·v2·v3.
    items = [("item1", "첫 번째 이건 신발건조기인데…", "v0"),
             ("item2", "두 번째 이건 3단우산인데…", "v2"),
             ("item3", "세 번째 이건 미니제습기인데…", "v3")]
    out = [{"role": "intro", "narration": "나만 몰랐던 꿀템들 빠르게 알려드릴게요"}]
    for role, nar, vid in items:
        b = {"role": role, "narration": nar}
        if with_src:
            b["src_video"] = vid
        out.append(b)
    out.append({"role": "cta", "narration": "댓글에 '나도' 남겨주세요"})
    return out


def test_항목은_자기_영상의_화면을_받는다():
    out = ep._pin_screens(_beats(True), _groups())
    for b in out:
        want = b.get("src_video")
        if want:
            assert (b.get("primary") or {}).get("video_id") == want, \
                "%s: 말은 %s인데 화면이 %s" % (b["role"], want,
                                            (b.get("primary") or {}).get("video_id"))


def test_src_video가_없으면_기존_배정_그대로():
    """8축(서사형)은 한 줄도 안 바뀌어야 한다 — 변경 전 실측값을 그대로 못박는다."""
    out = ep._assign_timeline(_beats(False), _groups())
    got = [(b["role"], (b.get("primary") or {}).get("video_id")) for b in out]
    assert got == [("intro", "v0"), ("item1", "v0"), ("item2", "v1"),
                   ("item3", "v2"), ("cta", "v3")], got
