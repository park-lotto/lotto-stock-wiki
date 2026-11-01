"""숏템리폿 회원 길 동일화(동일화명세 §2-6): 판 길이·B1~B6, 흥미 이음 관문, 원본 전체 판정, 말 없는 원본."""
import pytest

from tools.calcopy.hybrid import flow as F, rules as RU, script_audit, styles

V = "숏템리폿판"


def _st(**kw):
    return {"version": V, "fmt": "해외원본형", "log": [], "tries": {}, "bench": {"title": "t", "sheet": "b.jpg"}, "product_shots": ["p.jpg"],
            "origin": {"files": [{"name": "a.mp4", "dur": 20}]}, "origins": [{"id": "a", "how": "렌즈 같은 촬영분", "files": [{"name": "a.mp4", "dur": 20}]}],
            "coupang_cands": [{"product_id": "1", "image": "http://i/1.jpg"}, {"product_id": "2", "image": "http://i/2.jpg"}], **kw}


def test_style_loads_with_hybrid_settings():
    s = styles.load(V)                     # packs ↔ 옛 칸 일치 검사를 통과해야 한다
    assert (s["length"]["min"], s["length"]["max"]) == (30, 42)
    est = next(a for a in s["script"]["audit"] if a["kind"] == "est_length")
    assert (est["min"], est["max"]) == (30, 42)      # 판 길이와 대본 관문 길이는 같이 움직인다
    assert all(f"B{n}" in " ".join(s["script"]["brief"]) for n in range(1, 7))
    assert "흥미 이음" in s["script"]["research"] and s["script"]["interest_gate"] is True and s["material_n"] == [3, 6]


@pytest.mark.parametrize("a,b,v,ok", [("큰 물병", "4리터", "같음", True), ("큰 물병", "평범", "약함", False), ("큰 물병", "", "같음", False),
                                      ("", "4리터", "같음", False), ("큰 물병", "x", "없음", False)])
def test_interest_gate_owner(a, b, v, ok):
    assert (not RU.interest_gate(a, b, v)) is ok


def _done(st, pid="1"):
    return F.ph_product_done(st, {}, {"product_same": {"product_id": pid, "name": "n", "category": "생활"}}, {})


def test_gate_runs_after_product_done():
    st = _st()
    r = _done(st)
    assert r["then"] == "interest_look" and r["do"][0]["items"][0]["image"] == "http://i/1.jpg"
    r = F.ph_interest_look(st, {"isheet": {"file": "s.jpg"}}, {}, {})
    assert r["then"] == "interest_got" and "신기한 점" in r["review"][0]["ask"]


def test_same_goes_on_and_weak_moves_to_next_candidate():
    st = _st()
    _done(st)
    F.ph_interest_look(st, {}, {}, {})
    r = F.ph_interest_got(st, {}, {"interest_0": {"원본흥미": "큰 물병", "뒤흥미": "평범", "판정": "약함"}}, {})
    assert r == {"goto": "best"} and [c["product_id"] for c in st["coupang_cands"]] == ["2"] and "product" not in st and "큰 물병" in st["interest_note"]
    _done(st, "2")
    F.ph_interest_look(st, {}, {}, {})
    r = F.ph_interest_got(st, {}, {"interest_1": {"원본흥미": "큰 물병", "뒤흥미": "4리터", "판정": "같음", "근거": "사진"}}, {})
    assert r == {"goto": "reviews"} and st["interest"]["판정"] == "같음"


def test_three_misses_stop_the_topic():
    st = _st(interest_tried=["7", "8"], _interest_id="interest_2", product={"product_id": "1"})
    with pytest.raises(F._Stop) as e:
        F.ph_interest_got(st, {}, {"interest_2": {"원본흥미": "a", "뒤흥미": "b", "판정": "없음"}}, {})
    assert e.value.final and F.member_ok(e.value.why)


def test_given_product_skips_gate():
    st = _st(given_cands=[{"product_id": "1"}])
    assert F.ph_product_done(st, {}, {"given_same": {"product_id": "1", "name": "n", "category": "생활"}}, {}) == {"goto": "reviews"}


def test_other_foreign_style_has_no_gate():
    st = _st(version="대충판")
    F._style, keep = (lambda v: {"script": {}}), F._style
    fmt, F._fmt = F._fmt, (lambda s: "해외원본형")
    try:
        assert _done(st) == {"goto": "reviews"}
    finally:
        F._style, F._fmt = keep, fmt


def test_verify_question_asks_whole_video_foreign_only():
    st = _st(_verify={"keep": ["a"], "chk": ["a"]})
    r = F.f_of_verify(st, {"vs_0": {"file": "v.jpg"}}, {}, {})
    assert "영상 **전체**가 해외 원본" in r["review"][0]["ask"] and "리뷰" in F.OF_VERIFY_WHOLE
    fmt, F._fmt = F._fmt, (lambda s: "자막노래형")
    try:
        st["_verify"] = {"keep": ["a"], "chk": ["a"]}
        assert "영상 **전체**" not in F.f_of_verify(st, {"vs_0": {"file": "v.jpg"}}, {}, {})["review"][0]["ask"]
    finally:
        F._fmt = fmt


MD = "결론 출처 원음 없음 사실 금지 확인 못"


def test_empty_transcript_passes_without_spans():
    st = _st(product={"name": "n"}, _fwords={"a.mp4": {"words": [], "from": "받아쓰기"}})
    r = F.f_research_got(st, {}, {}, {})
    assert "받아쓰기가 비었다" in r["review"][0]["ask"] and "spans" not in r["review"][0]["need"]
    r = F.f_research_check(st, {}, {"research": {"조사_md": MD, "keywords": ["k"], "queries": ["q"]}}, {})
    assert r["then"] == "f_material" and st["research"]["spans"] == []
    assert "원음 줄(kind orig) 없이" in F._foreign_script_ctx(st)


@pytest.mark.parametrize("w", [{"words": [[1.0, "wow"]]}, {"words": [], "error": "ffmpeg"}])
def test_spans_still_required_when_speech_or_asr_failed(w):
    st = _st(product={"name": "n"}, _fwords={"a.mp4": w})
    r = F.f_research_check(st, {}, {"research": {"조사_md": MD, "keywords": ["k"], "queries": ["q"], "spans": []}}, {})
    assert "spans" in str(r.get("reject")) and r["then"] == "f_research_check"


def test_research_question_carries_style_and_interest():
    st = _st(product={"name": "n"}, interest={"판정": "같음", "원본흥미": "큰 물병"}, _fwords={"a.mp4": {"words": [[1, "x"]]}})
    ask = F.f_research_got(st, {}, {}, {})["review"][0]["ask"]
    assert "이 프리셋의 조사" in ask and "큰 물병" in ask


def test_same_product_still_fetches_back_material():
    st = _st(product={"mode": "exact", "name": "n"})
    assert F._alt_material_needed(st) and F._material_n(st) == (3, 6)
