"""한 편 안 장면 중복·소스 배분 — 주인 함수 backbone.finalize_scenes (카드 033, 2026-09-29).

실사고(job 68b48b12c7f5, generator=legacy): 1번 칸 alternate 와 4번 칸 primary 가 같은 장면(-39),
소스 5개 중 s2 는 0컷. 게이트가 "같은 장면이 반복됩니다(-39×2)"를 잡고도 그대로 출고됐다.
여기선 그 모양을 본뜬 합성 데이터로 계약을 잰다:
  칸 순서·칸 수·대사·primary 불변 / 재사용 0(seg·설명) / 안 쓴 소스 사용 / 포인트 비트 불가침 / 이어붙임 금지.
"""
import copy

from shopping_shorts import backbone, mix_pipeline, plan_gate


def _seg(vid, i, start, dur, desc=None, action=None):
    return {"video_id": vid, "seg_id": "%s-%d" % (vid, i), "start": float(start),
            "end": float(start) + dur, "scene_desc": desc or "%s 장면 %d" % (vid, i),
            "action": action}


def _src(vid, n, dur, gap=1.0):
    """시간순 조각 n개 — 조각 사이에 gap초를 둬 서로 '이어붙임'이 아니게."""
    return {"video_id": vid, "segments": [_seg(vid, i, i * (dur + gap), dur) for i in range(n)]}


def _pool():
    # s0 = 롱폼(조각 많음), s2 = 조각 3개뿐(안 쓰일 위험), s4 = 짧은 조각 많음 — job68 모양
    return [_src("s0", 12, 7.0), _src("s1", 6, 6.0), _src("s2", 3, 6.0), _src("s3", 6, 3.0),
            _src("s4", 10, 2.0)]


def _clip(pool, vid, i):
    src = next(s for s in pool if s["video_id"] == vid)
    return dict(src["segments"][i], video_id=vid)


def _beats(pool):
    c = lambda v, i: _clip(pool, v, i)      # noqa: E731
    return [
        {"beat_idx": 0, "narration": "이거 하나로 아침이 달라졌어요", "primary": c("s1", 2), "alternates": []},
        {"beat_idx": 1, "narration": "파우치를 열면 이렇게 들어 있어요", "primary": c("s0", 3),
         "alternates": [c("s0", 9)]},                                   # ← 4번 칸 primary 와 같은 장면
        {"beat_idx": 2, "narration": "부품이 딱 세 개라 간단해요", "primary": c("s0", 5), "alternates": []},
        {"beat_idx": 3, "narration": "청소도 금방 끝나고요", "primary": c("s0", 7), "alternates": []},
        {"beat_idx": 4, "narration": "스푼으로 저어 주면 완성이에요", "primary": c("s0", 9), "alternates": []},
        {"beat_idx": 5, "narration": "버튼만 누르면 추출이 시작돼요", "primary": c("s4", 2),
         "alternates": [c("s4", 4), c("s4", 6)]},
        {"beat_idx": 6, "narration": "크레마가 이렇게 올라와요", "primary": c("s3", 2),
         "alternates": [c("s3", 4)]},
        {"beat_idx": 7, "narration": "궁금하면 댓글 남겨 주세요", "primary": c("s4", 8),
         "alternates": [c("s4", 3)]},
    ]


def _material(beats):
    return [c for b in beats for c in [b.get("primary")] + list(b.get("alternates") or []) if c]


def _pids(beats):
    return [(b.get("primary") or {}).get("seg_id") for b in beats]


def test_job68_shape_repeat_removed_unused_source_in_and_slots_kept():
    pool = _pool()
    beats = _beats(pool)
    before = copy.deepcopy(beats)
    rep = {}
    out = backbone.finalize_scenes(beats, pool, report=rep)
    # 불변식: 칸 수·칸 순서·대사·primary 자리
    assert len(out) == len(before)
    assert [b["beat_idx"] for b in out] == [b["beat_idx"] for b in before]
    assert [b["narration"] for b in out] == [b["narration"] for b in before]
    assert _pids(out) == _pids(before)
    # 재사용 0 (seg_id·설명)
    mat = _material(out)
    assert len({c["seg_id"] for c in mat}) == len(mat)
    assert len({c["scene_desc"] for c in mat}) == len(mat)
    # 안 쓴 소스(s2) 사용
    assert "s2" in {c["video_id"] for c in mat}
    assert rep["ok"] is True and not rep["remaining_repeat_segs"] and not rep["unused_sources"]
    # 원본 불변(mutate 금지)
    assert beats == before


def test_replacement_prefers_less_used_source():
    pool = _pool()
    out = backbone.finalize_scenes(_beats(pool), pool)
    # 1번 칸의 겹친 alternate(s0-9)는 덜 쓴 소스의 컷으로 바뀐다 — s0(4번 쓰임)이 아니다
    new_alt = out[1]["alternates"][0]
    assert new_alt["seg_id"] != "s0-9"
    assert new_alt["video_id"] != "s0"


def test_same_desc_different_seg_counts_as_repeat():
    pool = _pool()
    beats = _beats(pool)
    twin = dict(_clip(pool, "s3", 5), scene_desc=beats[2]["primary"]["scene_desc"])   # 다른 seg, 같은 설명
    beats[6]["alternates"] = [twin]
    out = backbone.finalize_scenes(beats, pool)
    descs = [c["scene_desc"] for c in _material(out)]
    assert len(descs) == len(set(descs))


def test_point_beat_primary_is_inviolable():
    pool = _pool()
    beats = _beats(pool)
    # 뒤 칸(4번)이 포인트 비트(얹다) — 같은 primary 를 가진 앞 칸(3번, 비포인트)이 바뀌어야 한다
    beats[4]["narration"] = "마지막으로 크림을 듬뿍 얹어줍니다"
    beats[4]["primary"] = copy.deepcopy(beats[3]["primary"])
    assert backbone.is_point_beat(beats[4]) and not backbone.is_point_beat(beats[3])
    out = backbone.finalize_scenes(beats, pool)
    assert out[4]["primary"]["seg_id"] == beats[4]["primary"]["seg_id"]     # 포인트 primary 유지
    assert out[3]["primary"]["seg_id"] != beats[3]["primary"]["seg_id"]     # 비포인트 쪽이 바뀜
    assert len(set(_pids(out))) == len(out)


def test_later_primary_replaced_when_primaries_collide():
    pool = _pool()
    beats = _beats(pool)
    beats[3]["primary"] = copy.deepcopy(beats[2]["primary"])      # 2·3번 칸 primary 같음(둘 다 비포인트)
    out = backbone.finalize_scenes(beats, pool)
    assert out[2]["primary"]["seg_id"] == beats[2]["primary"]["seg_id"]     # 앞 칸 유지
    assert out[3]["primary"]["seg_id"] != beats[2]["primary"]["seg_id"]     # 뒤 칸 교체
    assert out[3].get("scene_finalized") == "primary_dedup"


def test_no_adjacent_splice_in_replacements():
    """교체 컷이 앞 클립의 **바로 다음 구간**(이어붙임)이면 안 된다 — 컷이 없는 화면이 된다."""
    pool = [
        {"video_id": "s0", "segments": [_seg("s0", 0, 0.0, 2.0), _seg("s0", 1, 2.0, 2.0),
                                        _seg("s0", 2, 4.0, 2.0)]},
        {"video_id": "s1", "segments": [_seg("s1", 0, 0.0, 2.0), _seg("s1", 1, 10.0, 2.0)]},
    ]
    c = lambda v, i: _clip(pool, v, i)      # noqa: E731
    beats = [
        {"beat_idx": 0, "narration": "하나", "primary": c("s0", 0), "alternates": [c("s1", 0)]},
        {"beat_idx": 1, "narration": "둘", "primary": c("s1", 1), "alternates": [c("s1", 0)]},  # 반복
    ]
    out = backbone.finalize_scenes(beats, pool)
    flat = _material(out)
    for a, b in zip(flat, flat[1:]):
        assert not backbone.is_continuous(a, b), (a["seg_id"], b["seg_id"])
    assert len({x["seg_id"] for x in flat}) == len(flat)


def test_idempotent_and_no_new_keys_when_clean():
    pool = _pool()
    once = backbone.finalize_scenes(_beats(pool), pool)
    twice = backbone.finalize_scenes(once, pool)
    assert twice == once
    bare = [{"beat_idx": 0, "narration": "x", "primary": _clip(pool, "s0", 0)}]   # alternates 키 없음
    assert backbone.finalize_scenes(bare, [pool[0]]) == bare


def test_gate_correction_runs_finalize_and_clears_repeat():
    """최종 관문(_run_gate_correction)이 반복을 마감한 뒤 재검사한다 — 게이트에 반복 위반이 안 남는다."""
    pool = _pool()
    beats = _beats(pool)
    assert any("같은 장면" in v for v in plan_gate.check_plan(beats, 30, pool_video_count=5)["violations"])
    plan = {"beats": beats}
    mix_pipeline._run_gate_correction(plan, pool, 30)
    assert not any("같은 장면" in v for v in plan["gate"]["violations"])
    assert plan["scene_finalize"]["ok"] is True
    assert "scene_repeat_alarm" not in plan
    assert _pids(plan["beats"]) == _pids(_beats(pool))


def test_gate_correction_alarms_when_unfixable():
    """대체 컷이 아예 없으면 조용히 넘기지 않고 경보 표식을 남긴다."""
    pool = [{"video_id": "s0", "segments": [_seg("s0", 0, 0.0, 2.0), _seg("s0", 1, 5.0, 2.0)]}]
    c = lambda i: _clip(pool, "s0", i)      # noqa: E731
    beats = [{"beat_idx": 0, "narration": "하나", "primary": c(0), "alternates": []},
             {"beat_idx": 1, "narration": "둘", "primary": c(1), "alternates": []},
             {"beat_idx": 2, "narration": "셋", "primary": c(0), "alternates": []}]
    plan = {"beats": beats}
    mix_pipeline._run_gate_correction(plan, pool, 30)
    assert plan.get("scene_repeat_alarm"), "반복이 남았는데 경보가 없다"
    assert "s0-0" in plan["scene_repeat_alarm"]["repeat_segs"]
