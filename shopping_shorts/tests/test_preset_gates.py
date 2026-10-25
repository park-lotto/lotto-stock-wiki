"""preset_make 렌더 전 관문 연결(engine/preset_gates, 10-25 밤) — 판정은 기존 주인(script_audit·narr_verify·render_bench)을 부르기만 하는지,
관문이 보는 그림이 굽는 그림(preset_make.part_vf)과 같은지, 멈추면 TTS·조각 굽기 전에 서는지, 납품이 그 판 관문 기록을 보는지.

결함 실례(10-25): 작품6 취객선비잔 남의 글자('일시품절' 쇼핑몰 화면)·멈춤 / 작품9 B·C 읽는 글 영문 'SNS' / 창고판 옥수수커터 B13 미달 손 납품 /
태양의맛썬 줄6 컷 앞 3프레임 번쩍(완성본 9.47~9.57초 — fit_shot 의 check_shot_cross 는 그 경계를 못 봤다)."""
import json
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import preset_gates as PG  # noqa: E402
from tools.calcopy.engine import preset_make as PM  # noqa: E402
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402

CFG = {"window": [540, 703], "cps": 8.8, "checks": {"length_s": {"allow": [1.0, 60.0]}}}


def _ff(*a):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, a)], check=True, stdin=subprocess.DEVNULL)


def _gray(src, vf, n):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1.000", "-i", str(src), "-an", "-vf", vf + ",format=gray", "-frames:v", str(n),
                          "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    return np.frombuffer(raw, np.uint8)


def _w(tmp, srcs, lines=None):
    """preset_make load_work+plan_check 뒤 꼴의 최소 작품."""
    lines = lines or [{"text": "첫 줄 이야기", "tts": "첫 줄 이야기."}, {"text": "둘째 줄 이야기", "tts": "둘째 줄 이야기."}]
    pieces = [{"text": l["text"], "chars": PM.nchar(l["text"]), "line": i} for i, l in enumerate(lines)]
    cuts = [{"src": Path(s).name, "path": Path(s), "ss": 1.0, "box": [100, 20, 300, 390], "crop": None, "pieces": [i], "move": None,
             "src_dur": 4.0, "meme": False} for i, s in enumerate(srcs)]
    return {"name": "시험", "data": tmp, "lines": lines, "pieces": pieces, "cuts": cuts, "voice": "v", "S": {}}


# ── 관문이 보는 그림 = 굽는 그림 ────────────────────────────────────────────
def test_plain_cut_gate_frame_equals_baked_frame(tmp_path):
    """늘림·움직임 없는 컷: render_bench.clip_cmd(관문 ⑦ cut_gray 가 재는 그림) 필터 = preset_make.part_vf(render_parts 가 굽는 필터) — 픽셀까지 같다."""
    src = tmp_path / "a.mp4"
    _ff("-f", "lavfi", "-i", "testsrc=s=640x480:r=30:d=4", "-pix_fmt", "yuv420p", src)
    W, H2 = PG.win_of(CFG)
    c = {"box": [100, 20, 300, 390], "speed": 1.0, "move": None, "n": 20}
    _, vf_gate, _ = RB.clip_cmd(src, 1.0, 20, c["box"], (W, H2))
    a, b = _gray(src, PM.part_vf(c, W, H2), 20), _gray(src, vf_gate, 20)
    assert a.size == 20 * W * H2 and np.array_equal(a, b)


def test_speed_move_cut_measured_with_part_vf(tmp_path, monkeypatch):
    """늘림·움직임 컷은 render_bench 그림(늘림·move 모름)이 아니라 part_vf 그대로 화면 프레임 수(pm_n)만큼 잰다."""
    seen = {}
    real = PM.part_vf

    def spy(pc, W, H):
        seen.update(pc)
        return real(pc, W, H)
    monkeypatch.setattr(PM, "part_vf", spy)
    src = tmp_path / "a.mp4"
    _ff("-f", "lavfi", "-i", "testsrc=s=640x480:r=30:d=4", "-pix_fmt", "yuv420p", src)
    c = {"src": str(src), "ss": 1.0, "crop": [100, 20, 300, 390], "frames": 24, "pm_n": 30, "speed": 0.8, "move": "sway"}
    assert PG._still_own(c, CFG) == []                     # testsrc 는 움직인다
    assert seen["n"] == 30 and seen["speed"] == 0.8 and seen["move"] == "sway"


# ── 꼴 바꾸기 ──────────────────────────────────────────────────────────────
def test_to_bench_measured_screen_vs_source_frames(tmp_path):
    w = _w(tmp_path, [tmp_path / "a.mp4", tmp_path / "b.mp4"])
    for k, c in enumerate(w["cuts"]):
        c.update(f0=k * 30, n=30, speed=1.0 if k == 0 else 0.8)
    G = PG.to_bench(w, CFG, "판")
    assert G["measured"] and [c["frames"] for c in G["T"]["cuts"]] == [30, 30]
    assert [c["frames"] for c in G["Tsrc"]["cuts"]] == [30, 24]          # 원본에서 읽는 길이 = n×speed
    assert [c["pm_k"] for c in G["T"]["cuts"]] == [0, 1] and G["T"]["end"] == 2.0


def test_plan_estimate_applies_fit_shot(tmp_path, monkeypatch):
    """--plan 어림 컷에도 build_cuts 의 샷 맞춤(preset_make.fit_shot)을 건 ss 로 잰다 — 렌더 때 옮겨질 자리를 그대로(w 는 안 바꾼다)."""
    from tools.calcopy.engine import check_shot_cross as CSC
    monkeypatch.setattr(CSC, "shot_cuts", lambda p, a, b: [1.1])
    w = _w(tmp_path, [tmp_path / "a.mp4"], [{"text": "가나다라마바사아자차카타파하", "tts": "가나다라마바사아자차카타파하."}])
    cfg = {**CFG, "fit_shot": {"enabled": True, "min_speed": 0.75, "flash_s": 0.4}}
    G = PG.to_bench(w, cfg)
    assert G["T"]["cuts"][0]["ss"] == pytest.approx(1.14) and w["cuts"][0]["ss"] == 1.0


# ── G-1 대본 글 ─────────────────────────────────────────────────────────────
def test_text_gate_latin_sns_but_exaggeration_ok(tmp_path):
    """작품9 B·C 꼴(읽는 글 'SNS')은 멈추고, 과장·약간의 창작('떼돈·난리')은 잡지 않는다(칼카피_시작 14)."""
    bad = _w(tmp_path, [], [{"text": "SNS에서 난리 난 그 제품", "tts": "SNS에서 난리 난 그 제품."}])
    ok = _w(tmp_path, [], [{"text": "떼돈 번 술잔의 정체", "tts": "떼돈 번 술잔의 정체."}])
    g = PG.text_gate(bad)
    assert g and "SNS" in g[0] and "줄1" in g[0]
    assert PG.text_gate(ok) == []


# ── ⑦ 문구 컷 번호 = preset_make 컷 번호 ───────────────────────────────────
def test_still_message_uses_preset_cut_index(tmp_path):
    mv, still = tmp_path / "mv.mp4", tmp_path / "still.mp4"
    _ff("-f", "lavfi", "-i", "testsrc=s=640x480:r=30:d=4", "-pix_fmt", "yuv420p", mv)
    _ff("-f", "lavfi", "-i", "color=c=gray:s=640x480:r=30:d=4", "-pix_fmt", "yuv420p", still)
    w = _w(tmp_path, [mv, still], [{"text": "가나다라마바사아자차카", "tts": "가."}, {"text": "가나다라마바사아자차카", "tts": "나."}])
    for k, c in enumerate(w["cuts"]):
        c.update(f0=k * 45, n=45, speed=1.0)
    G = PG.to_bench(w, CFG)
    G["cfg"] = CFG
    bad = [x for x in PG.cut_gates(G, None, tmp_path) if x.startswith("⑦")]
    assert len(bad) == 1 and "컷 멈춤 1 " in bad[0] and "still.mp4" in bad[0]


# ── 연결: 멈추면 TTS·조각 굽기 전에 선다(우회 없음) ───────────────────────────
def _stub_make(monkeypatch, tmp_path, w, calls):
    monkeypatch.setattr(PM, "load_preset", lambda p: ({}, {**CFG, "checks": {**CFG["checks"], "peak_max_dbfs": -1}}))
    monkeypatch.setattr(PM, "load_work", lambda *a: w)
    monkeypatch.setattr(PM, "plan_check", lambda *a: {"line_rate": None})
    monkeypatch.setattr(PM, "tts", lambda *a, **k: calls.append("tts") or tmp_path / "t.wav")
    monkeypatch.setattr(PM, "render_parts", lambda *a, **k: calls.append("render_parts") or (None, []))
    return types.SimpleNamespace(plan=False, out=str(tmp_path / "out"), cache=str(tmp_path / "c"), tts=None, allow_tts=False, test=True, tag=None)


def test_make_one_stops_before_tts_on_text_defect(tmp_path, monkeypatch):
    calls = []
    w = _w(tmp_path, [], [{"text": "SNS에서 난리", "tts": "SNS에서 난리."}])
    a = _stub_make(monkeypatch, tmp_path, w, calls)
    with pytest.raises(PG.GateStop, match="G-1"):
        PM.make_one(tmp_path, tmp_path, a)
    assert calls == []


def test_make_one_stops_before_parts_on_cut_defect(tmp_path, monkeypatch):
    calls = []
    w = _w(tmp_path, [])
    a = _stub_make(monkeypatch, tmp_path, w, calls)
    monkeypatch.setattr(PG, "voice_gate", lambda *a, **k: [])
    monkeypatch.setattr(PM, "narration", lambda *a: (tmp_path / "n.wav", 1.0))
    monkeypatch.setattr(PM, "timing", lambda *a: ([], 1.0))
    monkeypatch.setattr(PM, "fix_line_rates", lambda t, d, w_, c, n, p: (t, d, n))
    monkeypatch.setattr(PM, "build_cuts", lambda *a: None)
    monkeypatch.setattr(PG, "pre_render", lambda *a, **k: {"bad": ["④ 컷 3 줄7 남의 박힌 글자 3/3장"], "sheet": None, "measured": True})
    with pytest.raises(PG.GateStop, match="남의 박힌 글자"):
        PM.make_one(tmp_path, tmp_path, a)
    assert calls == ["tts"]                                # TTS 는 했고 조각 굽기는 안 했다


def test_make_one_stops_on_voice_gate(tmp_path, monkeypatch):
    calls = []
    a = _stub_make(monkeypatch, tmp_path, _w(tmp_path, []), calls)
    monkeypatch.setattr(PG, "voice_gate", lambda *a, **k: ["② 덩어리1 skip: 들림 '빠진 말'"])
    with pytest.raises(PG.GateStop, match="받아쓰기"):
        PM.make_one(tmp_path, tmp_path, a)
    assert calls == ["tts"]


# ── 관문 기록 → 납품 자물쇠 ─────────────────────────────────────────────────
def test_record_and_deliver_lock(tmp_path):
    from tools.calcopy.engine import deliver as D
    from tools.calcopy.engine import finalize as FZ
    fin = tmp_path / "r" / "final.mp4"
    fin.parent.mkdir()
    _ff("-f", "lavfi", "-i", "color=c=blue:s=1080x1920:r=30:d=1", "-f", "lavfi", "-i", "sine=d=1", "-shortest", "-pix_fmt", "yuv420p",
        "-c:a", "aac", fin)
    rec = FZ.seal(fin, "preset_make", None, log=lambda m: None)
    drive = tmp_path / "drive"
    (drive / "ch").mkdir(parents=True)
    doc = tmp_path / "doc"
    doc.mkdir()
    ok, why, _ = D.check(fin, drive / "ch", "01_test_item.mp4", doc, drive)
    assert not ok and any("관문 기록이 없다" in x for x in why)
    rows = [{"B": "B1", "항목": "길이", "값": 28, "기준": "23~33", "ok": True}]
    p = PG.record(doc, rec["md5"], rows + [{"B": "B13", "항목": "같은 소스 ±3초", "값": 20, "기준": "0", "ok": False}], ["⑦ 멈춤"], log=lambda m: None)
    assert json.loads(p.read_text(encoding="utf-8"))["ok"] is False
    ok, why, _ = D.check(fin, drive / "ch", "01_test_item.mp4", doc, drive)
    assert not ok and any("같은 소스" in x for x in why)
    PG.record(doc, rec["md5"], rows, ["G-1 대본 글"], log=lambda m: None)
    ok, why, _ = D.check(fin, drive / "ch", "01_test_item.mp4", doc, drive)
    assert ok, why
