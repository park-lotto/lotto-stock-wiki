"""관제 182 — 가림효과 '☑ 골라서'(장면 여러 개) 판정·렌더 창 합치기."""
from shopping_shorts import deco_frame, mix_pipeline


def _m(**kw):
    base = {"l": 10, "t": 10, "w": 20, "h": 10, "kind": "badge", "text": "SALE", "color": "#ff0000"}
    base.update(kw)
    return base


def test_scenes_list_splits_to_each_scene():
    spec = {"masks": [_m(), _m(text="B", scenes=[[3], [4], [5, 1]])]}
    g, scenes = deco_frame.split_scene_masks(spec)
    assert len(g["masks"]) == 1                       # 전체용은 그대로
    assert set(scenes) == {(3, None), (4, None), (5, 1)}


def test_old_single_beat_still_works():
    g, scenes = deco_frame.split_scene_masks({"masks": [_m(beat=2, cut=0)]})
    assert g["masks"] == [] and set(scenes) == {(2, 0)}


def test_empty_scenes_means_all():
    spec = {"masks": [_m(scenes=[])]}
    g, scenes = deco_frame.split_scene_masks(spec)
    assert scenes == {} and g is spec


def test_layers_merge_contiguous(monkeypatch):
    cuts = [{"beat_idx": b, "fin": float(b), "dur": 1.0} for b in range(6)]
    monkeypatch.setattr(mix_pipeline, "final_clip_pairs", lambda *a, **k: cuts)
    tpl = {"frame": {"masks": [_m(scenes=[[0], [3], [4], [5]])]}}
    lays = mix_pipeline._scene_mask_layers(tpl, {}, [], [])
    spans = [(round(x["start"], 2), round(x["start"] + x["dur"], 2)) for x in lays]
    assert spans == [(0.0, 1.0), (3.0, 6.0)]          # 1·2번 빠짐, 3~5는 한 겹


def test_capcut_gets_scene_masks_at_scene_times(tmp_path, monkeypatch):
    """캡컷 draft 에 4~6번 장면 시간(3~6초)에만 가림효과 그림이 실린다."""
    import json, subprocess
    from shopping_shorts import capcut_draft as cd
    cuts = [{"beat_idx": b, "fin": float(b), "dur": 1.0} for b in range(6)]
    monkeypatch.setattr(mix_pipeline, "final_clip_pairs", lambda *a, **k: cuts)
    tpl = {"frame": {"masks": [_m(scenes=[[3], [4], [5]])]}}
    lays = [{"path": l["_abspath"], "start": l["start"], "dur": l["dur"]}
            for l in mix_pipeline._scene_mask_layers(tpl, {}, [], []) if l.get("_abspath")]
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=1080x1920:d=6",
                    "-pix_fmt", "yuv420p", str(src)], check=True, stdin=subprocess.DEVNULL)
    plan = {"beats": [{"beat_idx": 0, "narration": "a", "primary": {"video_id": "s0", "start": 0.0, "end": 6.0}}]}
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": 6.0, "narration": "a"}]
    proj, _n, files = cd.assemble_draft_folder(
        tmp_path / "d", "C:/cap", plan=plan, timeline=tl, source_video_paths={"s0": str(src)},
        tts_paths={}, project_name="p", scene_dim_layers=lays)
    draft = json.loads((proj / "draft_content.json").read_text(encoding="utf-8"))
    mids = {m["id"] for m in draft["materials"]["videos"] if "scene-style-dim" in m["path"]}
    segs = [s["target_timerange"] for t in draft["tracks"] for s in t["segments"] if s["material_id"] in mids]
    assert segs == [{"start": 3_000_000, "duration": 3_000_000}]
