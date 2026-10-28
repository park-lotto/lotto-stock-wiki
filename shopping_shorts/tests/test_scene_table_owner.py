"""장면 id → 구간 판단의 주인 edit_plan.scene_table (관제 141, 2026-10-06 영상점검 다른 장면 9칸).

사고: 자동 편성(_dedup_and_fill)이 원본을 잘라 `…-2#2` id 를 만들었는데 화면 장면 표엔 없어서
화면 컷 계산이 그 칸에 컷 0개 → 완성본은 예비 계산으로 0.6초를 채워 뒤 칸 전부가 한 컷씩 밀렸다
(job 8baf28dc4794). 같은 함수가 원본 조각은 **같은 id 로 구간만** 줄여, 화면(id→표)과 렌더(비트 사본)가 갈렸다.
"""
from shopping_shorts import edit_plan as ep


def _extract():
    return {"s0": {"video_id": "s0", "segments": [
        {"seg_id": "g-1", "start": 0.0, "end": 5.5, "text": "a", "scene_desc": "과일을 붓는다"},
        {"seg_id": "g-2", "start": 5.5, "end": 11.3, "text": "b", "scene_desc": "버터를 올린다"},
    ]}}


def _inv():
    seg_map, _ = ep._build_inventory(list(_extract().values()))
    return seg_map


def test_plan_piece_id_resolves_in_table():
    """옛 job 의 `#2` 조각(인벤토리에 없음)도 표에서 비트 사본 구간으로 풀린다 — 화면 컷 0개의 뿌리."""
    inv = _inv()
    assert "g-2" in inv and "g-2#2" not in inv          # 전제: 사고 당시 모양
    plan = {"beats": [{"beat_idx": 0, "primary": {"video_id": "s0", "seg_id": "g-2#2", "start": 8.4, "end": 11.3,
                                                  "scene_desc": "버터를 올린다"}, "alternates": []}]}
    t = ep.scene_table(_extract(), plan)
    assert t["g-2#2"]["start"] == 8.4 and t["g-2#2"]["end"] == 11.3 and t["g-2#2"]["video_id"] == "s0"
    assert t["g-2"]["start"] == 5.5 and t["g-2"]["end"] == 11.3      # 진짜 조각은 안 덮는다


def test_unknown_source_piece_is_not_registered():
    """이 잡의 소스가 아닌 영상을 가리키는 id 는 등록하지 않는다(위조·옛 id 방어)."""
    plan = {"beats": [{"primary": {"video_id": "zz", "seg_id": "x#1", "start": 1.0, "end": 2.0}}]}
    assert "x#1" not in ep.scene_table(_extract(), plan)


def test_film_ids_still_resolve_and_film_false_skips_them():
    plan = {"beats": [{"primary": {"video_id": "s0", "seg_id": "g-1", "start": 0.0, "end": 5.5},
                       "scene_override": [{"video_id": "s0", "seg_id": "film_s0_1.00_2.50", "start": 1.0, "end": 2.5}]}]}
    assert ep.scene_table(_extract(), plan)["film_s0_1.00_2.50"]["end"] == 2.5
    assert "film_s0_1.00_2.50" not in ep.scene_table(_extract(), plan, film=False)


def test_dedup_and_fill_never_changes_span_under_same_id():
    """불변식: 나온 조각의 id 가 들어간 조각 id 와 같으면 구간도 같아야 한다(같은 id·다른 구간 금지)."""
    flat = [{"video_id": "s0", "seg_id": "g-2", "start": 5.5, "end": 11.3},
            {"video_id": "s0", "seg_id": "g-1", "start": 0.0, "end": 5.5}]
    spans_in = {s["seg_id"]: (s["start"], s["end"]) for s in flat}
    out = ep._dedup_and_fill([dict(s) for s in flat], need=4)
    assert len(out) == 4
    for s in out:
        if s["seg_id"] in spans_in:
            assert (s["start"], s["end"]) == spans_in[s["seg_id"]], s
    assert len({s["seg_id"] for s in out}) == 4                     # 조각마다 다른 id


def test_reserved_piece_gets_span_id():
    flat = [{"video_id": "s0", "seg_id": "g-2", "start": 5.5, "end": 11.3}]
    out = ep._dedup_and_fill([dict(s) for s in flat], need=1, reserved={ep._seg_key(flat[0])})
    assert out[0]["seg_id"] == "g-2#8.40-11.30" and out[0]["start"] == 8.4


def test_respine_plan_every_ref_resolves_with_same_span():
    """끝에서 끝: 시간순 재배치로 조각이 생겨도 표가 모든 참조를 **같은 구간으로** 푼다."""
    beats = [{"beat_idx": i, "narration": "n%d" % i, "primary": {"video_id": "s0", "seg_id": sid, "start": a, "end": b},
              "alternates": []}
             for i, (sid, a, b) in enumerate([("g-1", 0.0, 5.5), ("g-2", 5.5, 11.3), ("g-2", 5.5, 11.3),
                                              ("g-2", 5.5, 11.3), ("g-1", 0.0, 5.5)])]
    out = ep._chronological_respine(beats)
    t = ep.scene_table(_extract(), {"beats": out})
    for b in out:
        for s in [b["primary"]] + list(b.get("alternates") or []):
            got = t.get(s["seg_id"])
            assert got, s["seg_id"]
            assert (round(got["start"], 2), round(got["end"], 2)) == (round(s["start"], 2), round(s["end"], 2)), s
