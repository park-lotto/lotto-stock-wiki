"""kal.py 감시 빈 곳 1~5 (관제 319, 2026-11-06 개정안 kal v2 구현).

1 step_make 가 preset_make.make_one 을 부른다(make-00) · 렌더 기록 없는 --ours-mp4 거절
2 뜯기 받아쓰기 = tear_llm.ask(소리 → 스피치매틱스 + 제미나이 소리 판독, 그림 → claude_cli)
3 뜯기 materials=True + 옛 '건너뜀' 뜯기는 다시 뜯음(tteutgi-29)
4 verify 자동 통과 뒤 시청판정.json(sha 짝) 없으면 waiting_human(verify-07)
5 벤치 mp4 없으면 픽셀 층 조용히 건너뛰지 않음 — failed
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.calcopy.engine import kal


def _state(tmp_path, monkeypatch, slug="t1"):
    monkeypatch.setattr(kal, "ROOT", tmp_path)
    monkeypatch.setattr(kal, "DATA", tmp_path / "data")
    S = kal.State(slug, "@t1", "우리", 2, "아니오", "v1")
    S.save()
    return S


# ---------------------------------------------------------------- 1 make
def test_make_calls_make_one(tmp_path, monkeypatch):
    S = _state(tmp_path, monkeypatch)
    pdir = tmp_path / "channel/t1/preset/p1"
    pdir.mkdir(parents=True)
    (pdir / "manifest.json").write_text("{}", encoding="utf-8")
    S.step("copy").update({"state": "done", "outputs": {"preset": str(pdir)}})
    wdir = tmp_path / "work1"
    wdir.mkdir()
    (wdir / "대본.json").write_text(json.dumps({"lines": [{"text": "가나"}, {"text": "다라", "kind": "orig"}]}, ensure_ascii=False), encoding="utf-8")
    S.d["work"] = str(wdir)
    called = {}

    def fake_make_one(p, w, a):
        called["args"] = (Path(p), Path(w), a)
        out = tmp_path / "mk"
        out.mkdir()
        (out / "final.mp4").write_bytes(b"x")
        (out / "timeline.json").write_text(json.dumps({"pieces": [{"text": "가나", "line": 0, "t0": 0.0, "t1": 1.0, "f0": 0, "f1": 30},
                                                                  {"text": "다라", "line": 1, "t0": 1.0, "t1": 2.5, "f0": 30, "f1": 75}]}, ensure_ascii=False), encoding="utf-8")
        return {"ok": True, "out": str(out), "note": "통과", "seconds": 2.5}
    from tools.calcopy.engine import preset_make
    monkeypatch.setattr(preset_make, "make_one", fake_make_one)
    monkeypatch.setattr(kal, "disk_gate", lambda what: None)
    st, out, note = kal.step_make(S)
    assert st == "done", note
    assert called["args"][0] == pdir and called["args"][1] == wdir and called["args"][2].allow_tts and called["args"][2].test
    ours = json.loads(Path(out["ours_lines"]).read_text(encoding="utf-8"))
    assert [l["speaker"] for l in ours["lines"]] == ["나레", "원음"] and ours["dur"] == 2.5
    assert out["ours_mp4"].endswith("final.mp4")


def test_make_fail_is_failed(tmp_path, monkeypatch):
    S = _state(tmp_path, monkeypatch)
    pdir = tmp_path / "channel/t1/preset/p1"
    pdir.mkdir(parents=True)
    (pdir / "manifest.json").write_text("{}", encoding="utf-8")
    S.step("copy").update({"state": "done", "outputs": {"preset": str(pdir)}})
    S.d["work"] = str(tmp_path)
    from tools.calcopy.engine import preset_make

    def boom(p, w, a):
        raise SystemExit("manifest 에 channel_rules.make 가 없다")
    monkeypatch.setattr(preset_make, "make_one", boom)
    monkeypatch.setattr(kal, "disk_gate", lambda what: None)
    st, out, note = kal.step_make(S)
    assert st == "failed" and "channel_rules.make" in note


def test_make_without_work_waits(tmp_path, monkeypatch):
    S = _state(tmp_path, monkeypatch)
    monkeypatch.setattr(kal, "disk_gate", lambda what: None)
    st, out, note = kal.step_make(S)
    assert st == "waiting_human"


def test_make_rejects_unrendered_ours_mp4(tmp_path, monkeypatch):
    """렌더 기록(run_log.json final.md5) 없는 파일은 done 이 아니다 — 감시 적발 kal.py:524."""
    S = _state(tmp_path, monkeypatch)
    monkeypatch.setattr(kal, "disk_gate", lambda what: None)
    mp4, lines = tmp_path / "a.mp4", tmp_path / "a.json"
    mp4.write_bytes(b"abc")
    lines.write_text('{"lines": []}', encoding="utf-8")
    S.d["ours_mp4"], S.d["ours_lines"] = str(mp4), str(lines)
    st, out, note = kal.step_make(S)
    assert st != "done"
    (tmp_path / "run_log.json").write_text(json.dumps({"final": {"md5": hashlib.md5(b"abc").hexdigest()}}), encoding="utf-8")
    st, out, note = kal.step_make(S)
    assert st == "done"


# ---------------------------------------------------------------- 2 받아쓰기 창구
def test_tear_llm_routes_audio_to_speechmatics_and_gemini(monkeypatch):
    from tools.calcopy.engine import tear_llm
    sm = {"engine": "speechmatics", "lang": "ko", "segments": [{"start": 0.1, "end": 1.0, "text": "안녕 하세요"}, {"start": 2.0, "end": 3.0, "text": "hello"}],
          "words": [{"start": 0.1, "end": 0.5, "text": "안녕"}]}
    gm = {"segments": [{"start": 0.0, "end": 1.1, "speaker": "S1", "lang": "ko", "kind": "narration", "text": "안녕하세요"}],
          "speakers": [{"id": "S1", "gender": "female", "voice": "tts"}], "sfx": [{"t": 1.5, "kind": "띵"}], "bgm": {"present": True}, "_model": "g"}
    d, err = tear_llm.listen(b"mp3", "P", "asr", asr=lambda p: sm, judge=lambda parts, prompt, tag: (gm, None))
    assert err is None
    assert [s["text"] for s in d["segments"]] == ["안녕 하세요", "hello"]
    assert d["segments"][0]["speaker"] == "S1" and d["segments"][0]["kind"] == "narration" and d["segments"][0]["lang"] == "ko"
    assert d["segments"][1]["kind"] == "unknown"
    assert d["speakers"][0]["gender"] == "female" and d["sfx"] and d["words"]
    assert "speechmatics" in d["_model"]


def test_tear_llm_no_silent_swap(monkeypatch):
    """스피치매틱스가 아니면(위스퍼로 넘어감·실패) 실패로 돌려준다 — 공급자 몰래 바꾸기 금지."""
    from tools.calcopy.engine import tear_llm
    d, err = tear_llm.listen(b"mp3", "P", "asr", asr=lambda p: {"engine": "whisper:small", "segments": []}, judge=lambda *a: ({}, None))
    assert d is None and "speechmatics" in err


def test_tear_llm_images_go_to_claude(monkeypatch):
    from tools.calcopy.engine import tear_llm, claude_cli
    monkeypatch.setattr(claude_cli, "analyze_llm", lambda parts, prompt, tag="": ({"via": "claude"}, None))
    assert tear_llm.ask(["라벨", b"jpg"], "p", "t")[0]["via"] == "claude"


# ---------------------------------------------------------------- 3 꾸밈 판독
def test_tteutgi_uses_materials_and_tear_llm(tmp_path, monkeypatch):
    S = _state(tmp_path, monkeypatch)
    S.step("collect").update({"state": "done", "outputs": {"ids": ["a", "b"]}})
    S.d["channel"] = {"top_ids": ["a", "b"]}
    old = tmp_path / "channel/t1/뜯기/b"
    old.mkdir(parents=True)
    (old / "뜯기.json").write_text(json.dumps({"overlay_rules": {"failed": "건너뜀(--no-materials)"}}, ensure_ascii=False), encoding="utf-8")
    seen = []
    from tools.calcopy.engine import analyze, tear_llm
    monkeypatch.setattr(analyze, "analyze", lambda mp4, out, llm=None, materials=True: seen.append((Path(mp4).stem, llm, materials)) or {})
    st, out, note = kal.step_tteutgi(S)
    assert [s[0] for s in seen] == ["a", "b"]                      # 옛 '건너뜀' 뜯기(b)도 다시
    assert all(s[2] is True and s[1] is tear_llm.ask for s in seen)


# ---------------------------------------------------------------- 4·5 verify
def _verify_setup(tmp_path, monkeypatch, bench_mp4=True, verdict="통과"):
    S = _state(tmp_path, monkeypatch)
    (S.dir / "줄판독").mkdir(parents=True)
    (S.dir / "줄판독/b1.json").write_text('{"id": "b1", "lines": []}', encoding="utf-8")
    ours_mp4 = tmp_path / "ours.mp4"
    ours_mp4.write_bytes(b"ours")
    ol = tmp_path / "ours.json"
    ol.write_text('{"lines": []}', encoding="utf-8")
    S.step("make").update({"state": "done", "outputs": {"ours_mp4": str(ours_mp4), "ours_lines": str(ol)}})
    src = tmp_path / "data/t1/src"
    src.mkdir(parents=True)
    if bench_mp4:
        (src / "b1.mp4").write_bytes(b"b")
    K = kal.K
    monkeypatch.setattr(K, "_load_docs", lambda paths: [{"id": "b1", "lines": []}])
    monkeypatch.setattr(K, "media_of", lambda mp4, win: {})
    monkeypatch.setattr(K, "bench_media_src", lambda *a: {})
    monkeypatch.setattr(K, "match_table", lambda *a, **k: {"verdict": verdict, "rows": [], "n_bench": 1, "ours_n_lines": 0})
    monkeypatch.setattr(K, "with_pixel", lambda T, b, o, d: T)
    monkeypatch.setattr(K, "match_md", lambda T, title="": "md")
    monkeypatch.setattr(K, "watch_pack", lambda b, o, d: {"dir": str(d)})
    monkeypatch.setattr(kal, "tear_ours", lambda S_, m: {})
    return S, ours_mp4


def test_verify_pass_needs_watch_verdict(tmp_path, monkeypatch):
    S, om = _verify_setup(tmp_path, monkeypatch)
    st, out, note = kal.step_verify(S)
    assert st == "waiting_human" and "시청" in note
    p = S.dir / "_kal/시청판정.json"
    p.write_text(json.dumps({"sha256": "다른값", "verdict": "통과"}), encoding="utf-8")
    assert kal.step_verify(S)[0] == "waiting_human"            # 옛 편 판정은 무효
    p.write_text(json.dumps({"sha256": hashlib.sha256(b"ours").hexdigest(), "verdict": "통과", "who": "사장님"}), encoding="utf-8")
    assert kal.step_verify(S)[0] == "done"
    p.write_text(json.dumps({"sha256": hashlib.sha256(b"ours").hexdigest(), "verdict": "미달", "why": "끝 끊김"}), encoding="utf-8")
    assert kal.step_verify(S)[0] == "failed"


def test_verify_missing_bench_mp4_fails(tmp_path, monkeypatch):
    S, om = _verify_setup(tmp_path, monkeypatch, bench_mp4=False)
    st, out, note = kal.step_verify(S)
    assert st == "failed" and "벤치 mp4 없음" in note
    T = json.loads((S.dir / "_kal/재현일치도.json").read_text(encoding="utf-8"))
    assert T["verdict"] == "미달" and T["pixel"]["failed"]
