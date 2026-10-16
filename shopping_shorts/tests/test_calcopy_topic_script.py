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

    def yt_detail(vid, n):
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
           "yt_detail": lambda vid, n: {"id": vid, "failed": "시험: 상세 없음"}}
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
           "yt_detail": lambda vid, n: seen.append(vid) or {"id": vid, "failed": "x"}}
    r = T.bench({"id": "c1", "topic": "신라면", "query": "신라면"}, tmp_path, net, FakeLLM({}), limits=T.Limits(sleep=lambda s: None))
    assert seen == [] and any("폴백" in f for f in r["failed"])


def _narr_lines(sk, text_for):
    roles = [E._role_name(r) for r in sk["roles"]]
    return [{"fn": roles[k], "text": text_for(k), "facts": ["f1"]} for k in range(len(roles))]


def _filler(n, head=""):
    base = "그래서사람들이그걸알게된뒤로분위기가싹바뀌었다는얘기가돌았음"
    body = (base * (n // len(base) + 2))
    return (head + body)[:n - 1] + "음"


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
    assert 1 not in hit and 3 not in hit
    assert hit[2] == ["근거 없는 과장 ['극락']"]


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


def test_llm_budget_stops_calls():
    llm = T.LLM(fn=lambda p, t: ({"ok": 1}, None), budget=1)
    assert llm("a", "x")[0] and llm("b", "y") == (None, "budget")
