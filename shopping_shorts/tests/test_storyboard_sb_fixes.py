# -*- coding: utf-8 -*-
"""관제 120 장면배분 후속(2026-10-07): ① 스토리보드 일 시간 상한 ② 끼워 넣기 말투 = 그 보드 스타일
③ 끼운 문장 이음(앞뒤 문장·검수 재작성) ④ 0.8초 미만 조각(서버 하한 = 화면 하한) ⑤ 줄 효과음 분류별 볼륨."""
import json
import re
import sqlite3
import time
from pathlib import Path

import pytest

from shopping_shorts import storyboard as sb
from shopping_shorts import video_assemble as va

ROOT = Path(__file__).resolve().parents[1]


# ── ④ 0.8초 하한: 서버 한 곳 = 화면 값 ──────────────────────────────────────

def test_min_clip_server_equals_screen():
    js = (ROOT / "static" / "scene_play.js").read_text(encoding="utf-8")
    m = re.search(r"MIN_CLIP\s*=\s*([0-9.]+)", js)
    assert m and float(m.group(1)) == sb._min_clip() == va._MIN_CLIP


def _ex():
    return {"v1": {"segments": [
        {"seg_id": "v1-0", "start": 0.0, "end": 0.7, "scene_desc": "짧은 조각"},
        {"seg_id": "v1-1", "start": 0.7, "end": 2.5, "scene_desc": "긴 조각"},
        {"seg_id": "v1-2", "start": 2.5, "end": 3.29, "scene_desc": "0.79초"},
    ]}}


def _db(tmp_path):
    p = tmp_path / "t.db"
    if p.exists():
        return p
    c = sqlite3.connect(p)
    c.execute("create table spine(id integer, name text, situation_type text, fit_categories_json text, beat_roles_json text,"
              " beat_chain_json text, emotion_arc text, templates_json text, voice_json text, appeal text, status text)")
    c.execute("insert into spine values(1,'유튜브 썰','', '[]', ?, '[]', '', '{}', ?, '', 'approved')",
              (json.dumps(["title", "hook", "feature", "closing"]), json.dumps({"tone_note": "반말 썰", "endings": ["~거든"]})))
    c.execute("insert into spine values(2,'인스타 체험','', '[]', ?, '[]', '', '{}', ?, '', 'approved')",
              (json.dumps(["hook", "pain", "feature", "closing"]), json.dumps({"tone_note": "존댓말 체험담", "endings": ["~요"]})))
    c.commit()
    c.close()
    return p


def test_materials_drop_short_unless_kept(tmp_path):
    db = sb._ro(_db(tmp_path))
    segs, *_ = sb._materials(db, "j", _ex())
    assert set(segs) == {"v1-1"}                      # 0.7·0.79초는 AI 후보에서 빠진다
    segs, *_ = sb._materials(db, "j", _ex(), keep={"v1-0"})
    assert set(segs) == {"v1-0", "v1-1"}              # 사람이 담은 조각은 그대로


# ── ⑤ 줄 효과음 분류별 볼륨 ───────────────────────────────────────────────

def test_line_sfx_gain_table():
    base = sb.SFX_VOL_BASE
    for cat in ("리액션 탄성", "웃음", "박수/환호"):
        assert abs(base * sb.line_sfx_gain(cat) - 1.0) < 1e-9
    for cat in ("놀람", "긴장", None):
        assert abs(base * sb.line_sfx_gain(cat) - 0.8) < 1e-9


def test_sfx_events_carry_line_gain_render_and_capcut_use_it():
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": 2.0, "narration": "와 이거 뭐야", "sfx": sb.sfx_line(1, "리액션 탄성")},
          {"beat_idx": 1, "t0": 2.0, "dur": 2.0, "narration": "근데 진짜", "sfx": sb.sfx_line(2, "긴장")},
          {"beat_idx": 2, "t0": 4.0, "dur": 2.0, "narration": "옛 효과음", "sfx": {"asset_id": 3, "position": "first"}}]
    ev = va.sfx_events_for(tl, {0: "a.wav", 1: "b.wav", 2: "c.wav"})
    assert abs(0.6 * ev[0][2] - 1.0) < 1e-9 and abs(0.6 * ev[1][2] - 0.8) < 1e-9
    assert len(ev[2]) == 2                             # 줄 효과음이 아닌 것은 종전 그대로(보정 없음)
    # 렌더·캡컷은 '효과음 볼륨 × ev[2]' 같은 식(코드 확인 — 두 길이 같은 칸을 읽는다)
    src_va = (ROOT / "video_assemble.py").read_text(encoding="utf-8")
    src_cc = (ROOT / "capcut_draft.py").read_text(encoding="utf-8")
    assert "volume={sfx_vol * gain:.3f}" in src_va and "float(ev[2]) if len(ev) > 2" in src_va
    assert '"volume": _sfx_vol * _gain' in src_cc and "float(_ev[2]) if len(_ev) > 2" in src_cc


def test_sfx_pick_gets_category_for_volume():
    bank = {"웃음": [{"asset_id": 7}], "긴장": [{"asset_id": 8}]}
    plan = {"beats": [{"beat_idx": 0, "narration": "ㅋㅋ", "sfx_pick": 7, "sfx_manual": 1}]}
    sb.sfx_slots(plan, bank, key="k")
    assert plan["beats"][0]["sfx"]["cat"] == "웃음" and plan["beats"][0]["sfx"]["manual"] == 1


# ── ② ③ 끼워 넣기: 보드 말투·앞뒤 문장·검수 재작성 ───────────────────────────

def _board(yt):
    return {"names": ["유튜브 썰" if yt else "인스타 체험"], "sig_yt": yt, "sig_key": "j:k",
            "slots": [{"slot": "title" if yt else "hook", "line": "이거 보고 진짜 놀랐거든", "ids": ["v1-1"]},
                      {"slot": "hook", "line": "물만 부으면 거품이 올라와", "ids": []},
                      {"slot": "feature", "line": "손에 묻지도 않아", "ids": []},
                      {"slot": "closing", "line": "이러니 품절이지", "ids": []}]}


def test_insert_uses_board_platform_and_seam(tmp_path, monkeypatch):
    prompts = []

    def fake(prompt, schema, note=None, vertex=True, model=None):
        prompts.append(prompt)
        if "inserts" in json.dumps(schema):
            return {"inserts": [{"after": 2, "slot": "escalation", "line": "심지어 기름때도 바로 지워져", "ids": []}]}
        return {"fix": []}
    monkeypatch.setattr(sb.sg, "_call_json", fake)
    sb._HEAD_CACHE.clear()
    from shopping_shorts import story_writer as sw
    out = sb.insert(_db(tmp_path), "j", {"board": _board(True), "extra": ["escalation"], "key": "1"}, R={"inventory": {}}, ex=_ex())
    ins = prompts[0]
    assert sw.YT_BRIEF[:40] in ins and sw.IG_BRIEF[:40] not in ins     # 유튜브 보드 → 유튜브 말투 지침
    assert "끼울 자리의 앞뒤" in ins and "→ [여기] →" in ins            # 앞뒤 문장을 준다
    assert "반말 썰" in ins                                              # 그 스타일 말투
    assert sw.YT_BRIEF[:40] in prompts[1]                                # 흐름 검수도 같은 말투
    assert out["sig_yt"] is True and any(x.get("added") for x in out["slots"])
    prompts.clear()
    sb.insert(_db(tmp_path), "j", {"board": _board(False), "extra": ["escalation"], "key": "2"}, R={"inventory": {}}, ex=_ex())
    assert sw.IG_BRIEF[:40] in prompts[0] and sw.YT_BRIEF[:40] not in prompts[0]


def test_flow_fix_reverted_by_signal_is_rewritten_once(tmp_path, monkeypatch):
    """검수가 접속어만 붙였는데 신호어 보정이 그걸 떼어 원문이 되면 → 이유를 주고 한 번 다시 쓴다. 끝내 그대로면 메모를 지운다."""
    calls = {"flow": 0}

    def fake(prompt, schema, note=None, vertex=True, model=None):
        if "inserts" in json.dumps(schema):
            return {"inserts": [{"after": 2, "slot": "escalation", "line": "기름때도 바로 지워져", "ids": []}]}
        calls["flow"] += 1
        m = re.search(r"\n(\d+) \| 고조 \| ([^|]+) \|", prompt)
        n, line = int(m.group(1)), m.group(2).strip()
        if calls["flow"] == 1:
            return {"fix": [{"n": n, "why": "앞 칸과 이어 주는 접속어가 없음", "line": "그래서 " + line}]}
        return {"fix": [{"n": n, "why": "이음", "line": line + " 한 번에"}]}
    monkeypatch.setattr(sb.sg, "_call_json", fake)
    sb._HEAD_CACHE.clear()
    out = sb.insert(_db(tmp_path), "j", {"board": _board(True), "extra": ["escalation"], "key": "1"}, R={"inventory": {}}, ex=_ex())
    esc = next(x for x in out["slots"] if x.get("slot") == "escalation")
    assert out["flow_retry"] and calls["flow"] == 2      # 첫 검수('그래서 …')가 신호어 보정에 지워졌다 → 다시 썼다
    assert esc["line"].endswith("한 번에")
    # 메모가 남아 있다면 문장이 실제로 바뀐 것이어야 한다(고친 척 메모 금지)
    for x in out["slots"]:
        if x.get("fixed_why", "").startswith("흐름 검수"):
            assert not sb._same_line(x["line"], x.get("line_before"))


# ── ① 시간 상한 ───────────────────────────────────────────────────────────

def test_sb_run_timeout_and_late_result(monkeypatch):
    import shopping_shorts.app as app_mod
    gate = {"go": False}

    def slow():
        while not gate["go"]:
            time.sleep(0.01)
        return {"slots": [1]}
    jid = "t-timeout-%d" % time.time_ns()
    app_mod._sb_run(jid, "board:auto", slow)
    key = (jid, "board:auto")
    assert app_mod._SB_TASKS[key]["state"] == "run"
    app_mod._SB_TASKS[key]["t0"] -= app_mod._SB_TIMEOUT + 1          # 6분 넘은 척
    app_mod._sb_expire(jid)
    assert app_mod._SB_TASKS[key]["state"] == "error" and "시간 초과" in app_mod._SB_TASKS[key]["error"]
    gate["go"] = True                                                 # 늦게 끝나면 done 으로 덮는다
    for _ in range(300):
        if app_mod._SB_TASKS[key]["state"] == "done":
            break
        time.sleep(0.01)
    assert app_mod._SB_TASKS[key]["state"] == "done"


def test_sb_run_old_generation_does_not_clobber_new(monkeypatch):
    import shopping_shorts.app as app_mod
    g1, g2 = {"go": False}, {"go": False}

    def mk(g, val):
        def f():
            while not g["go"]:
                time.sleep(0.01)
            return {"v": val}
        return f
    jid = "t-gen-%d" % time.time_ns()
    key = (jid, "board:auto")
    app_mod._sb_run(jid, "board:auto", mk(g1, 1))
    app_mod._SB_TASKS[key]["t0"] -= app_mod._SB_TIMEOUT + 1
    app_mod._sb_run(jid, "board:auto", mk(g2, 2))                     # 시간 초과 뒤 다시 만들기 = 새 회차
    assert app_mod._SB_TASKS[key]["state"] == "run"
    g1["go"] = True
    time.sleep(0.2)
    assert app_mod._SB_TASKS[key]["state"] == "run"                   # 옛 회차 결과가 새 회차를 덮지 않는다
    g2["go"] = True
    for _ in range(300):
        if app_mod._SB_TASKS[key]["state"] == "done":
            break
        time.sleep(0.01)
    assert app_mod._SB_TASKS[key]["result"] == {"v": 2}
