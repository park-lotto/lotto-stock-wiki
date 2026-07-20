"""제작소 편집안 → CapCut draft(draft_content.json) 생성 (설계 2026-07-20 부록A, T2).

역공학 실측(설치 8.9.1.3802, Windows)에 맞춰 비트별 3트랙(영상/음성/자막)을 짠 CapCut 프로젝트를
만든다. 사용자가 캡컷을 열면 타임라인이 이미 짜여 있어 바로 편집할 수 있다.

시간 단위는 **마이크로초**(초×1_000_000). 에셋(mp4·mp3)은 draft가 **절대경로**로 참조하므로,
호출부가 asset_base 아래에 파일을 두고 그 절대경로를 넘겨야 캡컷이 찾는다. 없는 소스는 건너뛴다.

⚠️ 샘플 draft엔 device_id·mac_address가 있으나 여기선 무해 기본값으로 채운다(로드 영향은 육안 검증).
"""
import json
import shutil
import uuid
from pathlib import Path


def _uid():
    return str(uuid.uuid4()).upper()


def _us(sec):
    """초 → 마이크로초(정수)."""
    return int(round(max(0.0, float(sec)) * 1_000_000))


# ── 동반 material(전부 단순, 세그먼트당 새로 생성) ──────────────
def _speed():
    return {"id": _uid(), "type": "speed", "mode": 0, "speed": 1.0, "curve_speed": None}


def _sound_channel_mapping():
    return {"id": _uid(), "type": "", "audio_channel_mapping": 0, "is_config_open": False}


def _vocal_separation():
    return {"id": _uid(), "type": "vocal_separation", "choice": 0, "removed_sounds": [],
            "time_range": None, "production_path": "", "final_algorithm": "", "enter_from": ""}


def _placeholder_info():
    return {"id": _uid(), "type": "placeholder_info", "meta_type": "none",
            "res_path": "", "res_text": "", "error_path": "", "error_text": ""}


def _beat_material():
    return {"id": _uid(), "type": "beats", "enable_ai_beats": False, "gear": 404,
            "gear_count": 0, "mode": 404, "user_beats": [], "user_delete_ai_beats": None,
            "ai_beats": {"melody_url": "", "melody_path": "", "beats_url": "",
                         "beats_path": "", "melody_percents": [], "beat_speed_infos": []}}


def _canvas():
    return {"id": _uid(), "type": "canvas_color", "album_image": "", "blur": 0.0, "color": "",
            "image": "", "image_id": "", "image_name": "", "source_platform": 0, "team_id": ""}


def _sticker_animation():
    return {"id": _uid(), "type": "sticker_animation", "animations": [],
            "multi_language_current": "none"}


def _clip():
    return {"alpha": 1.0, "flip": {"horizontal": False, "vertical": False}, "rotation": 0.0,
            "scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.0}}


def _base_segment(material_id, target_start, target_dur, *, source_start=0, source_dur=None,
                  extra_refs=None, render_index=0, source_timerange=True):
    """세그먼트 공통 골격. source_timerange=False면 null(텍스트)."""
    seg = {
        "id": _uid(),
        "material_id": material_id,
        "target_timerange": {"start": target_start, "duration": target_dur},
        "source_timerange": ({"start": source_start,
                              "duration": source_dur if source_dur is not None else target_dur}
                             if source_timerange else None),
        "render_timerange": {"start": 0, "duration": 0},
        "extra_material_refs": extra_refs or [],
        "clip": _clip(), "uniform_scale": {"on": True, "value": 1.0},
        "speed": 1.0, "volume": 1.0, "last_nonzero_volume": 1.0,
        "visible": True, "reverse": False, "is_loop": False, "is_placeholder": False,
        "is_tone_modify": False, "intensifies_audio": False, "cartoon": False,
        "render_index": render_index, "track_render_index": 0, "track_attribute": 0,
        "group_id": "", "raw_segment_id": "", "template_id": "", "template_scene": "default",
        "keyframe_refs": [], "common_keyframes": [], "caption_info": None,
        "enable_adjust": True, "enable_lut": True, "enable_hsl": False,
        "enable_color_curves": True, "enable_color_wheels": True, "enable_video_mask": True,
        "enable_smart_color_adjust": False, "enable_adjust_mask": False,
        "enable_color_match_adjust": False, "enable_color_correct_adjust": False,
        "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
        "responsive_layout": {"enable": False, "target_follow": "", "size_layout": 0,
                              "horizontal_pos_layout": 0, "vertical_pos_layout": 0},
        "state": 0, "source": "segmentsourcenormal", "desc": "", "color_correct_alg_result": "",
        "digital_human_template_group_id": "", "lyric_keyframes": None,
    }
    return seg


def _video_material(path, name, dur_us, width, height):
    return {"id": _uid(), "type": "video", "path": path, "material_name": name,
            "duration": dur_us, "width": width, "height": height, "has_audio": True,
            "category_name": "local", "source": 0, "source_platform": 0,
            "crop": {"lower_left_x": 0.0, "lower_left_y": 1.0, "lower_right_x": 1.0,
                     "lower_right_y": 1.0, "upper_left_x": 0.0, "upper_left_y": 0.0,
                     "upper_right_x": 1.0, "upper_right_y": 0.0},
            "crop_ratio": "free", "crop_scale": 1.0, "media_path": "", "aigc_type": "none"}


def _audio_material(path, name, dur_us):
    return {"id": _uid(), "type": "music", "path": path, "name": name, "duration": dur_us,
            "category_name": "local", "wave_points": [], "music_id": "", "source_platform": 0,
            "check_flag": 1, "copyright_limit_type": "none"}


def _text_content(text, font_path, color=(1.0, 1.0, 1.0), size=15.0):
    import json
    r, g, b = color
    return json.dumps({
        "styles": [{"fill": {"alpha": 1.0, "content": {"render_type": "solid",
                    "solid": {"alpha": 1.0, "color": [r, g, b]}}},
                    "font": {"id": "", "path": font_path},
                    "range": [0, len(text)], "size": size}],
        "text": text}, ensure_ascii=False)


def _text_material(text, font_path):
    return {"id": _uid(), "type": "text", "content": _text_content(text, font_path),
            "name": "", "font_path": font_path, "font_size": 15.0, "text_color": "#FFFFFF",
            "text_alpha": 1.0, "alignment": 1, "line_feed": 1, "letter_spacing": 0.0,
            "line_spacing": 0.02, "text_size": 30, "border_width": 0.08, "border_alpha": 1.0,
            "has_shadow": False, "background_alpha": 1.0, "layer_weight": 1,
            "line_max_width": 0.82, "use_effect_default_color": True,
            "words": {"start_time": [], "end_time": [], "text": []},
            "combo_info": {"text_templates": []}, "sub_type": 0, "check_flag": 7}


_DEFAULT_FONT = ("C:/Users/TheRose/AppData/Local/CapCut/Apps/8.9.1.3802/"
                 "Resources/Font/SystemFont/en.ttf")


def build_draft(*, plan, timeline, source_video_paths, tts_paths, asset_paths,
                project_name, canvas=(1080, 1920), font_path=_DEFAULT_FONT, video_durs=None):
    """편집안 → (draft_content_dict, assets_to_copy).

    asset_paths: {real_path: 캡컷이 볼 절대경로} — 호출부가 파일을 그 절대경로에 두고 넘긴다.
                 (draft는 절대경로 참조라 브라우저 폴더 안에 에셋을 함께 써야 한다.)
    assets_to_copy: [(real_path, 캡컷절대경로)] — 호출부가 실제로 복사할 목록.
    없는 소스/음성은 건너뛴다."""
    cw, ch = canvas
    mats = {k: [] for k in (
        "videos", "audios", "texts", "speeds", "beats", "sound_channel_mappings",
        "vocal_separations", "placeholder_infos", "material_animations", "canvases")}
    vid_track = {"id": _uid(), "type": "video", "attribute": 0, "flag": 0,
                 "name": "", "is_default_name": True, "segments": []}
    aud_track = {"id": _uid(), "type": "audio", "attribute": 0, "flag": 0,
                 "name": "", "is_default_name": True, "segments": []}
    txt_track = {"id": _uid(), "type": "text", "attribute": 0, "flag": 0,
                 "name": "", "is_default_name": True, "segments": []}
    beats_by_idx = {b["beat_idx"]: b for b in plan.get("beats", [])}
    assets_to_copy = []
    total_us = 0

    for tl in timeline:
        idx = tl["beat_idx"]
        beat = beats_by_idx.get(idx, {})
        t0 = _us(tl.get("t0", 0.0))
        dur = _us(tl.get("dur", 0.0))
        if dur <= 0:
            continue
        total_us = max(total_us, t0 + dur)

        # ── 영상 트랙: 비트 primary 소스 클립 ──
        prim = beat.get("primary") or {}
        src_real = source_video_paths.get(prim.get("video_id"))
        if src_real and prim.get("start") is not None:
            abs_path = asset_paths.get(src_real)
            if abs_path:
                assets_to_copy.append((src_real, abs_path))
                sp, ca, sc, ph, vs = _speed(), _canvas(), _sound_channel_mapping(), _placeholder_info(), _vocal_separation()
                for m, key in ((sp, "speeds"), (ca, "canvases"), (sc, "sound_channel_mappings"),
                               (ph, "placeholder_infos"), (vs, "vocal_separations")):
                    mats[key].append(m)
                vdur = _us((video_durs or {}).get(src_real, 0.0)) or (t0 + dur)
                vm = _video_material(abs_path, prim.get("video_id", "clip"), vdur, cw, ch)
                mats["videos"].append(vm)
                seg = _base_segment(vm["id"], t0, dur, source_start=_us(prim["start"]),
                                    source_dur=dur, render_index=0,
                                    extra_refs=[sp["id"], ca["id"], sc["id"], ph["id"], vs["id"]])
                vid_track["segments"].append(seg)

        # ── 음성 트랙: 비트 TTS ──
        tts_real = tts_paths.get(idx)
        if tts_real:
            abs_path = asset_paths.get(tts_real)
            if abs_path:
                assets_to_copy.append((tts_real, abs_path))
                sp, ph, be, sc, vs = _speed(), _placeholder_info(), _beat_material(), _sound_channel_mapping(), _vocal_separation()
                for m, key in ((sp, "speeds"), (ph, "placeholder_infos"), (be, "beats"),
                               (sc, "sound_channel_mappings"), (vs, "vocal_separations")):
                    mats[key].append(m)
                am = _audio_material(abs_path, "beat_%02d" % idx, dur)
                mats["audios"].append(am)
                seg = _base_segment(am["id"], t0, dur, source_start=0, source_dur=dur,
                                    render_index=0,
                                    extra_refs=[sp["id"], ph["id"], be["id"], sc["id"], vs["id"]])
                aud_track["segments"].append(seg)

        # ── 자막 트랙: 비트 나레이션 ──
        text = (tl.get("narration") or "").strip()
        if text:
            anim = _sticker_animation()
            mats["material_animations"].append(anim)
            tm = _text_material(text, font_path)
            mats["texts"].append(tm)
            seg = _base_segment(tm["id"], t0, dur, source_timerange=False,
                                render_index=14000, extra_refs=[anim["id"]])
            txt_track["segments"].append(seg)

    tracks = [t for t in (vid_track, aud_track, txt_track) if t["segments"]]
    draft = _skeleton(project_name, cw, ch, total_us)
    draft["materials"].update(mats)
    draft["tracks"] = tracks
    return draft, assets_to_copy


def _skeleton(name, cw, ch, duration_us):
    """빈 draft 골격(0711 실측 기준). materials/tracks는 호출부가 채운다."""
    all_mat_keys = [
        "flowers", "videos", "tail_leaders", "audios", "images", "texts", "effects",
        "stickers", "canvases", "transitions", "audio_effects", "audio_fades", "beats",
        "material_animations", "placeholders", "placeholder_infos", "speeds", "common_mask",
        "chromas", "text_templates", "realtime_denoises", "audio_pannings", "audio_pitch_shifts",
        "video_trackings", "hsl", "drafts", "color_curves", "video_effects", "audio_balances",
        "sound_channel_mappings", "green_screens", "shapes", "material_colors", "vocal_separations",
        "vocal_beautifys", "manual_deformations", "manual_beautys", "plugin_effects"]
    return {
        "id": _uid(), "version": 360000, "new_version": "171.0.0", "name": name,
        "duration": duration_us, "fps": 30.0, "create_time": 0, "update_time": 0,
        "is_drop_frame_timecode": False, "color_space": -1,
        "canvas_config": {"ratio": "original", "width": cw, "height": ch, "background": None},
        "config": {"video_mute": False, "record_audio_last_index": 1, "extract_audio_last_index": 1,
                   "original_sound_last_index": 1, "subtitle_sync": True, "lyrics_sync": True,
                   "sticker_max_index": 1, "adjust_max_index": 1, "combination_max_index": 1,
                   "material_save_mode": 0, "maintrack_adsorb": True, "attachment_info": [],
                   "multi_language_mode": "none", "multi_language_main": "none",
                   "multi_language_current": "none", "multi_language_list": [],
                   "subtitle_taskinfo": [], "lyrics_taskinfo": [], "system_font_list": [],
                   "use_float_render": False, "subtitle_recognition_id": "", "lyrics_recognition_id": ""},
        "materials": {k: [] for k in all_mat_keys},
        "keyframes": {k: [] for k in ("videos", "audios", "texts", "stickers", "filters",
                                      "adjusts", "handwrites", "effects")},
        "keyframe_graph_list": [], "tracks": [], "group_container": None,
        "platform": {"os": "windows", "os_version": "10.0.26200", "app_id": 359289,
                     "app_version": "8.7.0", "app_source": "cc", "device_id": "",
                     "hard_disk_id": "", "mac_address": ""},
        "last_modified_platform": {"os": "windows", "os_version": "10.0.26200", "app_id": 359289,
                                   "app_version": "8.7.0", "app_source": "cc", "device_id": "",
                                   "hard_disk_id": "", "mac_address": ""},
        "render_index_track_mode_on": True, "free_render_index_mode_on": False,
        "source": "default", "draft_type": "video", "path": "", "relationships": [],
        "mutable_config": None, "cover": None, "retouch_cover": None, "extra_info": None,
        "static_cover_image_path": "", "time_marks": None, "lyrics_effects": [],
    }


def assemble_draft_folder(out_root, base_abs, *, plan, timeline, source_video_paths,
                          tts_paths, project_name, canvas=(1080, 1920), font_path=_DEFAULT_FONT,
                          probe=None):
    """draft 폴더를 out_root/<project>/ 에 실제로 조립한다(에셋 복사 + draft_content.json + meta).

    base_abs: 캡컷이 이 draft 폴더를 볼 **절대경로**(예: C:/capcutproject/CapCut Drafts). draft가
              에셋을 절대경로로 참조하므로, 프론트가 이 base 아래 <project>/에 파일을 쓰면 경로가 맞는다.
    probe(path)->초: 영상 길이 프로버(없으면 video_assemble._probe_duration). 반환: (proj_dir, project, filenames)."""
    if probe is None:
        from shopping_shorts.video_assemble import _probe_duration as probe
    project = safe_project_name(project_name)
    proj = Path(out_root) / project
    if proj.exists():
        shutil.rmtree(proj, ignore_errors=True)
    proj.mkdir(parents=True, exist_ok=True)
    base_abs = base_abs.replace("\\", "/").rstrip("/")

    # 소스 영상: 비트에 실제 쓰인 것만 폴더당 1회 복사. 캡컷이 볼 절대경로 매핑 구성.
    used_vids = {(plan_beat.get("primary") or {}).get("video_id")
                 for plan_beat in plan.get("beats", [])}
    asset_paths, video_durs = {}, {}
    for vid, real in source_video_paths.items():
        if vid not in used_vids or not real or not Path(real).exists():
            continue
        name = f"src_{safe_project_name(str(vid))}.mp4"
        shutil.copy(real, proj / name)
        asset_paths[real] = f"{base_abs}/{project}/{name}"
        try:
            video_durs[real] = probe(real)
        except Exception:
            video_durs[real] = 0.0
    # TTS: 비트별 복사
    for idx, real in tts_paths.items():
        if real and Path(real).exists():
            name = f"beat_{int(idx):02d}.mp3"
            shutil.copy(real, proj / name)
            asset_paths[real] = f"{base_abs}/{project}/{name}"

    draft, _ = build_draft(plan=plan, timeline=timeline, source_video_paths=source_video_paths,
                           tts_paths=tts_paths, asset_paths=asset_paths, project_name=project,
                           canvas=canvas, font_path=font_path, video_durs=video_durs)
    meta = build_meta(project, f"{base_abs}/{project}", draft["duration"])
    (proj / "draft_content.json").write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    (proj / "draft_meta_info.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return proj, project, sorted(p.name for p in proj.iterdir())


def safe_project_name(s, default="쇼핑쇼츠"):
    # 한글·영숫자는 isalnum()이 True(파이썬 str). 공백·_- 만 추가 허용.
    s = "".join(c for c in (s or "") if c.isalnum() or c in " _-").strip()
    return (s or default)[:50]


def build_meta(project_name, draft_folder, duration_us):
    """draft_meta_info.json(최소). draft_folder = 캡컷이 볼 이 프로젝트 폴더 절대경로."""
    return {
        "draft_id": _uid(), "draft_name": project_name, "draft_fold_path": draft_folder,
        "draft_root_path": draft_folder.rsplit("/", 1)[0].rsplit("\\", 1)[0],
        "draft_removable": True, "draft_timeline_materials_size": 0, "draft_type": "",
        "tm_draft_create": 0, "tm_draft_modified": 0, "draft_deeplink_url": "",
        "draft_cover": "draft_cover.jpg", "draft_enterprise_info": {"draft_enterprise_extra": "",
        "draft_enterprise_id": "", "draft_enterprise_name": "", "enterprise_material": []},
        "draft_materials": [], "draft_duration": duration_us,
    }
