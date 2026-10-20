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


@pytest.fixture(autouse=True)
def _no_news_network(monkeypatch):
    """자동 기사 찾기(find_articles)가 시험 중 진짜 뉴스 검색을 하지 않게 — 기사 시험은 net 을 직접 넘긴다."""
    for k in ("news_search", "daum_news_search", "bing_news_search"):
        monkeypatch.setitem(T.NET, k, lambda *a, **kw: [])


class FakeLLM:
    """tag → 답(dict 또는 함수(prompt)→dict). 부른 순서·프롬프트를 남긴다. TF.LLM 과 같은 꼴(.calls)."""

    def __init__(self, answers):
        self.answers, self.calls, self.prompts = answers, [], {}

    def __call__(self, prompt, tag):
        self.calls.append({"tag": tag})
        self.prompts[tag] = prompt
        a = self.answers.get(tag)
        if a is None and tag == "support":   # 줄↔근거 판정 기본 = 전부 예(그 판정을 시험하는 곳만 따로 답을 준다)
            n = prompt.count("\n   근거: ")
            return {"items": [{"i": i + 1, "ok": "예", "why": "가짜"} for i in range(n)]}, None
        if a is None:
            return None, "가짜: 답 없음"
        return (a(prompt) if callable(a) else json.loads(json.dumps(a))), None

    @property
    def tags(self):   # 기본 '예' 판정(support)은 빼고 센다 — 쓰기·다시 쓰기 흐름만 본다
        return [c["tag"] for c in self.calls if c["tag"] != "support" or "support" in self.answers]


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
    facts.write_text(json.dumps({"f1": {"text": "코스트코 2026-10-01 상품 페이지: 스프레드 반반 구성 1kg", "url": "https://www.costco.co.kr/p/682334"}},
                                ensure_ascii=False), encoding="utf-8")   # 식품 소재 → 기사·공식 페이지 근거(날짜·발췌) 필요
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

    def yt_detail(vid, n, url=None):
        title = next(v["title"] for vs in shorts.values() for v in vs if v["id"] == vid)
        return {"id": vid, "url": f"https://www.youtube.com/shorts/{vid}", "title": title, "views": 100, "date": "20260101",
                "description": "설명", "comments": [{"likes": 9, "text": "와 신기하다", "id": "c"}]}
    import datetime as dt
    today = dt.date.today().strftime("%Y%m%d")   # 가짜 네트워크도 날짜 통로를 준다 — 빠지면 run 이 진짜 yt-dlp 를 부른다
    return {"yt_search": yt_search, "yt_detail": yt_detail, "yt_upload_date": lambda vid: today}


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
                   "fit": {"items": [{"id": "c1", "fit": "예", "why": "제품"}, {"id": "c2", "fit": "예", "why": "제품"}]}, "score": _same_scores(["c1", "c2"])})
    res = T.run(SSEOL, tmp_path, n=5, source_kind="해외영상", keywords=["스피커", "신라면"], months=6, bench_n=1,
                net=_fake_net(), llm=llm, log=lambda *_: None, limits=T.Limits(sleep=lambda s: None))
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
    llm = FakeLLM({"bench_c1": {"points": []}, "bench_c2": {"points": []}, "fit": {"items": [{"id": "c1", "fit": "예", "why": "제품"}, {"id": "c2", "fit": "예", "why": "제품"}]}, "score": _same_scores(["c1", "c2"], drop_why="c2")})
    res = T.run(SSEOL, tmp_path, n=5, source_kind="해외영상", keywords=["스피커", "신라면"], bench_n=1, net=_fake_net(), llm=llm, log=lambda *_: None, limits=T.Limits(sleep=lambda s: None))
    rm = next(c for c in res["candidates"] if c["id"] == "c2")
    assert rm["scores"]["fun"]["score"] is None and "fun 근거 없음" in rm["flags"]
    assert rm["total"] == 7 * 5                               # 근거 없는 9점은 합계에 안 들어간다


def test_channel_fit_no_skips_scoring_and_promo_caps(tmp_path):
    """채널 결 '아니오'면 점수 호출에 안 들어가고 점수·추천 없음. 공식(채널 이름 official)·광고면 아는 대상/몰랐던 ≤5."""
    shorts = {"spk": [{"id": "sp1", "duration": 30, "views": 900, "title": "신기한 스피커 원판", "channel": "Gadget Official", "url": "u/sp1"}],
              "dog": [{"id": "dg1", "duration": 30, "views": 800, "title": "강아지 춤 신라면", "channel": "dogs", "url": "u/dg1"}]}
    net = {**_fake_net(), "yt_search": lambda q, n, m: shorts["spk"] if "스피커" in q else shorts["dog"] if "신라면" in q else [],
           "yt_detail": lambda vid, n, url=None: {"id": vid, "failed": "시험: 상세 없음"}}
    llm = FakeLLM({"fit": {"items": [{"id": "c1", "fit": "예", "why": "제품 시연"}, {"id": "c2", "fit": "아니오", "why": "동물 영상"}]},
                   "score": lambda p: _same_scores(["c1"]) if "c2." not in p else {"scores": []}})
    for c in ("c1", "c2"):
        llm.answers[f"bench_{c}"] = {"points": []}
    res = T.run(SSEOL, tmp_path, n=5, source_kind="해외영상", keywords=["스피커", "신라면"], bench_n=1, net=net, llm=llm, log=lambda *_: None,
                limits=T.Limits(sleep=lambda s: None))
    by = {c["id"]: c for c in res["candidates"]}
    assert "c2." not in llm.prompts["score"]                                   # 결 밖 후보는 점수 프롬프트에 없다
    assert by["c2"]["scores"]["known"]["score"] is None and any("채널 결 밖" in f for f in by["c2"]["flags"])
    assert by["c1"]["promo"] and by["c1"]["scores"]["known"]["score"] == T.PROMO_CAP and by["c1"]["scores"]["surprise"]["score"] == T.PROMO_CAP
    assert "c2" not in res["recommend"]


def test_article_gate_blocks_behind_topic_without_article(tmp_path):
    """제품비하인드·식품 소재는 기사(영상·SNS 아닌 URL+날짜+발췌)가 facts 에 없으면 facts_insufficient — LLM 을 부르지 않는다."""
    vid_only = tmp_path / "v.json"
    vid_only.write_text(json.dumps({"f1": {"text": "다이소 공식 쇼츠 설명: 베이커리 푸 봉제키링 신상", "url": "https://www.youtube.com/shorts/x"}},
                                   ensure_ascii=False), encoding="utf-8")
    llm = FakeLLM({"draft": {"lines": []}})
    S = E.run("yummyknow", "다이소 베이커리 푸 신상", tmp_path / "o", None, str(vid_only), llm=llm, log=lambda *_: None, source_kind="제품비하인드")
    assert S["status"] == "facts_insufficient" and llm.tags == [] and "기사 근거" in S["error"]
    art = {"f1": {"text": "위키트리 2026-09-16: 유튜버가 구미공장·안성공장 신라면을 같은 조건으로 끓여 비교", "url": "https://www.wikitree.co.kr/articles/1159999"}}
    assert E.article_gate({"topic": "신라면 구미공장"}, art, "해외영상")[0]                                   # 식품 낱말 → 대상, 기사 있음 → 통과
    assert not E.article_gate({"topic": "신라면 구미공장"}, {"f1": {"text": "짧음", "url": "https://news.x/1"}}, None)[0]   # 날짜·발췌 없음
    assert E.article_gate({"topic": "LED 수도꼭지"}, {}, "해외영상")[0]                                         # 대상 아님
    # 날짜·발췌가 있어도 영상·SNS 주소는 기사가 아니다(다이소 c3 초안의 facts 꼴)
    assert E.article_facts({"f1": {"text": "다이소 공식 쇼츠 2026-10-12 설명: 베이커리 푸 봉제키링 신상 공개", "url": "https://www.youtube.com/shorts/x"}}) == []


def test_source_kind_from_manifest_or_required():
    P = T.load_preset(SSEOL)
    assert P["manifest"].get("source_kind") == "해외영상" and P["rules"] and P["rules"].endswith("제품_이야기썰형.rules.json")
    assert P["manifest"].get("roles") == E.ROLES["sseolpulda"]
    with pytest.raises(SystemExit):   # manifest 없는 채널(slug)은 --source-kind 필수
        T.run("yummyknow", Path("."), source_kind=None, keywords=["x"], net=_fake_net(), llm=FakeLLM({}), log=lambda *_: None)


def test_db_candidates_from_reference_db_not_our_titles(tmp_path):
    """해외영상 = reference.db 해외 참고 채널 대표 영상 → 제목·날짜(메타) → 최근 60일만 → 제품 명사(LLM) → 후보는 그 히트 영상.
    오래된 영상·제품 아닌 제목은 빠지고 이유가 남는다(10-16 실측 표본: Kaiping Austler 'LED Basin Faucet' 8,192만)."""
    import datetime as dt
    today = dt.date.today()
    rows = [{"url": "https://www.youtube.com/shorts/h1", "id": "h1", "username": "Kaiping Austler", "views": 81_921_392, "keywords": ["gadgets"]},
            {"url": "https://www.youtube.com/shorts/h2", "id": "h2", "username": "Nick", "views": 70_000_000, "keywords": ["gadget"]},
            {"url": "https://www.youtube.com/shorts/h3", "id": "h3", "username": "Old", "views": 60_000_000, "keywords": ["gadget"]}]
    meta = {"h1": {"date": today.strftime("%Y%m%d"), "duration": 8.0, "title": "LED Basin Faucet for wholesale buyer #faucet"},
            "h2": {"date": today.strftime("%Y%m%d"), "duration": 29.0, "title": "1 Second vs 1 Hour Chicken"},
            "h3": {"date": (today - dt.timedelta(days=400)).strftime("%Y%m%d"), "duration": 20.0, "title": "old gadget"}}
    net = {**_fake_net(), "db_top": lambda n: rows, "yt_meta": lambda vid: meta[vid]}
    llm = FakeLLM({"db_nouns": {"items": [{"i": 0, "noun": "led basin faucet", "why": "LED Basin Faucet"}, {"i": 1, "noun": "", "why": "요리"}]},
                   "score": {"scores": []}})
    res = T.run(SSEOL, tmp_path, n=5, source_kind="해외영상", bench_n=1, net=net, llm=llm, log=lambda *_: None, limits=T.Limits(sleep=lambda s: None))
    assert [c["query"] for c in res["candidates"]] == ["led basin faucet"]
    c = res["candidates"][0]
    assert c["source"]["via"].startswith("reference.db") and c["source"]["url"].endswith("h1")
    assert "reference.db" in res["queries"][0]["why"] and "Kaiping" in res["queries"][0]["why"]
    assert "old gadget" not in llm.prompts["db_nouns"]   # 400일 전 영상은 명사 뽑기 전에 빠진다
    assert any("오래됨 1" in f["why"] for f in res["failed"])


def test_db_failure_recorded_no_fallback_to_our_titles(tmp_path):
    def boom(n):
        raise RuntimeError("ssh 막힘")
    llm = FakeLLM({"db_nouns": {"items": [{"i": 0, "noun": "fallback noun", "why": "x"}]}})   # 뭔가로 되돌아가면 후보가 생기게
    res = T.run(SSEOL, tmp_path, n=5, source_kind="해외영상", net={**_fake_net(), "db_top": boom, "yt_meta": lambda v: {}}, llm=llm, log=lambda *_: None,
                limits=T.Limits(sleep=lambda s: None))
    assert res["candidates"] == [] and any(f["where"] == "reference.db" for f in res["failed"])
    assert "db_nouns" not in llm.tags


def test_behind_queries_use_channel_angles_not_new_items():
    qs = [q["q"] for q in T.target_queries("제품비하인드", ["코스트코", "맘스터치"], 6)]
    assert qs == ["코스트코 억울", "맘스터치 영업비밀"] and not any("신상" in q for q in qs)
    with pytest.raises(SystemExit):   # 제품비하인드는 구체 명사를 사람이 준다(과거 제목에서 뽑지 않는다)
        T.run("yummyknow", Path("."), source_kind="제품비하인드", net=_fake_net(), llm=FakeLLM({}), log=lambda *_: None)


def test_official_and_ad_videos_excluded(tmp_path):
    """다이소 공식 채널 홍보·'광고' 표기 영상은 제품비하인드 후보에서 빠지고 이유가 남는다(10-16 실측: 후보 3개 전부 다이소 공식)."""
    vids = [{"id": "o1", "duration": 30, "views": 9, "title": "다이소 신상 공개", "channel": "다이소", "url": "u/o1"},
            {"id": "a1", "duration": 30, "views": 8, "title": "코스트코 신상 (유료광고)", "channel": "리뷰어", "url": "u/a1"},
            {"id": "k1", "duration": 30, "views": 7, "title": "다이소 억울한 이유", "channel": "썰채널", "url": "u/k1"}]
    net = {**_fake_net(), "yt_search": lambda q, n, m: vids}
    cands, failed = T.gather("제품비하인드", ["다이소 억울"], 5, None, set(), net, lambda *_: None, T.Limits(sleep=lambda s: None), 5,
                             brands=["다이소", "코스트코"])
    assert [c["source"]["id"] for c in cands] == ["k1"]
    why = " ".join(f["why"] for f in failed)
    assert "공식 채널" in why and "광고 표기" in why


def test_limit_exceeded_stops_and_records(tmp_path):
    """메타 조회 상한을 넘기면 더 검색하지 않고 멈춤 이유를 후보.json·후보표에 남긴다."""
    calls = []
    net = _fake_net()
    orig = net["yt_search"]
    net["yt_search"] = lambda q, n, m: (calls.append(q), orig(q, n, m))[1]
    lim = T.Limits(max_meta=12, sleep=lambda s: None)
    res = T.run(SSEOL, tmp_path, n=5, source_kind="해외영상", keywords=["스피커", "신라면", "라면"], bench_n=1, net=net,
                llm=FakeLLM({}), log=lambda *_: None, limits=lim, per_query=5)
    assert calls == ["스피커", "신라면"]                     # 세 번째 검색(5편 더 → 15 > 12) 전에 멈춤
    assert res["stopped"] and "메타 조회 상한 12편" in res["stopped"]
    assert res["limits"]["meta"] <= 12
    assert "멈춤" in (tmp_path / "후보표.md").read_text(encoding="utf-8")


def test_limits_refuse_too_fast_or_too_big():
    with pytest.raises(SystemExit):
        T.Limits(rate=0.5)
    with pytest.raises(SystemExit):
        T.Limits(max_meta=500)


def test_date_filter_keeps_recent_sorted_and_logs(tmp_path):
    """최근 N개월은 로컬에서: 날짜 모름·오래된 것은 빼고 이유를 failed 에 남긴다."""
    import datetime as dt
    today = dt.date.today()
    dates = {"a": today.strftime("%Y%m%d"), "b": (today - dt.timedelta(days=400)).strftime("%Y%m%d"), "c": None}
    pool = [{"id": k, "views": v} for k, v in (("a", 9), ("b", 8), ("c", 7))]
    failed = []
    kept = T.date_filter(pool, 3, {"yt_upload_date": lambda vid: dates[vid]}, T.Limits(sleep=lambda s: None), failed)
    assert [v["id"] for v in kept] == ["a"]
    assert "오래됨 1" in failed[0]["why"] and "날짜 모름 1" in failed[0]["why"]


def test_relevance_rejects_other_brand_same_place():
    """10-16 실측 결함: 키 '신라면'만 보던 판정이 '오뚜기 진라면 구미 공장 신설'을 신라면 구미공장 벤치에 넣었다."""
    topic = "신라면 구미공장 vs 안성공장 맛 차이"
    assert not T.relevance({"title": "오뚜기 진라면 구미 공장 신설", "description": ""}, "신라면 신상", topic)[0]
    assert T.relevance({"title": "신라면 구미공장 vs 안성공장 끓여 봄", "description": ""}, "신라면 신상", topic)[0]
    # 검색어(신라면)는 맞아도 소재 핵심(구미공장·안성공장…)이 하나뿐이면 다른 이야기 — 뺀다
    assert not T.relevance({"title": "신라면 먹방 리뷰", "description": ""}, "신라면 신상", topic)[0]


def test_bench_skips_fallback_marker_without_detail(tmp_path):
    seen = []
    net = {"yt_search": lambda q, n, m: [{"id": None, "fallback": "sp 필터 시간 초과 30초 → ytsearch 폴백 · 60초 이하 0편"}],
           "yt_detail": lambda vid, n, url=None: seen.append(vid) or {"id": vid, "failed": "x"}}
    r = T.bench({"id": "c1", "topic": "신라면", "query": "신라면"}, tmp_path, net, FakeLLM({}), limits=T.Limits(sleep=lambda s: None))
    assert seen == [] and any("폴백" in f for f in r["failed"])


def _narr_lines(sk, text_for):
    roles = [E._role_name(r) for r in sk["roles"]]
    return [{"fn": roles[k], "text": text_for(k), "facts": ["f1"]} for k in range(len(roles))]


def _filler(n, head=""):
    """공백 빼고 n글자 — 띄어쓰기 있는 말(띄어쓰기 지움 검사에 안 걸리게)."""
    words = (head + " 그래서 사람들이 그걸 알게 된 뒤로 분위기가 싹 바뀌었다는 얘기가 돌았음").split() * 20
    out, cnt = [], 0
    for w in words:
        if cnt + len(w) > n - 1:
            w = w[:max(0, n - 1 - cnt)]
        if w:
            out.append(w); cnt += len(w)
        if cnt >= n - 1:
            break
    return " ".join(out) + "음"


def test_off_topic_brand_and_missing_product_caught(tmp_path):
    """소재 이탈: 소재·사실에 없는 브랜드(진라면) 줄 → 실패, 나레 꼴은 소재 제품명(신라면)이 한 번도 없으면 실패 → 그 줄만 다시."""
    P = T.load_preset("yummyknow")
    if not P["tteutgi"]:
        pytest.skip("yummyknow 뜯기 없음")
    sk = E.skeleton(P, None, None)
    per = (sk["total"][0] + sk["total"][1]) // 2 // len(sk["roles"])
    facts = tmp_path / "f.json"
    facts.write_text(json.dumps({"f1": {"text": "뉴시스 2025-11-09 르포: 구미공장은 국내 신라면 생산량의 약 75%", "url": "https://www.newsis.com/view/NISX20251107"}},
                                ensure_ascii=False), encoding="utf-8")
    off = _narr_lines(sk, lambda k: _filler(per, "오뚜기진라면공장이" if k == 2 else ""))
    good = _narr_lines(sk, lambda k: _filler(per, "신라면구미공장이" if k == 0 else ""))
    llm = FakeLLM({"draft": {"lines": off}, "rewrite1": {"lines": [{"i": 1, **good[0]}, {"i": 3, **good[2]}]}})
    S = E.run("yummyknow", "신라면 구미공장 vs 안성공장 맛 차이", tmp_path / "o", None, str(facts), llm=llm, log=lambda *_: None)
    c0 = S["tries"][0]["check"]
    assert c0["off_topic_brand"] == [2] and c0["topic_match"]["other_brand"][2] == ["오뚜기", "진라면"]
    assert c0["product_missing"] == [0]
    assert "빼야 할 이름" in llm.prompts["rewrite1"] and "신라면" in llm.prompts["rewrite1"]
    assert S["final"]["check"]["ok"], S["final"]["check"]["bad"]


def test_captions_product_name_only_warns(inputs):
    """자막 꼴(썰풀다)은 제품명을 안 부르는 게 채널 꼴 — 없어도 실패 아님(경고만)."""
    S = _run(inputs, FakeLLM({"draft": {"lines": GOOD}}))
    tm = S["final"]["check"]["topic_match"]
    assert S["final"]["check"]["ok"] and tm["product_warn"] and not tm["product_missing"]


def test_range_number_written_as_single_value_fails():
    """(4) 바나나 편 실례: 근거 '6~8배'를 '8배'로 단정 → 실패. 범위 그대로·근거에 따로 있는 단일값은 통과."""
    facts = {"f1": {"text": "수입 바나나 가격이 국산의 6~8배", "url": ""}, "f2": {"text": "하루 3번 수확", "url": ""}}
    hit = E.number_ranges(["가격이 무려 8배임", "가격이 6~8배임", "하루 3번 딴다고"], facts)
    assert hit == {0: ["6~8"]}


def test_comment_promoted_to_fact_and_unsourced_hype_fail():
    """(5) 리센느 편 실례: 댓글 '전설의 포켓몬 수준'을 '취급을 받고 있음'으로(사실 승격) · 근거 없는 '극락' → 실패.
    '댓글에선 …라는 반응' 꼴은 통과, 감탄 칸(화자 감상)은 전언 표식 대상 아님."""
    facts = {"c1": {"text": "댓글(좋아요 900): 전설의 포켓몬 수준", "url": ""}, "f1": {"text": "한정판 3천 장 판매", "url": ""}}
    bench = {"points": {}, "texts": []}
    lines = [{"text": "팬들 사이에서 전설의 포켓몬 취급을 받고 있음", "facts": ["c1"]},
             {"text": "댓글에선 전설의 포켓몬 수준이라는 반응", "facts": ["c1"]},
             {"text": "한정판이라 사면 극락 간다는 얘기", "facts": ["f1"]},
             {"text": "이건 진짜 갖고 싶네", "facts": ["c1"]}]
    roles = ["반응", "반응", "진짜 이유", "감탄"]
    hit = E.comment_as_fact(lines, facts, bench, roles)
    assert 0 in hit and "댓글을 사실처럼" in hit[0][0]
    assert 1 not in hit and 3 not in hit and 2 not in hit      # 과장은 claim_off 한 곳(겹친 판정 합침)
    assert E.claim_off(lines, facts, bench)[2] == ["극락"]


def test_channel_linter_is_called_banggu():
    """(6) 방구석 rules.lint(주인) 를 부른다 — 마지막 본문 줄 어미·혼잣말 ㅋㅋ 반려가 줄 번호로 붙고, 문장 수는 전체 반려."""
    P = T.load_preset("banggu")
    if not P["tteutgi"]:
        pytest.skip("방구석 뜯기 없음")
    sk = E.skeleton(P, "narration", None)
    lines = [{"text": t, "facts": ["f1"]} for t in ("코스트코에 가면 꼭 산다는 EMMI 티라미수", "근데 사는 이유는 맛 때문이 아니라는데",
                                                   "컵을 살펴보니 유리로 돼 있고", "정작 꽂힌 포인트는 따로 있다는데", "그건 바로 이 유리컵이 튼튼해서임",
                                                   "아니 컵 때문에 산다니")]
    cl = E.channel_lint("banggu", lines, sk, {"f1": {"text": "EMMI 티라미수 유리컵", "url": ""}}, "유리컵 때문에 산다는 티라미수")
    assert cl["linter"] == "banggu.rules.lint"
    assert any("bg_close" in m for m in cl["by_line"].get(4, []))          # 본문 마지막 줄은 ~다고/~라고
    assert any("bg_comment_kk" in m for m in cl["by_line"].get(5, []))     # 혼잣말은 ㅋㅋ
    assert any("bg_lines" in m for m in cl["global"])                      # 본문 5문장 < 6
    assert E.channel_lint("yummyknow", lines, sk, {}, None)["linter"] is None


def test_channel_length_range_from_channel_bench():
    """(7) 나레 길이 = 채널 뜯기 편 받아쓰기 중앙값 ±20% — 방구석 311자(35초) 초안은 범위 밖."""
    P = T.load_preset("banggu")
    if not P["tteutgi"]:
        pytest.skip("방구석 뜯기 없음")
    (lo, hi), basis = E.channel_length(P, {}, 999)
    assert "채널 뜯기" in basis and hi < 311 and lo > 100


FIX = ROOT / "shopping_shorts/tests/fixtures/calcopy_engine"


def _fx(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


SSEOL_ORIG = ["아니 이거 해외 릴스에서 맨날 보이길래", "바이럴인 줄 알았는데...", "진짜 아무 데나 대면", "집 전체가 스피커로 변함;;",
              "소리 퍼지는 거 미쳤네", "이거 탐나는 거 인정?"]   # 썰풀다 틀 A 원본 줄(ZdeZ 뜯기) — 띄어쓰기 기준 원문


def test_spacing_removed_lines_fail():
    """(묶음4) 폴드8 초안: 폭 맞추려고 띄어쓰기를 지운 줄('울트라나온다길래안믿었는데'·'댓글창안닫은거멋지네') → 실패. 손 대본 LED·신라면은 0줄."""
    d = _fx("engine_fold8_c1")
    texts = [l["text"] for l in d["lines"]]
    assert sorted(E.spacing_off(texts, d["facts"])) == [1, 4]
    assert sorted(E.spacing_off(texts, d["facts"], SSEOL_ORIG)) == [1, 4]           # 원문 대비로 재도 같다
    for name in ("hand_led_faucet", "hand_shinramyun_gumi"):
        h = _fx(name)
        assert E.spacing_off([l["text"] for l in h["lines"]], h["facts"]) == {}, name
        assert E.spacing_off([l["text"] for l in h["lines"]], h["facts"], SSEOL_ORIG) == {}, name


def test_spacing_same_line_red_when_spaces_stripped():
    """답 아는 짝: 통과한 손 대본 줄의 공백만 지우면 빨강, 그대로면 초록(공백 비율 꼴과 긴 덩어리 꼴 둘 다)."""
    good = ["숨어 있던 호스 샤워기로 변신함;;", "구미 쪽이 국물 색도 더 진하고 기름기도 많아서 훨씬 맛있다는 평이 나왔다고 함."]
    assert E.spacing_off(good, {}, SSEOL_ORIG) == {}
    bad = [good[0].replace(" ", ""), good[1].replace(" 더 진하고 ", " 더진하고기름기도많아서훨씬 ").replace("기름기도 많아서 훨씬 ", "")]
    hit = E.spacing_off(bad, {}, SSEOL_ORIG)
    assert sorted(hit) == [0, 1], hit
    assert "덩어리" in hit[0] and "덩어리" in hit[1]
    half = ["숨어있던호스 샤워기로변신함;;"]          # 덩어리는 짧지만(7자) 공백 비율 0.06 < 원문 0.23×0.5
    assert 0 in E.spacing_off(half, {}, SSEOL_ORIG)


def test_claim_needs_same_claim_in_its_evidence():
    """(묶음4) 최상급·단정은 그 줄 근거 글에 같은 무리 주장이 있어야(영어 근거는 -est·first·world's 등)."""
    facts = {"f1": {"text": "충전 3시간이면 된다", "url": ""}, "f2": {"text": "삼성 주장 world's lightest fold", "url": ""}}
    lines = [{"text": "세계에서 최초로 나온 충전기", "facts": ["f1"]}, {"text": "제일 가벼운 폴드폰", "facts": ["f2"]}, {"text": "충전이 빠름", "facts": ["f1"]},
             {"text": "이건 절대 못 참지", "facts": ["f1"]}, {"text": "역대급으로 팔린 충전기", "facts": ["f1"]}, {"text": "유일하게 되는 폰", "facts": ["f2"]}]
    hit = E.claim_off(lines, facts, {"points": {}})
    assert sorted(hit) == [0, 3, 4, 5], hit
    assert set(hit[0]) == {"최초", "세계에서"} and hit[3] == ["절대"] and hit[4] == ["역대급"] and hit[5] == ["유일"]


def test_claim_red_on_engine_draft_green_on_hand_scripts():
    """답 아는 입력: 다이소 c3 초안 1번 '절대 먹지 말라고'(근거 f3 댓글엔 없음)·2번 '역대급으로' → 빨강.
    폴드8 4번 '세상에서 제일 가벼운'은 근거 f2 에 '세상에서 가장'이 있어 이 검사는 초록(회사 주장 단정은 줄↔근거 판정 몫). 손 대본 둘은 0줄."""
    d = _fx("engine_daiso_c3")
    bench = {"points": {}}   # 픽스처 벤치는 목록 꼴 — 이 시험은 사실(f*) 근거만 본다
    hit = E.claim_off(d["lines"], d["facts"], bench)
    assert hit.get(0) == ["절대"] and hit.get(1) == ["역대급"], hit
    f8 = _fx("engine_fold8_c1")
    assert 3 not in E.claim_off(f8["lines"], f8["facts"], {"points": {}})
    for name in ("hand_led_faucet", "hand_shinramyun_gumi"):
        h = _fx(name)
        assert E.claim_off(h["lines"], h["facts"], {"points": {}}) == {}, name


def test_claim_and_spacing_reach_rewrite_prompt(tmp_path):
    """검사가 다시 쓰기 지시까지 닿는다 — 다이소 c3 원 초안(절대·역대급) → 다시 쓰기 1 지시에 '근거 없는 최상급·단정'."""
    d = _fx("engine_daiso_c3")
    lines = [dict(l, facts=[i for i in l["facts"] if i.startswith("f")]) for l in d["lines"]]
    facts = tmp_path / "f.json"
    facts.write_text(json.dumps(d["facts"], ensure_ascii=False), encoding="utf-8")
    llm = FakeLLM({"draft": {"lines": lines}})
    S = E.run("yummyknow", "다이소 베이커리 푸 신상", tmp_path / "o", None, str(facts), llm=llm, log=lambda *_: None)
    c0 = S["tries"][0]["check"]
    assert c0["superlative"] == [0, 1] and c0["superlative_hit"] == {0: ["절대"], 1: ["역대급"]}
    assert "근거 없는 최상급·단정" in llm.prompts["rewrite1"]


def test_unsupported_line_caught_by_evidence_judge_and_rewritten(tmp_path):
    """(묶음4) 다이소 c3 초안 1번 줄 '절대 먹지 말라고 경고'(근거는 '228만 원 썼다'는 댓글뿐) — 줄↔근거 판정이 아니오 → 그 줄만 다시."""
    d = _fx("engine_daiso_c3")
    lines = [dict(l) for l in d["lines"]]
    lines[1]["text"] = lines[1]["text"].replace("역대급으로 ", "")
    for l in lines:   # 벤치 포인트(b*)는 이 시험에 안 싣는다 — 사실(f*) 근거만
        l["facts"] = [i for i in l["facts"] if i.startswith("f")]
    facts = tmp_path / "f.json"
    facts.write_text(json.dumps(d["facts"], ensure_ascii=False), encoding="utf-8")
    fixed = {"i": 1, "fn": lines[0]["fn"], "facts": ["f3"],
             "text": "한 달에 다이소에서만 228만 원 썼다는 댓글까지 달린 곰돌이 푸 베이커리 신상 얘기 아는 사람 있음? 요즘 댓글창이 아주 난리인데."}
    calls = {"n": 0}

    def support(p):
        calls["n"] += 1
        n = p.count("\n   근거: ")
        return {"items": [{"i": i + 1, "ok": "아니오" if (i == 0 and calls["n"] == 1) else "예",
                           "why": "근거는 228만 원 썼다는 댓글뿐, 먹지 말라는 경고는 없음" if i == 0 else "ok"} for i in range(n)]}
    llm = FakeLLM({"draft": {"lines": lines}, "support": support, "rewrite1": {"lines": [fixed]}})
    S = E.run("yummyknow", "다이소 베이커리 푸 신상", tmp_path / "o", None, str(facts), llm=llm, log=lambda *_: None)
    c0 = S["tries"][0]["check"]
    assert c0["unsupported"] == [0] and "경고" in c0["support_hit"][0]
    assert "근거가 문장을 뒷받침 안 함" in llm.prompts["rewrite1"]
    assert S["final"]["check"]["ok"], S["final"]["check"]["bad"]


def test_support_judge_failure_is_not_a_pass(inputs):
    """줄↔근거 판정이 답을 안 주면(빈 답·LLM 실패) 통과가 아니다 — 조용한 통과 금지."""
    S = _run(inputs, FakeLLM({"draft": {"lines": GOOD}, "support": {"items": []}}))
    assert not S["final"]["check"]["ok"] and S["final"]["check"]["unsupported"] == list(range(6))


def test_llm_budget_stops_calls():
    llm = T.LLM(fn=lambda p, t: ({"ok": 1}, None), budget=1)
    assert llm("a", "x")[0] and llm("b", "y") == (None, "budget")


# ── 창고 KPI 0/32 뿌리 수리(10-16 보드 담당 실측) ─────────────────────────
def test_spacing_ignores_digits_line():
    """창고 sseolpulda/14 '8,262,695회나 조회됐길래' — 1판(공백 비율)은 띄어쓰기 지움으로 잘못 잡았다(숫자 덩어리). 한글 어절은 2·5자로 정상."""
    assert E.spacing_off(["8,262,695회나 조회됐길래"], {}, SSEOL_ORIG) == {}
    assert 0 in E.spacing_off(["8,262,695회나조회됐다길래"], {}, SSEOL_ORIG)       # 한글을 붙여 쓰면(8자 덩어리·평균 7) 여전히 빨강


def test_support_prompt_marks_opinion_rows():
    """창고 sseolpulda/13 '과장 광고 아닐까 의심했는데'(의심 칸)를 '근거에 의심 없음'으로 반려 — 감상 칸은 표시해 느낌을 따지지 않게."""
    seen = {}

    def llm(prompt, tag):
        seen["p"] = prompt
        return {"items": [{"i": 1, "ok": "예"}, {"i": 2, "ok": "예"}]}, None
    lines = [{"text": "과장 광고 아닐까 의심했는데", "facts": ["b1"]}, {"text": "공이 로켓처럼 튀어 오름", "facts": ["b1"]}]
    out, err = E.support_check(lines, {}, {"points": {"b1": {"text": "(hook) 중력을 거스르는 문볼"}}}, llm, ["의심(처음엔 안 믿음) · 말끝 ~는데", "결과 과장"])
    assert out == {} and err is None
    assert "1. 줄 [감상 칸]: 과장 광고" in seen["p"] and "2. 줄: 공이" in seen["p"]


def test_caption_ranges_follow_width_when_width_judged():
    """창고 sseolpulda 13~16 넷 다 2번 줄 '글자 수·폭 범위 밖' — 프롬프트엔 원본 글자 수(11~13)를 주고 판정은 폭(546px±10%)이라
    12자를 쓰면 686px 로 반려됐다. 폭으로 판정하면 칸 글자 수도 폭 ÷ 한 글자 폭에서 준다."""
    P = T.load_preset(SSEOL, None)
    sk = E.skeleton(P, None, None)
    if not sk.get("width"):
        pytest.skip(f"폭 추정 없음: {sk.get('width_failed')}")
    lo, hi = sk["ranges"][1]
    assert hi <= 10, sk["ranges"]                                     # 1판: (11, 13)
    est, w = sk["width"]["est"], sk["width"]["orig"][1]
    assert abs(est("그냥 장식인가 싶었는데") - w) / w <= 0.10          # 그 범위(10자) 손 대본 줄은 폭 판정도 통과(LED 통과편 2번 줄)


def test_roles_fallback_instead_of_systemexit():
    """창고: 핫템리포트 프리셋에 roles 없음 → script 단계 SystemExit. 이제 채널 기본 → 없으면 DEFAULT_ROLES, 둘 다 '경보' 근거."""
    r, why = E.pick_roles({"slug": "hottemreport", "manifest": {}})
    assert r == E.ROLES["hottemreport"] and why.startswith("경보")
    r, why = E.pick_roles({"slug": "새채널", "manifest": {}})
    assert r == E.DEFAULT_ROLES and why.startswith("경보")
    assert E.pick_roles({"slug": "hottemreport", "manifest": {"roles": ["가", "나"]}}) == (["가", "나"], "프리셋 manifest.roles")
    assert E.pick_roles({"slug": "x", "manifest": {}}, ["a"]) == (["a"], "인자")


def _art_net(pages, daum=None, naver_fail=True):
    def naver(q, n):
        if naver_fail:
            raise RuntimeError("HTTP Error 403")
        return []
    return {"news_search": naver, "daum_news_search": lambda q, n: list(daum or []), "bing_news_search": lambda q, n: [],
            "article_page": lambda url: dict(pages[url])}


STARBUCKS = {"https://v.daum.net/v/1": {"url": "https://v.daum.net/v/1", "title": "스타벅스 '탱크데이' 후폭풍 어디까지", "date": "20260521090738",
                                        "excerpt": "스타벅스코리아가 탱크 데이 마케팅 논란의 여파로 여름철 프로모션을 잠정 연기했다"},
             "https://v.daum.net/v/2": {"url": "https://v.daum.net/v/2", "title": "탈러시아 현상 가속화, 전쟁이 돈벌이를 바꾼다", "date": "20220316",
                                        "excerpt": "인터뷰 자료의 저작권은 KBS 라디오에 있습니다. 인용보도 시 출처를 밝혀주시기 바랍니다"},
             "https://v.daum.net/v/3": {"url": "https://v.daum.net/v/3", "title": "스타벅스 탱크데이 정용진 사과", "date": "2026-05-26T23:58:31+09:00",
                                        "excerpt": "정용진 회장이 스타벅스코리아의 탱크데이 마케팅 논란 8일 만에 공개 사과했다"},
             "https://www.youtube.com/watch?v=x": {"url": "https://www.youtube.com/watch?v=x", "title": "스타벅스 탱크데이", "date": "2026-05-20",
                                                   "excerpt": "스타벅스 탱크데이 마케팅 논란 영상 정리 스타벅스 탱크데이"}}


def test_find_articles_two_relevant_dated_articles():
    """(묶음3 통로) 네이버 403 → 다음 뉴스. 영상 주소·무관 기사(빅맥송 검색에 걸린 KBS 라디오 인터뷰 꼴)는 거르고 관련 기사 2건."""
    topic = {"topic": "스타벅스 탱크데이 후폭풍 — 미니 탱크 이벤트 논란"}
    net = _art_net(STARBUCKS, daum=[{"url": u} for u in ("https://www.youtube.com/watch?v=x", "https://v.daum.net/v/2", "https://v.daum.net/v/1", "https://v.daum.net/v/3")])
    got, notes = E.find_articles(topic, net, log=lambda *_: None)
    assert [v["url"] for v in got.values()] == ["https://v.daum.net/v/1", "https://v.daum.net/v/3"], notes
    assert len(E.article_facts(got)) == 2
    assert any("news_search" in n and "실패" in n for n in notes) and any("관련 없음" in n for n in notes)
    none, _ = E.find_articles(topic, _art_net(STARBUCKS, daum=[{"url": "https://v.daum.net/v/2"}]), log=lambda *_: None)
    assert none == {}                                                   # 무관 기사만 → 0건(지어 넣지 않음)


def test_run_fills_articles_then_writes(tmp_path):
    """식품 소재 + facts 에 기사 없음 → 자동 기사 찾기 → 관문 통과 → 초안 LLM 호출. 찾기 0건이면 종전대로 facts_insufficient·LLM 안 부름."""
    pages = {"https://v.daum.net/v/9": {"url": "https://v.daum.net/v/9", "title": "바나나맛우유 단지 모양 50년", "date": "2026-10-01",
                                        "excerpt": "빙그레 바나나맛우유 단지 용기는 1974년 출시 뒤 모양을 바꾸지 않았다고 회사가 밝혔다"},
             "https://v.daum.net/v/8": {"url": "https://v.daum.net/v/8", "title": "바나나맛우유 용기 상표 등록", "date": "2016-05-02",
                                        "excerpt": "빙그레가 바나나맛우유 단지 모양 용기를 입체 상표로 등록했다고 2016년 밝혔다 바나나맛우유"}}
    net = _art_net(pages, daum=[{"url": "https://v.daum.net/v/9"}, {"url": "https://v.daum.net/v/8"}])
    llm = FakeLLM({"draft": {"lines": []}})
    S = E.run("yummyknow", "바나나맛우유 단지 모양", tmp_path / "o", None, None, llm=llm, log=lambda *_: None, net=net)
    assert S["status"] != "facts_insufficient" and "draft" in llm.tags, S.get("error")
    assert (tmp_path / "o" / "facts_기사.json").exists() and "자동 기사 찾기 2건" in S["article_gate"]
    llm2 = FakeLLM({"draft": {"lines": []}})
    S2 = E.run("yummyknow", "바나나맛우유 단지 모양", tmp_path / "o2", None, None, llm=llm2, log=lambda *_: None, net=_art_net({}, daum=[]))
    assert S2["status"] == "facts_insufficient" and llm2.tags == []


def test_copy_check_idiom_green_real_copy_red():
    """베낌 판정 주인 style_writer.copied_from — 연속 7자 또는 어절 3개. 관용구(인 줄 알았는데·알고 보니·솔직히·근데)만 겹치면 초록
    (창고 sseolpulda/16 '노트 팬들 뻥인 줄 알았는데'는 5글자 판정에서 '원본과 겹침'으로 반려됐다), 원본 10자를 그대로 쓰면 빨강."""
    green = ["노트 팬들 뻥인 줄 알았는데", "근데 알고 보니 솔직히 별로", "솔직히 소리 좋다 인정?"]
    red = ["해외 릴스에서 맨날 보이던 그 공", "그냥 진짜 아무 데나 대면 끝"]
    assert SW.copied_from(green, SSEOL_ORIG) == {}
    hit = SW.copied_from(red, SSEOL_ORIG)
    assert sorted(hit) == [0, 1], hit
    cc = SW.check_captions([{"text": t} for t in green + red], SSEOL_ORIG[:5], {"examples": []}, [(1, 99)] * 5)
    assert cc["copied_lines"] == [3, 4]
    assert SW.copied_from(["근데 알고 보니 솔직히 그냥 그럼"], ["근데 알고 보니 솔직히 별로였음"]) == {}   # 관용구 3개 연속(어절 4)만 겹침 → 초록
