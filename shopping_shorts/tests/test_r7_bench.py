# -*- coding: utf-8 -*-
"""칼카피 엔진 v1 묶음①②(관제 319) — R7 칸·짝 찾기·갈래 판정·MATCH_RULES R7 칸 · 잡도리 멈춤 통일.
판단 주인: r7.find_pair·branch_of·media·summarize · preset_save.save_r7 · kal_analyze._r7_row · flow_bench._pan_guard."""
import json
import subprocess

import pytest

from tools.calcopy.engine import r7 as R7
from tools.calcopy.hybrid import flow, flow_bench as FB
from tools.calcopy.hybrid import runner_ops as R


def _go(st, m=None, rp=None):
    return flow.step(st, m or {}, rp or {}, {})


def _st(phase, **bm):
    return {"fmt": "벤치마킹", "phase": phase, "log": [], "tries": {}, "bm": {"slug": "s", "style": "틀", "name": "n", **bm}}


# ---------------------------------------------------------------- 짝 찾기·갈래
def test_find_pair_states():
    info = {"id": "abcdefghijk", "title": "유치원 학예회 리허설", "description": "일상 속 순간들"}
    p = R7.find_pair(info, [])
    assert p["state"] == "none" and p["checked"]["desc_links"] == 0 and p["checked"]["channel_longs"] == 0 and p["verified_by"] is None
    p = R7.find_pair({**info, "description": "원본 https://www.youtube.com/watch?v=ZZZZZZZZZZZ 출처"}, [])
    assert p["state"] == "candidate" and p["how"] == "설명란 링크" and p["checked"]["desc_source_word"] is True
    p = R7.find_pair(info, [{"id": "LLLLLLLLLLL", "title": "학예회 리허설 풀버전"}])
    assert p["state"] == "candidate" and p["how"] == "같은 채널 롱폼 제목"
    p = R7.find_pair({**info, "description": "https://youtube.com/shorts/abcdefghijk"}, None, "목록 못 읽음")   # 쇼츠 링크는 롱폼 짝이 아니다
    assert p["state"] == "none" and p["checked"]["channel_longs"] is None and p["checked"]["longs_err"]


def test_branch_of_clip_unless_all_verified():
    g = R7.branch_of({"a": {"pair": {"state": "none"}}, "b": {"pair": {"state": "candidate"}}, "c": None})
    assert g["branch"] == R7.BRANCH_CLIP and g["missing"] == ["c"] and g["pairs"]["c"] == "none"
    assert R7.branch_of({"a": {"pair": {"state": "verified"}}})["branch"] == R7.BRANCH_BASE
    assert R7.branch_of({})["branch"] == R7.BRANCH_CLIP


def test_tear_got_judges_branch_once(monkeypatch):
    st = _st("bm_tear_got", videos=[{"id": "a"}, {"id": "b"}])
    r = _go(st, {"bm_tear": {"presets": [{"style": "틀", "sources": ["a", "b"]}], "failed": [],
                             "r7": {"a": {"pair": {"state": "none"}}}, "r7_failed": [{"video": "b", "why": "x"}]}})
    assert r["status"] == "execute"
    g = st["bm"]["branch"]
    assert g["branch"] == R7.BRANCH_CLIP and g["missing"] == ["b"] and any("경보: R7" in x for x in st["log"])


# ---------------------------------------------------------------- 같은 자 media (실제 ffmpeg 영상)
def _box_video(p, box_x=110, black_tail=0.5):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=360x640:r=30:d=2",
                    "-f", "lavfi", "-i", f"color=black:s=360x640:r=30:d={black_tail}", "-filter_complex",
                    f"[0]drawbox=x={box_x}:y=100:w=250:h=400:color=white:t=fill[a];[a][1]concat=n=2:v=1[v]", "-map", "[v]",
                    "-pix_fmt", "yuv420p", str(p)], check=True)


def test_media_box_offset_and_black_tail(tmp_path):
    mp4 = tmp_path / "v.mp4"
    _box_video(mp4)
    m = R7.media(str(mp4), [], None)
    assert m["crop"]["n"] == 1 and abs(m["crop"]["x_off_med"] - 165) <= 12        # 상자 가운데 235px(360폭, 가운데 180) → 1080 기준 +165
    assert m["end"]["kind"] == "black" and abs(m["end"]["sec"] - 0.5) <= 0.15


# ---------------------------------------------------------------- 저장·합치기
def _J(line_h=60, title=("제목 하나",)):
    return {"probe": {"h": 1920}, "layout": {"caption_pos": "above", "caption_band": [100, 200], "window": [0, 600, 1080, 700]},
            "captions": {"glyph": [{"line_h": line_h}]}, "cuts": {"times": [1.0]},
            "fonts": {"title_bands": {"bands": [{"role": "title", "text": [t]} for t in title]}},
            "overlay_rules": {"ok": True, "kind_share": {"화살표·도형": 1.0}}}


def test_from_tear_fields_and_failed_marks():
    T = R7.from_tear(_J())
    assert T["orig_caption"]["size_px"] == 60 and T["orig_caption"]["mode"] is None and T["title"]["lines"] == 1
    assert T["deco_kinds"] == ["화살표·도형"] and T["cut_at"] == [1.0]
    T = R7.from_tear({"probe": {"h": 1920}, "fonts": {"title_bands": {"failed": "quota"}}, "overlay_rules": {"failed": "quota"}})
    assert T["title"]["lines"] is None and T["title"]["failed"] == "quota" and T["deco_kinds"] is None and T["deco_failed"] == "quota"


def test_save_r7_summary(tmp_path):
    from tools.calcopy.engine import preset_save as P
    d = tmp_path / "preset" / "틀"
    for vid, x, lh in (("a", 0.0, 60), ("b", 100.0, 70), ("c", 20.0, 80)):
        P.save_r7(d, vid, {"pair": {"state": "none"}, "crop": {"x_off_med": x, "abs_med": abs(x), "in60_share": 1.0},
                           "orig_caption": {"size_px": lh, "pos": "above"}, "title": {"lines": 2, "chars": 10},
                           "end": {"sec": 0.5, "kind": "black", "last_shot": 2.0}, "deco_kinds": ["x"]})
    D = json.loads((d / "r7.json").read_text(encoding="utf-8"))
    S = D["summary"]
    assert set(D["per_video"]) == {"a", "b", "c"} and S["n"] == 3 and S["confidence"] == "ok"
    assert S["crop"]["x_off_med"] == 20.0 and S["crop"]["zoom"] == 1.0 and S["crop"]["mode"] is None
    assert S["orig_caption"]["size_px"] == 70 and S["title"]["lines"] == 2 and S["end"]["sec"] == 0.5 and S["deco_kinds"] == ["x"]


def test_tear_command_writes_r7_and_returns_pair(monkeypatch, tmp_path):
    from tools.calcopy.engine import bench_member as BM, preset_save as P, yt_channel as YC
    monkeypatch.setattr(BM, "member_llm", lambda: None)
    monkeypatch.setattr(BM, "tear", lambda mp4, d, llm: ({"id": mp4.stem}, {"k": 1}, None))
    monkeypatch.setattr(BM, "shape_key", lambda f: 1)
    monkeypatch.setattr(P, "save", lambda *a, **k: None)
    calls = []
    monkeypatch.setattr(YC, "long_videos", lambda u: calls.append(u) or [])
    monkeypatch.setattr(R7, "measure", lambda J, mp4, pair: {"pair": pair, "crop": {}, "end": {}})
    (tmp_path / "src").mkdir()
    for v in ("a1", "a2"):
        (tmp_path / "src" / f"{v}.info.json").write_text(json.dumps({"id": v, "title": "t", "description": "", "channel_url": "https://y/ch"}), encoding="utf-8")
    out = R.run_do(tmp_path, [{"id": "t", "cmd": "bm_tear", "slug": "s", "videos": [{"id": i, "mp4": f"src/{i}.mp4"} for i in ("a1", "a2")]}])["t"]
    assert out["r7"]["a1"]["pair"]["state"] == "none" and not out["r7_failed"]
    assert calls == ["https://y/ch"]                 # 같은 채널 롱폼 목록은 채널마다 한 번
    D = json.loads((tmp_path / "channel/s/preset/틀/r7.json").read_text(encoding="utf-8"))
    assert set(D["per_video"]) == {"a1", "a2"}


# ---------------------------------------------------------------- MATCH_RULES R7 칸
def _doc():
    return {"id": "a", "dur": 4.0, "lines": [{"t0": 0.0, "t1": 2.0, "text": "첫째 줄", "speaker": "나레", "layer": "채널", "enter": "pop"},
                                            {"t0": 2.0, "t1": 4.0, "text": "둘째 줄", "speaker": "나레", "layer": "채널", "enter": "pop"}]}


def _ours():
    return {"lines": [{"t0": 0.0, "t1": 2.0, "text": "첫째 줄", "speaker": "나레", "layer": "채널", "enter": "pop"}], "dur": 4.0}


def test_match_rows_r7_skip_without_r7_and_judge_with_it():
    from tools.calcopy.engine import kal_analyze as K
    rows = {r["key"]: r for r in K.match_table([_doc()], _ours(), None, None)["rows"]}
    assert all(rows[k]["judge"] == "skip" and rows[k]["core"] is False for k in K.R7_KEYS)
    bench = {"crop": {"x_off_med": 0.0}, "end": {"sec": 0.5}, "orig_caption": {"size_px": 60}, "title": {"lines": 2}}
    r7 = {"bench": bench, "branch": R7.BRANCH_CLIP, "ours": {"crop": {"x_off_med": 40.0}, "end": {"sec": 1.2}}}
    rows = {r["key"]: r for r in K.match_table([_doc()], _ours(), None, None, r7=r7)["rows"]}
    assert rows["crop.x"]["judge"] == "in" and rows["crop.x"]["core"] is True
    assert rows["end.sec"]["judge"] == "out" and rows["end.sec"]["core"] is True
    assert rows["caption.size"]["judge"] == "failed" and rows["caption.size"]["core"] is False
    rows = {r["key"]: r for r in K.match_table([_doc()], _ours(), None, None, r7={**r7, "branch": R7.BRANCH_BASE})["rows"]}
    assert rows["crop.x"]["judge"] == "failed" and "짝 대조" in rows["crop.x"]["diff"]


def test_bm_match_reads_r7_json_and_branch(tmp_path):
    from shopping_shorts.tests.test_flow_bench import _preset, _remake_out
    _remake_out(tmp_path)
    _preset(tmp_path)
    (tmp_path / "channel/s/preset/틀/r7.json").write_text(json.dumps({"summary": {"crop": {"x_off_med": 0.0}, "end": {"sec": 0.0}}}), encoding="utf-8")
    out = R.run_do(tmp_path, [{"id": "pan", "cmd": "bm_match", "slug": "s", "style": "틀", "work": "make/t1", "branch": R7.BRANCH_CLIP,
                               "line_reads": ["channel/s/줄판독/a.json"]}])["pan"]
    assert "error" not in out, out
    rows = {r["key"]: r for r in out["table"]["rows"]}
    assert rows["crop.x"]["core"] is True and rows["crop.x"]["judge"] == "failed"      # 완성본 없음 = 못 잼(통과 아님)
    assert "crop.x" in out["fails"]


def test_compare_do_sends_branch():
    st = _st("bm_compare", videos=[{"id": "a", "v360": "src/a_360.mp4"}], trial="t/final.mp4", trial_dir="t", trial_eye={"cuts": []},
             branch={"branch": R7.BRANCH_CLIP})
    r = _go(st)
    pan = next(d for d in r["do"] if d["cmd"] == "bm_match")
    assert pan["branch"] == R7.BRANCH_CLIP


# ---------------------------------------------------------------- 잡도리 멈춤 통일(②)
def _pan(st, fails, cands):
    return _go(st, {"pan": {"match_ok": False, "fails": fails, "cands": cands}})


def test_pan_keeps_going_past_three_when_fails_change():
    st = _st("bm_panbokki", trial="t.mp4")
    st["pan_n"] = 3
    st["bm"]["pan_cap"] = 6                                   # 첫 대조 실패 4칸 × 1.5
    r = _pan(st, ["a", "b", "c"], [{"path": "p"}])
    assert r["status"] == "execute" and r["do"][0]["cmd"] == "bm_fix" and st["pan_n"] == 4


def test_pan_cap_from_first_fails():
    st = _st("bm_panbokki", trial="t.mp4")
    _pan(st, ["a", "b", "c", "d"], [{"path": "p"}])
    assert st["bm"]["pan_cap"] == 6
    st2 = _st("bm_panbokki", trial="t.mp4")
    _pan(st2, ["a"], [{"path": "p"}])
    assert st2["bm"]["pan_cap"] == FB.PAN_CAP_MIN


def test_pan_same_fails_three_in_a_row_stops_before_cap():
    st = _st("bm_panbokki", trial="t.mp4")
    st["bm"]["pan_cap"] = 9
    for i in range(2):                                          # 고칠 자리는 매번 다르게(같은 do 되풀이는 flow._watch 가 따로 잡는다)
        st["phase"] = "bm_panbokki"
        assert _pan(st, ["x"], [{"path": f"p{i}"}])["status"] == "execute"
    st["phase"] = "bm_panbokki"
    r = _pan(st, ["x"], [{"path": "p9"}])
    assert r["status"] == "stop" and "여기까지 맞췄어요" in r["why"] and "x" in r["fix"] and st["pan_n"] == 2


def test_pan_stuck_uses_flow_redo_stuck(monkeypatch):
    monkeypatch.setattr(flow, "REDO_STUCK", 2)
    st = _st("bm_panbokki", trial="t.mp4")
    st["bm"]["pan_cap"] = 9
    assert _pan(st, ["x"], [{"path": "p1"}])["status"] == "execute"
    st["phase"] = "bm_panbokki"
    assert _pan(st, ["x"], [{"path": "p2"}])["status"] == "stop"


def test_pan_total_cap_stops():
    st = _st("bm_panbokki", trial="t.mp4")
    st["pan_n"] = 6
    st["bm"]["pan_cap"] = 6
    r = _pan(st, ["a", "b"], [{"path": "p"}])
    assert r["status"] == "stop" and "총 상한" in json.dumps(r["state"]["log"], ensure_ascii=False)


def test_confirm_back_has_no_own_count():
    assert not hasattr(FB, "CONFIRM_MAX") and not hasattr(FB, "PAN_MAX")
    st = _st("bm_confirm_got")
    st["bm"]["confirm_n"] = 7
    out = FB._back_to_pan(st, ["caption.y"], "확정 검사 불합격")
    assert out == {"goto": "bm_panbokki"} and st["bm"]["pan_back"] is True


def test_jev_retry_does_not_count_same_table(monkeypatch):
    from tools.calcopy.hybrid import jev_gate

    def boom(*a, **k):
        raise jev_gate.JevDown("no_key")
    monkeypatch.setattr(jev_gate, "decide", boom)
    st = _st("bm_panbokki", trial="t.mp4")
    _pan(st, ["x"], [{"path": "a"}, {"path": "b"}])
    for _ in range(3):                                         # 같은 표로 다시 시도 3번 — 같은 칸 연속으로 안 센다
        st["phase"] = "bm_panbokki"
        r = _go(st)
        assert r["why"] == "잠시 판단 서버가 쉬고 있어요"
    assert len(st["bm"]["pan_hist"]) == 1


# ---------------------------------------------------------------- 멈춤 종류(환경 → 자동 재시도 / 내용 → 회원 질문)
def test_stop_kind():
    assert FB.stop_kind([{"video": "a", "why": "MemoryError: Unable to allocate 211. KiB"}]) == "env"
    assert FB.stop_kind(["HTTP 429 Too Many Requests"]) == "env"
    assert FB.stop_kind([{"why": "MemoryError: x"}, {"why": "세로 쇼츠가 아님"}]) == "content"
    assert FB.stop_kind([]) == "content"


def test_tear_memory_error_retries_tear_not_asks_member():
    st = _st("bm_tear_got", videos=[{"id": "a", "mp4": "src/a.mp4"}])
    f = [{"video": v, "why": "MemoryError: Unable to allocate 11.9 MiB for an array"} for v in ("a", "b", "c")]
    r = _go(st, {"bm_tear": {"presets": [], "failed": f}})
    assert r["status"] == "execute" and [d["cmd"] for d in r["do"]] == ["bm_tear"]          # 사람 질문 없이 뜯기만 다시(받기부터 아님)
    assert "세로 쇼츠" not in json.dumps(r, ensure_ascii=False)


def test_tear_content_failure_asks_member():
    st = _st("bm_tear_got", videos=[{"id": "a", "mp4": "src/a.mp4"}])
    r = _go(st, {"bm_tear": {"presets": [], "failed": [{"video": "a", "why": "가로 영상이라 틀을 못 만듦"}]}})
    assert "세로 쇼츠" in json.dumps(r, ensure_ascii=False)


def test_fetch_retry_reissues_fetch_not_env():
    st = _st("bm_fetch", url="https://www.youtube.com/@x", n=3)
    r = _go(st)
    assert [d["cmd"] for d in r["do"]] == ["bm_fetch"]


def test_env_records_memory():
    st = _st("bm_env_got", url="https://www.youtube.com/@x", n=3)
    r = _go(st, {"bm_env": {"agy": True, "agy_login": True, "disk_gb": 50.0, "mem_free_gb": 3.1}})
    assert [d["cmd"] for d in r["do"]] == ["bm_fetch"] and any("메모리(커밋) 여유 3.1GB" in x for x in st["log"])
    assert isinstance(R.mem_free_gb(), (float, type(None)))


# ---------------------------------------------------------------- 모델 표 한 곳(하이쿠 0)
def test_claude_cli_model_table_no_haiku():
    import pathlib
    import re
    from tools.calcopy.engine import claude_cli as CC
    assert CC.MODEL_DEFAULT == "sonnet" and all(m in ("sonnet", "opus") for _, m in CC.MODEL_TABLE)
    assert CC.model_for("of_cat") == "sonnet" and CC.model_for("ma_fit_origin") == "opus" and CC.model_for("fx_target_aim") == "opus"
    root = pathlib.Path(__file__).resolve().parents[2] / "tools" / "calcopy"
    bad = [str(p) for p in root.rglob("*.py") if re.search(r"""model\s*=\s*["']haiku["']""", p.read_text(encoding="utf-8", errors="replace"))]
    assert bad == []


# ---------------------------------------------------------------- 칼카피 흐름 TTS = 피쉬 '차분한 해설가'(완성본·회원 제작 = 타입캐스트)
FISH_ID = "9a50287ddd26414690b538539ad52d61"


def test_calcopy_tts_is_fish_production_untouched():
    from tools.calcopy.engine import voices as VO, preset_make as PM
    assert VO.tts_for("calcopy") == {"provider": "fish", "voice_id": FISH_ID} and VO.tts_for("production") is None
    over = PM.voice_purpose({"purpose": "calcopy"})
    prov, emo = PM.voice_spec({**over, "emotion": None}, {"tts_provider": "typecast", "tts_emotion": "happy"}, over["voice_id"])
    assert prov == "fish" and emo is None
    assert PM.voice_purpose({}) is None
    prov, _ = PM.voice_spec({}, {"tts_provider": "typecast"}, "tc_6059dad0b83880769a50502f")
    assert prov == "typecast"


def test_bm_trial_task_carries_fish_tts():
    st = _st("bm_trial", url="https://www.youtube.com/@x")
    r = _go(st)
    q = r["review"][0]
    assert q["meta"]["purpose"] == "calcopy" and q["meta"]["tts"] == {"provider": "fish", "voice_id": FISH_ID} and "typecast" not in q["ask"]


def test_keep_production_voice_slot(tmp_path):
    from tools.calcopy.engine import preset_save as P
    D = P.keep_production_voice(tmp_path)
    assert D["production_voice"]["provider"] == "typecast" and D["production_voice"]["voice_id"] is None
    (tmp_path / "defaults.json").write_text(json.dumps({"production_voice": {"provider": "typecast", "voice_id": "tc_x"}}), encoding="utf-8")
    assert P.keep_production_voice(tmp_path)["production_voice"]["voice_id"] == "tc_x"
