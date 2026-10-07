# -*- coding: utf-8 -*-
"""관제 143 확장(10-06 사장님) — 2단계에 실제 짤이 미리 보이고(⭐ 중 랜덤, 같은 작업 = 같은 짤), 그 짤이 3단계에 그대로 들어간다.
줄 효과음: 짤 줄엔 리액션 탄성, 센 마무리엔 박수/환호. 썰 효과음팩과 같은 순간 두 발 없음. 자산 없으면 로그+건너뜀.
판단 주인: storyboard.meme_choose(짤 고르기) · storyboard.sfx_category/sfx_choose(효과음). 미리보기·3단계·API 는 그 함수를 부를 뿐."""
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod
from shopping_shorts import mix_pipeline
from shopping_shorts import sfx_pack
from shopping_shorts import storyboard as sb
from shopping_shorts import video_assemble as va
from shopping_shorts.store import Store
from shopping_shorts.tests.test_sfx_pack import _Store, _tl

POOL = {"놀람": [{"asset_id": i, "duration": 3.0} for i in range(11, 21)],
        "충격_입막": [{"asset_id": 31, "duration": 3.0}, {"asset_id": 32, "duration": 3.0}]}
FAV = {"놀람": [12, 15, 18]}
BANK = {"리액션 탄성": [{"asset_id": 501}, {"asset_id": 502}, {"asset_id": 503}], "박수/환호": [{"asset_id": 601}]}
WORDS = [{"word": "와", "start": 0.0, "end": 1.2}, {"word": "이거", "start": 1.3, "end": 1.6}]


def _board():
    return [{"slot": "hook", "line": "와 이거 뭐야", "meme_emotion": "놀람"},
            {"slot": "how", "line": "이렇게 쓰면 돼요"},
            {"slot": "twist", "line": "근데 진짜 충격", "meme_emotion": "충격_입막"},
            {"slot": "cta", "line": "이러니 품절대란이 났지"}]


# ── 짤 고르기 ─────────────────────────────────────────────────────

def test_즐겨찾기_랜덤_같은key_같은짤_key20개면_고루():
    got = []
    for n in range(20):
        a = sb.meme_choose("놀람", POOL["놀람"], FAV, "job%d" % n)["asset_id"]
        assert a == sb.meme_choose("놀람", POOL["놀람"], FAV, "job%d" % n)["asset_id"]     # 같은 작업 = 같은 짤
        got.append(a)
    c = Counter(got)
    assert set(c) == {12, 15, 18}, c                 # ⭐ 밖 짤은 안 나온다
    assert min(c.values()) >= 3, c                   # 20개 작업이면 ⭐ 3개가 고루(순번이면 12만 20번)


def test_즐겨찾기_없는_감정은_팩에서_종전_공식():
    import zlib
    cands = POOL["충격_입막"]
    a = sb.meme_choose("충격_입막", cands, FAV, "jobX")
    assert a is cands[zlib.crc32("jobX|충격_입막".encode("utf-8")) % len(cands)]


def test_2단계_미리고른_짤이_3단계_짤과_같다():
    for n in range(20):
        slots = _board()
        sb.meme_preview(slots, POOL, FAV, key="w-%d" % n)
        assert slots[0]["meme_auto"] == 1 and slots[0]["meme_pick"] in FAV["놀람"]
        assert slots[2]["meme_pick"] in (31, 32) and "meme_pick" not in slots[1]
        # 확정 길(carry_picks) → 3단계 meme_slots(다른 key 여도 2단계 짤 그대로)
        beats = [dict({"beat_idx": i, "narration": sl["line"], "sig_rank": 1 if i == 0 else (3 if i == 2 else 0),
                       "signal": "와" if i == 0 else ("근데" if i == 2 else "")}, **sb.carry_picks(sl)) for i, sl in enumerate(slots)]
        plan = {"beats": beats}
        sb.meme_slots(plan, lambda b: (WORDS if b["beat_idx"] == 0 else [{"word": "근데", "start": 0, "end": 1.1}], 4.0),
                      POOL, key="job-other", prefs=FAV)
        assert plan["beats"][0]["cutaway"]["asset_id"] == slots[0]["meme_pick"]
        assert plan["beats"][2]["cutaway"]["asset_id"] == slots[2]["meme_pick"]


def test_사람이_서랍에서_바꾼_짤은_그대로():
    slots = _board()
    slots[0]["meme_pick"], slots[0]["meme_manual"] = 19, 1    # 서랍에서 직접 고름(10-07: 명시 표식)
    sb.meme_preview(slots, POOL, FAV, key="w")
    assert slots[0]["meme_pick"] == 19 and "meme_auto" not in slots[0]


# ── 효과음 자리 ──────────────────────────────────────────────────

def test_줄_효과음_짤엔_리액션_센마무리엔_박수_자산없으면_로그():
    slots = _board()
    sb.meme_preview(slots, POOL, FAV, key="w")
    sb.sfx_preview(slots, BANK, key="w")
    assert slots[0]["sfx_cat"] == "리액션 탄성" and slots[0]["sfx_pick"] in (501, 502, 503)
    assert "sfx_pick" not in slots[1] and "sfx_cat" not in slots[1]          # 그 밖 줄은 썰 효과음팩 몫
    assert slots[3]["sfx_cat"] == "박수/환호" and slots[3]["sfx_pick"] == 601
    logs = []
    s2 = _board()
    sb.sfx_preview(s2, {}, key="w", log=logs.append)
    assert not any("sfx_pick" in x for x in s2) and "줄 1 효과음 없음(리액션 탄성)" in logs


def test_3단계_짤효과음_실림_짤빼면_빠짐_사람이뺀칸_그대로():
    cw = sb.meme_cut({"asset_id": 12}, 1.2, "놀람")
    plan = {"beats": [{"beat_idx": 0, "narration": "와 이거", "cutaway": dict(cw)},
                      {"beat_idx": 1, "narration": "그냥"},
                      {"beat_idx": 2, "narration": "와 또", "cutaway": dict(cw), "sfx_off": 1}]}
    sb.sfx_slots(plan, BANK, key="j")
    assert plan["beats"][0]["sfx"]["match_type"] == "line" and plan["beats"][0]["sfx"]["cat"] == "리액션 탄성"
    assert "sfx" not in plan["beats"][1] and "sfx" not in plan["beats"][2]
    plan["beats"][0].pop("cutaway")
    plan["beats"][0]["meme_off"] = 1
    sb.sfx_slots(plan, BANK, key="j")
    assert "sfx" not in plan["beats"][0]                     # 짤을 빼면 효과음도 빠진다
    res = sb.sfx_slots({"beats": [{"beat_idx": 0, "narration": "와", "cutaway": dict(cw)}]}, {}, key="j")
    assert res[0]["why"] == "효과음 없음(리액션 탄성)"


def test_2단계_효과음이_3단계_효과음과_같다():
    slots = _board()
    sb.meme_preview(slots, POOL, FAV, key="w-1")
    sb.sfx_preview(slots, BANK, key="w-1")
    beats = [dict({"beat_idx": i, "narration": sl["line"]}, **sb.carry_picks(sl)) for i, sl in enumerate(slots)]
    beats[0]["cutaway"] = sb.meme_cut({"asset_id": slots[0]["meme_pick"]}, 1.2, "놀람")
    sb.sfx_slots({"beats": beats}, BANK, key="job-other")
    assert beats[0]["sfx"]["asset_id"] == slots[0]["sfx_pick"] and beats[3]["sfx"]["asset_id"] == 601


def test_썰팩과_같은순간_두발_없음_그줄_첫발만_비움():
    tl = _tl()
    tl[3]["sfx"] = sb.sfx_line(501, "리액션 탄성")
    base = sfx_pack.plan_events(tl)
    got = sfx_pack.plan_events(tl, first_beats={3})
    t0 = tl[3]["t0"]
    assert [e for e in base if abs(e[1] - t0) < 0.05]            # 팩만이면 그 줄 시작에 한 발 있었다
    assert not [e for e in got if abs(e[1] - t0) < 0.05]         # 줄 효과음이 대신 — 팩은 비운다
    assert len(base) - len(got) == 1                             # 그 줄 나머지 팩 소리는 그대로
    # 렌더·캡컷 공통 입구: _resolve_sfx_paths(줄 효과음 남김) → sfx_events_for
    plan = {"beats": [dict(beat_idx=b["beat_idx"], **({"sfx": b["sfx"]} if b.get("sfx") else {})) for b in tl]}
    paths = mix_pipeline._resolve_sfx_paths(_Store(assets={501: {"media_path": "wow.wav"}}), plan, 3,
                                            job={"job_id": "j3", "customer_id": 3, "deco": {}})
    assert paths.get(3) == "wow.wav" and "_pack" in paths
    ev = va.sfx_events_for(tl, paths)
    at = [e for e in ev if abs(e[1] - t0) < 0.05]
    assert len(at) == 1 and at[0][0] == "wow.wav"


# ── API ─────────────────────────────────────────────────────────

@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    st = Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    ids = {}
    for emo in ("놀람", "놀람", "충격_입막"):
        f = tmp_path / ("m%d.mp4" % len(ids))
        f.write_bytes(b"x")
        ids.setdefault(emo, []).append(st.add_scene_asset({"asset_type": "clip", "render_mode": "cutaway", "media_path": str(f),
                                                           "duration": 3.0, "title": "t", "category": "meme", "tone": emo}, customer_id=0))
    f = tmp_path / "wow.wav"
    f.write_bytes(b"x")
    sid = st.add_scene_asset({"asset_type": "sfx", "media_path": str(f), "duration": 0.8, "title": "와우", "category": "리액션 탄성"}, customer_id=0)
    st.create_mix_job("j1", ["u"], 20, "free")
    st.update_mix_job("j1", status="ready_for_review", edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "narration": "그냥 문장", "tts_path": "x.mp3"}]})
    monkeypatch.setattr(mix_pipeline, "_meme_words_of", lambda b: (None, 4.0))
    monkeypatch.setattr(app_mod, "_sb_job", lambda req, key: (key, {"v": {}}, None))
    monkeypatch.setattr(app_mod, "_sb_gate", lambda req: None)        # 스토리보드 스위치는 이 시험 밖
    return st, ids, sid, TestClient(app_mod.app)


def test_api_2단계_고르기와_효과음서랍_짤빼면_효과음도(env):
    st, ids, sid, c = env
    st.set_setting("meme_enabled", "")
    assert c.get("/api/sfx/bank").status_code == 403
    r = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _board()}).json()
    assert "meme_pick" not in r["slots"][0]                     # 스위치 꺼짐 = 보드 그대로
    st.set_setting("meme_enabled", "1")
    bank = c.get("/api/sfx/bank").json()
    assert [x["name"] for x in bank["cats"]] == list(sb.SFX_CATS) and bank["items"][0]["id"] == sid
    r1 = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _board()}).json()["slots"]
    r2 = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _board()}).json()["slots"]
    assert r1[0]["meme_pick"] in ids["놀람"] and r1[0]["meme_pick"] == r2[0]["meme_pick"]
    assert r1[0]["sfx_pick"] == sid and "sfx_pick" not in r1[3]       # 박수/환호 자산 없음 → 건너뜀
    # 3단계: 짤 넣으면 리액션 효과음, 빼면 같이 빠진다
    c.post("/api/produce/mix/j1/meme", json={"beat_idx": 0, "asset_id": ids["놀람"][0]})
    assert st.get_mix_job("j1")["edit_plan"]["beats"][0]["sfx"]["asset_id"] == sid
    c.post("/api/produce/mix/j1/meme", json={"beat_idx": 0, "asset_id": None})
    assert "sfx" not in st.get_mix_job("j1")["edit_plan"]["beats"][0]
    # 3단계 서랍에서 고르기 → 사람 고름, 빼기 → sfx_off
    assert c.post("/api/produce/mix/j1/sfx", json={"beat_idx": 0, "asset_id": sid}).json()["sfx"]["manual"] == 1
    c.post("/api/produce/mix/j1/sfx", json={"beat_idx": 0})
    b0 = st.get_mix_job("j1")["edit_plan"]["beats"][0]
    assert "sfx" not in b0 and b0["sfx_off"] == 1


def test_api_효과음_별_저장_분류는_서버가_정하고_picks가_별을_쓴다(env):
    st, ids, sid, c = env
    st.set_setting("meme_enabled", "1")
    r = c.post("/api/sfx/prefs", json={"prefs": [{"asset_id": sid, "rank": 1}, {"asset_id": 999999}]}).json()
    assert r["prefs"] == [{"asset_id": sid, "cat": "리액션 탄성", "rank": 1}]
    assert c.get("/api/sfx/bank").json()["prefs"] == r["prefs"]
    slots = c.post("/api/produce/storyboard/w-1/picks", json={"slots": _board()}).json()["slots"]
    assert slots[0]["sfx_pick"] == sid and slots[0]["sfx_auto"] == 1
