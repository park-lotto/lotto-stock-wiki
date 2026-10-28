# -*- coding: utf-8 -*-
"""관제 139 감정짤 — 스토리보드 신호어 [1]·[3] 줄 맨 앞에 짤.
(1) storyboard.meme_slots 규칙(1~2초 자르기 · 남은 1초 미만 생략 · [2] 제외 · 감정 · 다른 끼움 장면 보존)
(2) scene_play.js scenesV2Alloc — 짤 컷이 첫 컷, 장면은 짤 뒤로 배분, 장면 하나 1.0초 이상(서버 러너로 실행)
(3) video_assemble.render_cut_plan — 첫 컷이 짤 파일, 렌더 덮어씌우기 대상에서 빠짐"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shopping_shorts import storyboard as sb

HERE = Path(__file__).resolve().parents[1]
RUNNER = HERE / "screen_clips_runner.js"
SCENE_PLAY = HERE / "static" / "scene_play.js"


def _words(*pairs):
    return [{"word": w, "start": s, "end": e} for w, s, e in pairs]


def _beat(idx, rank, signal, narr, **kw):
    b = {"beat_idx": idx, "narration": narr, "sig_rank": rank, "signal": signal}
    b.update(kw)
    return b


POOL = {"놀람": [{"asset_id": 11, "duration": 3.0}, {"asset_id": 12, "duration": 3.0}],
        "의심_황당": [{"asset_id": 21, "duration": 3.0}],
        "충격_입막": [{"asset_id": 31, "duration": 3.0}]}


def _run_slots(beats, words, dur):
    plan = {"beats": beats}
    res = sb.meme_slots(plan, lambda b: (words[b["beat_idx"]], dur[b["beat_idx"]]), POOL)
    return plan, {r["beat_idx"]: r for r in res}


def test_짤_길이는_신호어_끝_1초에서_2초로_자른다():
    beats = [_beat(0, 1, "이게 미친", "이게 미친 포인트인게 있어요"),
             _beat(1, 1, "와 진짜 이건 대박", "와 진짜 이건 대박 이에요"),
             _beat(2, 3, "헐", "헐 이걸 몰랐다니")]
    words = {0: _words(("이게", 0.04, 0.14), ("미친", 0.19, 0.41), ("포인트인게", 0.46, 0.88)),
             1: _words(("와", 0.0, 0.3), ("진짜", 0.4, 0.9), ("이건", 1.0, 1.6), ("대박", 1.7, 2.6), ("이에요", 2.7, 3.0)),
             2: _words(("헐", 0.1, 1.3), ("이걸", 1.4, 1.8))}
    plan, r = _run_slots(beats, words, {0: 4.0, 1: 5.0, 2: 4.0})
    assert r[0]["head_sec"] == 1.0                    # 0.41 → 하한 1.0
    assert r[1]["head_sec"] == 2.0                    # 2.6 → 상한 2.0
    assert r[2]["head_sec"] == 1.3                    # 그대로
    cw = plan["beats"][0]["cutaway"]
    assert cw["match_type"] == "meme" and cw["vid"] == "meme_%d" % cw["asset_id"] and cw["scene_min"] == 1.0


def test_감정은_자리와_낱말로():
    beats = [_beat(0, 1, "말도 안 돼", "말도 안 돼 이게 된다고"), _beat(1, 1, "와", "와 이거"), _beat(2, 3, "헐", "헐 대박")]
    words = {k: _words(("말도", 0, .3), ("안", .3, .5), ("돼", .5, 1.2), ("이게", 1.3, 1.5)) if k == 0 else
             _words(("와" if k == 1 else "헐", 0, 1.1), ("x", 1.2, 1.4)) for k in range(3)}
    _, r = _run_slots(beats, words, {0: 4, 1: 4, 2: 4})
    assert (r[0]["emotion"], r[1]["emotion"], r[2]["emotion"]) == ("의심_황당", "놀람", "충격_입막")


def test_남은_시간_1초_미만이면_짤_없음():
    beats = [_beat(0, 1, "와", "와 이거")]
    _, r = _run_slots(beats, {0: _words(("와", 0, 1.5), ("이거", 1.6, 2.0))}, {0: 2.4})
    assert r[0]["meme"] is False and "남은 시간" in r[0]["why"]


def test_자리_2와_신호어_없는_줄은_빼고_다른_끼움장면은_그대로():
    ai = {"asset_id": 99, "match_type": "manual"}
    beats = [_beat(0, 2, "와", "와 이거"), {"beat_idx": 1, "narration": "그냥 줄"},
             _beat(2, 1, "와", "와 이거", cutaway=dict(ai))]
    plan, r = _run_slots(beats, {k: _words(("와", 0, 1.1), ("이거", 1.2, 1.5)) for k in range(3)}, {0: 4, 1: 4, 2: 4})
    assert "cutaway" not in plan["beats"][0] and r[0]["meme"] is False
    assert 1 not in r
    assert plan["beats"][2]["cutaway"] == ai and r[2]["meme"] is False


def test_신호어가_줄에_없거나_짤이_없으면_이유와_함께_빠진다():
    beats = [_beat(0, 1, "와", "근데 이거"), _beat(1, 3, "헐", "헐 대박")]
    plan = {"beats": beats}
    res = {x["beat_idx"]: x for x in sb.meme_slots(plan, lambda b: (_words(("근데" if b["beat_idx"] == 0 else "헐", 0, 1.2)), 4.0),
                                                     {})}
    assert res[0]["meme"] is False and "신호어" in res[0]["why"]
    assert res[1]["meme"] is False and "짤 없음" in res[1]["why"]


# ── (2) 화면 배분(scene_play.js) ──────────────────────────────────────────────────
def _data(segs, dur, cutaway=None, caps=None):
    ids = list(segs)
    b = {"beat_idx": 0, "narration": "가",
         "primary": {"video_id": "s0", "seg_id": ids[0], "start": segs[ids[0]][0], "end": segs[ids[0]][1]},
         "alternates": [{"video_id": "s0", "seg_id": k, "start": segs[k][0], "end": segs[k][1]} for k in ids[1:]]}
    if cutaway:
        b["cutaway"] = cutaway
    return {"beats": [b], "segments": {k: {"video_id": "s0", "start": v[0], "end": v[1]} for k, v in segs.items()},
            "tts_dur": {"0": dur}, "src_duration": {"s0": 60.0}, "max_slowmo": 1.2, "cut_rule": "scenes_v2",
            "captions": {"0": caps or [{"text": "가", "start": 0.0, "end": dur}]}}


def _js(data, tmp_path):
    if shutil.which("node") is None:
        pytest.skip("node 없음")
    p = tmp_path / "d.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    r = subprocess.run(["node", str(RUNNER), str(SCENE_PLAY), str(p)], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(r.stdout)[0]["c"]


MEME = {"asset_id": 11, "match_type": "meme", "head_sec": 1.4, "vid": "meme_11", "scene_min": 1.0, "emotion": "놀람"}


def test_짤이_첫_컷이고_장면은_짤_뒤로_1초_이상(tmp_path):
    segs = {"a": (10.0, 13.0), "b": (20.0, 23.0), "c": (30.0, 33.0)}
    c = _js(_data(segs, 3.6, dict(MEME)), tmp_path)
    assert c[0]["v"] == "meme_11" and c[0]["s"] == 0 and abs(c[0]["d"] - 1.4) < 0.011 and abs(c[0]["sd"] - 1.4) < 0.011
    rest = c[1:]
    assert len(rest) == 2                                     # 남은 2.2초 → floor(2.2/1.0)=2 장면(3개 중 하나 뺌)
    assert all(x["d"] >= 1.0 - 1e-6 for x in rest)
    assert abs(sum(x["d"] for x in c) - 3.6) < 0.03


def test_짤_없는_칸은_종전_그대로(tmp_path):
    segs = {"a": (10.0, 13.0), "b": (20.0, 23.0), "c": (30.0, 33.0)}
    c0 = _js(_data(segs, 3.6), tmp_path)
    old = dict(MEME); old.pop("head_sec"); old["match_type"] = "manual"   # 옛 끼움 장면(덮어씌우기)
    c1 = _js(_data(segs, 3.6, old), tmp_path)
    assert c0 == c1 and len(c0) == 3 and all(x["v"] == "s0" for x in c0)


def test_남은_시간이_모자라면_화면도_짤을_뺀다(tmp_path):
    c = _js(_data({"a": (10.0, 13.0)}, 2.0, dict(MEME)), tmp_path)      # 2.0−1.4=0.6 < 1.0
    assert all(x["v"] == "s0" for x in c)


# ── (3) 완성본 컷 계획 ──────────────────────────────────────────────────────────
def test_render_cut_plan_첫_컷이_짤(monkeypatch):
    from shopping_shorts import screen_clips, video_assemble as va
    beat = {"beat_idx": 0, "narration": "와 이거", "cutaway": dict(MEME),
            "primary": {"video_id": "s0", "seg_id": "a", "start": 10.0, "end": 13.0}, "alternates": []}
    cuts = {"t": 3.0, "c": [{"v": "meme_11", "s": 0, "d": 1.4, "sd": 1.4, "fit": 0},
                            {"v": "s0", "s": 10.0, "d": 1.6, "sd": 1.6, "fit": 0}]}
    monkeypatch.setattr(screen_clips, "_CACHE", {screen_clips.beat_key(beat): cuts})
    monkeypatch.setenv("SCREEN_CLIPS", "1")
    plan = {"beats": [beat]}
    srcs = {"s0": "s0.mp4", **va.meme_sources(plan, {0: "meme11.mp4"})}
    assert srcs["meme_11"] == "meme11.mp4"
    out = va.render_cut_plan(plan, {0: "t.mp3"}, srcs, beat_durs={0: 3.0},
                             src_durs={"s0": 60.0, "meme_11": 3.0})
    clips = out[0]["clips"]
    assert clips[0]["video_id"] == "meme_11" and clips[0]["f_start"] == 0 and clips[0]["cfr"] == 42
    assert clips[1]["video_id"] == "s0"
    assert va.overlay_cutaway_path(beat, {0: "meme11.mp4"}) is None                 # 덮어씌우기 안 함
    assert va.overlay_cutaway_path({"beat_idx": 0, "cutaway": {"asset_id": 5}}, {0: "ai.mp4"}) == "ai.mp4"


def test_편성_지문에_head_sec가_들어간다():
    from shopping_shorts import mix_pipeline as mp
    b1 = {"beat_idx": 0, "narration": "가", "cutaway": dict(MEME)}
    b2 = {"beat_idx": 0, "narration": "가", "cutaway": dict(MEME, head_sec=1.6)}
    assert mp.plan_signature({"beats": [b1]}) != mp.plan_signature({"beats": [b2]})


def test_스토리보드_줄의_신호어_자리가_칸까지_실린다():
    from shopping_shorts.story_writer import storyboard_to_beat_sources
    r = storyboard_to_beat_sources([{"slot": "hook", "line": "와 이거", "ids": ["v-1"], "sig_rank": 1, "signal": "와"},
                                    {"slot": "x", "line": "그냥", "ids": []}])
    assert r["beat_sources"][0]["sig_rank"] == 1 and r["beat_sources"][0]["signal"] == "와"
    assert "sig_rank" not in r["beat_sources"][1]


def test_작업마다_다른_짤_같은작업은_같은짤():
    """10-06: 늘 목록 맨 앞이라 모든 영상에 같은 짤 — 작업 key 로 고르게."""
    from shopping_shorts import storyboard as sb
    pool = {"놀람": [{"asset_id": i, "duration": 2.0} for i in range(1, 51)]}

    def pick(key):
        plan = {"beats": [{"beat_idx": 0, "narration": "훅"},
                          {"beat_idx": 1, "narration": "이게 미친 포인트인게 정말 좋아요 아주 길게 말해요", "pinned": True,
                           "sig_rank": 1, "signal": "이게 미친 포인트인게"}]}
        words = [{"word": "이게", "start": 0.0, "end": 0.2}, {"word": "미친", "start": 0.2, "end": 0.5},
                 {"word": "포인트인게", "start": 0.5, "end": 1.3}, {"word": "정말", "start": 1.4, "end": 1.6}]
        sb.meme_slots(plan, lambda b: (words, 5.0), pool, key=key)
        return (plan["beats"][1].get("cutaway") or {}).get("asset_id")
    assert pick("job-a") == pick("job-a")
    assert len({pick("job-%d" % i) for i in range(20)}) >= 8
