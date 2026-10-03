# -*- coding: utf-8 -*-
"""관제 110 — 자막제거(청소) 뒤에도 **같은 편성이면 화면 컷이 그대로**여야 한다.

사고(2026-10-04 황선희님 c9fbcc3ac28c 7번 칸): 청소 전 화면 컷 s5 2.53초·s1 1.49초로 조립해 지웠는데, 청소가 끝나
DATA.clean_spans(지운 원본 구간)가 생기자 같은 편성의 화면 컷이 s5 2.13초·s1 1.90초로 바뀌었다 → s1 19.76~20.17초(0.41초)가
'안 지운 구간'이 돼 칸 전체(4.9초)가 원본으로 떨어지고 장면꾸미기에 원본 자막이 보였다.
검사: 청소 전 컷으로 clean_spans 를 만들고(그 컷이 읽은 구간 = 지운 구간) 다시 계산 → 컷이 같고, 읽는 창이 지운 구간 안.
"""
import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "screen_clips_runner.js"
SCENE_PLAY = HERE / "static" / "scene_play.js"


def _run(data, tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    r = subprocess.run(["node", str(RUNNER), str(SCENE_PLAY), str(p)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    return [b["c"] for b in json.loads(r.stdout)]


def _beat7(caps_starts, dur=4.896):
    """c9fbcc3ac28c 7번 칸과 같은 꼴: 서로 다른 영상의 장면 셋, 구절 경계에 전환을 맞춘다."""
    segs = {"a": ("s4", 17.0, 18.1), "b": ("s5", 17.7, 20.967), "c": ("s1", 18.267, 21.867)}
    ids = list(segs)
    mat = lambda k: {"video_id": segs[k][0], "seg_id": k, "start": segs[k][1], "end": segs[k][2]}   # noqa: E731
    ends = caps_starts[1:] + [dur]
    return {"beats": [{"beat_idx": 0, "narration": "가", "primary": mat(ids[0]), "alternates": [mat(k) for k in ids[1:]]}],
            "segments": {k: {"video_id": v[0], "start": v[1], "end": v[2]} for k, v in segs.items()},
            "tts_dur": {"0": dur}, "src_duration": {"s4": 24.59, "s5": 30.9, "s1": 24.4}, "max_slowmo": 1.2,
            "cut_rule": "scenes_v2",
            "captions": {"0": [{"text": "x", "start": a, "end": b} for a, b in zip(caps_starts, ends)]}}


def _spans_of(cuts):
    by = {}
    for c in cuts:
        by.setdefault(c["v"], []).append([round(c["s"], 3), round(c["s"] + c["sd"], 3)])
    return by


@pytest.mark.parametrize("caps", [[0.0, 0.87, 2.2, 3.4], [0.0, 0.87, 3.4], [0.0, 1.3, 2.9], [0.0, 2.4]])
def test_같은_편성이면_청소_뒤에도_컷이_그대로(tmp_path, caps):
    before = _run(_beat7(caps), tmp_path)[0]
    d2 = copy.deepcopy(_beat7(caps))
    d2["clean_spans"] = _spans_of(before)            # 청소본 = 이 컷들이 읽은 구간을 지운 것
    after = _run(d2, tmp_path)[0]
    assert [(c["v"], round(c["s"], 2), round(c["d"], 2)) for c in after] == \
           [(c["v"], round(c["s"], 2), round(c["d"], 2)) for c in before], (before, after)
    for c in after:                                  # 읽는 창이 지운 구간 안 — 밖이면 원본 자막·증분 청소(과금)
        assert any(a - 0.02 <= c["s"] and c["s"] + c["sd"] <= b + 0.02 for a, b in d2["clean_spans"][c["v"]]), (c, d2["clean_spans"])


def test_컷_하나만_못_덮으면_그_컷만_원본이고_나머지는_청소본(tmp_path):
    """c9fbcc3ac28c 7번 칸: s4·s5 컷은 지운 구간 안, s1 컷만 끝 0.41초가 밖 → 종전엔 칸 전체가 원본으로 나갔다."""
    from shopping_shorts import clean_base as cb
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 4.9, "phrase_sync": False,
                       "primary": {"video_id": "s4", "seg_id": "a", "start": 17.0, "end": 18.1},
                       "scene_override": [{"video_id": "s4", "seg_id": "a", "start": 17.0, "end": 18.1},
                                          {"video_id": "s5", "seg_id": "b", "start": 17.7, "end": 20.967},
                                          {"video_id": "s1", "seg_id": "c", "start": 18.267, "end": 21.867}],
                       "manual_cuts": [{"video_id": "s4", "seg_id": "a", "start": 17.0, "dur": 0.87},
                                       {"video_id": "s5", "seg_id": "b", "start": 17.7, "dur": 2.13},
                                       {"video_id": "s1", "seg_id": "c", "start": 18.267, "dur": 1.9}]}]}
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = cb.save_base(tmp_path, sig="x", path=str(tmp_path / "final_clean_x.mp4"), plan={"beats": []},
                        cuts=[{"video_id": "s4", "beat_idx": 0, "src": 17.0, "fin": 0.0, "dur": 0.87, "sdur": 0.87},
                              {"video_id": "s5", "beat_idx": 0, "src": 17.7, "fin": 0.87, "dur": 2.53, "sdur": 2.53},
                              {"video_id": "s1", "beat_idx": 0, "src": 18.267, "fin": 3.4, "dur": 1.5, "sdur": 1.49}])
    plan2, unc, _ = cb.remap_plan(plan, base, tts_durs={0: 4.9}, src_durs={"s4": 24.6, "s5": 30.9, "s1": 24.4})
    assert unc == [0]                                                   # 판정은 그대로 — 증분 청소(0.41초) 대상
    (m,) = plan2["_clean_need"]["0"]
    assert m["video_id"] == "s1" and abs(m["start"] - 19.757) < 0.01 and abs(m["end"] - 20.167) < 0.02
    vids = [c["video_id"] for c in plan2["beats"][0]["manual_cuts"]]
    assert vids == ["clean", "clean", "s1"], vids                       # 덮인 두 컷은 청소본, 못 덮은 컷만 원본
    assert abs(sum(c["dur"] for c in plan2["beats"][0]["manual_cuts"]) - 4.9) < 0.02


def test_덮인_컷이_하나도_없으면_종전대로_원본_재료(tmp_path):
    from shopping_shorts import clean_base as cb
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 2.0, "phrase_sync": False,
                       "primary": {"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 2.0},
                       "manual_cuts": [{"video_id": "s0", "seg_id": "a", "start": 0.0, "dur": 2.0}]}]}
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = cb.save_base(tmp_path, sig="x", path=str(tmp_path / "final_clean_x.mp4"), plan={"beats": []},
                        cuts=[{"video_id": "s0", "beat_idx": 0, "src": 0.0, "fin": 0.0, "dur": 1.5, "sdur": 1.5}])
    plan2, unc, _ = cb.remap_plan(plan, base, tts_durs={0: 2.0}, src_durs={"s0": 10.0})
    assert unc == [0] and plan2["beats"][0]["manual_cuts"] == plan["beats"][0]["manual_cuts"]
