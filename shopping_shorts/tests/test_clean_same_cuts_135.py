# -*- coding: utf-8 -*-
"""관제 135 — 자막제거 뒤 **편성을 안 바꿨으면 지운 그 컷 그대로**(관제 110 의 재발 막기).

사고(2026-10-06 황선희님 d20c9f3d6a54 6번 칸): 고급으로 전체를 지운 직후, 같은 편성인데 화면 컷이 달라져
(s3 20.567초 컷 1.2초 → 1.42초) 지운 끝을 0.22초 넘었고 그 컷이 원본으로 나가 장면꾸미기에 원본 자막이 보였다.
110 의 판정("청소 구간을 안 보고 짠 컷이 지운 구간 안인가")이 다듬기 전 컷을 봐서, 전환 가드가 머리를 0.1초 옮긴 컷
(s3 0.0 → 0.1초)이 '밖'으로 떨어졌다. 자료 = 그 작업의 실제 컷 계산 입력(대본·장면 설명은 뺐다).

검사 ① 화면 컷(서버 러너 = 편집 화면과 같은 JS): 청소 구간 + 청소 당시 컷 기록을 주면 모든 칸 컷이 기록과 같다.
     ② 안전망(clean_base._remap_replay): 편성이 스냅샷과 같은 칸은 컷이 벗어나도 청소 당시 컷으로 재생(안 덮인 칸 아님).
        편성이 달라진 칸은 종전대로 안 덮인 칸(증분 청소 대상).
"""
import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "screen_clips_runner.js"
SCENE_PLAY = HERE / "static" / "scene_play.js"
FIX = Path(__file__).resolve().parent / "fixtures" / "clean_drift_135.json"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")


def _run(data, tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    r = subprocess.run(["node", str(RUNNER), str(SCENE_PLAY), str(p)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    return [b["c"] for b in json.loads(r.stdout)]


def _key(cuts):
    return [(c["v"], round(c["s"], 2), round(c["sd"] if c["sd"] is not None else c["d"], 2)) for c in cuts]


@needs_node
def test_청소_뒤_모든_칸_컷이_청소_당시_기록과_같다(tmp_path):
    data = json.loads(FIX.read_text(encoding="utf-8"))
    got = _run(data, tmp_path)
    for i, cuts in enumerate(got):
        rec = [(v, round(s, 2), round(sd, 2)) for v, s, sd in data["clean_cuts"][str(i)]]
        assert _key(cuts) == rec, (i, _key(cuts), rec)


@needs_node
def test_청소_전_컷과_청소_뒤_컷이_같다(tmp_path):
    """청소 구간·기록이 없던 때(청소 전)의 컷 = 청소 뒤 컷. 6번 칸 마지막 컷이 지운 끝(21.767초)을 넘지 않는다."""
    data = json.loads(FIX.read_text(encoding="utf-8"))
    before = copy.deepcopy(data)
    before.pop("clean_spans"); before.pop("clean_cuts")
    assert [_key(c) for c in _run(data, tmp_path)] == [_key(c) for c in _run(before, tmp_path)]
    last = _run(data, tmp_path)[5][-1]
    assert last["v"] == "s3" and last["s"] + last["sd"] <= 21.767 + 0.02, last


@needs_node
def test_편성이_바뀐_칸은_종전대로_청소_구간을_보고_짠다(tmp_path):
    """기록과 다른 컷이 나오는 칸(음성이 길어짐)은 청소 당시 컷을 억지로 쓰지 않는다 — 컷 길이 합이 새 음성 길이."""
    data = json.loads(FIX.read_text(encoding="utf-8"))
    data["tts_dur"]["5"] = float(data["tts_dur"]["5"]) + 1.0
    cuts = _run(data, tmp_path)[5]
    assert abs(sum(c["d"] for c in cuts) - data["tts_dur"]["5"]) < 0.05, cuts


def _plan_and_base(tmp_path, cb):
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 4.9, "phrase_sync": False,
                       "primary": {"video_id": "s4", "seg_id": "a", "start": 17.0, "end": 18.1},
                       "scene_override": [{"video_id": "s4", "seg_id": "a", "start": 17.0, "end": 18.1},
                                          {"video_id": "s5", "seg_id": "b", "start": 17.7, "end": 20.967},
                                          {"video_id": "s1", "seg_id": "c", "start": 18.267, "end": 21.867}],
                       # 지금 컷 계산이 내놓은 컷 — 청소 당시(0.87/2.53/1.49)와 달라져 s1 컷이 지운 끝을 0.41초 넘는다
                       "manual_cuts": [{"video_id": "s4", "seg_id": "a", "start": 17.0, "dur": 0.87},
                                       {"video_id": "s5", "seg_id": "b", "start": 17.7, "dur": 2.13},
                                       {"video_id": "s1", "seg_id": "c", "start": 18.267, "dur": 1.9}]}]}
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = cb.save_base(tmp_path, sig="x", path=str(tmp_path / "final_clean_x.mp4"), plan={"beats": []},
                        cuts=[{"video_id": "s4", "beat_idx": 0, "src": 17.0, "fin": 0.0, "dur": 0.87, "sdur": 0.87},
                              {"video_id": "s5", "beat_idx": 0, "src": 17.7, "fin": 0.87, "dur": 2.53, "sdur": 2.53},
                              {"video_id": "s1", "beat_idx": 0, "src": 18.267, "fin": 3.4, "dur": 1.5, "sdur": 1.49}])
    return plan, base


def test_안전망_편성이_그대로면_청소_당시_컷으로_재생(tmp_path, capsys):
    from shopping_shorts import clean_base as cb
    plan, base = _plan_and_base(tmp_path, cb)
    (tmp_path / "final_clean_x.plan.json").write_text(json.dumps(plan), encoding="utf-8")     # 정본을 만들 때의 편성 = 지금 편성
    plan2, unc, _ = cb.remap_plan(plan, base, tts_durs={0: 4.9}, src_durs={"s4": 24.6, "s5": 30.9, "s1": 24.4})
    assert unc == [] and plan2["_clean_need"] == {}                    # 원본도, 다시 지우기(과금)도 없다
    b = plan2["beats"][0]
    assert b["clean_frozen"] is True
    assert [(c["video_id"], c["start"], c["dur"]) for c in b["manual_cuts"]] == \
           [("clean", 0.0, 0.87), ("clean", 0.87, 2.53), ("clean", 3.4, 1.5)]
    assert "clean_cut_drift" in capsys.readouterr().err                # 조용히 넘기지 않는다 — 경보 한 줄


def test_안전망_편성이_바뀐_칸은_종전대로_안_덮인_칸(tmp_path):
    from shopping_shorts import clean_base as cb
    plan, base = _plan_and_base(tmp_path, cb)
    snap = copy.deepcopy(plan)
    snap["beats"][0]["target_seconds"] = 4.5                           # 청소 뒤 고객이 이 칸을 바꿨다
    (tmp_path / "final_clean_x.plan.json").write_text(json.dumps(snap), encoding="utf-8")
    plan2, unc, _ = cb.remap_plan(plan, base, tts_durs={0: 4.9}, src_durs={"s4": 24.6, "s5": 30.9, "s1": 24.4})
    assert unc == [0] and "0" in plan2["_clean_need"]
    assert [c["video_id"] for c in plan2["beats"][0]["manual_cuts"]] == ["clean", "clean", "s1"]


def test_청소_당시_컷_기록(tmp_path):
    from shopping_shorts import clean_base as cb
    base = {"cuts": [{"video_id": "s1", "beat_idx": 0, "src": 1.0, "sdur": 2.0, "dur": 2.0},
                     {"video_id": "s2", "beat_idx": 0, "src": 3.0, "sdur": 1.0, "dur": 1.2},
                     {"video_id": "s1", "beat_idx": 1, "src": 1.0, "dur": 2.0}]}          # 읽은 길이 없는 옛 기록 → 그 칸은 뺀다
    assert cb.recorded_cuts(base) == {0: [["s1", 1.0, 2.0], ["s2", 3.0, 1.0]]}
