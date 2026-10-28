"""정본 job 캡컷·ZIP 컷 = 렌더 컷 계획 그대로(자리만 소스별 파일 좌표로) — 2026-09-27 11cfc4a4b75c 관문 실패.

왜: 캡컷·ZIP 은 청소본 조각을 소스별 파일로 옮긴 편성으로 render_cut_plan 을 **다시** 돌려, 소스별 파일 길이로 시작 당기기·
  읽는 길이·정지를 새로 정했다 → 렌더(통짜 청소본)와 7칸 read·freeze / 8칸 start 가 갈렸다(캡컷 2·ZIP 2).
  이제 export_sources_for 가 렌더 컷 계획을 소스별 파일 좌표로 옮겨 plan["_cut_plan"] 에 싣고, 캡컷(capcut_segments)·
  ZIP(_beat_source_clips)은 그걸 옮겨 적기만 한다.
합성 정본: 원본 s0 10.0~12.0초를 청소본 0.0초 자리에 담았는데 실제로는 0.1초 늦게 들어 있다(보정 off=0.1).
  렌더 컷은 청소본 0.6초부터 = 원본 10.5초 → 소스별 파일(조각 off 0) 0.5초.
"""
from shopping_shorts import capcut_draft as cd
from shopping_shorts import clean_base as cb
from shopping_shorts import export_bundle as eb
from shopping_shorts import mix_pipeline as mp


def _base(off=0.1):
    c = {"video_id": "s0", "beat_idx": 0, "src": 10.0, "fin": 0.0, "dur": 2.0, "sdur": 2.0, "cleaned": True}
    if off:
        c["off"] = off
    return {"sig": "x", "path": "/nope.mp4", "cuts": [c], "beat_keys": {}, "extras": {}}


def _layout():
    return {"s0": {"path": "/tmp/capcut_src_s0.mp4",
                   "pieces": [{"rv": "clean", "sid": "clean-0", "cs": 10.0, "ce": 12.0, "fin": 0.1, "k": 1.0,
                               "off": 0.0, "len": 2.0}]}}


def _cut_plan():
    clip = {"video_id": "clean", "seg_id": "clean-0", "start": 0.6, "src_dur": 1.0, "out_dur": 1.0}
    cp = {"j": 0, "clip": clip, "video_id": "clean", "cfr": 30, "nf": 30, "f_start": 0, "c_src": 1.0, "c_out": 1.0,
          "play_out": 0.9, "freeze": 0.1, "start": 0.6, "nf_play": 27, "speed": 1.111, "move_fr": 27, "hold_fr": 3}
    return [{"beat": {"beat_idx": 0}, "idx": 0, "tts": None, "tts_dur": 1.0, "head_trim": 0.0, "runout": 0.0,
             "f0": 0, "nfr": 30, "segs": [], "ofr": 0, "clips": [cp]}]


def test_map_uses_calibrated_coords_and_keeps_render_values():
    regs = cb._regions(_base())
    got = mp._map_cut_plan_to_sources(_cut_plan(), _layout(), regs, set())
    cp = got[0]["clips"][0]
    assert cp["video_id"] == "s0" and abs(cp["start"] - 0.5) < 1e-6, cp          # 원본 10.5초 = 파일 0.5초
    assert abs(cp["clip"]["start"] - 0.5) < 1e-6 and cp["clip"]["video_id"] == "s0"
    for k in ("c_src", "play_out", "freeze", "speed", "move_fr", "hold_fr", "f_start", "cfr"):
        assert cp[k] == _cut_plan()[0]["clips"][0][k], k                          # 읽는 길이·배속·정지·자리는 렌더 그대로


def test_capcut_and_zip_follow_mapped_render_plan(monkeypatch, tmp_path):
    regs = cb._regions(_base())
    plan = {"beats": [{"beat_idx": 0}], "_cut_plan": mp._map_cut_plan_to_sources(_cut_plan(), _layout(), regs, set())}
    segs = cd.capcut_segments(plan, [{"beat_idx": 0, "dur": 1.0}], {"s0": "/tmp/capcut_src_s0.mp4"})
    s = segs[0][0]
    assert abs(s["start"] - 0.5) < 1e-6 and abs(s["read"] - 27 / 30 * 1.111) < 1e-6 and s["hold"], s
    cuts = []
    monkeypatch.setattr(eb, "_cut_clip", lambda src, a, b, out: cuts.append((src, round(a, 4), round(b, 4))) or True)
    eb._beat_source_clips(plan, [{"beat_idx": 0, "dur": 1.0, "role": "hook"}], {"s0": "/tmp/capcut_src_s0.mp4"},
                          tmp_path, src_durs={"s0": 5.0})
    assert cuts == [("/tmp/capcut_src_s0.mp4", 0.5, 1.5)], cuts


def test_uncalibrated_regions_would_be_wrong():
    """보정 전 좌표(off 없음)로 옮기면 0.6초가 나온다 — 캡컷이 보정 좌표를 안 타면 이 1~3프레임이 갈린다(사보타주 기준)."""
    regs0 = cb._regions(_base(off=0))
    got = mp._map_cut_plan_to_sources(_cut_plan(), _layout(), regs0, set())
    assert got is None or abs(got[0]["clips"][0]["start"] - 0.5) > 0.05


def test_raw_source_cuts_renamed():
    plan = [{"beat": {}, "idx": 0, "f0": 0, "nfr": 30, "clips": [
        {"j": 0, "clip": {"video_id": "s1", "start": 2.0}, "video_id": "s1", "start": 2.0}]}]
    got = mp._map_cut_plan_to_sources(plan, {"s1": {"path": "x", "pieces": []}}, [], {"s1"})
    assert got[0]["clips"][0]["video_id"] == "s1_raw" and got[0]["clips"][0]["start"] == 2.0


def test_render_does_not_pull_start_before_piece(monkeypatch):
    """파일 끝에 붙은 조각: 모자란 읽기를 채우려 시작을 **조각 앞(= 앞 컷의 조각)**으로 당기지 않는다 — 조각 시작에서 멈추고 정지.
    (11cfc4a4b75c 8칸: 청소본 20.233초 조각을 파일 끝 22.021초에 맞춰 20.149초로 당겨 앞 조각 0.084초를 읽었다)"""
    from shopping_shorts import video_assemble as va
    clip = {"video_id": "clean", "seg_id": "clean-17", "start": 20.233, "src_dur": 1.872, "out_dur": 1.8667}
    monkeypatch.setattr(va, "plan_beat_clips_for", lambda *a, **k: [dict(clip)])
    monkeypatch.setattr(va, "_trans_sec", lambda: 0.0)
    beat = {"beat_idx": 8, "scene_override": [{"video_id": "clean", "seg_id": "clean-17", "start": 20.233, "end": 22.105}]}
    out = va.render_cut_plan({"beats": [beat]}, {8: "x.mp3"}, {"clean": "/c.mp4"}, beat_durs={8: 1.8667},
                             src_durs={"clean": 22.021})
    cp = out[0]["clips"][0]
    assert abs(cp["start"] - 20.233) < 1e-6, cp["start"]
    assert abs(cp["c_src"] - (22.021 - 20.233)) < 1e-6 and cp["speed"] < 1.0, (cp["c_src"], cp["speed"])   # 모자란 몫 = 느리게(1.15배 안)
    # 조각 정보가 없으면 종전대로 소스 안으로만 당긴다
    beat2 = {"beat_idx": 8, "primary": {"video_id": "other", "seg_id": "o", "start": 0.0, "end": 1.0}}
    out2 = va.render_cut_plan({"beats": [beat2]}, {8: "x.mp3"}, {"clean": "/c.mp4"}, beat_durs={8: 1.8667},
                              src_durs={"clean": 22.021})
    assert abs(out2[0]["clips"][0]["start"] - (22.021 - 1.872)) < 1e-6
