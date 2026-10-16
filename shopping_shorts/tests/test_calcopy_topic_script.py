"""소재 찾기(topic_find)·대본 쓰기(script_engine) 엔진 — LLM·네트워크는 가짜(고정 답). 실제 프리셋(썰풀다 A·yummyknow) 규칙을 읽는다.

사보타주로 확인한 것(2026-10-16): 역할 칸 검사·근거 검사·말투 검사·겹침 벌점을 하나씩 끄면 해당 시험이 깨진다.
"""
import json
from pathlib import Path

import pytest

from tools.calcopy import style_writer as SW
from tools.calcopy.engine import script_engine as E
from tools.calcopy.engine import topic_find as T

ROOT = Path(__file__).resolve().parents[2]
SSEOL = "channel/sseolpulda/preset/A_흰바탕창/창아래_검정"
pytestmark = pytest.mark.skipif(not (ROOT / SSEOL / "manifest.json").exists(), reason="썰풀다 프리셋 없음")


class FakeLLM:
    """tag → 답(dict 또는 함수(prompt)→dict). 부른 순서·프롬프트를 남긴다. TF.LLM 과 같은 꼴(.calls)."""

    def __init__(self, answers):
        self.answers, self.calls, self.prompts = answers, [], {}

    def __call__(self, prompt, tag):
        self.calls.append({"tag": tag})
        self.prompts[tag] = prompt
        a = self.answers.get(tag)
        if a is None:
            return None, "가짜: 답 없음"
        return (a(prompt) if callable(a) else json.loads(json.dumps(a))), None

    @property
    def tags(self):
        return [c["tag"] for c in self.calls]


# 썰풀다 6칸 — 줄 길이·말끝·겹침 검사를 통과하는 줄(ZdeZ 통과편과 같은 꼴, 글자 수는 원본 ±15% 안)
GOOD = [
    {"fn": "발견 맥락", "text": "해외 영상에서 다들 하도 신기하다길래", "facts": ["b1"]},
    {"fn": "의심", "text": "솔직히 다 광고라 생각했는데", "facts": ["b2"]},
    {"fn": "반전 시연", "text": "어디든 툭 갖다 대면", "facts": ["f1"]},
    {"fn": "결과 과장", "text": "온 집안이 초대형 우퍼로 둔갑함;;", "facts": ["f1"]},
    {"fn": "감탄", "text": "소리 퍼지는 게 예술이네", "facts": ["b3"]},
    {"fn": "인정·댓글유도", "text": "이거 은근 탐나는 거 인정?", "facts": ["b3"]},
]


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    # 폭 추정은 to_frame 글꼴에 기대 다른 담당 작업으로 흔들린다 → 글자 수 기준으로 시험(폭 경로는 실측에서 본다)
    monkeypatch.setattr(SW, "width_estimator", lambda *_: (_ for _ in ()).throw(RuntimeError("시험: 폭 추정 끔")))
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps({"f1": {"text": "금속 원판을 물체에 대면 그 물체가 울려 스피커가 된다", "url": "https://example.com/a"}}, ensure_ascii=False), encoding="utf-8")
    bench = tmp_path / "c1.md"
    bench.write_text("# 벤치\n\n## 포인트\n\n- [b1] (hook) 해외에서 퍼진 바이럴 가젯 — v_x\n- [b2] (twist) 다들 광고인 줄 의심 — v_y\n"
                     "- [b3] (reaction) 댓글: 갖고 싶다는 반응 — v_z\n", encoding="utf-8")
    return {"facts": str(facts), "bench": str(bench), "out": tmp_path / "out"}


def _run(inputs, llm, **kw):
    return E.run(SSEOL, "닿으면 스피커 — 금속 원판", inputs["out"], inputs["bench"], inputs["facts"], llm=llm, log=lambda *_: None, **kw)


def _fix(i, line):
    return {"lines": [{"i": i, **line}]}


def test_good_draft_passes_without_rewrite(inputs):
    llm = FakeLLM({"draft": {"angle": "아무 데나 대면 스피커", "twist": "3번 줄", "lines": GOOD}})
    S = _run(inputs, llm)
    assert llm.tags == ["draft"], S["final"]["check"]["bad"]
    assert S["final"]["check"]["ok"]
    # remake.py --script 가 읽는 꼴: final.lines[text] · facts{id:{text,url}} · gate
    assert [l["text"] for l in S["final"]["lines"]] == [g["text"] for g in GOOD]
    assert S["facts"]["f1"]["url"] == "https://example.com/a" and "b1" in S["facts"]
    assert S["final"]["lines"][2]["sources"] == ["https://example.com/a"]
    for f in ("대본.json", "대본_검사.md", "대본_계획.md", "roles.json"):
        assert (inputs["out"] / f).exists()
    assert json.loads((inputs["out"] / "roles.json").read_text(encoding="utf-8"))["roles"] == E.ROLES["sseolpulda"]


def test_missing_role_is_caught_and_rewritten(inputs):
    llm = FakeLLM({"draft": {"lines": GOOD[:5]}, "rewrite1": _fix(6, GOOD[5])})
    S = _run(inputs, llm)
    first = S["tries"][0]["check"]
    assert 5 in first["role_missing"] and "칸 역할 빠짐/어긋남" in first["bad"][5]
    assert llm.tags == ["draft", "rewrite1"] and "6번 칸" in llm.prompts["rewrite1"]
    assert S["final"]["check"]["ok"]


def test_wrong_role_order_is_caught(inputs):
    swapped = [GOOD[1], GOOD[0]] + GOOD[2:]
    llm = FakeLLM({"draft": {"lines": swapped}, "rewrite1": {"lines": [{"i": 1, **GOOD[0]}, {"i": 2, **GOOD[1]}]}})
    S = _run(inputs, llm)
    assert set(S["tries"][0]["check"]["role_missing"]) >= {0, 1}
    assert S["final"]["check"]["ok"]


def test_line_without_ground_is_caught_and_rewritten(inputs):
    bad = [dict(l) for l in GOOD]
    bad[2] = {**bad[2], "facts": []}
    bad[4] = {**bad[4], "facts": ["f9"]}     # 없는 번호도 근거 아님
    llm = FakeLLM({"draft": {"lines": bad}, "rewrite1": {"lines": [{"i": 3, **GOOD[2]}, {"i": 5, **GOOD[4]}]}})
    S = _run(inputs, llm)
    c0 = S["tries"][0]["check"]
    assert c0["no_ground"] == [2, 4] and c0["unknown_ids"] == ["f9"]
    assert "3번 칸" in llm.prompts["rewrite1"] and "5번 칸" in llm.prompts["rewrite1"]
    assert S["final"]["check"]["ok"]


def test_polite_mixed_is_caught_and_rewritten(inputs):
    bad = [dict(l) for l in GOOD]
    bad[4] = {**bad[4], "text": "소리 퍼지는 게 예술이에요"}
    llm = FakeLLM({"draft": {"lines": bad}, "rewrite1": _fix(5, GOOD[4])})
    S = _run(inputs, llm)
    assert 4 in S["tries"][0]["check"]["tone_off"]
    assert any("말투 섞임" in w for w in S["tries"][0]["check"]["bad"][4])
    assert S["final"]["check"]["ok"]


def test_unsourced_number_is_caught(inputs):
    bad = [dict(l) for l in GOOD]
    bad[3] = {**bad[3], "text": "집이 3초 만에 우퍼로 둔갑함;;"}
    llm = FakeLLM({"draft": {"lines": bad}, "rewrite1": _fix(4, GOOD[3])})
    S = _run(inputs, llm)
    assert 3 in S["tries"][0]["check"]["numbers_unsourced"]
    assert S["final"]["check"]["ok"]


def test_rewrite_stops_after_two_rounds(inputs):
    bad = [dict(l) for l in GOOD]
    bad[2] = {**bad[2], "facts": []}
    llm = FakeLLM({"draft": {"lines": bad}, "rewrite1": _fix(3, bad[2]), "rewrite2": _fix(3, bad[2])})
    S = _run(inputs, llm)
    assert llm.tags == ["draft", "rewrite1", "rewrite2"]
    assert not S["final"]["check"]["ok"]
    assert "미통과" in (inputs["out"] / "대본_검사.md").read_text(encoding="utf-8")


def test_llm_failure_is_recorded_not_silent(inputs):
    S = _run(inputs, FakeLLM({}))
    assert "초안 LLM 실패" in S["error"]


def test_narration_total_length_yummyknow(tmp_path):
    """yummyknow(나레 꼴): 전체 글자 수가 원본 받아쓰기 합 ±15% 밖이면 가장 짧은 줄을 다시 쓴다."""
    P = T.load_preset("yummyknow")
    if not P["tteutgi"]:
        pytest.skip("yummyknow 뜯기 없음")
    sk = E.skeleton(P, None, None)
    assert sk["mode"] == "narration" and sk["honorific"] == "반말" and sk["total"]
    lo, hi = sk["total"]

    def say(n):   # 원본과 안 겹치는 말 n글자(공백 빼고)
        base = "그래서사람들이그걸알게된뒤로분위기가싹바뀌었다는얘기가돌았음"
        return (base * (n // len(base) + 1))[:n - 1] + "음"
    per = (lo - 20) // 5            # 일부러 전체가 모자라게
    roles = [E._role_name(r) for r in sk["roles"]]
    short = [{"fn": roles[k], "text": say(per), "facts": ["f1"]} for k in range(5)]
    longer = {"fn": roles[0], "text": say(per + 40), "facts": ["f1"]}
    facts = tmp_path / "f.json"
    facts.write_text(json.dumps({"f1": "코스트코 스프레드 반반 구성"}, ensure_ascii=False), encoding="utf-8")
    llm = FakeLLM({"draft": {"lines": short}, "rewrite1": lambda p: {"lines": [{"i": 1, **longer}]}})
    S = E.run("yummyknow", "코스트코 스프레드", tmp_path / "o", None, str(facts), llm=llm, log=lambda *_: None)
    c0 = S["tries"][0]["check"]
    assert c0["total_off"] and c0["total_off"]["chars"] < lo
    assert llm.tags[:2] == ["draft", "rewrite1"]
    assert S["final"]["check"]["total_off"] is None, S["final"]["check"]


# ── 소재 찾기 ─────────────────────────────────────────────────────────────
def _fake_net():
    shorts = {
        "speaker": [{"id": "sp1", "duration": 30, "views": 900, "title": "닿으면 스피커 골전도 진동 스피커 아무데나 붙이면 소리", "url": "u/sp1"}],
        "ramen": [{"id": "rm1", "duration": 30, "views": 800, "title": "신라면 구미 공장 하루 생산량 비밀", "url": "u/rm1"}],
    }

    def yt_search(q, n, months):
        if "스피커" in q or q == "speaker":
            return shorts["speaker"]
        if "신라면" in q or q == "ramen":
            return shorts["ramen"]
        return []

    def yt_detail(vid, n):
        title = next(v["title"] for vs in shorts.values() for v in vs if v["id"] == vid)
        return {"id": vid, "url": f"https://www.youtube.com/shorts/{vid}", "title": title, "views": 100, "date": "20260101",
                "description": "설명", "comments": [{"likes": 9, "text": "와 신기하다", "id": "c"}]}
    return {"yt_search": yt_search, "yt_detail": yt_detail}


def _same_scores(ids, drop_why=None):
    row = lambda: {k: {"score": 7, "why": "벤치 포인트에 그 반응이 있음"} for k, _ in T.CRITERIA}  # noqa: E731
    out = []
    for i in ids:
        r = {"id": i, **row(), "angle": "각도"}
        if i == drop_why:
            r["fun"] = {"score": 9, "why": ""}
        out.append(r)
    return {"scores": out}


def test_topic_overlap_with_made_lowers_score(tmp_path):
    llm = FakeLLM({"bench_c1": {"points": [{"kind": "hook", "text": "아무 데나 붙이면 스피커", "from": "v_sp1"}], "best_angle": "x"},
                   "bench_c2": {"points": [{"kind": "number", "text": "하루 생산량", "from": "v_rm1"}]},
                   "score": _same_scores(["c1", "c2"])})
    res = T.run(SSEOL, tmp_path, n=5, source_kind="해외영상", keywords=["스피커", "신라면"], months=6, bench_n=1,
                net=_fake_net(), llm=llm, log=lambda *_: None)
    by = {c["id"]: c for c in res["candidates"]}
    sp, rm = by["c1"], by["c2"]
    assert "스피커" in sp["topic"] and "신라면" in rm["topic"]
    assert sp["overlap"]["score"] >= T.OVERLAP_CUT and "ZdeZ" in sp["overlap"]["with"]
    assert rm["overlap"]["score"] < T.OVERLAP_CUT
    assert sp["total"] < rm["total"]                       # 같은 6기준 점수인데 겹친 쪽이 깎인다
    assert res["recommend"] == ["c2"]
    assert any("이미 만든 소재" in f for f in sp["flags"])
    md = (tmp_path / "후보표.md").read_text(encoding="utf-8")
    assert "c1" in md and "겹침" in md
    # 벤치 파일 → 대본 엔진이 근거 번호로 읽는다
    b = E.load_bench(str(tmp_path / "벤치" / "c2.md"))
    assert b["points"]["b1"]["url"] == "https://www.youtube.com/shorts/rm1"


def test_score_without_reason_is_dropped(tmp_path):
    llm = FakeLLM({"bench_c1": {"points": []}, "bench_c2": {"points": []}, "score": _same_scores(["c1", "c2"], drop_why="c2")})
    res = T.run(SSEOL, tmp_path, n=5, source_kind="해외영상", keywords=["스피커", "신라면"], bench_n=1, net=_fake_net(), llm=llm, log=lambda *_: None)
    rm = next(c for c in res["candidates"] if c["id"] == "c2")
    assert rm["scores"]["fun"]["score"] is None and "fun 근거 없음" in rm["flags"]
    assert rm["total"] == 7 * 5                               # 근거 없는 9점은 합계에 안 들어간다


def test_source_kind_required():
    with pytest.raises(SystemExit):
        T.run(SSEOL, Path("."), source_kind=None, keywords=["x"], net=_fake_net(), llm=FakeLLM({}), log=lambda *_: None)


def test_keyword_bundles_use_hashtags_and_skip_bait_words():
    kw = T.keyword_bundles([{"views": 8_800_000, "title": "Make sure #BoneConductionSpeaker insane"},
                            {"views": 1_000, "title": "The insane secret chair"}])
    assert "bone conduction speaker" in kw and "insane" not in kw and "secret" not in kw


def test_bench_drops_unrelated_videos(tmp_path):
    """10-16 실측 결함: 벤치 검색이 조회순 무관 영상(ASMR·pov)을 물어 왔다 → 검색어 낱말이 없는 영상은 뺀다."""
    net = {"yt_search": lambda q, n, m: [{"id": "a"}, {"id": "b"}],
           "yt_detail": lambda vid, n: {"id": vid, "url": vid, "title": {"a": "Bone conduction speaker test", "b": "pov: you can't sleep"}[vid],
                                        "description": "", "comments": []}}
    c = {"id": "c1", "topic": "x", "key": "bone conduction speaker",
         "query": T.bench_query("bone conduction speaker", "I Can t Sleep Without Sound Pillow Speaker")}
    assert c["query"].startswith("bone conduction speaker") and "sleep" in c["query"]
    r = T.bench(c, tmp_path, net, FakeLLM({}), n_videos=2, delay=0)
    assert [v["id"] for v in r["videos"]] == ["a"] and any("무관 영상 제외" in f for f in r["failed"])


def test_llm_budget_stops_calls():
    llm = T.LLM(fn=lambda p, t: ({"ok": 1}, None), budget=1)
    assert llm("a", "x")[0] and llm("b", "y") == (None, "budget")
