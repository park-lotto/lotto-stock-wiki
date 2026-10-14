# -*- coding: utf-8 -*-
"""관제 203 — 3단계 짤 자리(앞/중간/뒤)·길이 조절.
(1) storyboard.meme_adjust 규칙 (2) scene_play.js scenesV2Alloc 이 자리대로 짤 컷을 둔다 (3) 편성 지문이 자리를 본다"""
from shopping_shorts import storyboard as sb
from shopping_shorts.tests.test_meme_head_139 import MEME, _data, _js   # 같은 러너·데이터 모양


def test_자리와_길이를_바꾸면_manual_로_남는다():
    cw, why = sb.meme_adjust(dict(MEME), 4.0, 3.0, pos="tail", sec=2.5)
    assert why is None and cw["pos"] == "tail" and cw["head_sec"] == 2.5 and cw["manual"] == 1
    back, _ = sb.meme_adjust(cw, 4.0, 3.0, pos="head")
    assert "pos" not in back                                  # 앞 = 종전 모양(표식 없음)


def test_길이_범위와_남은_장면_하한():
    assert sb.meme_adjust(dict(MEME), 4.0, 3.0, sec=0.25)[0] is None      # 0.5초 미만
    assert sb.meme_adjust(dict(MEME), 4.0, 2.0, sec=2.25)[0] is None      # 짤 파일보다 김
    assert sb.meme_adjust(dict(MEME), 3.0, 3.0, sec=2.5)[0] is None       # 뒤 장면 0.5초 < 1.0초
    assert sb.meme_adjust(dict(MEME), 4.0, 3.0, pos="left")[0] is None
    assert sb.meme_adjust({"match_type": "ai"}, 4.0, 3.0, pos="mid")[0] is None


def test_짤_바꿔도_자리는_meme_cut_이_싣는다():
    assert sb.meme_cut({"asset_id": 5}, 1.2, "놀람", manual=True, pos="mid")["pos"] == "mid"
    assert "pos" not in sb.meme_cut({"asset_id": 5}, 1.2, "놀람", pos="head")


SEGS = {"a": (10.0, 13.0), "b": (20.0, 23.0), "c": (30.0, 33.0)}


def test_뒤_짤은_마지막_컷(tmp_path):
    c = _js(_data(SEGS, 3.6, dict(MEME, pos="tail")), tmp_path)
    assert c[-1]["v"] == "meme_11" and c[-1]["s"] == 0 and abs(c[-1]["d"] - 1.4) < 0.011
    assert all(x["v"] == "s0" for x in c[:-1]) and abs(sum(x["d"] for x in c) - 3.6) < 0.03


def test_가운데_짤은_장면_사이(tmp_path):
    c = _js(_data(SEGS, 3.6, dict(MEME, pos="mid")), tmp_path)
    vs = [x["v"] for x in c]
    assert vs == ["s0", "meme_11", "s0"] and abs(sum(x["d"] for x in c) - 3.6) < 0.03


def test_가운데_짤_장면_하나면_둘로_나눠_이어_튼다(tmp_path):
    c = _js(_data({"a": (10.0, 14.0)}, 3.6, dict(MEME, pos="mid")), tmp_path)
    assert [x["v"] for x in c] == ["s0", "meme_11", "s0"]
    assert c[2]["s"] > c[0]["s"] + 0.5                        # 뒤 조각은 앞 조각에 이어서(같은 화면 반복 아님)
    assert abs(sum(x["d"] for x in c) - 3.6) < 0.03


def test_앞_짤은_종전과_같다(tmp_path):
    assert _js(_data(SEGS, 3.6, dict(MEME)), tmp_path) == _js(_data(SEGS, 3.6, dict(MEME, pos="head")), tmp_path)


def test_편성_지문이_자리를_본다():
    from shopping_shorts import mix_pipeline as mp
    b1 = {"beat_idx": 0, "narration": "가", "cutaway": dict(MEME)}
    b2 = {"beat_idx": 0, "narration": "가", "cutaway": dict(MEME, pos="tail")}
    assert mp.plan_signature({"beats": [b1]}) != mp.plan_signature({"beats": [b2]})


def test_render_cut_plan_뒤_짤이_마지막_컷(monkeypatch):
    from shopping_shorts import screen_clips, video_assemble as va
    beat = {"beat_idx": 0, "narration": "와 이거", "cutaway": dict(MEME, pos="tail"),
            "primary": {"video_id": "s0", "seg_id": "a", "start": 10.0, "end": 13.0}, "alternates": []}
    cuts = {"t": 3.0, "c": [{"v": "s0", "s": 10.0, "d": 1.6, "sd": 1.6, "fit": 0},
                            {"v": "meme_11", "s": 0, "d": 1.4, "sd": 1.4, "fit": 0}]}
    monkeypatch.setattr(screen_clips, "_CACHE", {screen_clips.beat_key(beat): cuts})
    monkeypatch.setenv("SCREEN_CLIPS", "1")
    plan = {"beats": [beat]}
    srcs = {"s0": "s0.mp4", **va.meme_sources(plan, {0: "meme11.mp4"})}
    out = va.render_cut_plan(plan, {0: "t.mp3"}, srcs, beat_durs={0: 3.0}, src_durs={"s0": 60.0, "meme_11": 3.0})
    clips = out[0]["clips"]
    assert [c["video_id"] for c in clips] == ["s0", "meme_11"] and clips[1]["cfr"] == 42
    assert va.overlay_cutaway_path(beat, {0: "meme11.mp4"}) is None
