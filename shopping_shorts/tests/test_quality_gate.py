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
    assert match_verdict({"rows": rows, "n_bench": 2}, upgrade=True)[0] is False       # sfx.rate 는 뼈대 칸(표준 §11 ③) — 업그레이드 판도 필수
    rows[5] = {"key": "sfx.rate", "judge": "in", "core": True}
    rows.append({"key": "thumb.frame0", "judge": "out", "core": True})                  # 겉모양 칸 — 업그레이드 판은 바꿔도 된다
    assert match_verdict({"rows": rows, "n_bench": 2}, upgrade=True)[0] is True
    assert match_verdict({"rows": rows, "n_bench": 2}, upgrade=False)[0] is False
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
    assert len(llm.calls) == 2                                                        # 시트 1장 × 2회 채점(두 번이 같으면 3회째 없음)
    assert scene_fit.gold_check([r["score"] for r in res["rows"]], ["low" if not t else "high" for t in truth])["ok"]
    llm2 = FakeLLM()
    scene_fit.measure_render(tmp_path / "work", llm=llm2)
    assert len(llm2.calls) == 0                                                       # 같은 시트 = 캐시(재계산 0)
    roles = {f"N{k}": ("나레 훅" if k in (2, 6) else "본문") for k in range(10)}
    s2 = scene_fit.summarize([r["score"] for r in res["rows"]], [roles[r["cut"]["line"]] for r in res["rows"]])
    assert s2["below_base"] == 8 and s2["below_min"] == 1 and s2["skipped_roles"] == 2   # 훅 줄 컷은 미만 비율 분모에서 뺀다
    assert fit_verdict(s, {"mean": 8.0, "below_rate": 0.1})[0] is False               # 평균 6.9 < 7.0, 미만 30% > 20%
    assert fit_verdict(s, {"mean": 7.5, "below_rate": 0.25})[0] is True
    assert fit_verdict(s, None)[0] is None                                            # 벤치 fit 없음 = 미측정


def test_line_cps_reads_render_table():
    from tools.calcopy.hybrid.quality_gate import line_cps_verdict
    assert line_cps_verdict({"N1": 8.7, "N2": 8.8}, 0.35)[0] is True
    assert line_cps_verdict({"N1": 8.7, "N2": 8.8, "N3": 4.1}, 0.35)[0] is False     # 12편 N3 되풀이 꼴(평균의 ±35% 밖)
    assert line_cps_verdict(None, 0.35)[0] is None                                     # 렌더가 표를 안 남김 = 미측정
    assert line_cps_verdict({"N1": 8.7}, None)[0] is None                              # 주인 상수 없음 = 미측정


# ---------------------------------------------------------------- 표준 §11 ② B13: 겹침 항상 × · 거리 min(3, 0.25×길이)
def test_b13_overlap_and_length_scaled_gap():
    from tools.calcopy.hybrid.quality_gate import reuse_violations_bench

    def c(src, ss, dur, t0, line):
        return {"src": src, "ss": ss, "dur": dur, "t0": t0, "t1": t0 + dur, "line": line}
    ep13 = [c("mkA.mp4", 0.0, 2.486, 15.0, "N4"), c("mkA.mp4", 1.2, 2.12, 17.49, "O3"), c("mkA.mp4", 6.0, 0.49, 23.85, "N6")]
    bad = reuse_violations_bench(ep13, {"mkA.mp4": 7.5})
    assert any(b.startswith("겹침") and "(N4)" in b and "(O3)" in b for b in bad), bad        # 13편 N4↔O3 같은 프레임 1.2~2.49
    assert not any("(N6)" in b for b in bad), bad                                           # 7.5초 소스 문턱 1.875초, O3 끝 3.32 → N6 6.0 = 2.68초 떨어짐
    long_src = [c("d2.mp4", 24.087, 2.19, 19.6, "N5"), c("d2.mp4", 28.2, 1.45, 11.3, "N3")]
    assert reuse_violations_bench(long_src, {"d2.mp4": 80.0})                               # 긴 소스 = 3초 안 1.92초 떨어짐 → ×
    assert not reuse_violations_bench([c("d2.mp4", 0.0, 2.0, 0.0, "N1"), c("d2.mp4", 2.0, 2.0, 2.0, "N1")], {"d2.mp4": 80.0})   # 이어 읽기


# ---------------------------------------------------------------- 표준 §11 ① B18 줄 간격 = 판 timing · B18a 줄 안 쉼
def test_b18_gap_follows_timing_and_b18a_inline():
    from tools.calcopy.hybrid.quality_gate import gap_verdict, inline_pause_verdict
    assert gap_verdict([("N2→N3", 0.08, 0.095), ("N3→O2", 0.08, 0.129)])[0] is True       # 잇템로그 13편 실측(판 timing.gap 0.08)
    assert gap_verdict([("N2→N3", 0.08, 0.30)])[0] is False                                 # 옛 상수 0.30 으로 쉬면 벤치(붙여 말함)와 다르다
    th = {"comma": 0.22, "period": 0.30}
    assert inline_pause_verdict([("N7", ["comma"], [0.23, 0.09])], th)[0] is True
    assert inline_pause_verdict([("N7", ["comma"], [0.10])], th)[0] is False
    assert inline_pause_verdict([], th)[0] is None


def test_strict_catches_null_transition():
    from tools.calcopy.engine.kal_analyze import check_doc
    doc = {"id": "x", "dur": 5.0, "title_lines": [], "source_label": None, "beats": None, "narr_share": None, "notes": [],
           "lines": [{"t0": 0.0, "t1": 1.0, "speaker": "나레", "text": "가", "layer": "채널", "enter": "cut", "emph": [], "sticker": [], "sfx": None,
                      "scene": "얼굴", "cut_at": [], "role": "훅", "y": [1, 2], "fill_hex": "#FFFFFF", "fit": 7,
                      "transition": None, "motion": "cam", "confidence": "눈"}]}
    assert any("transition" in e for e in check_doc(doc, strict=True)["errors"])
    doc["lines"][0]["transition"] = "cut"
    assert not check_doc(doc, strict=True)["errors"]


def test_enter_append_is_its_own_word_not_decoration():
    from tools.calcopy.engine.kal_analyze import _decorated, enter_key
    assert enter_key("append") == "append" and enter_key("쌓기(아래로)") == "append"
    assert _decorated({"enter": "append"})["enter_fx"] is False


def test_scene_fit_gold_fixture_check():
    from tools.calcopy.oneshot.scene_fit import gold_check
    G = json.loads((FIX.parent / "scene_fit_gold.json").read_text(encoding="utf-8"))
    gold = [r["gold"] for r in G["rows"]]
    assert gold.count("low") == 3 and gold.count("high") == 3
    real = [7, 5, 1, 5, 10, 1, 10, 10, 1, 7]                       # 10-25 실제 Claude 소넷 루브릭 2~3회 중앙값(보고 표)
    assert gold_check(real, gold)["ok"]
    old = [10, 6, 1, 5, 8, 1, 6, 6, 1, 5]                           # 10-24 옛 fit_judge 한 번 채점 — 분류로는 혼동 0(옛 미달은 '7 미만 비율' 자 탓)
    assert gold_check(old, gold)["ok"]
    assert not gold_check([7, 5, 7, 5, 10, 1, 10, 10, 1, 7], gold)["ok"]   # 틀린 컷(2)을 7로 = 혼동
    assert not gold_check([7, 5, 1, 5, 5, 1, 10, 10, 1, 7], gold)["ok"]    # 맞는 컷(4)을 5로 = 혼동


# ---------------------------------------------------------------- gate() 배선(행 쌓기·초·캐시·보고 파일) — 10-25 row() 재귀 사고 재발 막기
def test_gate_wiring_minimal(tmp_path):
    from tools.calcopy.hybrid.quality_gate import gate
    doc, R = tmp_path / "doc", tmp_path / "work" / "render"
    doc.mkdir(); R.mkdir(parents=True)
    _ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=108x192:r=30:d=1", "-pix_fmt", "yuv420p", R / "final.mp4")
    (R / "timeline.json").write_text(json.dumps({"cuts": [], "lines": {"N1": [0.0, 1.0]}, "end": 1.0}), encoding="utf-8")
    (R / "자막표.json").write_text(json.dumps({"rows": [], "sfx": [{"t": 0.1}] * 5, "check": {"ok": True, "reference": "x", "worst_slot_diff": 0}}), encoding="utf-8")
    r = gate("잇템로그판", doc, tmp_path / "work", only=("자막·효과", "표식"), eye_pack=False, log=lambda *a: None)
    what = {x["what"]: x for x in r["rows"]}
    assert r["ok"] is False and len(r["rows"]) == 3, r["rows"]
    assert what["B14 효과음 과다(≤ 벤치 p90)"]["ok"] is False                      # 5발/1초
    assert what["render_info 표식(판 sha·렌더러 sig·reference)"]["ok"] is False   # render_info 없음 = 불신
    assert all(isinstance(x["sec"], float) for x in r["rows"])
    assert (doc / "품질관문.json").exists() and (tmp_path / "work" / "gate_stage_log.json").exists()


# ---------------------------------------------------------------- frame_metrics 글자 사이 빈칸이 전부 40px 넘음 → median([]) 로 죽던 것(10-25)
def test_frame_metrics_all_gaps_wide(tmp_path):
    import cv2
    import numpy as np
    from tools.calcopy.engine.kal_analyze import frame_compare, frame_metrics
    img = np.zeros((300, 1080, 3), np.uint8)
    for x0 in (200, 400, 600):
        cv2.rectangle(img, (x0, 100), (x0 + 50, 200), (255, 255, 255), -1)
        cv2.rectangle(img, (x0 - 6, 94), (x0 + 56, 206), (0, 0, 0), 3)
    p = tmp_path / "f.png"
    cv2.imwrite(str(p), img)
    m = frame_metrics(str(p), (0, 300))
    assert m["letter_gap_px"] is None and m["letter_gap_n"] == 0 and m["letter_gap_dropped"] >= 1
    row = next(r for r in frame_compare(str(p), str(p), (0, 300))["rows"] if r["key"] == "letter_gap_px")
    assert row["pass"] is False and "미측정" in row["diff"]                           # 표본 0 은 통과가 아니다


# ---------------------------------------------------------------- 업그레이드 자 연결(05 engine/upgrade_table) — kal_analyze 이름으로 불린다
def test_upgrade_table_is_wired(monkeypatch):
    from tools.calcopy.engine import kal_analyze as K
    from tools.calcopy.engine import upgrade_table as U
    monkeypatch.setattr(U, "upgrade_table", lambda st, doc, work: {"called": (st, doc, work)})
    assert K.upgrade_table("판", "d", "w") == {"called": ("판", "d", "w")}


# ---------------------------------------------------------------- 표준 ⑯ 전환 세기(02 transition_drop) — 장치 끈 판 대조 −0.072 는 통과하면 안 된다
def test_transition_strength_drop_verdict():
    from tools.calcopy.hybrid.quality_gate import drop_verdict
    bench = [0.923, 0.587, 0.72]                                   # 잇템로그 벤치 zoomblur 3회(02 f619f36fe 실측)
    assert drop_verdict([0.654] * 9, bench)[0] is True             # 장치 켠 우리 완성본 중앙 0.654(9경계)
    assert drop_verdict([-0.072], bench)[0] is False               # 장치 끈 키치잇판 같은 시각 대조 −0.072
    assert drop_verdict([], bench)[0] is False                     # 벤치엔 전환이 있는데 우리 경계 0개
    assert drop_verdict([0.5], [])[0] is None                      # 벤치 표본 없음 = 미측정
    assert drop_verdict([0.966], bench)[0] is False                # 마스크 안 뺀 창 전체 자(0.966)로 재면 +34% → 밖


def test_ref_row_not_in_verdict(tmp_path):
    from tools.calcopy.hybrid.quality_gate import _row
    rows = []
    _row(rows, "화면", "참고", lambda: (False, "x"), "s", ref=True)
    assert rows[0]["ref"] is True and rows[0]["ok"] is False
