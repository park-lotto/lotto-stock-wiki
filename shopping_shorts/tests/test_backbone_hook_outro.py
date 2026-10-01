# -*- coding: utf-8 -*-
"""assign_cuts 훅 우선·뒷컷 제외·배속 힌트 (2026-10-01 사장님 지시, 카드 051).

고치기 전 코드에서 이 검사가 실패하는지 먼저 봤다(0순위-A1c): outro 컷이 훅 줄에 붙고 hook 컷이 뒤로 밀렸다.
"""
from shopping_shorts import backbone_assemble as ba


def _src(vid, segs):
    return {"video_id": vid, "segments": [dict(s, seg_id=f"{vid}-{i}") for i, s in enumerate(segs)]}


def _mats():
    # s0 = 백본(씨앗), s1 = 서브. s1-0 뒷컷(CTA), s1-1 평범, s1-2 훅(반전), s1-3 문제
    return [
        _src("s0", [{"start": 0, "end": 3, "scene_desc": "원본 제품 전체", "shot_role": "완성"}]),
        _src("s1", [
            {"start": 0, "end": 3, "scene_desc": "채널 구독 안내 화면", "shot_role": "기타", "is_outro": True},
            {"start": 3, "end": 6, "scene_desc": "제품 외관을 손에 들고 보여줌", "shot_role": "완성", "speed_hint": 1.0},
            {"start": 6, "end": 9, "scene_desc": "접힌 막대가 십자로 펴짐", "shot_role": "조작",
             "hook_type": "반전", "hook_why": "접힌 막대가 십자로", "speed_hint": 0.8},
            {"start": 9, "end": 12, "scene_desc": "기존 둔탁한 거치대로 불편", "shot_role": "문제", "hook_type": "문제"},
        ]),
    ]


def _run(lines):
    srcs = _mats()
    idx = ba._seg_index(srcs)
    groups = {"groups": [], "order": [], "product": "거치대"}
    bs, rep = ba.assign_cuts(lines, groups, idx, "s0")
    return bs, idx


def test_outro_cut_never_used():
    bs, idx = _run([{"role": "훅", "text": "해외 천재가 만든 제품의 정체", "group": -1},
                    {"role": "전환", "text": "이건 바로 거치대", "group": -1},
                    {"role": "CTA", "text": "벌써 품절", "group": -1}])
    used = [s for b in bs for s in b["segs"]]
    assert "s1-0" not in used, used


def test_hook_line_gets_hook_cut_first():
    bs, idx = _run([{"role": "훅", "text": "해외 천재가 만든 제품의 정체", "group": -1}])
    assert bs[0]["segs"][0] == "s1-2", bs[0]


def test_speed_hint_carried_as_data_only():
    bs, idx = _run([{"role": "훅", "text": "해외 천재가 만든 제품의 정체", "group": -1}])
    assert bs[0].get("speed_hints") == {"s1-2": 0.8}, bs[0]
    assert idx["s1-1"]["speed"] == 1.0 and "speed_hints" in bs[0]


def test_source_block_shows_hook_speed_outro():
    srcs = _mats()
    txt = ba._source_block(srcs[1], False)
    assert "훅:반전(접힌 막대가 십자로)" in txt
    assert "뒷컷(안 씀)" in txt


def test_normalize_tags_keeps_new_keys():
    from shopping_shorts import frame_script as fs
    out = fs.normalize_tags([{"seg_no": 1, "scene_desc": "x", "hook_type": "클로즈업", "hook_why": "제품이 화면 가득",
                              "is_outro": "true", "moments": "0~2초 염", "tempo": "빠름", "speed_hint": "0.8",
                              "appeal_kind": "기능"},
                             {"seg_no": 2, "scene_desc": "y", "hook_type": "엉뚱", "speed_hint": "9"}], 2)
    assert out[0]["hook_type"] == "클로즈업" and out[0]["is_outro"] is True and out[0]["speed_hint"] == 0.8
    assert out[0]["appeal_kind"] == "기능" and out[0]["tempo"] == "빠름"
    assert out[1]["hook_type"] == "" and out[1]["speed_hint"] is None
