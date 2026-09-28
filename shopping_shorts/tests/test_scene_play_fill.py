"""모자란 읽는 창 채우기(scene_play.js fillShortWindow) — 장면 끝에서 소재가 살짝 모자라 멈추는 것을 없앤다(2026-09-27 사장님).

규칙(우선순위): ① 꼬리를 뒤로(다음 장면 전환·원본 끝·청소 구간 끝 앞까지) ② 머리를 앞으로(앞 장면 전환·청소 구간 시작까지)
  ③ 남는 몫만 종전 느리게→정지. 전환 목록이 없으면 안 늘린다. 청소본 칸은 DATA.clean_spans 안에서만.
  채우기 뒤에 잔상 가드(guardReadWindow)가 마지막에 한 번 더 본다.
검사는 전부 **서버 러너**(node screen_clips_runner.js scene_play.js data.json) — 화면·미리보기·완성본·캡컷이 쓰는 그 계산.
합성: 구절 맞춤 칸(자막 1구절 = 컷 1개, 1.5초) + 조각 [10.0, 11.2] — 조각을 0.3초 넘쳐 종전엔 조각 안에서 1.25배로 늘리다
  상한 1.15배를 넘은 몫이 정지(planClips 구절 경로의 "살짝 넘침" 규칙 = 실제 정지 컷의 흔한 꼴).
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")

HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "screen_clips_runner.js"
SCENE_PLAY = HERE / "static" / "scene_play.js"


def _data(cuts=None, spans=None, seg=(10.0, 11.2), dur=1.5, sid="a", reel=60.0):
    d = {"beats": [{"beat_idx": 0, "narration": "가", "primary": {"video_id": "s0", "seg_id": sid, "start": seg[0], "end": seg[1]},
                    "alternates": []}],
         "segments": {sid: {"video_id": "s0", "start": seg[0], "end": seg[1]}},
         "tts_dur": {"0": dur}, "src_duration": {"s0": reel},
         "captions": {"0": [{"text": "가", "start": 0.0, "end": dur}]}}
    if cuts is not None:
        d["scenecuts"] = {"s0": cuts}
    if spans is not None:
        d["clean_spans"] = spans
    return d


def _run(data, tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    r = subprocess.run(["node", str(RUNNER), str(SCENE_PLAY), str(p)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    c = json.loads(r.stdout)[0]["c"]
    assert len(c) == 1, c
    return c[0]


def test_baseline_is_short_without_scenecuts(tmp_path):
    """전환 목록이 없으면 종전 그대로(0.3초 모자람 → 느리게·정지). 이 합성이 실제로 모자란 컷인지 먼저 확인."""
    c = _run(_data(None), tmp_path)
    assert c["s"] == 10.0 and abs(c["d"] - 1.5) < 1e-6 and abs(c["sd"] - 1.2) < 1e-6, c
    assert c["d"] / c["sd"] > 1.15, "정지가 생기는 합성이어야 한다"


def test_tail_extends_when_no_cut(tmp_path):
    c = _run(_data([5.0, 20.0]), tmp_path)
    assert c["s"] == 10.0 and abs(c["sd"] - 1.5) < 1.5e-3, c        # 원본 뒤 같은 장면으로 채움 → 정지 없음


def test_tail_blocked_then_head_pulls(tmp_path):
    c = _run(_data([9.0, 11.3]), tmp_path)
    assert c["s"] + c["sd"] <= 11.3 + 1e-9, c                        # 다음 장면 첫 프레임은 안 읽는다
    assert abs(c["s"] - 9.8) < 1.5e-3 and abs(c["sd"] - 1.5) < 1.5e-3, c   # 모자란 몫은 앞(같은 장면)으로
    assert c["s"] >= 9.0


def test_both_blocked_keeps_old_rule(tmp_path):
    c = _run(_data([10.0, 11.2]), tmp_path)
    assert c["s"] == 10.0 and abs(c["sd"] - 1.2) < 1e-6, c           # 막히면 종전(느리게→정지)


def test_clean_spans_limit(tmp_path):
    """청소본 칸 — 지운 구간 [9.9, 11.3] 밖으로는 안 나간다(원본 자막·증분 청소 과금 방지)."""
    c = _run(_data([5.0, 20.0], {"s0": [[9.9, 11.3]]}), tmp_path)
    assert c["s"] >= 9.9 - 1e-9 and c["s"] + c["sd"] <= 11.3 + 1e-9, c
    assert abs(c["s"] - 9.9) < 1.5e-3 and abs(c["sd"] - 1.4) < 1.5e-3, c


def test_window_outside_clean_spans_not_moved(tmp_path):
    c = _run(_data([5.0, 20.0], {"s0": [[20.0, 30.0]]}), tmp_path)
    assert c["s"] == 10.0 and abs(c["sd"] - 1.2) < 1e-6, c


def test_clean_spans_error_means_no_fill(tmp_path):
    c = _run(_data([5.0, 20.0], {"__error__": 1}), tmp_path)
    assert c["s"] == 10.0 and abs(c["sd"] - 1.2) < 1e-6, c


def test_film_piece_not_extended(tmp_path):
    """사람이 필름에서 정한 구간(film_)은 그 구간만 — 잘라 낸 꼬다리가 되살아나지 않게."""
    c = _run(_data([5.0, 20.0], sid="film_s0_10.00_11.20"), tmp_path)
    assert c["s"] == 10.0 and abs(c["sd"] - 1.2) < 1e-6, c


def test_reel_end_limits(tmp_path):
    c = _run(_data([5.0], reel=11.3), tmp_path)
    assert c["s"] + c["sd"] <= 11.3 + 1e-9, c


def test_guard_runs_after_fill(tmp_path):
    """순서: 채우기(꼬리 11.5까지) 뒤 가드가 머리 0.05초의 전환(10.05)을 뺀다 — 가드가 마지막."""
    c = _run(_data([10.05, 20.0]), tmp_path)
    assert abs(c["s"] - 10.05) < 1e-6, c
    assert abs(c["s"] + c["sd"] - 11.5) < 1.5e-3, c


def test_fill_before_guard_in_code():
    """★2026-09-28: fillShortWindow 는 finish(fitBeatCuts)의 창 놓기로 대체됐다 — 창 놓기(재배분 포함) → 가드 순서, 옛 함수는 없다."""
    src = SCENE_PLAY.read_text(encoding="utf-8")
    i = src.index("const finish = (base, manual) =>")
    body = src[i:src.index("return base;\n  };", i)]
    code = "\n".join(ln.split("//")[0] for ln in body.splitlines())
    assert code.index("fitCutLens(") < code.index("guardReadWindow("), "재배분·창 놓기 → 가드 순서"
    whole = "\n".join(ln.split("//")[0] for ln in src.splitlines())
    assert "fillShortWindow(" not in whole, "옛 채우기 함수가 남으면 판단이 두 벌이 된다"


def test_app_clean_spans_from_regions(monkeypatch, tmp_path):
    """DATA.clean_spans = clean_base._regions(지운 원본 구간)를 소재별로 합친 것 — 판단은 clean_base 한 곳. 정본 없으면 {}."""
    from shopping_shorts import app, clean_base as cb
    monkeypatch.setattr(cb, "load_base", lambda work: {"cuts": []})
    monkeypatch.setattr(cb, "_regions", lambda base: [("clean", "clean-0", "s0", 1.0, 2.0, 0, 1), ("clean", "clean-1", "s0", 2.01, 3.0, 1, 1),
                                                      ("clean", "clean-2", "s0", 5.0, 6.0, 2, 1), ("cb1", "cb1", "s1", 0.5, 0.9, 0, 1)])
    assert app._lab_clean_spans({}, tmp_path) == {"s0": [[1.0, 3.0], [5.0, 6.0]], "s1": [[0.5, 0.9]]}
    monkeypatch.setattr(cb, "load_base", lambda work: None)
    assert app._lab_clean_spans({}, tmp_path) == {}
    monkeypatch.setattr(cb, "load_base", lambda work: (_ for _ in ()).throw(RuntimeError("x")))
    assert app._lab_clean_spans({}, tmp_path) == {"__error__": 1}       # 못 읽으면 화면이 안 늘린다(과금 방지)
    src = Path(app.__file__).read_text(encoding="utf-8")
    i = src.index("def api_mix_scene_lab_data(")
    assert '"clean_spans": _lab_clean_spans(job, work)' in src[i:src.index(chr(10) + "@app.", i)]
