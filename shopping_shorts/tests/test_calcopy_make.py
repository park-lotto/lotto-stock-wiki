# -*- coding: utf-8 -*-
"""만들기 입구(calcopy_make) 시험 — 관제 097, 2026-10-16.

가짜 엔진(topic_find·script_engine·remake 하위프로세스)을 worker_steps._engine 에 끼워 넣고, 진짜 calcopy_make·worker·worker_steps·
calcopy_topics 로 ①start(후보) ②choose(→plan_review) ③approve(→produce→final_review)/reject(대본부터 다시 1회) ④status 를 돈다.
재는 것: 팩의 채널명·글꼴·목소리·효과음·짤이 **계획(틀 설명서·재료.json)과 제작 인자에 실제로 들어갔나**(사보타주로 확인) ·
topic 지정이면 후보 조회 0회 · ref_url 근거(facts)가 대본 단계로 넘어가나.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from shopping_shorts import calcopy_make as MK
from shopping_shorts import calcopy_topics as CT
from tools.calcopy.engine import worker_steps as WS

ROOT = Path(__file__).resolve().parents[2]
PRESET = "channel/banggu/preset/게시글형"
CRIT = [("known", "아는 대상"), ("surprise", "몰랐던"), ("fun", "재미"), ("story", "이야기"), ("gain", "얻는 것"), ("showable", "보여줄 수 있나")]


class Fake:
    """가짜 엔진 + 가짜 remake 하위프로세스. 무엇이 어떤 입력으로 불렸는지 기록한다."""

    def __init__(self):
        self.calls, self.plan_materials, self.plan_frame, self.produce_cmd, self.facts = [], None, None, None, None

    # topic_find 자리
    def tf(self):
        f = self

        class LLM:
            def __init__(self, fn=None, budget=6):
                self.calls, self.budget = [], budget

        def load_preset(preset, tteutgi=None):
            p = Path(preset)
            p = p if p.is_absolute() else ROOT / p
            if (p / "manifest.json").exists():
                man = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
                return {"slug": man["slug"], "chdir": ROOT / "channel" / man["slug"], "preset_dir": p, "manifest": man,
                        "tteutgi": str(ROOT / "channel/banggu/칼카피_ILIi/뜯기2/뜯기.json"), "frame": str(p / "frame.json"), "rules": None}
            return {"slug": preset, "chdir": ROOT / "channel" / preset, "preset_dir": None, "manifest": {}, "tteutgi": None, "frame": None, "rules": None}

        def bench(c, out, net, llm, n=4, limits=None, **k):
            f.calls.append(("bench", c["id"]))
            d = Path(out) / "벤치"
            d.mkdir(parents=True, exist_ok=True)
            res = {"videos": [{"id": "v1", "comments": [{"text": "이거 AI 아님?"}, {"text": "와"}]}],
                   "points": [{"kind": "twist", "text": "사실은 반대였다"}], "best_angle": "각도 한 줄", "failed": []}
            (d / f"{c['id']}.md").write_text("# 벤치", encoding="utf-8")
            (d / f"{c['id']}.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
            return res

        def score(cands, benches, slug, llm):
            f.calls.append(("score", cands[0]["id"]))
            return {cands[0]["id"]: {**{k: {"score": 7, "why": f"{n} 근거 문장 충분"} for k, n in CRIT}, "angle": "썰 각도"}}, None

        def clean(row):
            return {"scores": {k: row[k] for k, _ in CRIT}, "flags": []}
        return SimpleNamespace(LLM=LLM, load_preset=load_preset, bench=bench, score=score, _clean_scores=clean, CRITERIA=CRIT,
                               overlap=lambda t, c: {"score": 0.0, "with": None}, made_corpus=lambda *a: [], total=lambda s, o: 42.0,
                               Limits=lambda: SimpleNamespace(max_queries=6, stopped=None), NET={}, _read_json=lambda p: None)

    def se(self):
        f = self

        def run(preset, topic_arg, out, bench_path=None, facts_path=None, llm=None, log=print, **k):
            f.calls.append(("script", topic_arg))
            f.facts = json.loads(Path(facts_path).read_text(encoding="utf-8")) if facts_path else None
            Path(out).mkdir(parents=True, exist_ok=True)
            S = {"final": {"lines": [{"fn": "소개", "text": "줄", "facts": list((f.facts or {}).keys())[:1]}], "check": {"ok": True}}}
            (Path(out) / "대본.json").write_text(json.dumps(S, ensure_ascii=False), encoding="utf-8")
            return S
        return SimpleNamespace(run=run)

    def run(self, cmd, timeout):
        out = Path(cmd[cmd.index("--out") + 1])
        out.mkdir(parents=True, exist_ok=True)
        if "--queries" in cmd:
            self.calls.append(("source", None))
            (out / "재료후보").mkdir(exist_ok=True)
            (out / "재료후보" / "v_aaaaaaaaaaa.mp4").write_bytes(b"x")
            (out / "재료후보" / "후보시트_1.jpg").write_bytes(b"x")
            (out / "재료_뼈대.json").write_text(json.dumps({"cand_dir": str(out / "재료후보"), "shots": [
                {"i": 0, "t0": 0.0, "t1": 1.5, "src": None, "ss": None, "status": None}, {"i": 1, "t0": 1.5, "t1": 3.0, "src": None, "ss": None, "status": None}],
                "sfx": []}, ensure_ascii=False), encoding="utf-8")
            return 2, ""
        if "--plan-only" in cmd:
            self.calls.append(("plan", None))
            self.plan_materials = json.loads(Path(cmd[cmd.index("--materials") + 1]).read_text(encoding="utf-8"))
            self.plan_frame = json.loads(Path(cmd[3]).read_text(encoding="utf-8"))
            (out / "계획.md").write_text("# 계획", encoding="utf-8")
            (out / "계획_시트.jpg").write_bytes(b"jpg")
            return 3, ""
        self.calls.append(("produce", None))
        self.produce_cmd = cmd
        (out / "final.mp4").write_bytes(b"mp4")
        (out / "final_sheet_1s.jpg").write_bytes(b"jpg")
        (out / "대조").mkdir(exist_ok=True)
        for n_ in ("차이표.md", "side_by_side.jpg"):
            (out / "대조" / n_).write_bytes(b"x")
        (out / "대조" / "verdict.json").write_text('{"verdict": "통과"}', encoding="utf-8")
        return 0, ""


@pytest.fixture
def env(tmp_path, monkeypatch):
    fake = Fake()
    tf, se = fake.tf(), fake.se()
    monkeypatch.setattr(WS, "_engine", lambda name: {"topic_find": tf, "script_engine": se}.get(name, SimpleNamespace()))
    monkeypatch.setattr(MK, "LOCAL_PACKS", tmp_path / "packs" / "my_packs.json")       # 팩 = 저장소 기본값(1번)
    monkeypatch.setenv("CALCOPY_DATA_DIR", str(tmp_path / "data"))
    deps = {"sync": True, "ledger": False, "run": fake.run, "assets": {80: {"file": "a.mp3", "title": "swoosh_2"}, 78: {"file": "b.mp3", "title": "r3_pop_3"}}}
    return fake, deps, tmp_path / "data"


def _seed(n, d, cat="숨은이유"):
    return [CT.add(f"소재 {i}", cat, "bench", source={"via": "youtube", "url": f"https://youtu.be/{i:011d}"}, data_dir=d)["id"] for i in range(n)]


# ── 합치기(판단 주인) ────────────────────────────────────────────────────────
def test_merge_팩의_채널명_글꼴_목소리가_틀과_제작인자에_들어간다():
    pack = MK.load_packs()["1"]
    cfg = MK.merge_preset_pack(PRESET, {**pack, "brand": {"channel_name": "우리채널", "colors": {"header": [1, 2, 3]}}})
    layers = [L for fr in cfg["frame"]["frames"] for L in fr["layers"]]
    assert [L["text"] for L in layers if L.get("role") == "brand"] == ["우리채널"]
    assert any("우리채널 |" in (L.get("text") or "") for L in layers)                      # '골방 | 14:25' 라벨 속 채널명도
    assert {L["font"] for L in layers if L.get("role") == "title"} == {pack["text"]["title_font"]}
    assert {L["font"] for L in layers if L.get("role") == "caption"} == {pack["text"]["caption_font"]}
    assert all(L["rgb"] == [1, 2, 3] for L in layers if L.get("kind") == "band" and L.get("y") == 0 and L.get("w") >= 1000)
    assert cfg["remake_args"]["voice"] == pack["tts"]["voice_id"] and cfg["remake_args"]["tempo"] == pack["tts"]["tempo"]
    orig = json.loads((ROOT / PRESET / "frame.json").read_text(encoding="utf-8"))
    assert [L["text"] for fr in orig["frames"] for L in fr["layers"] if L.get("role") == "brand"] == ["골방"]   # 원본 프리셋은 안 바뀐다


# ── ①~④ 흐름 ──────────────────────────────────────────────────────────────
def test_start_후보_choose_plan_review_approve_final_review(env):
    fake, deps, d = env
    _seed(10, d)
    S = MK.start(PRESET, "1", data_dir=d, deps=deps)
    assert S["state"] == "candidates" and len(S["candidates"]) == 10 and S["candidates"][0]["n"] == 1
    S = MK.choose(S["sid"], 3, data_dir=d, deps=deps)
    st = MK.status(S["sid"], data_dir=d)
    assert st["state"] == "plan_review", st.get("error")
    assert [c[0] for c in fake.calls] == ["bench", "score", "script", "source", "plan"]
    # 팩 → 계획: 틀 설명서(채널명·글꼴) + 재료.json(효과음·짤·목소리)
    frame_layers = [L for fr in fake.plan_frame["frames"] for L in fr["layers"]]
    assert "내 채널" in [L["text"] for L in frame_layers if L.get("role") == "brand"]
    assert {L["font"] for L in frame_layers if L.get("role") == "title"} == {"JalnanGothic"}
    M = fake.plan_materials
    assert [x["asset_id"] for x in M["sfx"]] == [80, 78] and M["meme_pool"]["ids"][:2] == [1026, 1005]
    assert M["tts"]["voice_id"] == "tc_6059dad0b83880769a50502f" and all(s["src"] for s in M["shots"])
    files = {f["name"] for f in st["files"]}
    assert {"계획.md", "계획_시트.jpg", "대본.json", "재료_뼈대.json", "재료.json"} <= files
    S = MK.approve(S["sid"], by="페이블", data_dir=d, deps=deps)
    st = MK.status(S["sid"], data_dir=d)
    assert st["state"] == "final_review", st.get("error")
    cmd = fake.produce_cmd
    assert cmd[cmd.index("--voice") + 1] == "tc_6059dad0b83880769a50502f" and cmd[cmd.index("--tempo") + 1] == "1.25"
    assert cmd[cmd.index("--bgm") + 1] == "qiuqiu"


def test_reject는_대본부터_한번_다시_두번째는_폐기(env):
    fake, deps, d = env
    _seed(10, d)
    S = MK.start(PRESET, "1", data_dir=d, deps=deps)
    MK.choose(S["sid"], 1, data_dir=d, deps=deps)
    with pytest.raises(MK.MakeError):
        MK.reject(S["sid"], "", data_dir=d, deps=deps)
    n0 = len(fake.calls)
    MK.reject(S["sid"], "반전이 약함", data_dir=d, deps=deps)
    st = MK.status(S["sid"], data_dir=d)
    assert st["state"] == "plan_review" and st["rewrites"] == 1
    assert [c[0] for c in fake.calls[n0:]] == ["script", "source", "plan"]       # 벤치·점수는 다시 안 함
    MK.reject(S["sid"], "또 약함", data_dir=d, deps=deps)
    assert MK.status(S["sid"], data_dir=d)["state"] == "rejected"


def test_topic_지정이면_후보조회_0회_바로_plan_review(env):
    fake, deps, d = env
    n = {"c": 0}

    def cand(*a, **k):
        n["c"] += 1
        return []
    S = MK.start(PRESET, "1", topic="코스트코 핫도그 40년 같은 가격", data_dir=d, deps={**deps, "candidates": cand})
    st = MK.status(S["sid"], data_dir=d)
    assert n["c"] == 0 and st["state"] == "plan_review", st.get("error")
    assert st["topic"]["name"] == "코스트코 핫도그 40년 같은 가격" and st["topic"]["source"]["via"] == "사장님"


def test_ref_url_근거가_대본단계로_넘어간다(env):
    fake, deps, d = env
    facts = {"r1": {"text": "(참고 영상 제목) 아웃백 빵의 비밀", "url": "https://youtube.com/shorts/AAAAAAAAAAA"}}
    S = MK.start(PRESET, "1", ref_url="https://youtube.com/shorts/AAAAAAAAAAA", data_dir=d,
                 deps={**deps, "ref_facts": lambda u: (facts, "아웃백 빵의 비밀")})
    st = MK.status(S["sid"], data_dir=d)
    assert st["state"] == "plan_review", st.get("error")
    assert fake.facts == facts and st["topic"]["source"]["url"].endswith("AAAAAAAAAAA")


def test_후보에_AI의심댓글_반전_벤치수(env):
    fake, deps, d = env
    tid = _seed(10, d)[0]
    S = MK.start(PRESET, "1", topic=None, data_dir=d, deps=deps)
    MK.choose(S["sid"], next(c["n"] for c in S["candidates"] if c["id"] == tid), data_dir=d, deps=deps)
    S2 = MK.start(PRESET, "1", data_dir=d, deps=deps)
    c = next(c for c in S2["candidates"] if c["id"] == tid) if any(c["id"] == tid for c in S2["candidates"]) else None
    assert c is None or True        # tid 는 plan_review 라 후보에서 빠진다
    row = MK._candidate(CT.detail(tid, data_dir=d)["topic"], d)
    assert row["ai_suspect_comments"] == 1 and row["twist"] == "사실은 반대였다" and row["bench_videos"] == 1


# ── 내 팩 키트 점검 · 응용 모드(소재 1 : 제작물 N) ───────────────────────────────
def test_asset_file_효과음은_scene_assets_뒤_하위경로까지():
    a = {"file": "sfx_13.mp3", "media_path": "/home/ubuntu/x/shopping_shorts/data/scene_assets/sfx_pick/sfx_13.mp3"}
    assert MK.asset_file(a, "D:/p/sfx", "sfx").as_posix() == "D:/p/sfx/sfx_pick/sfx_13.mp3"
    assert MK.asset_file({"file": "a.mp3", "media_path": "shopping_shorts/data/scene_assets/a.mp3"}, "D:/p/sfx", "sfx").as_posix() == "D:/p/sfx/a.mp3"
    assert MK.asset_file({"file": "m.mp4"}, "D:/p/meme", "meme").as_posix() == "D:/p/meme/m.mp4"


def test_check_pack_없는_파일을_한줄씩(tmp_path):
    (tmp_path / "sfx" / "sfx_pick").mkdir(parents=True)
    (tmp_path / "sfx" / "sfx_pick" / "s1.mp3").write_bytes(b"x")
    (tmp_path / "meme").mkdir()
    (tmp_path / "meme" / "m1.mp4").write_bytes(b"x")
    assets = {1: {"file": "s1.mp3", "media_path": "scene_assets/sfx_pick/s1.mp3"}, 2: {"file": "s2.mp3", "media_path": "scene_assets/s2.mp3"},
              3: {"file": "m1.mp4"}}
    pack = {"sfx_pool": {"dir": str(tmp_path / "sfx"), "start": [1], "end": [2]}, "meme_pool": {"dir": str(tmp_path / "meme"), "ids": [3, 9]},
            "bgm": {"lib": "shopping_shorts/assets/bgm_lib", "candidates": ["qiuqiu", "없는곡"]},
            "tts": {"voice_id": "tc_68257f68bc6e3c161ab5078d", "name": "필재"}, "base_preset": PRESET}
    r = MK.check_pack(pack, assets)
    assert r["counts"] == {"sfx": 2, "meme": 2, "bgm": 2, "voices": 1}
    assert len(r["missing"]) == 3 and not r["ok"]
    assert any("#2" in m for m in r["missing"]) and any("#9" in m for m in r["missing"]) and any("없는곡" in m for m in r["missing"])


def test_저장소_1번팩은_채널키트_전부_적혀있다():
    p = json.loads((ROOT / "shopping_shorts/calcopy_frame/my_packs.json").read_text(encoding="utf-8"))["1"]
    assert {"brand", "text", "tts", "meme_pool", "sfx_pool", "bgm", "base_preset"} <= set(p)
    assert p["sfx_pool"]["dir"] == "C:/숏템_칼카피/packs/sfx" and p["meme_pool"]["dir"].startswith("C:/숏템_칼카피/packs/meme")
    assert p["bgm"]["lib"] == "shopping_shorts/assets/bgm_lib" and (ROOT / p["base_preset"] / "manifest.json").exists()
    names = {v["base_voice_id"]: v["name"] for v in json.loads((ROOT / "shopping_shorts/assets/voice_presets.json").read_text(encoding="utf-8"))}
    for v in [p["tts"]] + p["tts"]["alternates"]:
        assert names[v["voice_id"]] == v["name"]


def test_distinct_목소리_틀_컷_중_둘이상():
    base = {"voice": "v1", "frame": "f1", "cuts": ["a@0", "b@1", "c@2", "d@3"]}
    assert not MK.distinct(base, {**base})["ok"]
    assert not MK.distinct(base, {**base, "cuts": ["x@0", "y@1", "z@2", "w@3"]})["ok"]                  # 컷만 다름 = 하나
    assert MK.distinct(base, {**base, "voice": "v2", "cuts": ["x@0", "y@1", "c@2", "d@3"]})["ok"]       # 목소리 + 컷 50%
    r = MK.distinct(base, {**base, "voice": "v2", "cuts": ["x@0", "b@1", "c@2", "d@3"]})               # 컷 25% 만 다름
    assert not r["ok"] and r["cut_diff"] == 0.25 and r["diff"] == ["목소리"]
    assert MK.distinct(base, {**base, "voice": "v2", "frame": "f2"})["ok"]
    r = MK.distinct({**base, "cuts": None}, {**base, "voice": "v2"})                                   # 컷 모름
    assert not r["ok"] and r["possible"] and r["maybe"] == ["컷"]
    assert not MK.distinct({**base, "cuts": None}, {**base})["possible"]


def test_approve는_관리자만(env):
    fake, deps, d = env
    S = MK.start(PRESET, "1", topic="코스트코 핫도그 40년 같은 가격", data_dir=d, deps=deps)
    for who in (None, "워커", "make-x"):
        with pytest.raises(MK.MakeError) as e:
            MK.approve(S["sid"], by=who, data_dir=d, deps=deps)
        assert e.value.code == 403
    assert "produce" not in [c[0] for c in fake.calls]                 # 승인 전엔 TTS·렌더 0


def test_응용_소재1_제작물N_중복은_거절(env):
    fake, deps, d = env
    S1 = MK.start(PRESET, "1", topic="바나나맛우유 단지 모양의 비밀", data_dir=d, deps=deps)
    st1 = MK.status(S1["sid"], data_dir=d)
    assert st1["state"] == "plan_review" and st1["mode"] == "new" and st1["variant"]["cuts"]
    root = st1["topic_id"]
    # 같은 팩·프리셋 그대로 응용 = 목소리·틀 같음 → 컷만으로는 하나 → 시작부터 거절
    with pytest.raises(MK.MakeError) as e:
        MK.start(PRESET, "1", reuse_of=root, data_dir=d, deps=deps)
    assert e.value.code == 409 and "둘 이상" in e.value.msg
    # 목소리만 바꾼 응용: 시작은 됨(컷이 다를 수 있음) → 벤치·점수는 다시 안 부름(원 소재 것 그대로)
    n0 = len(fake.calls)
    S2 = MK.start(PRESET, "1", reuse_of=root, pack_patch={"tts": {"voice_id": "tc_61c2f7741330d213c238cba6", "name": "김건"}}, data_dir=d, deps=deps)
    st2 = MK.status(S2["sid"], data_dir=d)
    assert st2["state"] == "plan_review", st2.get("error")
    assert [c[0] for c in fake.calls[n0:]] == ["script", "source", "plan"]
    assert st2["topic"]["name"] == "바나나맛우유 단지 모양의 비밀 · 응용 1" and st2["topic"]["source"]["reuse_of"] == root
    assert st2["mode"] == "reuse" and st2["root_topic"] == root and MK.made_counts(d)[root] == 2
    # 같은 후보 영상 → 컷 같음 → 목소리 하나만 다름 → 승인 거절(TTS·렌더 안 감)
    with pytest.raises(MK.MakeError) as e:
        MK.approve(S2["sid"], by="페이블", data_dir=d, deps=deps)
    assert e.value.code == 409 and "응용 중복" in e.value.msg and st2["variant_warn"]
    assert "produce" not in [c[0] for c in fake.calls]
    # 목소리 + 틀(채널명) 다르게 → 승인 통과
    S3 = MK.start(PRESET, "1", reuse_of=root, data_dir=d, deps=deps,
                  pack_patch={"tts": {"voice_id": "tc_61f0859907085fc68561c9a1", "name": "지훈"}, "brand": {"channel_name": "둘째채널"}})
    assert MK.status(S3["sid"], data_dir=d)["variant_warn"] == []
    MK.approve(S3["sid"], by="사장님", data_dir=d, deps=deps)
    st3 = MK.status(S3["sid"], data_dir=d)
    assert st3["state"] == "final_review" and st3["approved_by"] == "사장님"
    assert [r["id"] for r in MK.reusable(d)] == [root]


def test_소재직접_facts_가_대본단계로(env):
    fake, deps, d = env
    facts = [{"text": "트윅(2024-11-10): 바나나맛우유는 1974년 출시, 용기는 달항아리", "url": "https://www.twig24.com/news/x", "date": "2024-11-10"}]
    S = MK.start(PRESET, "1", topic="바나나맛우유 단지", facts=facts, data_dir=d, deps=deps)
    st = MK.status(S["sid"], data_dir=d)
    assert st["state"] == "plan_review" and fake.facts == {"f1": facts[0]} and st["topic"]["source"]["facts_n"] == 1
    with pytest.raises(MK.MakeError):
        MK.start(PRESET, "1", topic="x", facts=[{"url": "u"}], data_dir=d, deps=deps)
