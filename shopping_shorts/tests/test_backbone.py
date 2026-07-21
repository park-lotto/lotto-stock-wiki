from shopping_shorts import backbone


def _seg(seg_id, text="", scene_desc="", action=None):
    d = {"seg_id": seg_id, "start": 0, "end": 2, "text": text, "scene_desc": scene_desc}
    if action is not None:
        d["action"] = action
    return d


def test_segment_action_reads_stored_tag():
    assert backbone.segment_action(_seg("A", action="붓다")) == "붓다"


def test_segment_action_falls_back_to_dict():
    assert backbone.segment_action(_seg("A", text="뚜껑을 당겨서 뜯어요")) == "당기다"


def test_coverage_full_when_pool_has_all_actions():
    backbone_src = {"video_id": "BB", "segments": [
        _seg("BB-1", action="붓다"), _seg("BB-2", action="섞다")]}
    pool = [{"video_id": "S1", "segments": [_seg("S1-1", action="붓다")]},
            {"video_id": "S2", "segments": [_seg("S2-1", action="섞다")]}]
    r = backbone.coverage(backbone_src, pool)
    assert r["coverage_pct"] == 1.0
    assert r["uncovered"] == []


def test_coverage_reports_uncovered_actions():
    backbone_src = {"video_id": "BB", "segments": [
        _seg("BB-1", action="붓다"), _seg("BB-2", action="자르다")]}
    pool = [{"video_id": "S1", "segments": [_seg("S1-1", action="붓다")]}]
    r = backbone.coverage(backbone_src, pool)
    assert r["coverage_pct"] == 0.5
    assert r["uncovered"] == ["자르다"]


def test_beat_action_mismatch_catches_fit5_lie():
    # 바나나 실사고: 나레이션은 '자르다'인데 화면은 '뒤집다' → fit이 5여도 불일치
    beat = {"narration": "바나나 썰어 넣고", "fit": 5,
            "primary": {"seg_id": "s2-4", "scene_desc": "팬케이크를 뒤집는 모습", "action": "뒤집다"}}
    assert backbone.beat_action_mismatch(beat) is True


def test_beat_action_match_ok():
    beat = {"narration": "바나나 썰어 넣고", "fit": 3,
            "primary": {"seg_id": "x", "scene_desc": "칼로 바나나를 써는", "action": "자르다"}}
    assert backbone.beat_action_mismatch(beat) is False


def test_reconcile_swaps_screen_to_matching_action():
    beat = {"narration": "바나나 썰어 넣고", "fit": 5,
            "primary": {"seg_id": "s2-4", "scene_desc": "뒤집는", "action": "뒤집다", "video_id": "BB"}}
    pool = [{"video_id": "S1", "segments": [_seg("S1-9", scene_desc="바나나 써는", action="자르다")]}]
    nb, need_rewrite = backbone.reconcile_beat_by_action(beat, pool)
    assert need_rewrite is False
    assert nb["primary"]["action"] == "자르다" and nb.get("action_fixed") is True


def test_reconcile_flags_rewrite_when_no_clip():
    beat = {"narration": "바나나 썰어 넣고",
            "primary": {"seg_id": "x", "scene_desc": "뒤집는", "action": "뒤집다"}}
    pool = [{"video_id": "S1", "segments": [_seg("S1-1", action="붓다")]}]  # 자르다 없음
    nb, need_rewrite = backbone.reconcile_beat_by_action(beat, pool)
    assert need_rewrite is True and nb.get("need_rewrite") is True


def test_ping_pong_swaps_screen_when_clip_available():
    # 비트: 말=자르다, 화면=뒤집다(불일치). 풀에 자르다 클립 있음 → 화면 스왑, 재작성 안 씀.
    beats = [{"beat_idx": 0, "narration": "바나나 썰어 넣고",
              "primary": {"seg_id": "BB-4", "scene_desc": "뒤집는", "action": "뒤집다", "video_id": "BB"}}]
    pool = [{"video_id": "S1", "segments": [_seg("S1-9", scene_desc="써는", action="자르다")]}]
    called = {"n": 0}

    def rewrite(bs):
        called["n"] += 1
        return {}
    out = backbone.ping_pong_reconcile(beats, pool, rewrite_call=rewrite)
    assert out[0]["primary"]["action"] == "자르다"
    assert called["n"] == 0                       # 스왑으로 해결 → 재작성 호출 안 함


def test_ping_pong_rewrites_narration_when_no_clip():
    # 풀에 자르다 클립 없음 → 나레이션을 화면(뒤집다)에 맞게 재작성
    beats = [{"beat_idx": 0, "narration": "바나나 썰어 넣고",
              "primary": {"seg_id": "x", "scene_desc": "팬케이크 뒤집는", "action": "뒤집다"}}]
    pool = [{"video_id": "S1", "segments": [_seg("S1-1", action="붓다")]}]

    def rewrite(bs):
        return {b["beat_idx"]: "노릇하게 뒤집어 주면" for b in bs}
    out = backbone.ping_pong_reconcile(beats, pool, rewrite_call=rewrite)
    assert out[0]["narration"] == "노릇하게 뒤집어 주면"
    assert not backbone.beat_action_mismatch(out[0])   # 이제 안 어긋남


def test_ping_pong_noop_when_all_match():
    beats = [{"beat_idx": 0, "narration": "바나나 써는",
              "primary": {"scene_desc": "써는", "action": "자르다"}}]
    out = backbone.ping_pong_reconcile(beats, [], rewrite_call=lambda bs: {})
    assert out == beats


def test_narration_seconds_from_syllables():
    # 한국어 초당 5.7음절 → 57자면 약 10초
    s = backbone.narration_seconds("가" * 57)
    assert 9.5 < s < 10.5


def test_clip_seconds_sums_primary_and_alternates():
    beat = {"primary": {"start": 0, "end": 3},
            "alternates": [{"start": 0, "end": 2}, {"start": 0, "end": 1.5}]}
    assert backbone.clip_seconds(beat) == 6.5


def test_length_status_over_under_ok():
    # 나레이션 10초인데 화면 3초 → over(화면이 모자라 대사가 넘침)
    over = {"narration": "가" * 57, "primary": {"start": 0, "end": 3}, "alternates": []}
    assert backbone.length_status(over) == "over"
    # 나레이션 3초, 화면 10초 → under(화면이 남음)
    under = {"narration": "가" * 17, "primary": {"start": 0, "end": 10}, "alternates": []}
    assert backbone.length_status(under) == "under"
    # 얼추 맞으면 ok
    ok = {"narration": "가" * 57, "primary": {"start": 0, "end": 10}, "alternates": []}
    assert backbone.length_status(ok) == "ok"


def test_fill_clips_to_cover_narration():
    # 화면 3초인데 대사 10초 필요 → 풀에서 같은 행위 클립 더 붙여 채움
    beat = {"narration": "가" * 57, "primary": {"start": 0, "end": 3, "action": "붓다", "video_id": "BB"},
            "alternates": []}
    pool = [{"video_id": "S1", "segments": [
        {"seg_id": "S1-1", "start": 0, "end": 4, "scene_desc": "붓는", "action": "붓다"},
        {"seg_id": "S1-2", "start": 0, "end": 4, "scene_desc": "또붓는", "action": "붓다"}]}]
    nb = backbone.fill_clips_to_cover(beat, pool)
    assert backbone.clip_seconds(nb) >= backbone.narration_seconds(beat["narration"]) * 0.9


def test_fill_story_beat_no_action_uses_balanced_broll():
    # 스토리형 나레이션(요리행위 없음) — action 매칭이 실패해도 소스 균형 B롤로 화면을
    # 채운다. 안 쓴 릴(s2)을 끌어와 한 릴 루프-반복을 막는 게 핵심(2026-07-21).
    beat = {"narration": "밤마다 야식 타령하는 남편 때문에 골치가 정말 아팠거든요",
            "primary": {"seg_id": "s1-13", "start": 0, "end": 0.7, "video_id": "s1"},
            "alternates": []}
    pool = [
        {"video_id": "s1", "segments": [{"seg_id": "s1-2", "start": 0, "end": 1.0, "scene_desc": "감자"}]},
        {"video_id": "s2", "segments": [
            {"seg_id": "s2-1", "start": 0, "end": 3, "scene_desc": "굽는 감자"},
            {"seg_id": "s2-2", "start": 3, "end": 6, "scene_desc": "담는 감자"}]},
    ]
    nb = backbone.fill_clips_to_cover(beat, pool)
    assert backbone.clip_seconds(nb) >= backbone.narration_seconds(beat["narration"]) * 0.9
    vids = [a["video_id"] for a in nb["alternates"]]
    assert "s2" in vids        # 안 쓴 릴에서 B롤을 끌어옴(반복 방지)


def test_fill_broll_prefers_same_source_for_coherence():
    # B롤은 primary와 같은 소스(=같은 요리) 조각을 먼저 붙인다 — 엉뚱한 타요리 조각(바나나
    # 커스터드 실사고) 방지. 같은 소스를 다 쓴 뒤에야 다른 소스로 넘어간다.
    beat = {"narration": "가" * 40,
            "primary": {"seg_id": "p", "start": 0, "end": 1, "video_id": "s1"}, "alternates": []}
    pool = [
        {"video_id": "s1", "segments": [{"seg_id": "s1-a", "start": 0, "end": 3, "scene_desc": "s1"}]},
        {"video_id": "s2", "segments": [{"seg_id": "s2-a", "start": 0, "end": 3, "scene_desc": "s2"}]},
    ]
    nb = backbone.fill_clips_to_cover(beat, pool)
    assert nb["alternates"][0]["video_id"] == "s1"   # 같은 소스(요리 일관성) 먼저


def test_broll_excludes_effect_clips():
    # 원본 효과 박힌 조각(has_effect)은 B롤 채움에서 빠진다(2026-07-21 19초 효과조각).
    beat = {"narration": "가" * 40,
            "primary": {"seg_id": "p", "start": 0, "end": 1, "video_id": "s1"}, "alternates": []}
    pool = [{"video_id": "s1", "segments": [
        {"seg_id": "eff", "start": 0, "end": 3, "scene_desc": "효과", "has_effect": True},
        {"seg_id": "clean", "start": 3, "end": 6, "scene_desc": "깨끗"}]}]
    nb = backbone.fill_clips_to_cover(beat, pool)
    ids = [a["seg_id"] for a in nb["alternates"]]
    assert "clean" in ids and "eff" not in ids   # 효과 조각 제외, 깨끗한 것만


def test_action_pool_excludes_effect_clips():
    pool = [{"video_id": "s1", "segments": [
        {"seg_id": "a1", "action": "붓다", "has_effect": True, "start": 0, "end": 2},
        {"seg_id": "a2", "action": "붓다", "start": 2, "end": 4}]}]
    got = backbone.pick_clips_for_action("붓다", pool)
    assert [c["seg_id"] for c in got] == ["a2"]   # 효과 조각 a1 제외


def test_fill_to_explicit_need_covers_actual_tts():
    # need(=실 TTS 길이)를 주면 나레이션 추정과 무관하게 그 길이까지 채운다(프리즈 뿌리 fix).
    beat = {"narration": "가" * 5,   # 추정으론 짧지만
            "primary": {"seg_id": "p", "start": 0, "end": 1.0, "video_id": "s1"}, "alternates": []}
    pool = [{"video_id": "s1", "segments": [
        {"seg_id": "s1-a", "start": 0, "end": 2.0, "scene_desc": "a"},
        {"seg_id": "s1-b", "start": 2.0, "end": 4.0, "scene_desc": "b"}]}]
    nb = backbone.fill_clips_to_cover(beat, pool, need=4.5)
    assert backbone.clip_seconds(nb) >= 4.5 * 0.9   # 실 TTS 4.5초까지 채움


def test_target_chars_from_clip():
    beat = {"primary": {"start": 0, "end": 10}, "alternates": []}
    # 10초 * 5.7 = 57자
    assert 54 <= backbone.target_chars(beat) <= 60


def test_ping_pong_trims_overflow_narration():
    # 대사가 화면보다 훨씬 김 + 풀에 채울 클립 없음 → trim_call로 대사 줄여 장면 안 넘게
    beats = [{"beat_idx": 0, "narration": "가" * 60,
              "primary": {"seg_id": "x", "start": 0, "end": 3, "action": "붓다"}, "alternates": []}]
    pool = []  # 채울 클립 없음
    trimmed = {}

    def trim(items):
        for it in items:
            trimmed[it["beat_idx"]] = it["target_chars"]
        return {it["beat_idx"]: "가" * it["target_chars"] for it in items}
    out = backbone.ping_pong_reconcile(beats, pool, rewrite_call=None, trim_call=trim)
    # 3초 화면 → 약 17자로 트림 요청됨
    assert 0 in trimmed and trimmed[0] <= 20
    assert backbone.length_status(out[0]) == "ok"


def test_dedup_and_balance_removes_repeat():
    # 두 비트가 같은 클립(s1-1) → 두번째는 안 쓴 같은 행위 클립으로 교체(반복 제거)
    beats = [
        {"beat_idx": 0, "narration": "붓기1", "primary": {"seg_id": "s1-1", "action": "붓다", "video_id": "s1"}},
        {"beat_idx": 1, "narration": "붓기2", "primary": {"seg_id": "s1-1", "action": "붓다", "video_id": "s1"}},
    ]
    pool = [{"video_id": "s0", "segments": [
        {"seg_id": "s0-3", "start": 0, "end": 2, "scene_desc": "다른 붓는", "action": "붓다"}]}]
    out = backbone.dedup_and_balance(beats, pool)
    ids = [b["primary"]["seg_id"] for b in out]
    assert len(set(ids)) == 2          # 반복 제거됨
    assert "s0-3" in ids               # 안 쓴 클립으로 교체


def test_dedup_prefers_underused_source():
    # 편중된 s1 대신 덜 쓴 소스(s0) 우선으로 교체
    beats = [
        {"beat_idx": 0, "narration": "a", "primary": {"seg_id": "s1-1", "action": "붓다", "video_id": "s1"}},
        {"beat_idx": 1, "narration": "b", "primary": {"seg_id": "s1-1", "action": "붓다", "video_id": "s1"}},
    ]
    pool = [
        {"video_id": "s1", "segments": [{"seg_id": "s1-9", "start": 0, "end": 2, "action": "붓다", "scene_desc": "s1붓"}]},
        {"video_id": "s0", "segments": [{"seg_id": "s0-9", "start": 0, "end": 2, "action": "붓다", "scene_desc": "s0붓"}]},
    ]
    out = backbone.dedup_and_balance(beats, pool)
    assert out[1]["primary"]["video_id"] == "s0"   # 덜 쓴 소스 우선


def test_generate_backbone_script_uses_flow_and_inventory():
    captured = {}

    def fake_call(prompt, schema):
        captured["prompt"] = prompt
        return {"beats": [
            {"narration": "우리만의 새 훅이에요", "seg_id": "BB-1"},
            {"narration": "여기서 계란을 부어요", "seg_id": "S1-1"}]}

    flow = [{"seg_id": "BB-1", "action": "자르다", "scene_desc": "써는", "seconds": 2},
            {"seg_id": "BB-2", "action": "붓다", "scene_desc": "붓는", "seconds": 3}]
    inv = [{"video_id": "BB", "seg_id": "BB-1", "action": "자르다", "scene_desc": "써는"},
           {"video_id": "S1", "seg_id": "S1-1", "action": "붓다", "scene_desc": "다른 붓는"}]
    beats = backbone.generate_backbone_script(flow, inv, 20, call=fake_call)
    assert [b["narration"] for b in beats] == ["우리만의 새 훅이에요", "여기서 계란을 부어요"]
    # 흐름과 인벤토리가 프롬프트에 실렸나
    assert "써는" in captured["prompt"] and "S1-1" in captured["prompt"]


def test_generate_backbone_script_drops_invented_segids():
    # 인벤토리에 없는 seg_id를 모델이 지어내면 드롭(없는 장면 요구 차단)
    fake = lambda p, s: {"beats": [{"narration": "진짜", "seg_id": "BB-1"},
                                    {"narration": "가짜장면", "seg_id": "ZZ-99"}]}
    inv = [{"video_id": "BB", "seg_id": "BB-1", "action": "자르다", "scene_desc": "써는"}]
    beats = backbone.generate_backbone_script([], inv, 20, call=fake)
    assert [b["seg_id"] for b in beats] == ["BB-1"]   # ZZ-99 드롭


def test_backbone_flow_extracts_skeleton():
    bb = {"video_id": "BB", "segments": [
        _seg("BB-1", scene_desc="바나나 써는", action="자르다"),
        _seg("BB-2", scene_desc="계란 붓는", action="붓다")]}
    flow = backbone.backbone_flow(bb)
    assert [f["action"] for f in flow] == ["자르다", "붓다"]
    assert flow[0]["scene_desc"] == "바나나 써는" and "narration" not in flow[0]  # 대사 아님


def test_scene_inventory_lists_all_available():
    sources = [
        {"video_id": "BB", "segments": [_seg("BB-1", action="붓다")]},
        {"video_id": "S1", "segments": [_seg("S1-1", action="자르다")]},
    ]
    inv = backbone.scene_inventory(sources)
    acts = {i["action"] for i in inv}
    assert acts == {"붓다", "자르다"} and len(inv) == 2


def test_pick_backbone_most_segments():
    sources = [
        {"video_id": "A", "segments": [_seg("A-1"), _seg("A-2")]},
        {"video_id": "B", "segments": [_seg("B-1"), _seg("B-2"), _seg("B-3"), _seg("B-4")]},
        {"video_id": "C", "segments": [_seg("C-1")]},
    ]
    assert backbone.pick_backbone(sources) == "B"


def test_pick_backbone_only_insta_youtube():
    # 백본 = 인스타/유튜브(한글 대본)만. 샤오홍슈는 세그 많고 댓글 많아도 서브 전용.
    sources = [
        {"video_id": "s0", "segments": [_seg("s0-1")]},
        {"video_id": "s1", "segments": [_seg(f"s1-{i}") for i in range(9)]},
    ]
    meta = {"s0": {"platform": "instagram", "comments": 10},
            "s1": {"platform": "xiaohongshu", "comments": 999}}
    assert backbone.pick_backbone(sources, meta=meta) == "s0"
    # 유튜브도 백본 가능
    meta2 = {"s0": {"platform": "youtube", "comments": 5},
             "s1": {"platform": "douyin", "comments": 999}}
    assert backbone.pick_backbone(sources, meta=meta2) == "s0"


def test_platform_of_url():
    assert backbone.platform_of("https://www.instagram.com/reel/DaFEF/") == "instagram"
    assert backbone.platform_of("https://youtube.com/shorts/abc") == "youtube"
    assert backbone.platform_of("https://youtu.be/abc") == "youtube"
    assert backbone.platform_of("https://www.xiaohongshu.com/explore/xx") == "xiaohongshu"
    assert backbone.platform_of("https://www.douyin.com/video/xx") == "douyin"
    assert backbone.platform_of("https://www.tiktok.com/@x/video/1") == "tiktok"
    assert backbone.platform_of("") == ""


def test_pick_backbone_forced_override():
    # 사장님이 메인 지정하면 그게 무조건 우선
    sources = [{"video_id": "s0", "segments": [_seg("s0-1")]},
               {"video_id": "s1", "segments": [_seg("s1-1")]}]
    meta = {"s0": {"platform": "instagram", "comments": 1},
            "s1": {"platform": "instagram", "comments": 999}}
    assert backbone.pick_backbone(sources, meta=meta, forced="s0") == "s0"


def test_pick_backbone_by_comments_among_eligible():
    sources = [{"video_id": "s0", "segments": [_seg("s0-1")]},
               {"video_id": "s1", "segments": [_seg("s1-1")]}]
    meta = {"s0": {"platform": "instagram", "comments": 50},
            "s1": {"platform": "instagram", "comments": 200}}
    assert backbone.pick_backbone(sources, meta=meta) == "s1"   # 댓글 많은 것


def test_pick_backbone_none_on_empty():
    assert backbone.pick_backbone([]) is None


def test_order_by_backbone_sorts_body_by_backbone_time():
    # body 비트 3개, 백본(BB) 화면이 시간 뒤죽박죽 → 백본 start 순으로 재정렬. 꼬리(CTA)는 고정.
    beats = [
        {"beat_idx": 0, "narration": "결과", "primary": {"seg_id": "BB-9", "start": 9, "end": 10, "video_id": "BB"}},
        {"beat_idx": 1, "narration": "재료", "primary": {"seg_id": "BB-1", "start": 1, "end": 2, "video_id": "BB"}},
        {"beat_idx": 2, "narration": "조리", "primary": {"seg_id": "BB-5", "start": 5, "end": 6, "video_id": "BB"}},
        {"beat_idx": 3, "narration": "댓글 남겨주세요", "primary": {"seg_id": "X-1", "start": 0, "end": 1, "video_id": "X"}},
    ]
    out = backbone.order_by_backbone(beats, "BB")
    # 앞 3개(movable body) 화면이 백본 start 오름차순(1,5,9), 꼬리(CTA)는 고정
    starts = [b["primary"]["start"] for b in out[:3]]
    assert starts == [1, 5, 9]
    assert out[3]["primary"]["seg_id"] == "X-1"   # 꼬리 고정
    # 나레이션(대사)은 제자리 — 화면만 시간순으로
    assert [b["narration"] for b in out] == ["결과", "재료", "조리", "댓글 남겨주세요"]


def test_order_by_backbone_keeps_action_fixed():
    # ping_pong이 고친(action_fixed) 비트는 순서 재배치에서 제외(앵커)
    beats = [
        {"beat_idx": 0, "narration": "썰기", "action_fixed": True,
         "primary": {"seg_id": "S1-9", "start": 9, "end": 10, "video_id": "S1"}},
        {"beat_idx": 1, "narration": "재료", "primary": {"seg_id": "BB-1", "start": 1, "end": 2, "video_id": "BB"}},
        {"beat_idx": 2, "narration": "조리", "primary": {"seg_id": "BB-5", "start": 5, "end": 6, "video_id": "BB"}},
    ]
    out = backbone.order_by_backbone(beats, "BB")
    assert out[0]["primary"]["seg_id"] == "S1-9"   # action_fixed 그대로


def test_pick_clips_excludes_backbone_video():
    pool = [{"video_id": "BB", "segments": [_seg("BB-1", action="붓다")]},
            {"video_id": "S1", "segments": [_seg("S1-1", action="붓다")]}]
    clips = backbone.pick_clips_for_action("붓다", pool, exclude_video="BB")
    assert len(clips) == 1 and clips[0]["video_id"] == "S1"
