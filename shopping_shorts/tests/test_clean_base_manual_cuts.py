# -*- coding: utf-8 -*-
"""청소본 정본은 손으로 정한 컷(manual_cuts)을 그대로 옮겨야 한다 (2026-09-26 강규봉님 job 7bbb1329aff0).

실사고: 장면편집으로 컷을 고친 뒤 '완성본 만들기'가 미리보기와 다른 장면을 냈다. 청소본 계열
(_beat_materials → coverage·remap_plan·증분 청소)이 manual_cuts를 모르고 scene_override만 봐서,
청소본을 만들던 때(15:06)의 **옛 컷 배치**로 조립했다. 10칸 중 1·5·7·8번이 달랐다.
  1번: 고객 컷 s2 2.533부터 5.17초 한 컷 → 완성본은 옛 두 컷(2.54+2.62초, 뒤 컷은 s2 8.967 = 딴 장면)
"""
import json
from pathlib import Path

import pytest

from shopping_shorts import clean_base as cb
from shopping_shorts import video_assemble as va

DATA = Path(__file__).parent / "fixtures" / "clean_base_job7bbb_manual.json"


@pytest.fixture
def job7bbb(tmp_path):
    d = json.loads(DATA.read_text(encoding="utf-8"))
    base = d["base"]
    # 손 컷 규칙을 시험한다 — 실데이터는 10칸 모두 컷 리듬 칸이라(화면이 손 컷을 안 씀) 표식을 뗀 사본을 쓴다.
    #   컷 리듬 칸 규칙은 test_rhythm_beats_ignore_manual_cuts_like_editor 가 원본 그대로 시험한다.
    for bb in d["edit_plan"]["beats"]:
        bb.pop("cut_rhythm", None)
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base["path"] = str(tmp_path / "final_clean_x.mp4")
    (tmp_path / cb.BASE_FILE).write_text(json.dumps(base), encoding="utf-8")
    return d["edit_plan"], cb.load_base(tmp_path)


def _src_of(base, piece):
    """청소본 조각 → 원본 (video_id, 시작, 끝)."""
    c = base["cuts"][int(piece["seg_id"].rsplit("-", 1)[1])]
    cs, _ce, fin, k = cb._cut_geom(c)
    return c["video_id"], cs + (piece["start"] - fin) / k, cs + (piece["end"] - fin) / k


def test_manual_cut_outside_clean_is_changed_not_old_layout(job7bbb):
    """고객 컷이 청소본에 없는 구간을 품은 칸은 '바뀐 장면'이다 — 옛 컷으로 조용히 채우면 안 된다.
    1번(s2 5.07~7.70 미청소)·3번(s1 6.08~7.17)·6번(s1 15.10~16.33). 종전 코드는 전부 covered로 보고 옛 컷을 썼다.
    4번(s0 3.72~6.99)은 4번 옛 컷(2.37~5.64)+2번 컷(4.9~7.3)이 이어 덮으므로 covered가 맞다.
    2번(화면 = 재료 film_s0 9.03초~)·7번(화면 = s2 13.09초 한 컷 3.48초, 청소본엔 2.04초까지)도 화면 기준 미청소."""
    plan, base = job7bbb
    cov = cb.coverage(plan, base)
    assert sorted(k for k, v in cov.items() if v != "covered") == [1, 2, 3, 6, 7], cov
    _plan2, uncovered, _ = cb.remap_plan(plan, base)
    assert uncovered == [1, 2, 3, 6, 7]


def test_covered_manual_beats_replay_exact_customer_cuts(job7bbb):
    """덮이는 칸(0·4·5·8)은 청소본 조각이 **고객 컷의 원본 구간 그대로**여야 한다(순서·길이까지)."""
    plan, base = job7bbb
    plan2, _unc, _ = cb.remap_plan(plan, base)
    orig = {b["beat_idx"]: b for b in plan["beats"]}
    for b in plan2["beats"]:
        bi = b["beat_idx"]
        if bi not in (0, 4, 5, 8):
            continue
        want = va.synced_manual_cuts(orig[bi], None)         # 화면과 같은 정리(syncCuts) 기준
        got = b["manual_cuts"]
        assert all(c["video_id"] == "clean" for c in got), bi
        assert abs(sum(c["dur"] for c in got) - sum(c["dur"] for c in want)) < 0.15, bi
        # 조각을 원본으로 되돌리면 고객 컷 구간이 순서대로 이어진다
        spans = [_src_of(base, {"seg_id": c["seg_id"], "start": c["start"], "end": c["start"] + c["sdur"]}) for c in got]
        cursor = 0
        for w in want:
            ws, we = float(w["start"]), float(w["start"]) + float(w["dur"])
            pos = ws
            while (cursor < len(spans) and we - pos >= 0.13 and spans[cursor][0] == w["video_id"]
                   and abs(spans[cursor][1] - pos) < 0.13):
                pos = spans[cursor][2]
                cursor += 1
            assert we - pos < 0.13, (bi, w, spans)
        assert cursor == len(spans), (bi, spans)


def test_render_plan_uses_remapped_cuts(job7bbb):
    """렌더 계획(plan_beat_clips_for)이 옮긴 컷을 그대로 쓴다 — 5번 칸: 고객 한 컷 3.87초."""
    plan, base = job7bbb
    plan2, _unc, _ = cb.remap_plan(plan, base)
    b5 = next(b for b in plan2["beats"] if b["beat_idx"] == 5)
    clips = va.plan_beat_clips_for(b5, 3.86, {"clean": 36.0})
    assert [c["video_id"] for c in clips] == ["clean"] * len(clips)
    assert abs(sum(c["out_dur"] for c in clips) - 3.86) < 0.02
    # 첫 조각은 청소본의 s0 13.267 자리(fin 19.908)에서 시작 — 옛 배치와 같지만 길이는 고객 컷 기준
    assert abs(clips[0]["start"] - 19.908) < 0.01


def test_slowed_clean_cut_does_not_cover_unread_source(tmp_path):
    """느리게 구운 컷(dur 4초·원본 2초)은 원본 2초까지만 지운 것이다 — 뒤 2초를 덮었다고 보면 안 된다."""
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 4.0, "phrase_sync": False,
                       "primary": {"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 4.0},
                       "manual_cuts": [{"video_id": "s0", "seg_id": "a", "start": 0.0, "dur": 4.0}]}]}
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = cb.save_base(tmp_path, sig="x", path=str(tmp_path / "final_clean_x.mp4"), plan={"beats": []},
                        cuts=[{"video_id": "s0", "beat_idx": 0, "src": 0.0, "fin": 0.0, "dur": 4.0, "sdur": 2.0}])
    assert cb.coverage(plan, base) == {0: "new"}


def test_multi_piece_extras_all_used(tmp_path):
    """증분 청소한 조각이 둘이면 둘 다 쓴다 — 예전엔 첫 조각만 써서 돈 내고 지운 장면이 빠졌다."""
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 4.0,
                       "scene_override": [{"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 2.0},
                                          {"video_id": "s1", "seg_id": "b", "start": 5.0, "end": 7.0}]}]}
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = cb.save_base(tmp_path, sig="x", path=str(tmp_path / "final_clean_x.mp4"), plan={"beats": []}, cuts=[])
    key = cb.beat_material_key(plan["beats"][0])
    for k in (0, 1):
        p = tmp_path / ("cb0_%d.mp4" % k)
        p.write_bytes(b"x" * 10)
        base = cb.add_extra(tmp_path, base, vid="cb0_%d" % k, path=str(p), beat_idx=0, material_key=key, seconds=2.0)
    assert cb.coverage(plan, base) == {0: "covered"}
    plan2, unc, _ = cb.remap_plan(plan, base)
    assert unc == []
    assert [m["video_id"] for m in plan2["beats"][0]["scene_override"]] == ["cb0_0", "cb0_1"]


# ── 렌더 컷 재생(remap_plan(src_durs=…)) ─────────────────────────────────────────────


def _flat(clips, base=None):
    """컷 계획 → 원본 좌표 [(영상, 시작, 읽는 길이)], 원본에서 이어지는 조각은 합친다."""
    out = []
    for c in clips:
        if base is not None and c["video_id"] == "clean":
            cut = next(x for x in base["cuts"]
                       if float(x["fin"]) - 1e-3 <= c["start"] < float(x["fin"]) + float(x["dur"]) - 1e-3)
            cs, _ce, fin, k = cb._cut_geom(cut)
            v, s, l = cut["video_id"], cs + (c["start"] - fin) / k, float(c.get("src_dur") or c["out_dur"]) / k
        else:
            v, s, l = c["video_id"], float(c["start"]), float(c.get("src_dur") or c["out_dur"])
        if out and out[-1][0] == v and abs(out[-1][1] + out[-1][2] - s) < 0.15:
            out[-1] = (v, out[-1][1], s + l - out[-1][1])
        else:
            out.append((v, s, l))
    return out


def test_replay_reproduces_editor_cuts_for_every_covered_beat(job7bbb):
    """청소본 조립 = 편집 화면(원본 조립)과 같은 컷 — 칸마다 원본으로 되돌려 대조한다(실데이터)."""
    plan, base = job7bbb
    d = json.loads(DATA.read_text(encoding="utf-8"))
    tts = {int(k): v for k, v in d["tts_durs"].items()}
    plan2, unc, _ = cb.remap_plan(plan, base, tts_durs=tts, src_durs=d["src_durs"])
    assert unc == [1, 2, 3, 6, 7]
    assert set(plan2["_clean_need"]) == {"1", "2", "3", "6", "7"}
    orig = {b["beat_idx"]: b for b in plan["beats"]}
    checked = 0
    for b in plan2["beats"]:
        bi = b["beat_idx"]
        if bi in unc:
            continue
        want = _flat(va.plan_beat_clips_for(orig[bi], tts[bi], d["src_durs"]))
        got = _flat(va.plan_beat_clips_for(b, tts[bi], {"clean": 36.0}), base)
        assert len(want) == len(got), (bi, want, got)
        for (wv, ws, wl), (gv, gs, gl) in zip(want, got):
            assert wv == gv and abs(ws - gs) < 0.15 and abs(wl - gl) < 0.2, (bi, want, got)
        checked += 1
    assert checked == 5          # 0·4·5·8·9


def test_replay_uses_located_extras_after_incremental(job7bbb, tmp_path):
    """증분 청소가 원본 위치를 남기면 다음 재배치가 그 조각으로 덮는다(1번 칸 → covered, 재과금 0)."""
    plan, base = job7bbb
    d = json.loads(DATA.read_text(encoding="utf-8"))
    tts = {int(k): v for k, v in d["tts_durs"].items()}
    p = tmp_path / "cb1_0.mp4"
    p.write_bytes(b"x" * 10)
    base = cb.add_extra(tmp_path, base, vid="cb1_0", path=str(p), beat_idx=1,
                        material_key=cb.beat_material_key(plan["beats"][1]), seconds=5.37,
                        src_vid="s2", src_start=2.533)
    plan2, unc, _ = cb.remap_plan(plan, base, tts_durs=tts, src_durs=d["src_durs"])
    assert 1 not in unc
    b1 = next(b for b in plan2["beats"] if b["beat_idx"] == 1)
    assert [c["video_id"] for c in b1["manual_cuts"]] == ["cb1_0"]


def test_tail_gap_is_slowed_not_recharged(tmp_path):
    """컷 끝 0.2초만 안 지워졌으면(2초 컷의 10%) 재청소 대신 지운 1.8초를 2초에 느리게 담는다."""
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 2.0, "phrase_sync": False,
                       "primary": {"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 2.0},
                       "manual_cuts": [{"video_id": "s0", "seg_id": "a", "start": 0.0, "dur": 2.0}]}]}
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = cb.save_base(tmp_path, sig="x", path=str(tmp_path / "final_clean_x.mp4"), plan={"beats": []},
                        cuts=[{"video_id": "s0", "beat_idx": 0, "src": 0.0, "fin": 0.0, "dur": 1.8, "sdur": 1.8}])
    plan2, unc, _ = cb.remap_plan(plan, base, tts_durs={0: 2.0}, src_durs={"s0": 10.0})
    assert unc == []
    (c,) = plan2["beats"][0]["manual_cuts"]
    assert c["video_id"] == "clean" and abs(c["dur"] - 2.0) < 1e-3 and abs(c["sdur"] - 1.8) < 1e-3 and c["pspeed"]
    clips = va.plan_beat_clips_for(plan2["beats"][0], 2.0, {"clean": 1.8})
    assert abs(clips[0]["playback_speed"] - 0.9) < 1e-3 and abs(clips[0]["out_dur"] - 2.0) < 1e-3


def test_big_tail_gap_still_recleans(tmp_path):
    """0.5초 모자람(25%)은 느리게 메우면 티가 난다 → 재청소 대상."""
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 2.0, "phrase_sync": False,
                       "primary": {"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 2.0},
                       "manual_cuts": [{"video_id": "s0", "seg_id": "a", "start": 0.0, "dur": 2.0}]}]}
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = cb.save_base(tmp_path, sig="x", path=str(tmp_path / "final_clean_x.mp4"), plan={"beats": []},
                        cuts=[{"video_id": "s0", "beat_idx": 0, "src": 0.0, "fin": 0.0, "dur": 1.5, "sdur": 1.5}])
    plan2, unc, _ = cb.remap_plan(plan, base, tts_durs={0: 2.0}, src_durs={"s0": 10.0})
    assert unc == [0] and plan2["_clean_need"]["0"][0]["end"] == 2.0


def test_reclean_only_uncleaned_gap(job7bbb):
    """1번 칸 고객 컷 s2 2.533~7.703 중 청소본에 있는 건 2.533~5.073 — 다시 지울 건 **5.073~7.703만**(컷 전체 아님)."""
    plan, base = job7bbb
    d = json.loads(DATA.read_text(encoding="utf-8"))
    tts = {int(k): v for k, v in d["tts_durs"].items()}
    plan2, _unc, _ = cb.remap_plan(plan, base, tts_durs=tts, src_durs=d["src_durs"])
    (m,) = plan2["_clean_need"]["1"]
    assert m["video_id"] == "s2" and abs(m["start"] - 5.073) < 0.01 and abs(m["end"] - 7.703) < 0.02


def test_gap_extra_stitches_with_clean_pieces(job7bbb, tmp_path):
    """빈 부분만 지운 조각(src 5.073~)을 붙이면 청소본 조각 + 새 조각이 이어져 1번 칸이 덮인다."""
    plan, base = job7bbb
    d = json.loads(DATA.read_text(encoding="utf-8"))
    tts = {int(k): v for k, v in d["tts_durs"].items()}
    p = tmp_path / "cb1_0.mp4"
    p.write_bytes(b"x" * 10)
    base = cb.add_extra(tmp_path, base, vid="cb1_0", path=str(p), beat_idx=1,
                        material_key=cb.beat_material_key(plan["beats"][1]), seconds=2.83,
                        src_vid="s2", src_start=5.073)
    plan2, unc, _ = cb.remap_plan(plan, base, tts_durs=tts, src_durs=d["src_durs"])
    assert 1 not in unc
    b1 = next(b for b in plan2["beats"] if b["beat_idx"] == 1)
    assert [c["video_id"] for c in b1["manual_cuts"]] == ["clean", "cb1_0"]
    assert abs(sum(c["dur"] for c in b1["manual_cuts"]) - 5.17) < 0.02


def test_partial_base_skip_beat_is_not_recleaned(job7bbb):
    """장면 골라 지우기 정본: 안 고른 칸(skip_beats)·안 지운 컷(cleaned False)은 청소 대상이 아니고 조각으로도 안 쓴다."""
    plan, base = job7bbb
    d = json.loads(DATA.read_text(encoding="utf-8"))
    tts = {int(k): v for k, v in d["tts_durs"].items()}
    base = dict(base, partial=True, skip_beats=[1, 3, 6])
    base["cuts"] = [dict(c, cleaned=(c["beat_idx"] not in (1, 3, 6))) for c in base["cuts"]]
    plan2, unc, _ = cb.remap_plan(plan, base, tts_durs=tts, src_durs=d["src_durs"])
    assert not ({1, 3, 6} & set(unc)) and not ({"1", "3", "6"} & set(plan2["_clean_need"]))
    orig = {b["beat_idx"]: b for b in plan["beats"]}
    for bi in (1, 3, 6):
        b = next(x for x in plan2["beats"] if x["beat_idx"] == bi)
        assert b.get("manual_cuts") == orig[bi].get("manual_cuts")      # 원본 그대로
    # 안 지운 컷(1번 칸 옛 컷 s2 2.533~)을 8번 칸이 빌려 쓰지 않는다
    for b in plan2["beats"]:
        for c in b.get("manual_cuts") or []:
            if c["video_id"] == "clean":
                assert base["cuts"][int(c["seg_id"].rsplit("-", 1)[1])]["cleaned"] is not False


def test_rhythm_beats_ignore_manual_cuts_like_editor():
    """컷 리듬 칸은 화면(planClips rhythmOne)이 손 컷을 안 쓰고 조각 한 번씩 비례로 그린다 — 서버도 같게.
    강규봉님 8번 칸(리듬 max 2.9): 재료 mpc8q3-1(s2 0.6~2.533) 한 조각을 4.54초 — 원본 뒤를 이어 읽는다
    (화면도 2026-09-26부터 같은 규칙: 멈추지 않고 실제 장면)."""
    d = json.loads(DATA.read_text(encoding="utf-8"))
    tts = {int(k): v for k, v in d["tts_durs"].items()}
    for b in d["edit_plan"]["beats"]:
        assert b.get("cut_rhythm") and va.synced_manual_cuts(b, tts[b["beat_idx"]]) == []
    b8 = d["edit_plan"]["beats"][8]
    (c,) = va.plan_beat_clips_for(b8, tts[8], d["src_durs"])
    assert c["video_id"] == "s2" and abs(c["start"] - 0.6) < 1e-6
    assert abs(c["src_dur"] - tts[8]) < 0.02 and abs(c["out_dur"] - tts[8]) < 0.02   # 멈춤 없이 1배속
