# -*- coding: utf-8 -*-
"""관제 143 감정짤 회원 기능 — 감정별 우선 짤 · 사람이 고른 짤 보존 · [＋짤] 길이 · 2단계 미리 고른 짤 · 스위치 꺼짐 불변.
판단 주인: storyboard.meme_head(길이) · storyboard.meme_slots(자리·고르기). 서버 API 는 그 함수를 부를 뿐."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod
from shopping_shorts import mix_pipeline
from shopping_shorts import storyboard as sb
from shopping_shorts.store import Store

STATIC = Path(__file__).resolve().parents[1] / "static"
POOL = {"놀람": [{"asset_id": 11, "duration": 3.0}, {"asset_id": 12, "duration": 3.0}, {"asset_id": 13, "duration": 3.0}],
        "충격_입막": [{"asset_id": 31, "duration": 3.0}]}


def _w(*pairs):
    return [{"word": w, "start": s, "end": e} for w, s, e in pairs]


def _beat(idx, rank, signal, narr, **kw):
    b = {"beat_idx": idx, "narration": narr, "sig_rank": rank, "signal": signal}
    b.update(kw)
    return b


WORDS = _w(("와", 0.0, 1.2), ("이거", 1.3, 1.6))


def _slots(beats, prefs=None, key="k"):
    plan = {"beats": beats}
    res = sb.meme_slots(plan, lambda b: (WORDS, 4.0), POOL, key=key, prefs=prefs)
    return plan, {r["beat_idx"]: r for r in res}


# ── 판단(storyboard) ─────────────────────────────────────────────

def test_우선_짤부터_순서대로_한편에_같은짤_두번_없음():
    beats = [_beat(0, 1, "와", "와 이거"), _beat(1, 1, "와", "와 이거")]
    prefs = sb.meme_prefs_by_emotion([{"asset_id": 13, "emotion": "놀람", "rank": 1},
                                      {"asset_id": 12, "emotion": "놀람", "rank": 2}])
    _p, r = _slots(beats, prefs)
    assert r[0]["asset_id"] == 13 and r[1]["asset_id"] == 12


def test_우선_짤_없으면_종전_해시_그대로():
    beats = [_beat(0, 1, "와", "와 이거")]
    _p, a = _slots([dict(b) for b in beats], prefs=None, key="job1")
    _p, b = _slots([dict(b) for b in beats], prefs={}, key="job1")
    assert a[0]["asset_id"] == b[0]["asset_id"]          # prefs 가 비면 결과 불변


def test_사람이_고른_짤과_뺀_칸은_다시_정할때_보존():
    manual = sb.meme_cut({"asset_id": 31}, 1.4, "충격_입막", manual=True)
    beats = [_beat(0, 1, "와", "와 이거", cutaway=dict(manual)), _beat(1, 1, "와", "와 이거", meme_off=1)]
    plan, r = _slots(beats, prefs={"놀람": [11]})
    assert plan["beats"][0]["cutaway"] == manual            # 손댄 짤 그대로
    assert "cutaway" not in plan["beats"][1] and r[1]["why"] == "사람이 뺌"


def test_2단계_미리_고른_짤을_먼저():
    beats = [_beat(0, 1, "와", "와 이거", meme_pick=31)]
    plan, r = _slots(beats, prefs={"놀람": [11]})
    assert r[0]["asset_id"] == 31 and plan["beats"][0]["cutaway"]["emotion"] == "충격_입막"


def test_더하기짤_길이_신호어_없으면_기본_남은장면_1초():
    b = {"beat_idx": 0, "narration": "그냥 문장", "signal": ""}
    assert sb.meme_head(b, None, 4.0, manual=True) == (sb.MEME_DEFAULT_SEC, None)
    head, why = sb.meme_head(b, None, 2.0, manual=True)          # 2.0-1.25 < 1.0
    assert head is None and "남은 시간" in why
    assert sb.meme_head(b, None, 4.0)[0] is None                  # 자동은 신호어 시각 없으면 안 넣는다
    b2 = {"beat_idx": 0, "narration": "와 이거", "signal": "와"}
    assert sb.meme_head(b2, WORDS, 4.0, manual=True) == (1.2, None)   # 자동과 같은 규칙


def test_신호어_감정을_칸에_싣는다():
    from shopping_shorts import story_writer as _sw
    slots = [{"slot": "hook", "line": "a"}, {"slot": "reveal", "line": "b"}, {"slot": "escalation", "line": "c"},
             {"slot": "escalation", "line": "d"}, {"slot": "twist", "line": "e"}, {"slot": "land", "line": "f"}]
    sb.apply_signals(slots, "k", 0, True)
    for sl in slots:
        exp = sb.meme_emotion(int(sl.get("sig_rank") or 0), sl.get("signal") or "") if sl.get("sig_rank") else None
        assert sl.get("meme_emotion") == exp


def test_스토리보드_줄의_미리고른짤이_편성까지():
    from shopping_shorts.story_writer import storyboard_to_beat_sources
    out = storyboard_to_beat_sources([{"slot": "esc", "line": "와 이거", "ids": [], "sig_rank": 1, "signal": "와", "meme_pick": 31}])
    assert out["beat_sources"][0]["meme_pick"] == 31


# ── API ─────────────────────────────────────────────────────────

@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    st = Store(db)
    monkeypatch.setattr(app_mod, "DB_PATH", db)
    ids = []
    for emo in ("놀람", "놀람", "충격_입막"):
        f = tmp_path / ("m%d.mp4" % len(ids))
        f.write_bytes(b"x")
        ids.append(st.add_scene_asset({"asset_type": "clip", "render_mode": "cutaway", "media_path": str(f),
                                       "duration": 3.0, "title": "t", "category": "meme", "tone": emo}, customer_id=0))
    st.create_mix_job("j1", ["u"], 20, "free")
    st.update_mix_job("j1", status="ready_for_review", edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "narration": "그냥 문장", "tts_path": "x.mp3"},
        {"beat_idx": 1, "narration": "다른 칸", "cutaway": {"asset_id": 99, "match_type": "ai"}}]})
    monkeypatch.setattr(mix_pipeline, "_meme_words_of", lambda b: (None, 4.0))
    return st, ids, TestClient(app_mod.app)


def test_스위치_꺼지면_전부_403_편성_불변(env):
    st, ids, c = env
    st.set_setting("meme_enabled", "")
    before = st.get_mix_job("j1")["edit_plan"]
    for r in (c.get("/api/meme/pack"), c.get("/api/meme/prefs"), c.post("/api/meme/prefs", json={"prefs": []}),
              c.get("/api/meme/%d/media" % ids[0]), c.post("/api/produce/mix/j1/meme", json={"beat_idx": 0, "asset_id": ids[0]})):
        assert r.status_code == 403
    assert st.get_mix_job("j1")["edit_plan"] == before
    assert c.get("/meme_pack", follow_redirects=False).status_code == 302
    assert c.get("/api/me").json().get("meme") is False


def test_우선짤_저장_감정은_서버가_정하고_자동배치에_반영(env):
    st, ids, c = env
    st.set_setting("meme_enabled", "1")
    r = c.post("/api/meme/prefs", json={"prefs": [{"asset_id": ids[1], "emotion": "엉뚱", "rank": 1}, {"asset_id": 424242, "rank": 2}]})
    assert r.status_code == 200
    assert r.json()["prefs"] == [{"asset_id": ids[1], "emotion": "놀람", "rank": 1}]
    pk = c.get("/api/meme/pack").json()
    assert {e["name"]: e["count"] for e in pk["emotions"]} == {"놀람": 2, "충격_입막": 1}
    assert mix_pipeline._meme_prefs(st, 0) == {"놀람": [ids[1]]}


def test_더하기짤_서버가_길이_계산_manual_표시_다른끼움장면은_거절(env):
    st, ids, c = env
    st.set_setting("meme_enabled", "1")
    r = c.post("/api/produce/mix/j1/meme", json={"beat_idx": 0, "asset_id": ids[2]})
    assert r.status_code == 200, r.text
    cw = st.get_mix_job("j1")["edit_plan"]["beats"][0]["cutaway"]
    assert cw["manual"] == 1 and cw["head_sec"] == sb.MEME_DEFAULT_SEC and cw["emotion"] == "충격_입막" and cw["vid"] == "meme_%d" % ids[2]
    assert c.post("/api/produce/mix/j1/meme", json={"beat_idx": 1, "asset_id": ids[0]}).status_code == 409
    r = c.post("/api/produce/mix/j1/meme", json={"beat_idx": 0, "asset_id": None})
    b0 = st.get_mix_job("j1")["edit_plan"]["beats"][0]
    assert r.status_code == 200 and "cutaway" not in b0 and b0["meme_off"] == 1


def test_화면_스위치_자리():
    sbjs = (STATIC / "sidebar.js").read_text(encoding="utf-8")
    assert "/meme_pack" in sbjs and "ss-meme-only" in sbjs and "d.meme === true" in sbjs
    lab = (STATIC / "scene_lab.html").read_text(encoding="utf-8")
    assert "memeControl(i)" in lab and "DATA.meme_enabled" in lab and "/meme_pack.js" in lab
    prod = (STATIC / "produce.html").read_text(encoding="utf-8")
    assert "sbMemeCell" in prod and "window.MEME_ON" in prod and "MIX_MEME_ON" in prod
