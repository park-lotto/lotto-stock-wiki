"""지침서 작가(관제 241) — guide_writer 검수·1회 재작성·정보형 관문, storyboard 연결(카드·보드 모양)."""
from shopping_shorts import guide_writer as gw
from shopping_shorts import storyboard as sb

SEGS = {"a1": 3.0, "a2": 3.0, "a3": 3.0, "a4": 3.0, "a5": 3.0, "a6": 3.0, "a7": 3.0, "a8": 3.0, "a9": 3.0}
TEXTS = {k: "창문 유리에 롤러로 페인트를 바르자 뿌옇게 변한다" for k in SEGS}


def _slots(lines, cta=True):
    out = [{"slot": s, "line": t, "ids": ["a%d" % (i + 1)]} for i, (s, t) in enumerate(lines)]
    if cta:
        out.append({"slot": "cta", "line": "창문 시선 가리고 싶으시면 댓글에 유리 남겨주세요", "ids": ["a9"]})
    return out


GOOD = [("hook", "엄마가 욕실 창 보시더니 유리 언제 바꿨냐고 물으시더라고요"), ("situation", "전셋집이라 시트지는 자국 남을까 봐 못 붙이고 있었거든요"),
        ("pain", "근데 엄마 눈엔 새로 맞춘 불투명 유리로 보였나 봐요"), ("reveal", "바로 유리창에 칠하는 젖빛 페인트예요"),
        ("howto", "테이프만 두르고 롤러로 한 번 밀었는데"), ("effect", "햇빛은 그대로 들고 바깥만 김 서린 거울처럼 흐려지더라고요"),
        ("extra", "심지어 이사 갈 땐 끝을 잡고 당기면 한 장으로 벗겨진대요"), ("end", "엄마는 지금도 유리값 아끼지 말라고 잔소리하세요")]


def test_check_catches_length_ban_number_ids():
    bad = _slots([("hook", "짧다")] * 2)
    why = gw.check(bad, "A", "화면")
    assert any("길이" in w for w in why) and any("칸" in w for w in why)
    why = gw.check(_slots([(s, t.replace("흐려지더라고요", "버려진 듯 흐려지더라고요 3초")) for s, t in GOOD]), "A", "화면")
    assert any("버려진" in w for w in why) and any("숫자 3" in w for w in why)
    s = _slots(GOOD)
    s[0]["ids"] = []
    assert any("ids" in w for w in gw.check(s, "A", "화면"))
    assert gw.check(_slots(GOOD), "A", "화면") == [], gw.check(_slots(GOOD), "A", "화면")


def test_write_retries_once_with_reasons():
    calls = []

    def call(prompt, schema):
        calls.append(prompt)
        if len(calls) == 1:
            return {"mold": "A2", "slots": _slots([("hook", "짧다")])}
        return {"mold": "A2", "first_line_style": GOOD[0][1], "slots": _slots(GOOD)}
    r, left, style, note = gw.write(call, "g:expA", "홈템", "a1(3초): 창문", [], [], "", scene_text="창문")
    assert len(calls) == 2 and "직전 답이 코드 검수에 걸렸다" in calls[1]
    assert left == [] and style == "A" and r["guide_tries"] == 2


def test_info_style_gate_falls_back_to_experience():
    seen = {}

    def call(prompt, schema):
        seen["p"] = prompt
        return {"mold": "A1", "slots": _slots(GOOD)}
    r, left, style, note = gw.write(call, "g:infoB", "홈템", "a1(3초): 창문", [], [], "", scene_text="창문에 바르는 페인트")
    assert style == "A" and "관문" in note and "스타일 A(체험형)" in seen["p"]
    # 이야기 사실이 2줄 이상이면 정보형 그대로 — 씨앗·참고 대본이 실린다
    r, left, style, note = gw.write(call, "g:infoB", "홈템", "a1", [], [], "", scene_text="개발자가 만든 제품\n방송 다음 날 7분 만에 팔렸다")
    assert style == "B" and "씨앗 대본" in seen["p"]


def test_families_cards_only_when_switch_on(monkeypatch):
    monkeypatch.setattr(sb, "_ro", lambda p: None)
    monkeypatch.setattr(sb, "_families", lambda db: [])
    assert sb.families("x") == []
    ids = [f["id"] for f in sb.families("x", guide=True)]
    assert ids == ["g:expA", "g:infoB"]


def test_board_guide_same_shape_as_board(monkeypatch):
    def fake(prompt, schema, note=None, vertex=True):
        if schema is sb.S4:
            return {"fix": []}
        return {"mold": "A2", "first_line_style": GOOD[0][1], "slots": _slots(GOOD) + [{"slot": "end", "line": "없는 조각", "ids": ["zz"]}][:0]}
    monkeypatch.setattr(sb.sg, "_call_json", fake)
    b = sb._board_guide("g:expA", {"kind": "홈템", "missing": []}, "a1(3초): 창문", [], SEGS, TEXTS, jkey="j:g:expA")
    for k in ("names", "slots", "check", "fixed", "left_flags", "star_missing", "role_fixed", "role_left", "extra", "extra_missing", "sig_key", "sig_yt"):
        assert k in b, k
    assert b["names"] == ["체험형(지침서)"] and len(b["slots"]) == 9 and b["slots"][-1].get("cta_mark")
    assert all(set(s["ids"]) <= set(SEGS) for s in b["slots"]) and b["guide"]["left"] == []
    assert len(b["check"]) == len(b["slots"])


def test_scene_seconds_and_mold_exclusion():
    why = gw.check([{"slot": "cta", "line": "욕실 사생활 가리고 싶으시면 댓글에 페인트 남겨주세요", "ids": ["a"]}], "A", "", segs={"a": 2.0})
    assert any("장면이 모자람" in w for w in why)
    sec = gw.section("guide_home", "A")
    assert "3. 첫 줄 틀 사전" in sec and "3. 첫 줄 틀 사전" not in gw._no_molds(sec) and "4. 블록 배치" in gw._no_molds(sec)


# 실제 버텍스가 만든 지침서 보드(2026-10-20 라이브 함수 시험, 유리 페인트 재료) — 확정 → 3단계 상속 계획(렌더·캡컷이 같이 쓰는 편집 계획)까지
LIVE_BOARD = [
 {
  "slot": "hook",
  "line": "저희 아내가 창문에 이런 걸 해놨는데 보는 사람마다 깜짝 놀라더라고요",
  "ids": [
   "s28",
   "s29",
   "s31"
  ]
 },
 {
  "slot": "situation",
  "line": "얼마 전에 놀러 온 친구가 유리 새로 바꿨냐고 묻는 거예요",
  "ids": [
   "s15",
   "s16",
   "s19"
  ]
 },
 {
  "slot": "pain",
  "line": "이웃집과 너무 가까워서 매번 커튼 치는 게 답답했거든요",
  "ids": [
   "s17",
   "s18"
  ]
 },
 {
  "slot": "reveal",
  "line": "근데 이건 쓱 칠해주면 젖빛으로 바뀌는 페인트예요",
  "ids": [
   "s14",
   "s40",
   "s43"
  ]
 },
 {
  "slot": "howto",
  "line": "테이프 붙이고 롤러로 밀면 금방 가려지더라고요",
  "ids": [
   "s20",
   "s22",
   "s25"
  ]
 },
 {
  "slot": "effect",
  "line": "은은하게 빛만 환하게 들어와요",
  "ids": [
   "s26",
   "s38",
   "s39"
  ]
 },
 {
  "slot": "extra",
  "line": "심지어 나중에 알코올을 뿌려 긁어내면 싹 지워져요",
  "ids": [
   "s10",
   "s11",
   "s12"
  ]
 },
 {
  "slot": "end",
  "line": "친구는 아직도 돈 들여 특수 유리를 깐 줄 알더라고요",
  "ids": [
   "s36",
   "s50"
  ]
 },
 {
  "slot": "cta",
  "line": "욕실 사생활 가리고 싶으시면 댓글에 페인트 남겨주세요",
  "ids": [
   "s09"
  ],
  "cta_mark": True
 }
]


def test_live_guide_board_flows_to_inherit_plan():
    from shopping_shorts import edit_plan, story_writer, ai_match
    ids = sorted({c for s in LIVE_BOARD for c in s["ids"]}, key=lambda x: int(x[1:]))
    segs = [{"seg_id": c, "video_id": "v", "start": i * 2.0, "end": i * 2.0 + 2.0, "shot_role": "사용중", "scene_desc": c,
             "change": "", "text": "", "is_key": False} for i, c in enumerate(ids)]
    conv = story_writer.storyboard_to_beat_sources(LIVE_BOARD)
    assert len(conv["script"].splitlines()) == len(LIVE_BOARD) == len(conv["beat_sources"])
    assert all(x["pinned"] for x in conv["beat_sources"])
    plan = edit_plan.build_inherit_plan([{"video_id": "v", "segments": segs}], conv["script"], conv["beat_sources"])
    assert plan and len(plan["beats"]) == len(LIVE_BOARD)
    got = [[r["seg_id"] for r in [bt["primary"]] + list(bt.get("alternates") or [])] for bt in plan["beats"]]
    assert got == [s["ids"] for s in LIVE_BOARD], got
    assert all(ai_match.is_pinned(bt) for bt in plan["beats"])


def test_no_reference_names_in_live_files_or_prompts():
    """숏템 금지 이름(참고 작가·레퍼런스 채널 이름) — 지침서·작가 코드·버텍스 프롬프트 어디에도 0(2026-10-21 사장님 '절대 금지')."""
    import os
    import re
    ban = re.compile("|".join(["노" + "바", "두유" + "노", "홈디" + "노", "homedesign" + "note", "hd" + "n[AB]", "이븐" + "쇼핑", "even" + "shopping"]))
    here = os.path.dirname(gw.__file__)
    files = [gw.__file__] + [os.path.join(gw.GUIDES, f) for f in os.listdir(gw.GUIDES)]
    for f in files:
        assert not ban.search(open(f, encoding="utf-8").read()), f
    for k in gw.STYLES:
        assert not ban.search(gw.build(k, "홈템", "a1(3초): x", [], [], "")), k
        assert not ban.search(gw.STYLES[k]["name"]), k
    assert here
