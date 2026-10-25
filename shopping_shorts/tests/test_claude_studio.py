# -*- coding: utf-8 -*-
"""숏템 설정 화면 서버판(관제 266) — claude_studio 판단을 못 박는다.

1. 프리셋 목록 = 틀 있는 프리셋 전부 + 형식 묶음 이름·순서(이름표 _groups)
2. 저장 = 회원이 바꾼 칸만, 엔진 check 가 거절하면 저장 안 함
3. 기본값으로 = 빈 칸 + 시각(지우지 않는다 — PC 가 '되돌림'도 받게)
4. PC 맞추기(sync_merge) = 프리셋마다 더 최근 것이 이긴다 · 옛 PC 값이 웹 값을 덮지 못한다
5. 회원에게 보이는 '바꾼 것' 줄에 벤치 원래 글·내부 값이 없다
엔진(미리보기·검사)은 가짜로 바꾼다 — 실제 엔진 대조는 tools/claude_portal/studio_ui_check.py(브라우저) 몫.
"""
import json
from pathlib import Path

import pytest

from shopping_shorts import claude_portal as cp
from shopping_shorts import claude_studio as cs
from shopping_shorts.store import Store

CAT = {"fonts": ["A", "B"], "caption_enter": [], "emphasis": ["color"], "caption_mode": ["accumulate"], "voices": [], "bgm": [],
       "templates": [], "default_pack": {"text": {"title_font": "A"}, "tts": {"tempo": 1.36}},
       "preset_defaults": {}}


def _w(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def env(monkeypatch, tmp_path):
    croot = tmp_path / "repo"
    monkeypatch.setenv("CLAUDE_CHANNEL_ROOT", str(croot))
    monkeypatch.setenv("CLAUDE_STORE_DIR", str(tmp_path / "store"))
    for slug, style in (("banggu", "게시글형"), ("zzz", "A_흰바탕창/창아래_검정")):
        d = croot / "channel" / slug / "preset" / style
        _w(d / "frame.json", {"layers": []})
        _w(d / "manifest.json", {"slug": slug})
    st = Store(tmp_path / "t.db")
    calls = []

    def fake(req):
        calls.append(req)
        if req["op"] == "check":
            return {"errors": ["모르는 글꼴: X"] if (req["pack"].get("text") or {}).get("title_font") == "X" else []}
        if req["op"] == "preview":
            return {"snapshot": {}, "context": {"scenes": []}, "title": "t",
                    "applied": ["hook 글 '골방 | 14:25' → '내 채널 | 14:25'", "hook 제목 글꼴 JalnanGothic → B",
                                "제작 인자 voice=tc_6059dad0b8", "편마다 값 2칸 = 프리셋 잰 값(중앙값)"]}
        return {"catalog": CAT}
    monkeypatch.setattr(cs.WORKER_ONE, "call", fake)
    monkeypatch.setattr(cs, "catalog", lambda: CAT)
    ids = [p["id"] for p in cp.presets(st)]
    return {"st": st, "calls": calls, "ids": ids}


def test_presets_grouped_in_ledger_order(env):
    s = cs.state(env["st"], 7)
    assert len(s["presets"]) == 2 and s["host"] == "server"
    by_name = {p["name"]: p["group"] for p in s["presets"]}
    assert by_name["제품비하인드썰형"] == "썰커뮤니티형"
    assert s["presets"][0]["name"] == "제품비하인드썰형"          # _groups 순서: 썰커뮤니티형이 먼저, 이름표 없는 것은 '기타' 끝
    assert s["presets"][-1]["group"] == "기타"
    assert "default_pack" not in s["catalog"] and "preset_defaults" not in s["catalog"]


def test_save_keeps_only_changed_and_rejects_bad(env):
    st, pid = env["st"], env["ids"][0]
    assert cs.save(st, 7, pid, {"text": {"title_font": "B"}})["ok"]
    s = cs.state(st, 7)
    assert s["changed"] == {"text": {"title_font": "B"}}           # 기본 팩 칸(tempo)은 저장하지 않는다
    assert s["pack"]["tts"]["tempo"] == 1.36 and s["pack"]["text"]["title_font"] == "B"
    bad = cs.save(st, 7, pid, {"text": {"title_font": "X"}})
    assert not bad["ok"] and "모르는 글꼴" in bad["errors"][0]
    assert cs.state(st, 7)["changed"] == {"text": {"title_font": "B"}}   # 거절된 값은 안 남는다


def test_reset_leaves_tombstone_and_unknown_preset_refused(env):
    st, pid = env["st"], env["ids"][0]
    cs.save(st, 7, pid, {"text": {"title_font": "B"}})
    cs.reset(st, 7, pid)
    ch = cs._read(st, 7)["channels"][pid]
    assert ch["pack"] == {} and ch["updated"] > 0
    with pytest.raises(cp.PortalError):
        cs.select(st, 7, "p_0000000000")


def test_sync_merge_newest_wins():
    pid_a, pid_b = "p_aaaaaaaaaa", "p_bbbbbbbbbb"
    web = {"current": pid_a, "current_at": 200, "channels": {pid_a: {"pack": {"x": "web"}, "updated": 200},
                                                          pid_b: {"pack": {"x": "web-old"}, "updated": 100}}}
    pc = {"current": pid_b, "current_at": 150, "channels": {pid_a: {"pack": {"x": "pc-old"}, "updated": 120},
                                                         pid_b: {"pack": {"x": "pc"}, "updated": 300},
                                                         "../evil": {"pack": {}, "updated": 999}}}
    out, n = cs.sync_merge(web, pc)
    assert out["channels"][pid_a]["pack"] == {"x": "web"}           # 옛 PC 값이 웹에서 바꾼 것을 못 덮는다
    assert out["channels"][pid_b]["pack"] == {"x": "pc"}
    assert out["current"] == pid_a                                   # 더 최근에 고른 쪽
    assert "../evil" not in out["channels"] and n == 1


def test_applied_lines_hide_bench_text_and_internal_ids(env):
    st, pid = env["st"], env["ids"][0]
    got = cs.preview(st, 7, pid)["applied"]
    joined = " ".join(got)
    assert "골방" not in joined and "tc_" not in joined and "편마다" not in joined
    assert any("제목 글꼴" in s for s in got)


def test_pc_sync_refuses_when_engine_check_broken(env, monkeypatch):
    """검사가 못 돌면(엔진 워커 오류) 합치지 않고 거절 — PC 가 서버 결과를 그대로 써서 멀쩡한 칸이 지워지는 것을 막는다."""
    monkeypatch.setattr(cs.CP, "_front", lambda store, ctx, route: (7, {}, None))
    monkeypatch.setattr(cs.WORKER_ONE, "call", lambda req: {"error": "엔진 미리보기가 멈췄습니다"})
    pid = env["ids"][0]
    with pytest.raises(cp.PortalError):
        cs.pc_sync({}, {"channels": {pid: {"pack": {"text": {"title_font": "B"}}, "updated": 5}}}, env["st"])
    assert cs._read(env["st"], 7)["channels"] == {}
