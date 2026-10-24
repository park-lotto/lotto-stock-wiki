# -*- coding: utf-8 -*-
"""품질 관문 한 벌(tools/calcopy/hybrid/quality_gate.py) — 사보타주 시험(관제 263 지시서 04, 2026-10-24).

항목마다 "그 결함이 있는 입력"으로 ×가 뜨는지 먼저 본다(표준 §5-1). 옛 bench_check 는 이 다섯 중 썸네일 하나만 잡았다
(실측: 효과음 39발·되감김·A-B-A·컷 중앙 — bench_check 에 항목이 없어 전부 ○로 통과).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).with_name("fixtures") / "quality_gate"
LINE_READS = ROOT / "channel" / "ititemlog" / "줄판독"


def _bench_docs():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(LINE_READS.glob("*.json"))]


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], check=True, stdin=subprocess.DEVNULL, capture_output=True)


# ---------------------------------------------------------------- 사보타주 1: 효과음 39발 → B14 ×
def test_b14_sfx_39_fails_zero_passes():
    from tools.calcopy.hybrid.quality_gate import sfx_excess
    docs = _bench_docs()
    assert docs, "잇템로그 줄판독이 있어야 한다"
    bad, msg = sfx_excess(39, 29.03, docs)          # 재미썸홈 총알람 1판 = 팩21 39발 / 29.03초(handoff 10-17)
    assert bad is False, msg
    ok, msg = sfx_excess(0, 27.77, docs)
    assert ok is True, msg
    assert sfx_excess(3, 27.0, [])[0] is None         # 벤치 줄판독 없음 = 미측정(통과 아님)


# ---------------------------------------------------------------- 사보타주 2: 컷 중앙 2.85 vs 벤치 1.63 → match cut.median ×
def _ours_doc(dur=29.0):
    return {"lines": [{"t0": i * 2.0, "t1": i * 2.0 + 1.8, "speaker": "나레", "text": "가나다라마바", "enter": "instant", "emph": [], "sticker": [],
                       "sfx": None, "layer": "채널"} for i in range(14)], "dur": dur}


def test_match_cut_median_banana_fails():
    from tools.calcopy.engine.kal_analyze import match_table
    from tools.calcopy.hybrid.quality_gate import match_verdict
    T = match_table(_bench_docs(), _ours_doc(), {"cut_median": 2.85, "lufs": -14.0}, {"cut_median": [1.63], "lufs": [-14.0]})
    row = next(r for r in T["rows"] if r["key"] == "cut.median")
    assert row["judge"] == "out", row                   # 방구석 바나나 1판 2.85초 vs 원본 1.63(handoff 10-16 반려)
    ok, msg, bad = match_verdict(T, upgrade=False)
    assert ok is False and "cut.median" in bad
    T2 = match_table(_bench_docs(), _ours_doc(), {"cut_median": 1.70, "lufs": -14.0}, {"cut_median": [1.63], "lufs": [-14.0]})
    assert next(r for r in T2["rows"] if r["key"] == "cut.median")["judge"] == "in"


# ---------------------------------------------------------------- 사보타주 3: 되감김 0.37초 → B16' ×
def test_rewind_itemhome1_fails_and_fixed_passes():
    from tools.calcopy.engine import check_seams
    bad = check_seams.check(str(FIX / "rewind_itemhome1판_16.8s.mp4"))
    assert bad["ok"] is False and bad["되감김"], bad["되감김"]        # 아이템홈 1편 1판 17초 되감김 0.37초(사장님 지적 10-17)
    good = check_seams.check(str(FIX / "norewind_itemhome2판_16.8s.mp4"))
    assert good["ok"] is True and not good["되감김"]                  # 같은 자리 2판(되감김 0)


# ---------------------------------------------------------------- 사보타주 4: A-B-A → B16 ×
def test_aba_detected_on_narr_cuts():
    from tools.calcopy.hybrid.checks import aba_violations
    seq = ["d2.mp4", "d2.mp4", "mkA.mp4", "d2.mp4", "mkA.mp4", "mkA.mp4"]   # 잇템로그 13편 나레 컷 순서 일부(N4 mkA → N5 d2 → N5 mkA)
    cuts = [{"src": s, "t0": float(i), "t1": float(i + 1)} for i, s in enumerate(seq)]
    assert aba_violations(cuts)
    assert not aba_violations([{"src": s, "t0": float(i), "t1": float(i + 1)} for i, s in enumerate(["a", "a", "b", "b", "c"])])


# ---------------------------------------------------------------- 사보타주 5: 썸네일 2프레임 없음 → 썸네일 ×
def test_thumb_two_frames(tmp_path):
    from PIL import Image
    from tools.calcopy.hybrid.quality_gate import thumb_stamped
    doc = tmp_path / "doc"
    (doc / "thumb").mkdir(parents=True)
    (doc / "썸네일.json").write_text(json.dumps({"pick": "A"}), encoding="utf-8")
    Image.new("RGB", (108, 192), (230, 20, 20)).save(doc / "thumb" / "A.jpg")
    good, bad = tmp_path / "good.mp4", tmp_path / "bad.mp4"
    _ffmpeg("-f", "lavfi", "-i", "color=c=0xE61414:s=108x192:r=30:d=1", "-f", "lavfi", "-i", "color=c=blue:s=108x192:r=30:d=1",
            "-filter_complex", "[0:v]trim=end_frame=2,setpts=PTS-STARTPTS[a];[a][1:v]concat=n=2:v=1[v]", "-map", "[v]", "-pix_fmt", "yuv420p", good)
    _ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=108x192:r=30:d=1", "-pix_fmt", "yuv420p", bad)
    ok, msg = thumb_stamped(good, doc)
    assert ok is True, msg
    ok, msg = thumb_stamped(bad, doc)
    assert ok is False, msg


# ---------------------------------------------------------------- 표식: style_sha 지우면 불신
def test_marker_requires_style_sha(tmp_path):
    from tools.calcopy.hybrid.quality_gate import marker_verdict
    sf = tmp_path / "판.json"
    sf.write_text('{"name": "x"}', encoding="utf-8")
    sha = hashlib.sha256(sf.read_bytes()).hexdigest()
    info = {"style_sha": sha[:16], "renderer_sig": "render_bench@abc", "placement_check": {"reference": "ro1l3u734v4"}}
    assert marker_verdict(info, sf)[0] is True
    assert marker_verdict({k: v for k, v in info.items() if k != "style_sha"}, sf)[0] is False
    assert marker_verdict({k: v for k, v in info.items() if k != "placement_check"}, sf)[0] is False
    sf.write_text('{"name": "y"}', encoding="utf-8")               # 렌더 뒤 판 파일이 바뀜
    assert marker_verdict(info, sf)[0] is False


# ---------------------------------------------------------------- 1차 자: 필수 칸 미측정 = ×
def test_match_unmeasured_required_cell_fails():
    from tools.calcopy.hybrid.quality_gate import match_verdict
    rows = [{"key": "len.duration", "judge": "in", "core": True}, {"key": "cut.median", "judge": "in", "core": True},
            {"key": "speech.cps.나레", "judge": "in", "core": True}, {"key": "chunk.chars", "judge": "in", "core": True},
            {"key": "chunk.sec", "judge": "in", "core": True}, {"key": "sfx.rate", "judge": "in", "core": True},
            {"key": "mix.lufs", "judge": "failed", "core": False}]
    assert match_verdict({"rows": rows, "n_bench": 2}, upgrade=False)[0] is True       # 참고 칸 미측정은 판정 밖
    rows[5] = {"key": "sfx.rate", "judge": "failed", "core": True}
    ok, msg, bad = match_verdict({"rows": rows, "n_bench": 2}, upgrade=False)
    assert ok is False and "sfx.rate(미측정)" in bad
    assert match_verdict({"rows": rows, "n_bench": 2}, upgrade=True)[0] is True        # 업그레이드 판 = 뼈대 칸만 필수
    rows[1] = {"key": "cut.median", "judge": "failed", "core": True}
    assert match_verdict({"rows": rows, "n_bench": 2}, upgrade=True)[0] is False


def test_match_new_cells_measured_from_line_reads():
    from tools.calcopy.engine.kal_analyze import match_table, transition_key
    assert transition_key("cut") == "cut" and transition_key("zoomblur(약하게)") == "zoomblur"
    assert transition_key("none(같은 컷 안 자막만)") is None and transition_key(None) is None
    ours = {**_ours_doc(29.5), "transition_rate": {"cut": 1.0}, "sfx_rate": 0.0, "frame0_kind": "card"}
    T = match_table(_bench_docs(), ours, None, None)
    keys = {r["key"]: r for r in T["rows"]}
    for k in ("transition.rate", "sfx.rate", "sticker.rate", "meme.rate", "thumb.frame0"):
        assert k in keys and keys[k]["bench"] is not None, keys.get(k)
    assert keys["thumb.frame0"]["judge"] == "in"
    assert keys["sfx.rate"]["judge"] == "out"          # 벤치 2편 효과음 0.034~0.067/초 vs 우리 0


# ---------------------------------------------------------------- 장면↔대사 어댑터: 컷 10개(맞음 7·틀림 3) → 손 정답 ±1칸
def test_scene_fit_render_adapter(tmp_path):
    from tools.calcopy.hybrid.quality_gate import fit_verdict
    from tools.calcopy.oneshot import scene_fit
    R = tmp_path / "work" / "render"
    R.mkdir(parents=True)
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=s=180x320:r=30:d=10", "-pix_fmt", "yuv420p", R / "final.mp4")
    truth = [True, True, False, True, True, True, False, True, False, True]          # 손 정답: 틀린 컷 2·6·8
    cuts = [{"line": f"N{k}", "src": "x.mp4", "ss": 0, "t0": float(k), "t1": float(k + 1), "kind": "tts"} for k in range(10)]
    rows = [{"line": f"N{k}", "t0": float(k), "t1": float(k + 1), "text": ("맞음" if t else "틀림") + f" {k}", "speaker": "narr"} for k, t in enumerate(truth)]
    (R / "timeline.json").write_text(json.dumps({"cuts": cuts, "lines": {}, "end": 10.0}), encoding="utf-8")
    (R / "자막표.json").write_text(json.dumps({"rows": rows}, ensure_ascii=False), encoding="utf-8")

    class FakeLLM:
        def __init__(self):
            self.calls = []

        def __call__(self, parts, prompt, tag):
            self.calls.append(tag)
            fits = [{"n": int(j), "score": 9 if "맞음" in piece else 2, "seen": "-", "want": "-"}
                    for j, piece in re.findall(r"^(\d+): «([^»]*)»", prompt, re.M)]
            return {"fits": fits}, None
    llm = FakeLLM()
    res = scene_fit.measure_render(tmp_path / "work", llm=llm)
    s = res["summary"]
    assert s["judged"] == 10 and abs(s["below_min"] - 3) <= 1, s
    assert len(llm.calls) <= 3                                                        # 시트 10칸 1회 · 편당 ≤3회
    assert fit_verdict(s, {"mean": 8.0, "below_rate": 0.1})[0] is False               # 평균 6.9 < 7.0, 미만 30% > 20%
    assert fit_verdict(s, {"mean": 7.5, "below_rate": 0.25})[0] is True
    assert fit_verdict(s, None)[0] is None                                            # 벤치 fit 없음 = 미측정


def test_line_cps_verdict():
    from tools.calcopy.hybrid.quality_gate import line_cps_verdict
    assert line_cps_verdict({"N1": 20, "N2": 22}, {"N1": 2.3, "N2": 2.5})[0] is True
    assert line_cps_verdict({"N1": 20, "N2": 22, "N3": 20}, {"N1": 2.3, "N2": 2.5, "N3": 4.9})[0] is False   # 12편 N3 4.90자/초 꼴(되풀이)
    assert line_cps_verdict({"N1": 20}, {})[0] is None
