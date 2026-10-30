"""10-30 썰템쇼 회원 시험 6차: '화자 대사 썰형'인데 「화자 : 대사」 줄이 0개 — 판에 '옵션 0~3' 으로만 있고 만들 수단(보이는 글·읽는 글 가르기)이 없었다.
줄 who 칸 → 자막 첫 덩어리 앞 '<화자> : '(render_bench.who_prefix 한 곳), 목소리는 tts(대사)만. 대본 검사 speaker_lines(판 1~3)·cap_chars·자동 나눔이 같은 자로 센다.
실데이터 재현: 6차 작업 폴더 복사본(C:/t/who_chk) L3 에 who 를 넣고 렌더 단계만 → 5.2초 프레임에 '아웃백 : 아웃백 전용이라'(벤치 jECu '벨 : …' 꼴)."""
from tools.calcopy.hybrid import render_bench as RB, rules as RU, script_audit as SA


def _S(who=None):
    L = {"id": "L3", "kind": "tts", "tts": "우리 매장 전용이라 절대 안 팜.", "caps": ["우리 매장 전용이라", "절대 안 팜"]}
    if who:
        L["who"] = who
    return {"title_lines": [], "lines": [{"id": "L1", "kind": "tts", "tts": "첫 줄.", "caps": ["첫 줄"]}, L]}


def test_who_shows_only_on_first_chunk_and_not_in_tts():
    S = _S("아웃백")
    T = RB.timeline(S, {"cuts": {"L1": [{"src": "a.mp4", "ss": 0}], "L3": [{"src": "a.mp4", "ss": 1}]}}, {"cps_target": 7.0, "timing": {}}, None, None)
    rows = [r for r in T["rows"] if r["line"] == "L3"]
    assert rows[0]["text"] == "아웃백 : 우리 매장 전용이라" and rows[1]["text"] == "절대 안 팜"
    assert "아웃백" not in S["lines"][1]["tts"]
    assert RB.who_prefix(S["lines"][0], 0) == ""


def test_speaker_lines_rule_counts_who():
    r = {"kind": "speaker_lines", "min": 1, "max": 3, "who_max": 6}
    ok0, why0 = SA.rule_check(r, _S(), {})
    ok1, _ = SA.rule_check(r, _S("아웃백"), {})
    bad, why = SA.rule_check(r, _S("아주아주긴화자이름"), {})
    assert not ok0 and "0개" in why0 and ok1 and not bad


def test_cap_chars_and_split_count_the_who_prefix():
    st = {"caption": {"chunk_max_chars": 10}, "script": {"audit": [{"kind": "cap_chars", "max": "chunk_max_chars", "of": "tts"}]}}
    S = _S("한국업체")
    ok, why = SA.rule_check(st["script"]["audit"][0], S, st)
    assert not ok and "한국업체 : " in why                      # 보이는 글('화자 : ' 포함)로 잰다
    RU.caps_split_fix(S, st)
    ok, why = SA.rule_check(st["script"]["audit"][0], S, st)
    assert ok, why
