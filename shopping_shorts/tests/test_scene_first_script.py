# -*- coding: utf-8 -*-
"""장면-먼저 이븐쇼핑 대본(관제 카드 043) — 판단 주인 scene_first_script.make_drafts · 렌더 쪽 표식 mix_pipeline keep_cuts."""
from shopping_shorts import mix_pipeline as mp
from shopping_shorts import scene_first_script as sfs


def _src(vid, n, secs=3.0):
    return {"video_id": vid, "segments": [
        {"seg_id": "%s-%d" % (vid, k), "start": k * secs, "end": (k + 1) * secs, "scene_desc": "장면 %s-%d" % (vid, k),
         "shot_role": "실증"} for k in range(n)]}


SRCS = [_src("a", 6), _src("b", 6)]
BOARD = {"product": "열수축 필름", "slots": [
    {"slot": 0, "cuts": ["a-0"], "secs": 2.5, "shows": "제품"},
    {"slot": 1, "cuts": ["a-1", "a-2"], "secs": 5.0, "shows": "여러 컷"},
    {"slot": 2, "cuts": ["a-3"], "secs": 2.5, "shows": "제품 정체"},
    {"slot": 3, "cuts": ["b-0", "b-1"], "secs": 5.0, "shows": "드라이어로 밀착"},
    {"slot": 4, "cuts": ["b-2"], "secs": 3.0, "shows": "상자 포장"},
    {"slot": 5, "cuts": ["b-3", "b-4"], "secs": 4.0, "shows": "벗기면 새것"},
    {"slot": 6, "cuts": ["a-4"], "secs": 2.0, "shows": "정리된 신발"}]}
LINES = {"lines": [
    {"slot": 0, "text": "신발 지키는 천재의 발명품."},
    {"slot": 1, "text": "최근 딱 봤을 때는 비닐 같은 게 난리라는데"},
    {"slot": 2, "text": "열수축 필름."},
    {"slot": 3, "text": "열만 쐬면 착 붙는다는 거."},
    {"slot": 4, "text": "상자까지 밀봉된다고."},
    {"slot": 5, "text": "벗기면 새것이라는 거."},
    {"slot": 6, "text": "싹 지켜 준다고."}]}


def _fake(answers):
    calls = []

    def call(prompt, schema):
        calls.append(prompt)
        return answers[len(calls) - 1] if len(calls) - 1 < len(answers) else {}
    return call, calls


def _run(monkeypatch, answers, srcs=SRCS):
    monkeypatch.setattr(sfs, "_visual_sources", lambda job, seed_text="": srcs)
    call, calls = _fake(answers)
    note = {}
    drafts, why = sfs.make_drafts({"extract": {}}, call=call, note=note)
    return drafts, why, calls, note


def test_장면표가_먼저_불리고_글자예산은_장면길이에서(monkeypatch):
    drafts, why, calls, note = _run(monkeypatch, [BOARD, LINES])
    assert why == "" and len(drafts) == 1
    assert "화면부터" in calls[0] and "대사를 쓴다" in calls[1]          # 순서: 장면표 → 대사
    cps = sfs._cps()
    for b in note["board"]:
        assert b["chars"] == int(b["secs"] * cps * 0.95)                # 글자 수 = 장면 초에서
    assert "약 %d자" % note["board"][0]["chars"] in calls[1]


def test_신호어는_코드가_붙이고_초안은_장면먼저_표식(monkeypatch):
    drafts, _, _, _ = _run(monkeypatch, [BOARD, LINES])
    d = drafts[0]
    texts = [b["text"] for b in d["beats"]]
    assert texts[2].startswith("이건 바로 ") and texts[3].startswith("이게 말도 안 되는게 ")
    assert texts[4].startswith("심지어 ") and texts[5].startswith("근데 진짜 충격적인 포인트는 ")
    assert d["scene_cut"] is True and d["made_by"] == "장면먼저"
    assert [b["src_segs"] for b in d["beats"]][3] == ["b-0", "b-1"]     # 고른 컷 그대로 3단계로


def test_칸길이는_가장짧은컷_곱하기_컷수로_잘린다(monkeypatch):
    srcs = [_src("a", 6), {"video_id": "b", "segments": [
        {"seg_id": "b-0", "start": 0, "end": 3.0}, {"seg_id": "b-1", "start": 3.0, "end": 4.2},
        {"seg_id": "b-2", "start": 4.2, "end": 7.2}, {"seg_id": "b-3", "start": 7.2, "end": 10.2},
        {"seg_id": "b-4", "start": 10.2, "end": 13.2}]}]
    drafts, why, calls, note = _run(monkeypatch, [BOARD, LINES], srcs=srcs)
    b3 = next(b for b in note["board"] if b["slot"] == 3)
    assert abs(b3["secs"] - 2.4) < 1e-6                                 # 1.2초 컷 × 2 — 넘치면 같은 장면 반복
    assert any("가장 짧은 컷" in p for p in note["problems"])
    assert b3["secs"] < 3.5 and any("하한" in p for p in note["problems"])


def test_화면보다_긴줄은_다시쓰고_그래도_길면_안을_안낸다(monkeypatch):
    long = dict(LINES)
    long = {"lines": [dict(x) for x in LINES["lines"]]}
    long["lines"][4]["text"] = "상자까지 방수로 밀봉되고 서류도 책도 습기 없이 오래오래 보관된다고"
    drafts, why, calls, _ = _run(monkeypatch, [BOARD, long, long])      # 다시 쓰기도 그대로 긴 답
    assert len(calls) == 3 and "칸4" in calls[2]                        # 넘친 줄만 다시 쓰기 1회
    assert drafts == [] and "고조2" in why


def test_마무리_어미가_틀리면_다시쓴다(monkeypatch):
    bad = {"lines": [dict(x) for x in LINES["lines"]]}
    bad["lines"][6]["text"] = "깔끔하게 정리해 줌."
    fixed = {"lines": [{"slot": 6, "text": "싹 지켜 준다고."}]}
    drafts, why, calls, _ = _run(monkeypatch, [BOARD, bad, fixed])
    assert why == "" and drafts[0]["beats"][6]["text"] == "싹 지켜 준다고."
    assert "'라는데/준다고/다고'로 끝" in calls[2]


def test_한줄에_문장이_둘이면_안을_안낸다(monkeypatch):
    two = {"lines": [dict(x) for x in LINES["lines"]]}
    two["lines"][4]["text"] = "상자도. 된다고."
    drafts, why, _, _ = _run(monkeypatch, [BOARD, two, two])
    assert drafts == [] and "문장2개" in why                            # 3단계 상속이 줄 수로 짝짓는다


def test_없는컷_중복컷은_버리고_칸이_비면_안을_안낸다(monkeypatch):
    sb = {"product": "x", "slots": [dict(s) for s in BOARD["slots"]]}
    sb["slots"][2] = {"slot": 2, "cuts": ["a-0", "zz-9"], "secs": 2.5, "shows": ""}   # a-0 은 훅이 이미 씀
    drafts, why, calls, note = _run(monkeypatch, [sb])
    assert drafts == [] and "칸2" in why and len(calls) == 1


def _seg(vid, s, e):
    return {"video_id": vid, "start": s, "end": e, "seg_id": "%s:%s" % (vid, s)}


def test_keep_cuts는_컷을_안줄이고_구절맞춤_홀드를_끈다():
    beats = [
        {"beat_idx": 0, "role": "훅", "narration": "훅", "primary": _seg("v1", 0, 3)},
        {"beat_idx": 1, "role": "고조1", "narration": "착 붙는다는 거", "target_seconds": 3.8,
         "primary": _seg("v1", 3, 5), "alternates": [_seg("v2", 0, 2)]},
        {"beat_idx": 2, "role": "미끼", "narration": "난리라는데", "target_seconds": 4.5,
         "primary": _seg("v1", 5, 7), "alternates": [_seg("v2", 2, 4), _seg("v3", 0, 2)]}]
    plan = {"beats": [dict(b) for b in beats]}
    mp._trim_for_cut_rhythm(plan, keep_cuts=True)
    assert [len(b.get("alternates") or []) for b in plan["beats"]] == [0, 1, 2]     # 넘긴 컷 그대로
    assert all(b["phrase_sync"] is False for b in plan["beats"])
    assert [b["cut_rhythm"]["hold"] for b in plan["beats"]] == [False, False, False]
    # 종전 경로는 그대로(회귀 0): 구절맞춤 켬 · 고조1 결과 줄 홀드 → 컷 1개 · 4.5초 미끼 → 2컷
    old = {"beats": [dict(b) for b in beats]}
    mp._trim_for_cut_rhythm(old)
    assert [len(b.get("alternates") or []) for b in old["beats"]] == [0, 0, 1]
    assert all(b["phrase_sync"] is True for b in old["beats"])
    assert [b["cut_rhythm"]["hold"] for b in old["beats"]] == [True, True, False]


def test_keep_cuts면_상속편성이_옆컷을_이어붙이지_않는다():
    """장면-먼저는 칸 길이·컷 수를 2단계가 정했다 — 상속의 이어붙이기(컷당 2.2초만 셈)·채우기가 컷을 더하면 안 된다
    (실측 job sfe8a8b848fd: 넘긴 컷 11개에 6개가 덧붙었다)."""
    from shopping_shorts import edit_plan as EP
    src = [{"video_id": "s0", "segments": [
        {"seg_id": "s0-%d" % i, "start": float(i * 3), "end": float(i * 3 + 3), "text": "말", "scene_desc": "화면%d" % i,
         "shot_role": "사용중"} for i in range(10)]}]
    script = "이건 바로 열수축 필름이라는 거\n이게 말도 안 되는게 드라이기 열만으로 신발에 착 붙는다는 거"
    srcs = [{"role": "공개", "seg": "s0-2", "segs": ["s0-2"]}, {"role": "고조1", "seg": "s0-5", "segs": ["s0-5", "s0-7"]}]
    keep = EP.build_inherit_plan(src, script, srcs, keep_cuts=True)
    ids = [[b["primary"]["seg_id"]] + [a["seg_id"] for a in b.get("alternates") or []] for b in keep["beats"]]
    assert ids == [["s0-2"], ["s0-5", "s0-7"]]
    old = EP.build_inherit_plan(src, script, srcs)                        # 종전(회귀 0): 대사가 길면 이어 붙인다
    old_ids = [[b["primary"]["seg_id"]] + [a["seg_id"] for a in b.get("alternates") or []] for b in old["beats"]]
    assert sum(len(x) for x in old_ids) > 3
