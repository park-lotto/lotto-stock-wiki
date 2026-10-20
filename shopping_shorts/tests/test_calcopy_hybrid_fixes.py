# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 1차 실전(손태영 162분 · 한혜진 169분 · 김가연) 버그 회귀 — 실제 실패 입력으로 고정 (관제 097, 2026-10-18).

네트워크·Typecast·서버는 부르지 않는다(가짜로 바꿔 끼움). 손태영 실제 소리·프레임이 있는 PC 에선 그 표본으로도 잰다(없으면 건너뜀).
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import gemini_server as GS, name_dict as ND, narr_align as NA, stage_log, tts_pause as TP, yt_fetch as YF  # noqa: E402
from tools.calcopy.hybrid import checks, name_check, render_itssum as RI, render_jaemi as RJ, screen as SC, thumb  # noqa: E402
from tools.calcopy.hybrid.common import StageError, jload, jsave  # noqa: E402

W = Path("C:/숏템_칼카피/yanshottem/하이브리드_손태영")
D = ROOT / "channel/yanshottem/하이브리드_손태영"
T = Path("C:/숏템_칼카피/yanshottem/_hybrid_pipeline_test/손태영")


def _need(*ps):
    for p in ps:
        if not Path(p).exists():
            pytest.skip(f"표본 없음: {p}")


# ── 1. screen: 후보 하나가 시간초과/멈춤이어도 단계는 살고 screen.json 은 부분이라도 쓴다 · 제목 NFD/띄어쓰기 ──
def test_screen_timeout_isolated_and_partial_json(tmp_path, monkeypatch):
    sd = tmp_path / "screen"; sd.mkdir()
    jsave(sd / "candidates.json", {"candidates": [{"id": "GOOD0000001"}, {"id": "SLOW0000002"}]})
    for vid in ("GOOD0000001", "SLOW0000002"):
        jsave(sd / f"{vid}.info.json", {"title": unicodedata.normalize("NFD", "네이처리퍼블릭 / 진생 로얄 실크"), "duration": 30, "formats": [{"height": 1080, "vcodec": "avc1"}]})

    def fake_ytdlp(args, timeout=600, stall_sec=None, watch=None, log=None):
        if "SLOW0000002" in " ".join(map(str, args)):
            raise subprocess.TimeoutExpired(args, timeout)              # 10-18 손태영: 이 예외가 ex.map 을 뚫고 단계를 죽였다
        return YF.Result(0, "", "", 0.1)
    monkeypatch.setattr(YF, "ytdlp", fake_ytdlp)
    monkeypatch.setattr(YF, "fetch_subs", lambda *a, **k: [])
    monkeypatch.setattr(SC, "_sheet", lambda mp4s, dst: None)
    res = SC.screen(tmp_path, ["진생 로얄"], log=lambda *a: None)
    assert (tmp_path / "screen.json").exists()
    rows = {r["id"]: r for r in res["rows"]}
    assert rows["GOOD0000001"]["title_hit"] is True                     # NFD 제목도 적중
    assert "TimeoutExpired" in rows["SLOW0000002"]["error"]
    assert res["errors"] and res["errors"][0]["id"] == "SLOW0000002"


def test_screen_all_fail_still_writes_json(tmp_path, monkeypatch):
    sd = tmp_path / "screen"; sd.mkdir()
    jsave(sd / "candidates.json", {"candidates": [{"id": "BAD00000001"}]})
    monkeypatch.setattr(SC, "_ytdlp", lambda args, timeout=240: subprocess.CompletedProcess(args, 1, "", "ERROR: 403"))
    with pytest.raises(StageError):
        SC.screen(tmp_path, ["x"], log=lambda *a: None)
    assert jload(tmp_path / "screen.json")["errors"]


def test_kw_hit_nfc_and_spaces():
    assert YF.kw_hit(unicodedata.normalize("NFD", "네이처리퍼블릭 / 진생 로얄 실크 워"), ["진생 로얄"])
    assert YF.kw_hit("NATURE REPUBLIC 진생로얄실크 워터리 크림", ["진생 로얄"])
    assert not YF.kw_hit("다른 크림", ["진생 로얄"])


def test_screen_slow_candidate_skips_remaining_previews(tmp_path, monkeypatch):
    sd = tmp_path / "screen"; sd.mkdir()
    jsave(sd / "SLOW0000002.info.json", {"title": "x", "duration": 60, "formats": []})
    calls = []

    def fake_ytdlp(args, timeout=600, stall_sec=None, watch=None, log=None):
        calls.append(args)
        return YF.Result(-9, "", "stall", 41.0, stalled=True)
    monkeypatch.setattr(YF, "ytdlp", fake_ytdlp)
    monkeypatch.setattr(YF, "fetch_subs", lambda *a, **k: [])
    monkeypatch.setattr(SC, "_sheet", lambda mp4s, dst: None)
    r = SC.screen_one(sd, "SLOW0000002", ["x"], log=lambda *a: None)
    assert r["slow"] and len(calls) == 1                                # 토막 3개 중 첫 번째에서 멈추면 나머지는 안 받는다


# ── 2. download: 자막은 영상과 다른 호출 — 자막 429 가 영상 받기를 못 죽인다 ──
def test_download_subs_failure_does_not_fail_video(tmp_path, monkeypatch):
    def fake_full(url, dst, fmt=None, timeout=0, stall_sec=0, extra=None, log=None):
        Path(dst).write_bytes(b"0" * 2000); return YF.Result(0, "", "", 1.0)
    monkeypatch.setattr(YF, "download_full", fake_full)
    monkeypatch.setattr(YF, "fetch_subs", lambda url, stem, langs="ko", tries=3, log=print: [])   # 429 → 빈 목록
    out = SC.download(tmp_path, ["P9DqLkT7X5Q"], log=lambda *a: None)
    assert out and out[0].exists()


def test_ytdlp_stall_watch_kills_only_that_process(tmp_path):
    """받는 파일이 안 자라면 그 프로세스만 끊는다(이미지 이름 kill 금지). yt-dlp 대신 파이썬으로 '멈춘 받기'를 흉내."""
    real = YF.subprocess.Popen
    py = sys.executable

    class P:
        def __init__(self, cmd, **kw):
            self.p = real([py, "-c", "import time; time.sleep(30)"], **kw)
        def wait(self, timeout=None): return self.p.wait(timeout=timeout)
        def kill(self): self.p.kill()
        @property
        def returncode(self): return self.p.returncode
    YF.subprocess.Popen = P
    try:
        YF.POLL_SEC, poll0 = 0.2, YF.POLL_SEC
        t0 = time.time()
        r = YF.ytdlp(["x"], timeout=20, stall_sec=1.0, watch=tmp_path / "clip")
    finally:
        YF.subprocess.Popen = real; YF.POLL_SEC = poll0
    assert r.stalled and time.time() - t0 < 10


# ── 3. gemini_server shim 은 스크립트로도 돈다 ──
def test_hybrid_gemini_server_shim_runs_as_script():
    r = subprocess.run([sys.executable, str(ROOT / "tools/calcopy/hybrid/gemini_server.py"), "--help"], capture_output=True, text=True, cwd=str(ROOT.parent))
    assert r.returncode == 0 and "asr" in r.stdout


# ── 4. 서버 ASR: 모델 2개 교차 표식 · 대체 모델 · 시간초과는 결과로 ──
def test_ask_files_marks_cross_ok_and_fallback(monkeypatch, tmp_path):
    sent = {}

    def fake_ssh(code, payload, timeout=420):
        sent.update(payload)
        return {"runs": [[{"model": "gemini-3-flash-preview", "json": {"text": "a"}, "tries": 1, "sec": 3.0},
                          {"model": "gemini-3.5-flash", "why": "ClientError: 429", "tries": 9},
                          {"model": "gemini-flash-latest", "json": {"text": "a"}, "tries": 1, "sec": 4.0, "fallback": True}],
                         [{"model": "gemini-3-flash-preview", "why": "timeout", "tries": 1}, {"model": "gemini-3.5-flash", "why": "ClientError: 429", "tries": 9},
                          {"model": "gemini-flash-latest", "why": "timeout", "tries": 1}, {"model": "gemini-3.5-flash-lite", "why": "ClientError: 429", "tries": 9}]]}
    monkeypatch.setattr(GS, "_ssh_py", fake_ssh)
    monkeypatch.setattr(GS, "_audio_b64", lambda *a, **k: "AAAA")
    from tools.calcopy.engine import gemini_free as GF
    monkeypatch.setattr(GF, "_ask_local", lambda *a, **k: (None, "quota"))   # 로컬 대체도 막힌 경우 — 교차 모자람이 그대로 남아야 한다
    r = GS.ask_files([("x.mp3", 0, 1), ("x.mp3", 1, 2)], "p")
    assert sent["fallback"] == list(GS.FALLBACK_MODELS) and sent["cross_n"] == 2 and sent["req_timeout"] == GS.REQ_TIMEOUT_SEC
    assert r["jobs"][0]["cross_ok"] is True and r["jobs"][0]["ok_models"] == ["gemini-3-flash-preview", "gemini-flash-latest"]
    assert r["jobs"][1]["cross_ok"] is False and r["jobs"][1]["ok_models"] == [] and len(r["jobs"][1]["failed"]) == 6   # 서버 4 + 로컬 대체 2
    assert GS.texts(r["jobs"][0]) == ["a", "a"]
    assert "gemini-2.5-flash" not in GS.MODELS + GS.FALLBACK_MODELS    # 서버 404


def test_remote_code_has_timeout_and_fallback_phase():
    assert "http_options=types.HttpOptions(timeout=" in GS.REMOTE and "fallback" in GS.REMOTE and "timeout " in GS.REMOTE


def test_server_ai_min_cross_counts_fallback_models(monkeypatch):
    from tools.calcopy.hybrid import server_ai
    monkeypatch.setattr(GS, "ask_files", lambda files, prompt, mode, models, max_tries=8: {
        "sec": 1.0, "jobs": [{"runs": [{"model": "gemini-3-flash-preview", "json": {"text": "하나", "speakers": 1}}, {"model": "gemini-3.5-flash", "why": "429"},
                                        {"model": "gemini-flash-latest", "json": {"text": "하나", "speakers": 1}, "fallback": True}],
                              "ok_models": ["gemini-3-flash-preview", "gemini-flash-latest"], "cross_ok": True, "failed": [{"model": "gemini-3.5-flash", "why": "429"}]}]})
    res = server_ai.asr_clips("x.mp3", [(0, 1)])
    assert res["min_cross"] == 2 and server_ai.texts_of(res, 0) == ["하나", "하나"] and "gemini-flash-latest" in res["ok_models"]
    assert server_ai.ASR_MODELS == GS.MODELS


# ── 5·6. 문장 경계·문장부호 자리 = 글자 시각(align) 주인 ──
def _align(text: str, cps: float = 10.0, pause: float = 0.3, start: float = 0.2) -> dict:
    ch, s, e, t = [], [], [], start
    for c in text:
        ch.append(c)
        if c in ",.?!":
            s.append(t); e.append(t); t += pause
        elif c == " ":
            s.append(t); e.append(t)
        else:
            s.append(t); t += 1 / cps; e.append(t)
    return {"characters": ch, "character_start_times_seconds": s, "character_end_times_seconds": e}


def test_itssum_split_by_align_uses_line_end_periods():
    S = {"voice": {"voice_id": "v"}, "cps_target": 8, "lines": [{"id": "H", "seg": "A", "kind": "tts", "tts": "첫 줄, 문장이에요."}, {"id": "B1", "seg": "B", "kind": "tts", "tts": "둘째 줄이에요."},
                                                             {"id": "B2", "seg": "B", "kind": "tts", "tts": "셋째 줄?"}]}
    al = _align(RI.tts_text(S))
    spans = RI.split_by_align(S, al)
    assert len(spans) == 3 and spans[0][0] == pytest.approx(0.2) and spans[0][1] <= spans[1][0] < spans[1][1] <= spans[2][0]
    # 쉼표(첫 줄 안)는 경계가 아니다. 경계 = 마침표 쉼(0.3초) 안에서 끝 +END_PAD·시작 −HEAD_PAD 여유(10-21 손태영 첫 음절 잘림) — 겹치지 않는다
    slots = [s for s in __import__("tools.calcopy.engine.narr_align", fromlist=["x"]).punct_slots(RI.tts_text(S), al) if s[0] == "."]
    a0, b0 = slots[0][1], slots[0][2]
    assert spans[0][1] == pytest.approx(min(b0, a0 + RI.END_PAD)) and a0 < spans[0][1] <= b0 and spans[1][0] >= max(spans[0][1], b0 - RI.HEAD_PAD) - 1e-9


def test_itssum_align_boundary_vs_silence_guess_on_real_tts():
    """10-18 증명: 새 TTS 에서 소리 틈 어림은 H|B1 경계를 1초 늦게(4.73) 잡았고 align 은 3.84 — 서버 받아쓰기로 3.84~4.75 가 '저도'(B1 첫 낱말)임을 확인."""
    _need(T / "proof_align.json", T / "asr/itssum_boundary.json")
    pr = jload(T / "proof_align.json")["itssum"]
    assert pr["how"] == "align" and pr["align_vs_guess_max"] > 0.5
    asr = jload(T / "asr/itssum_boundary.json")["jobs"][0]
    assert any("저도" in (r.get("json") or {}).get("text", "") for r in asr["runs"])


def test_itssum_silence_guess_still_matches_hand_spans_on_old_tts():
    """옛 합성본(align 없음)은 틈 어림이 손 tts_spans 와 같아야 한다(손태영 실제 narr_full.mp3)."""
    _need(W / "잇썸홈판/render/narr_full.mp3", D / "잇썸홈판/대본.json")
    S = jload(D / "잇썸홈판/대본.json"); L = RI.tts_lines(S)
    spans, _ = RI.split_sentences(W / "잇썸홈판/render/narr_full.mp3", len(L), [RI.nchar(l["tts"]) for l in L])
    for l, (a, b) in zip(L, spans):
        assert abs(a - S["tts_spans"][l["id"]][0]) < 0.05 and abs(b - S["tts_spans"][l["id"]][1]) < 0.05


def test_jaemi_auto_punct_matches_hand_and_last_sentence_split_on_real_tts():
    """손태영 재미썸 옛 합성본(align 없음): 자동 문장부호 자리 = 손 값 ±0.05, 끝 문장 시작은 마지막 '말 구간'이 아니라 끝 줄 앞 부호의 쉼(rate_last 14.3 → 7.7)."""
    _need(T / "proof_narr_auto.json")
    j = jload(T / "proof_narr_auto.json")["jaemi"]
    assert j["how"] == "silence_guess" and j["max_diff"] < 0.05
    assert j["old_rate_last"] > 12 and 5 <= j["rate_last"] <= 9 and abs(j["rate_last"] / j["rate_body"] - 1) < 0.3


def test_jaemi_align_punct_lands_on_dips_on_real_tts():
    _need(T / "proof_align.json")
    j = jload(T / "proof_align.json")["jaemi"]
    assert j["how"] == "align" and all(d == 0.0 for _, _, d, _ in j["punct_on_dip"])
    assert all(0.20 <= p[3] <= 0.33 for p in j["pauses"])


def test_jaemi_period_without_gap_gets_pause_inserted(tmp_path):
    """쉼 안 쉰 마침표(틈 0) — shape 가 방 잡음으로 쉼을 새로 넣는다(옛 코드는 i1<=i0 면 건너뛰어 '근처 무음 없음'으로 멈췄다)."""
    import numpy as np, wave
    sr = 44100; t = np.arange(int(2.0 * sr)) / sr
    x = (np.sin(2 * np.pi * 220 * t) * 8000).astype(np.int16)
    src = tmp_path / "v.wav"; w = wave.open(str(src), "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes()); w.close()
    TP.PAUSE = {",": 0.235, ".": 0.315}
    log = TP.shape(str(src), {"characters": ["가", ".", "가"], "character_start_times_seconds": [0.95, 1.0, 1.0], "character_end_times_seconds": [1.0, 1.0, 1.05]}, str(tmp_path / "o.mp3"))
    assert log and log[0]["was"] == 0.0 and abs(log[0]["now"] - 0.315) < 0.01
    assert NA.duration(tmp_path / "o.mp3") > 2.25


def test_auto_punct_at_skips_period_instead_of_dying():
    S = {"lines": [{"tts": "첫 문장이야."}, {"tts": "둘째 문장이야."}], "render": {}}
    RJ_marks = RJ.punct_marks(S)
    assert RJ_marks == ["."]


# ── 7. 계획 단계 컷 길이 검사(잇썸 어림 over → 멈춤 · 재미썸 max) ──
def test_jaemi_b_group_max_checked_in_timeline():
    S = {"lines": [{"slot": "f1", "text": "앞 줄이야.", "tts": "앞 줄이야."}, {"slot": "b", "text": "뒤 줄 길게 말하는 중이야.", "tts": "뒤 줄 길게 말하는 중이야."}],
         "pieces": [{"caption": "앞 줄이야"}, {"caption": "뒤 줄 길게"}, {"caption": "말하는 중이야"}], "orig": [{"id": "O1", "span": [0, 2.0]}], "cps_target": 8}
    M = {"A": [{"at": 0.0, "src": "a.mp4", "ss": 0, "crop": [0, 0, 700, 700]}], "F1": [{"src": "a.mp4", "ss": 1, "crop": [0, 0, 700, 700]}],
         "B": [{"src": "b.mp4", "ss": 0, "crop": [0, 0, 900], "pieces": [1, 2], "max": 0.5}]}
    with pytest.raises(StageError, match="원본 샷보다 길다"):
        RJ.timeline(S, M, None, None, est_cps=8)
    M["B"][0]["max"] = 9.0
    assert RJ.timeline(S, M, None, None, est_cps=8)["b_groups"][0]["over"] == 0.0


def test_itssum_plan_stops_on_estimated_overflow(tmp_path):
    _need(D / "잇썸홈판/대본.json", W / "src")
    S, M = jload(D / "잇썸홈판/대본.json"), jload(D / "잇썸홈판/재료.json")
    M["B"][0]["max"] = 1.0                                               # B1 첫 컷(어림 3.2초)에 샷 경계 1.0
    doc = tmp_path / "doc"; doc.mkdir(); jsave(doc / "대본.json", S); jsave(doc / "재료.json", M)
    with pytest.raises(StageError, match="계획에서 컷이 원본 샷보다 길다"):
        RI.render(doc, tmp_path / "work", plan_only=True, log=lambda *a: None)


# ── 8·9·10. checks: B13 원음 구간 안 컷 · 받아쓰기 창 여유·캐시 · 허용 오차 ──
def test_b13_scene_cuts_inside_same_orig_span_are_not_reuse():
    # 10-18 손태영: O5 원음 479.85~482.45 밑 화면을 479.95 / 480.9 로 끊음(0.1초 되감김 — 입 모양 맞춤) → 옛 규칙은 '재사용'
    a = {"src": "1VKx4f262GM.mp4", "ss": 479.95, "dur": 1.05, "t0": 9.717, "t1": 10.767, "seg": "A", "line": "O"}
    b = {"src": "1VKx4f262GM.mp4", "ss": 480.5, "dur": 1.5, "t0": 10.767, "t1": 12.267, "seg": "A", "line": "O"}
    spans = [("1VKx4f262GM.mp4", 479.85, 482.45)]
    assert checks.reuse_violations([a, b]) != []                       # 원음 구간 정보 없이는 걸린다(0.5초 되감김 — 옛 거짓 ×)
    assert checks.reuse_violations([a, b], spans) == []
    c = {"src": "1VKx4f262GM.mp4", "ss": 480.5, "dur": 1.0, "t0": 20.0, "t1": 21.0, "seg": "B", "line": "B4"}   # B 에서 같은 장면 다시 = 진짜 재사용
    assert checks.reuse_violations([a, b, c], spans)


def test_orig_spans_of_both_versions():
    S_it = {"lines": [{"kind": "orig", "src": "x.mp4", "spans": [[1, 2], [3, 4]]}, {"kind": "tts"}]}
    assert checks.orig_spans_of(S_it, "잇썸홈판") == [("x.mp4", 1.0, 2.0), ("x.mp4", 3.0, 4.0)]
    assert checks.orig_spans_of({"orig": [{"id": "O1", "span": [5, 6]}]}, "재미썸홈판") == [("*", 5.0, 6.0)]


def test_asr_check_pads_windows_and_caches(tmp_path, monkeypatch):
    from tools.calcopy.hybrid import server_ai
    calls = []

    def fake_clips(final, spans, **k):
        calls.append(list(spans))
        return {"runs": [{"model": "m1", "clips": [{"i": 0, "text": "이게 빨리 품절", "speakers": 1}, {"i": 1, "text": "손태영 씨가", "speakers": 1}]},
                         {"model": "m2", "clips": [{"i": 0, "text": "이게 빨리 품절", "speakers": 1}, {"i": 1, "text": "손태영 씨가", "speakers": 1}]}],
                "ok_models": ["m1", "m2"], "min_cross": 2, "cross_per_clip": [2, 2], "sec": 1.0}
    monkeypatch.setattr(server_ai, "asr_clips", fake_clips)
    monkeypatch.setattr(checks, "dur_of", lambda p: 30.0)
    monkeypatch.setattr(checks, "md5", lambda p: "abc")
    cache = tmp_path / "asr_cache.json"
    r = checks.asr_check(Path("final.mp4"), [(3.847, 12.317)], "손태영", (0.0, 3.6), "이게 빨리 품절", log=lambda *a: None, cache=cache)
    assert calls[0][0] == (3.697, 12.467) and calls[0][1] == (0.0, 3.75)   # 앞 0.15 여유(0 아래로는 안 감)
    assert r["name_ok_models"] == 2 and r["min_cross"] == 2
    checks.asr_check(Path("final.mp4"), [(3.847, 12.317)], "손태영", (0.0, 3.6), "이게 빨리 품절", log=lambda *a: None, cache=cache)
    assert len(calls) == 1                                               # 두 번째는 캐시


def test_tolerances_for_rounding(monkeypatch):
    assert 1.199 >= checks.CUT_MIN - checks.FRAME_TOL                     # 한혜진 B4 1.199 vs 1.20
    assert abs(1.0664 / 1.1849 - 1) <= checks.TEMPO_TOL + checks.TEMPO_ROUND_TOL   # −10% 깎인 값의 반올림


# ── 11. 썸네일: 눈 뜬 프레임 · 손 선택 유지 · 배경 작은 얼굴 무시 ──
def test_thumb_prefers_open_eyes_on_real_frames():
    """10-18 손태영: 자동이 고른 a_seg 2.55초(눈 반감)·thumb_base 7.05초(손으로 입 가림) 대신 손으로 고른 6.05초·1.8초(눈 뜸)가 이겨야 한다."""
    _need(W / "잇썸홈판/render/a_seg.mp4", W / "재미썸홈판/render/thumb_base.mp4", thumb.MODEL)
    det = thumb._detector(); win = (0, 420, 1080, 1080)
    s_auto, i_auto = thumb.score(det, thumb._frame(W / "잇썸홈판/render/a_seg.mp4", 2.55, win))
    s_hand, i_hand = thumb.score(det, thumb._frame(W / "잇썸홈판/render/a_seg.mp4", 6.05, win))
    assert i_auto["eye_open"] is False and i_hand["eye_open"] is True and s_hand > s_auto
    s_auto2, _ = thumb.score(det, thumb._frame(W / "재미썸홈판/render/thumb_base.mp4", 7.05, win))
    s_hand2, i_hand2 = thumb.score(det, thumb._frame(W / "재미썸홈판/render/thumb_base.mp4", 1.8, win))
    assert i_hand2["eye_open"] and s_hand2 > s_auto2


def test_make_thumb_keeps_manual_and_honours_thumb_at(tmp_path, monkeypatch):
    R = tmp_path / "render"; R.mkdir(); doc = tmp_path / "doc"; doc.mkdir()
    jsave(R / "render_info.json", {"version": "잇썸홈판"})
    (R / "final.jpg").write_bytes(b"MANUAL"); (R / "final.jpg.manual").write_bytes(b"")
    jsave(doc / "대본.json", {"thumb": {}})
    r = thumb.make_thumb(doc, tmp_path, log=lambda *a: None)
    assert r["kept"] and (R / "final.jpg").read_bytes() == b"MANUAL"
    (R / "final.jpg.manual").unlink()
    jsave(doc / "대본.json", {"thumb": {"keep": True}})
    assert thumb.make_thumb(doc, tmp_path, log=lambda *a: None)["kept"]
    jsave(doc / "대본.json", {"thumb": {"at": 6.05}})
    ran = []
    monkeypatch.setattr(thumb, "_clean_a", lambda doc, work, info: R / "base.mp4")
    monkeypatch.setattr(thumb, "_detector", lambda: None)
    monkeypatch.setattr(thumb, "run", lambda cmd: ran.append(cmd) or (R / "final.jpg").write_bytes(b"AT"))
    monkeypatch.setattr(thumb, "_frame", lambda *a, **k: None)
    jsave(R / "frame_A.json", {"layers": [{"kind": "video", "x": 0, "y": 420, "w": 1080, "h": 1080}]})
    r = thumb.make_thumb(doc, tmp_path, log=lambda *a: None)
    assert r["picked"]["manual_at"] and "6.050" in " ".join(map(str, ran[0])) and (doc / "thumb.jpg").exists()


def test_faces_of_ignores_small_background_faces(monkeypatch):
    class Det:
        def setInputSize(self, s): pass
        def detect(self, im):
            import numpy as np
            s = im.shape[0] / 1080.0                                  # 축소 입력마다 같은 얼굴을 그 크기로 돌려준다
            f = np.array([[100, 100, 300, 360, 150, 200, 250, 200, 200, 280, 170, 330, 230, 330, 0.95],
                          [20, 20, 40, 50, 25, 30, 35, 30, 30, 40, 27, 45, 33, 45, 0.9]], dtype=np.float32)
            f[:, :14] *= s
            return None, f
    import numpy as np
    im = np.zeros((1080, 1080, 3), np.uint8)
    fs = thumb.faces_of(Det(), im)
    assert len(fs) == 1 and fs[0]["h"] > 100                             # 포스터 얼굴(작음)은 셈에서 뺀다


# ── 12·C·F. 이름: 이/가 · 표기 이중 삽입 · 연음 허용 ──
def test_josa_and_phrase():
    assert ND.josa("손태영") == "이" and ND.josa("손태영 씨") == "가" and ND.josa("최, 은경이") == "가" and ND.josa("김가연") == "이"
    assert name_check.PHRASE.format(c="손태영", j=ND.josa("손태영")) == "손태영이 직접 산 거예요."


def test_apply_does_not_double_insert_spelling():
    d = {"names": {"한혜진": {"tts": "한혜진 씨"}}}
    assert ND.apply("한혜진 씨가 산 거예요.", "한혜진", d=d) == "한혜진 씨가 산 거예요."
    assert ND.apply("한혜진이 산 것, 한혜진 씨도", "한혜진", d=d) == "한혜진 씨가 산 것, 한혜진 씨도"
    assert ND.apply("최은경 씨가", "최은경", d={"names": {"최은경": {"tts": "최, 은경"}}}) == "최, 은경 씨가"


def test_apply_reattaches_josa_after_prefixed_spelling():
    """10-18 최화정·서인영·채정안: 표기 '방송인 OO 씨'가 '최화정이'→'방송인 최화정 씨이'로 비문 — 다섯 편이 손으로 고쳤다."""
    d = {"names": {"최화정": {"tts": "방송인 최화정 씨"}}}
    ap = lambda t: ND.apply(t, "최화정", d=d)
    assert ap("먹천재로 소문난 최화정이 고른 김") == "먹천재로 소문난 방송인 최화정 씨가 고른 김"
    assert ap("최화정은 말했다") == "방송인 최화정 씨는 말했다"
    assert ap("최화정을 따라") == "방송인 최화정 씨를 따라"
    assert ap("최화정이랑 같이") == "방송인 최화정 씨랑 같이"
    assert ap("최화정 씨가 산") == "방송인 최화정 씨가 산"          # '씨 씨가' 안 됨
    assert ap("방송인 최화정 씨가 산") == "방송인 최화정 씨가 산"    # 이미 표기 — 그대로
    assert ap("최화정") == "방송인 최화정 씨"


def test_heard_ok_uses_alias_list():
    d = {"names": {"한혜진": {"heard_ok": ["한예진", "하녜진"]}}}
    assert ND.heard_ok("한혜진", "[하녜진]이 산", d=d) and ND.heard_ok("한혜진", "한예진이", d=d) and not ND.heard_ok("한혜진", "한지민이", d=d)


# ── 13. TTS 캐시는 글 해시 — 줄을 고치면 다시 합성 ──
def test_synth_cached_resynthesizes_on_text_change(tmp_path, monkeypatch):
    calls = []

    def fake_synth(text, out, voice_id, speed=None, model_id=None):
        calls.append(text); Path(out).write_bytes(b"0" * 5000); return {"characters": list(text), "character_start_times_seconds": [0] * len(text), "character_end_times_seconds": [0] * len(text)}
    import shopping_shorts.typecast_tts as tt
    monkeypatch.setattr(tt, "synthesize", fake_synth)
    from shopping_shorts.channelkit import providers
    monkeypatch.setattr(providers, "typecast_key", lambda f=None: "k")
    monkeypatch.setattr(NA, "_proc_slots", lambda: [])
    mp3 = tmp_path / "narr_full.mp3"
    a1 = NA.synth_cached("첫 글.", "v", 1.25, mp3, log=lambda *a: None)
    a2 = NA.synth_cached("첫 글.", "v", 1.25, mp3, log=lambda *a: None)
    assert len(calls) == 1 and a1 == a2
    NA.synth_cached("고친 글.", "v", 1.25, mp3, log=lambda *a: None)
    assert calls == ["첫 글.", "고친 글."] and list(tmp_path.glob("narr_full_old_*.mp3"))
    legacy = tmp_path / "old.mp3"; legacy.write_bytes(b"0" * 5000)
    assert NA.synth_cached("x", "v", None, legacy, log=lambda *a: None) is None and len(calls) == 2   # 사이드카 없는 옛 mp3 는 재합성 안 함(유료)


def test_tts_concurrency_cap_is_one_place():
    assert NA.TTS_CONCURRENCY <= 3 and NA._TTS_SEM._initial_value == NA.TTS_CONCURRENCY


# ── D. 동시 쓰기: 사전·장부 잠금 ──
def test_stage_log_concurrent_done_keeps_all_rows(tmp_path):
    p = tmp_path / "stage_log.json"
    def work(k):
        tm = stage_log.Timer(p)
        for i in range(20):
            tm.done(f"s{k}", i)
    th = [threading.Thread(target=work, args=(k,)) for k in range(4)]
    [t.start() for t in th]; [t.join() for t in th]
    assert len(jload(p)["stages"]) == 80


def test_name_dict_update_concurrent(tmp_path, monkeypatch):
    monkeypatch.setattr(ND, "DICT", tmp_path / "name_dict.json")
    def work(k):
        for i in range(10):
            ND.update("한혜진", lambda e: e.setdefault("voices", {}).__setitem__(f"v{k}_{i}", "x"))
    th = [threading.Thread(target=work, args=(k,)) for k in range(3)]
    [t.start() for t in th]; [t.join() for t in th]
    assert len(ND.load()["names"]["한혜진"]["voices"]) == 30


# ── 증명 렌더(실자료) — 손 값 없는 대본으로 두 판이 끝까지 나온다 ──
def test_proof_full_renders_without_hand_values():
    _need(T / "잇썸홈판/render/render_info.json", T / "재미썸홈판/render/render_info.json")
    it = jload(T / "잇썸홈판/render/render_info.json")
    assert it["split_how"] == "align" and it["tts_align"] and all(c["over"] == 0 for c in it["timeline"]["cuts"]) and 20 <= it["final_dur"] <= 35
    j = jload(T / "재미썸홈판/render/render_info.json")["report"]
    assert j["atempo"]["punct_how"] == "align" and all(0.2 <= p["now"] <= 0.33 for p in j["atempo"]["pauses"]) and 20 <= j["dur"] <= 35
