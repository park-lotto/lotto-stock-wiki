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
                  extra_refs=None, render_index=0, source_timerange=True, volume=1.0):
    """세그먼트 공통 골격. source_timerange=False면 null(텍스트).
    volume=0.0으로 원본 클립 오디오를 음소거한다(영상 트랙 전용 — 우리 TTS만 들리게)."""
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
        "speed": 1.0, "volume": volume, "last_nonzero_volume": 1.0,
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


def _hex_rgb(h, default=(1.0, 1.0, 1.0)):
    """'#ffcc00' → (1.0, 0.8, 0.0). 캡컷 content는 0~1 실수 RGB를 쓴다.
    이상한 값이면 기본색 — 자막이 안 나가는 것보다 흰색이라도 나가는 게 낫다."""
    try:
        t = str(h or "").strip().lstrip("#")
        if len(t) == 3:
            t = "".join(c * 2 for c in t)
        if len(t) != 6:
            return default
        return tuple(int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except (TypeError, ValueError):
        return default


def _hex_norm(h, default="#ffffff"):
    """'ffcc00'/'#FFCC00' → '#ffcc00'. 캡컷 머티리얼은 '#rrggbb' 문자열을 쓴다."""
    t = str(h or "").strip()
    if not t:
        return default
    if not t.startswith("#"):
        t = "#" + t
    return t.lower() if len(t) == 7 else default


def _text_content(text, font_path, color=(1.0, 1.0, 1.0), size=15.0):
    import json
    r, g, b = color
    return json.dumps({
        "styles": [{"fill": {"alpha": 1.0, "content": {"render_type": "solid",
                    "solid": {"alpha": 1.0, "color": [r, g, b]}}},
                    "font": {"id": "", "path": font_path},
                    "range": [0, len(text)], "size": size}],
        "text": text}, ensure_ascii=False)


# 캡컷 캡션의 기본 글자 크기(실측: 캡컷이 만든 캡션 머티리얼의 font_size).
_CC_BASE_FONT_SIZE = 16.0
# 우리 화면(제작소 자막꾸미기)의 기본 글자 크기 — caption_style_json의 size 기본값.
_UI_BASE_FONT_SIZE = 50.0


def _caption_style_to_cc(style):
    """제작소 자막 스타일(caption_style_json) → 캡컷 캡션 머티리얼에 넣을 값들.

    ★고객 제보(2026-08-28 "캡컷으로 보내니 템플릿은 안 따라온다"): 종전엔 색·크기·
      외곽선·그림자가 **전부 고정값**이라 캡컷엔 늘 흰색 기본 자막만 갔다
      (caption_style_json 참조 0건 — grep으로 확인).

    ⚠️**위치(x_pct·y_pct)는 여기서 다루지 않는다.** 캡컷 clip.transform의 좌표계
      (부호·스케일)를 실측한 근거가 없다. 짐작해서 넣으면 자막이 화면 밖으로 날아간다 —
      안 옮기면 캡컷 기본 위치라 최소한 보이기는 한다. 실측 뒤에 붙일 것.
    ⚠️폰트 파일도 아직 안 보낸다 — 고객 PC엔 우리 폰트가 없어 경로만 넣으면 깨진다.
      draft 폴더에 동봉하는 작업이 따로 필요하다(다음 단계).
    """
    st = style if isinstance(style, dict) else {}
    out = {}
    # 글자색 — content(0~1 RGB)와 머티리얼(#rrggbb) 둘 다 캡컷이 본다.
    out["rgb"] = _hex_rgb(st.get("color"), (1.0, 1.0, 1.0))
    out["text_color"] = _hex_norm(st.get("color"))
    # 크기 — 캡컷 단위로 환산(우리 50 = 캡컷 16 기준 비례).
    #   ⚠️이 비율은 **추정**이다(캡컷 size 단위를 실측한 자료가 없다). 사장님이 실물에서
    #     보고 조정할 수 있게 한 곳(_CC_BASE_FONT_SIZE/_UI_BASE_FONT_SIZE)에만 적는다.
    try:
        ui = float(st.get("size") or _UI_BASE_FONT_SIZE)
    except (TypeError, ValueError):
        ui = _UI_BASE_FONT_SIZE
    ratio = max(0.3, min(3.0, ui / _UI_BASE_FONT_SIZE))       # 과한 값은 잘라 안전하게
    out["font_size"] = round(_CC_BASE_FONT_SIZE * ratio, 2)
    # 외곽선 — 캡컷 캡션 기본 border_width=0.24(실측). 우리 outline_w(px)를 그 비율로.
    if st.get("outline"):
        try:
            w = float(st.get("outline_w") or 0)
        except (TypeError, ValueError):
            w = 0
        out["border_color"] = _hex_norm(st.get("outline_color"), "#000000")
        out["border_width"] = round(0.24 * max(0.5, min(3.0, (w or 6) / 6.0)), 3)
        out["border_alpha"] = 1.0
    else:
        out["border_color"] = ""
        out["border_width"] = 0.0
        out["border_alpha"] = 0.0
    # 그림자
    if st.get("shadow"):
        out["has_shadow"] = True
        out["shadow_color"] = _hex_norm(st.get("shadow_color"), "#000000")
        try:
            d = float(st.get("shadow_d") or 3)
        except (TypeError, ValueError):
            d = 3
        out["shadow_distance"] = round(max(1.0, min(20.0, d * 1.7)), 2)   # 5.0(기본) ≈ 3×1.7
    else:
        out["has_shadow"] = False
        out["shadow_color"] = ""
    return out


def _text_material(text, font_path, style=None):
    """자막 머티리얼 — **캡션(subtitle)** 으로 만든다(2026-08-26 고객 요청).

    ★고객 제보(진진님): "캡컷에 보내보니 자막이 **텍스트**로 붙더라. 캡션으로 붙게
      해주시면 좋겠다. 텍스트로 오니 (숏템에서 맞춘 게 틀어져) 일일이 조정해야 해서
      시간이 걸린다."

    ★실측(사장님 캡컷 프로젝트 '곰팡이 방지 실리콘' 등 5개, 2026-08-26):
        캡컷이 만든 캡션도 **트랙 타입은 text**다 — 갈리는 곳은 머티리얼의 type이다.
          캡션: type='subtitle' · check_flag=31 · line_max_width=10.0 · border_width=0.24
          텍스트: type='text'   · check_flag=7  · line_max_width=0.82
        캡션에만 있는 키(recognize_type·recognize_task_id·base_content 등)도 함께 넣는다 —
        캡컷이 자막 패널에서 다루려면 이 필드들을 본다.
    ★추측하지 않았다. 실제 캡컷이 저장한 파일에서 그대로 가져온 값이다.
    """
    cc = _caption_style_to_cc(style)
    content = _text_content(text, font_path, color=cc["rgb"], size=cc["font_size"])
    return {"id": _uid(), "type": "subtitle", "content": content,
            "base_content": "", "recognize_type": 0, "recognize_task_id": "",
            "recognize_text": "", "recognize_model": "", "punc_model": "",
            "name": "", "font_path": font_path,
            "font_size": cc["font_size"], "text_color": cc["text_color"],
            "text_alpha": 1.0, "alignment": 1, "line_feed": 1, "letter_spacing": 0.0,
            "line_spacing": 0.02, "text_size": int(round(cc["font_size"])),
            "border_width": cc["border_width"], "border_alpha": cc["border_alpha"],
            "border_color": cc["border_color"], "border_mode": 0, "bold_width": 0.0,
            "has_shadow": cc["has_shadow"], "background_alpha": 0.0, "background_color": "",
            "background_style": 0, "background_round_radius": 0.0,
            "background_height": 0.14, "background_width": 0.14,
            "background_horizontal_offset": 0.0, "background_vertical_offset": 0.0,
            "layer_weight": 1, "line_max_width": 10.0,
            "use_effect_default_color": False,
            "fixed_width": -1.0, "fixed_height": -1.0,
            "force_apply_line_max_width": False, "global_alpha": 1.0,
            "group_id": "", "initial_scale": 1.0, "is_rich_text": False,
            "italic_degree": 0, "language": "", "shadow_alpha": 0.9,
            "shadow_angle": -45.0, "shadow_color": cc["shadow_color"],
            "shadow_distance": cc.get("shadow_distance", 5.0),
            "shadow_smoothing": 1.0, "typesetting": 0, "underline": False,
            "underline_offset": 0.22, "underline_width": 0.05,
            "words": {"start_time": [], "end_time": [], "text": []},
            "current_words": {"end_time": [], "start_time": [], "text": []},
            "caption_template_info": {"category_id": "", "category_name": "",
                                      "effect_id": "", "is_new": False, "path": "",
                                      "request_id": "", "resource_id": "",
                                      "resource_name": "", "source_platform": 0},
            "combo_info": {"text_templates": []}, "sub_type": 0, "check_flag": 31}


_DEFAULT_FONT = ("C:/Users/TheRose/AppData/Local/CapCut/Apps/8.9.1.3802/"
                 "Resources/Font/SystemFont/en.ttf")


def _safe_part(s, limit=20):
    """파일명 조각 안전화 — 한글은 살리고 경로에 위험한 문자만 뺀다."""
    out = "".join(c for c in (s or "") if c.isalnum() or c in "_-")
    return out[:limit]


def _cut(src, start, end, out_path):
    """소스 [start,end]를 잘라 out_path(mp4)로. **export_bundle._cut_clip을 그대로 쓴다**
    (0순위-B: 컷 방식이 두 벌이 되면 ZIP과 캡컷의 조각이 달라진다).
    실패해도 예외를 안 던진다 — 조각 하나가 실패해도 내보내기 전체는 살아야 한다."""
    try:
        from shopping_shorts.export_bundle import _cut_clip
        return _cut_clip(src, start, end, out_path)
    except Exception as e:      # noqa: BLE001
        print("조각 컷 실패(%s): %s" % (getattr(out_path, "name", out_path), str(e)[:100]))
        return False


def _beat_clips(beat, beat_dur, src_durs):
    """비트의 화면 조각 계획 — **렌더와 같은 함수**를 쓴다(0순위-B).

    실제 렌더(`video_assemble._render_mix`)와 캡컷이 서로 다른 계산을 하면 "캡컷에서 연 것"과
    "완성본"이 다른 영상이 된다. 그래서 계획은 `plan_beat_clips_for` 하나가 정한다.

    ★import를 함수 안에서 한다 — capcut_draft는 순수 생성기라 모듈 최상단에서 video_assemble
      (ffmpeg 계열)을 끌어오면 테스트·임포트가 무거워진다.
    실패해도 draft 생성 자체는 살려야 하므로(내보내기가 통째로 죽으면 안 된다) 못 구하면
    primary 하나로 되돌아간다 — 종전 동작과 같다.
    """
    try:
        from shopping_shorts.video_assemble import plan_beat_clips_for
        clips = plan_beat_clips_for(beat, float(beat_dur or 0.0), src_durs or {})
        if clips:
            return clips
    except Exception as e:      # noqa: BLE001 — 계획 실패가 내보내기를 죽이면 안 된다
        print("capcut 조각 계획 실패(primary로 대체): %s" % str(e)[:120])
    prim = beat.get("primary") or {}
    if prim.get("video_id") and prim.get("start") is not None:
        return [{"video_id": prim["video_id"], "start": prim["start"],
                 "src_dur": float(beat_dur or 0.0), "out_dur": float(beat_dur or 0.0)}]
    return []


def _watermark_material(wm, font_path):
    """꾸미기 워터마크(채널 닉네임) → 캡컷 **텍스트** 머티리얼.

    ★고객 제보(2026-08-28 "캡컷으로 보내니 템플릿은 안 따라온다")의 2단계.
      자막(캡션)과 달리 이건 **텍스트**로 넣는다 — 자막 패널에 섞이면 대사 자막을
      다룰 때 워터마크까지 함께 잡혀 오히려 불편하다(캡션 type='subtitle'은 자막 전용).

    ⚠️**위치는 못 맞춘다.** 캡컷 clip.transform 좌표계를 실측한 근거가 없어(부호·스케일)
      짐작해 넣으면 화면 밖으로 날아간다. 캡컷 기본 위치(가운데)로 들어가니
      사장님·고객이 한 번 끌어서 옮기면 된다 — 안 오는 것보다 낫다.
      좌표계를 실측하면 여기와 자막 위치를 함께 붙일 것.
    """
    text = str((wm or {}).get("text") or "").strip()
    if not text:
        return None
    st = {"color": (wm or {}).get("color") or "#ffffff",
          "size": (wm or {}).get("size") or 30,
          "outline": (wm or {}).get("outline", True),
          "outline_color": (wm or {}).get("outline_color") or "#000000",
          "outline_w": (wm or {}).get("outline_w") or 3,
          "shadow": False}
    cc = _caption_style_to_cc(st)
    m = _text_material(text, font_path, st)
    # ★캡션이 아니라 **텍스트**로 되돌린다(실측값: type='text' · check_flag=7 ·
    #   line_max_width=0.82). 이 셋이 캡션과 텍스트를 가르는 자리다.
    m["type"] = "text"
    m["check_flag"] = 7
    m["line_max_width"] = 0.82
    # 투명도(alpha) — 워터마크는 보통 반투명이다.
    try:
        a = float((wm or {}).get("alpha", 0.6))
    except (TypeError, ValueError):
        a = 0.6
    m["text_alpha"] = max(0.05, min(1.0, a))
    m["global_alpha"] = m["text_alpha"]
    return m


def build_draft(*, plan, timeline, source_video_paths, tts_paths, asset_paths,
                project_name, canvas=(1080, 1920), font_path=_DEFAULT_FONT, video_durs=None,
                caption_style=None, deco=None):
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

        # ── 영상 트랙: 비트의 화면 조각 **전부** ──
        # ★2026-08-23 수정. 예전엔 `beat["primary"]` **하나만** 올렸다. 그런데 비트 하나에는
        #   화면이 여러 개 붙는다(primary + alternates, 실험실 편성이면 scene_override).
        #   실측: 조각 19개인 job이 캡컷엔 7개만 갔다 = 완성본과 **다른 영상**이 열렸다.
        #   계획은 렌더와 **같은 함수**가 준다(video_assemble.plan_beat_clips_for, 0순위-B) —
        #   여기서 따로 나누면 또 어긋난다.
        _srcd = {vid: (video_durs or {}).get(real, 0.0)
                 for vid, real in source_video_paths.items() if real}
        _clips = _beat_clips(beat, tl.get("dur", 0.0), _srcd)
        _acc = t0
        for ci, c in enumerate(_clips):
            src_real = source_video_paths.get(c.get("video_id"))
            abs_path = asset_paths.get(src_real) if src_real else None
            if not abs_path:
                continue
            # 마지막 조각은 반올림 오차를 흡수해 비트 끝에 정확히 맞춘다(빈틈·겹침 0).
            c_dur = (t0 + dur - _acc) if ci == len(_clips) - 1 else _us(c.get("out_dur", 0.0))
            if c_dur <= 0:
                continue
            assets_to_copy.append((src_real, abs_path))
            sp, ca, sc, ph, vs = _speed(), _canvas(), _sound_channel_mapping(), _placeholder_info(), _vocal_separation()
            for m, key in ((sp, "speeds"), (ca, "canvases"), (sc, "sound_channel_mappings"),
                           (ph, "placeholder_infos"), (vs, "vocal_separations")):
                mats[key].append(m)
            vdur = _us((video_durs or {}).get(src_real, 0.0)) or (t0 + dur)
            vm = _video_material(abs_path, c.get("video_id", "clip"), vdur, cw, ch)
            mats["videos"].append(vm)
            # volume=0.0 → 원본 클립 오디오 음소거(원본 음악·말소리 제거, 우리 TTS만 들리게).
            # last_nonzero_volume=1.0이라 사장님이 캡컷에서 필요하면 되살릴 수 있다.
            # source_dur은 **읽을 원본 길이**(src_dur)다 — out_dur을 쓰면 슬로모 구간이 어긋난다.
            seg = _base_segment(vm["id"], _acc, c_dur, source_start=_us(c.get("start", 0.0)),
                                source_dur=_us(c.get("src_dur", 0.0)) or c_dur,
                                render_index=0, volume=0.0,
                                extra_refs=[sp["id"], ca["id"], sc["id"], ph["id"], vs["id"]])
            vid_track["segments"].append(seg)
            _acc += c_dur

        # ── 음성 트랙: 비트 TTS ──
        tts_real = tts_paths.get(idx)
        _head = _us(tl.get("head_trim", 0.0))   # 앞트림 → 오디오 소스 시작 오프셋
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
                seg = _base_segment(am["id"], t0, dur, source_start=_head, source_dur=dur,
                                    render_index=0,
                                    extra_refs=[sp["id"], ph["id"], be["id"], sc["id"], vs["id"]])
                aud_track["segments"].append(seg)

        # ── 자막 트랙: 비트 나레이션 ──
        text = (tl.get("narration") or "").strip()
        if text:
            anim = _sticker_animation()
            mats["material_animations"].append(anim)
            tm = _text_material(text, font_path, caption_style)
            mats["texts"].append(tm)
            # ★실측(캡컷이 만든 캡션 세그먼트): render_index=0 · track_render_index=2.
            #   종전엔 render_index=14000(텍스트 관례)이라 자막 패널에서 다르게 다뤄졌다.
            seg = _base_segment(tm["id"], t0, dur, source_timerange=False,
                                render_index=0, extra_refs=[anim["id"]])
            seg["track_render_index"] = 2
            txt_track["segments"].append(seg)

    # ── 워터마크(채널 닉네임) — 영상 전체에 한 칸(2026-08-28 고객 제보 2단계) ──
    #   ★자막 트랙과 **따로** 둔다: 같은 트랙에 넣으면 대사 자막과 시간이 겹쳐
    #     캡컷이 하나를 밀어낸다(둘 다 전 구간에 있을 수 없다).
    wm_track = {"id": _uid(), "type": "text", "attribute": 0, "flag": 0,
                "name": "", "is_default_name": True, "segments": []}
    wm_mat = _watermark_material((deco or {}).get("watermark"), font_path)
    if wm_mat and total_us > 0:
        mats["texts"].append(wm_mat)
        wseg = _base_segment(wm_mat["id"], 0, total_us, source_timerange=False,
                             render_index=0)
        wseg["track_render_index"] = 3        # 자막(2)보다 위
        wm_track["segments"].append(wseg)

    tracks = [t for t in (vid_track, aud_track, txt_track, wm_track) if t["segments"]]
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
                          probe=None, final_video=None, caption_style=None, deco=None):
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
    # ★2026-08-23 — 여기도 `primary`만 보고 있었다(같은 병의 **세 번째 자리**).
    #   alternates 소스가 복사되지 않아 asset_paths에 없고, 그러면 아래 build_draft가
    #   그 조각을 **조용히 건너뛴다**(실측: 화면 3개인 비트가 타임라인에 2개만 올라감).
    #   화면 재료의 단일 출처(_beat_material)와 같은 기준으로 모은다.
    def _vids_of(pb):
        segs = pb.get("scene_override") or ([pb.get("primary")] + list(pb.get("alternates") or []))
        return {s.get("video_id") for s in segs if s}
    used_vids = set()
    for plan_beat in plan.get("beats", []):
        used_vids |= _vids_of(plan_beat)
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

    draft, _ = build_draft(caption_style=caption_style, deco=deco,
                           plan=plan, timeline=timeline, source_video_paths=source_video_paths,
                           tts_paths=tts_paths, asset_paths=asset_paths, project_name=project,
                           canvas=canvas, font_path=font_path, video_durs=video_durs)

    # ── 미디어 보관함(2026-08-23 사장님 "라이브러리에 조각 영상들 불러올 수 있게") ──
    #   타임라인은 그대로 두고, **장면 조각을 캡컷 보관함에 넣어** 끌어다 갈아끼울 수 있게 한다.
    #   자막·TTS는 트랙이 따로라 갈아끼워도 그대로 남는다.
    media = []
    cw2, ch2 = canvas
    #   ① 장면 조각 — 원본에서 잘라낸 **깨끗한 화면**(자막·효과 안 구워짐).
    #      갈아끼워도 자막이 어긋나지 않는다. 파일명을 비트 순서로 지어 보관함에서 정렬된다.
    for tl in timeline:
        beat = {b["beat_idx"]: b for b in plan.get("beats", [])}.get(tl["beat_idx"])
        if not beat:
            continue
        _srcd = {vid: (video_durs or {}).get(real, 0.0)
                 for vid, real in source_video_paths.items() if real}
        for ci, c in enumerate(_beat_clips(beat, tl.get("dur", 0.0), _srcd)):
            real = source_video_paths.get(c.get("video_id"))
            if not real or not Path(real).exists():
                continue
            role = _safe_part(tl.get("role") or beat.get("role") or "")
            name = "cut_%02d_%d%s.mp4" % (int(tl["beat_idx"]), ci, ("_" + role) if role else "")
            out = proj / name
            st = float(c.get("start", 0.0))
            if not _cut(real, st, st + float(c.get("src_dur", 0.0) or 0.0), out):
                continue
            media.append({"path": f"{base_abs}/{project}/{name}", "name": name,
                          "dur": float(c.get("out_dur", 0.0) or 0.0), "w": cw2, "h": ch2})
    #   ② 완성본 — 참고용. 보관함에만 넣고 타임라인엔 안 올린다(TTS와 겹치면 두 번 들린다).
    if final_video and Path(final_video).exists():
        shutil.copy(final_video, proj / "final.mp4")
        try:
            _fdur = probe(final_video)
        except Exception:
            _fdur = 0.0
        media.append({"path": f"{base_abs}/{project}/final.mp4", "name": "final.mp4",
                      "dur": _fdur, "w": cw2, "h": ch2})
    #   ③ 이미 복사해 둔 소스 원본·TTS도 보관함에 올려 바로 쓸 수 있게 한다.
    #      ★TTS는 video_durs에 없다(영상만 잰다) — 길이 0으로 넣으면 보관함에서 못 쓴다.
    #        음성은 여기서 따로 잰다.
    for real, abs_path in asset_paths.items():
        nm = abs_path.rsplit("/", 1)[-1]
        is_vid = nm.lower().endswith(".mp4")
        dur = (video_durs or {}).get(real, 0.0)
        if not dur:
            try:
                dur = probe(real)
            except Exception:
                dur = 0.0
        media.append({"path": abs_path, "name": nm, "dur": dur,
                      "w": cw2 if is_vid else 0, "h": ch2 if is_vid else 0})

    meta = build_meta(project, f"{base_abs}/{project}", draft["duration"], media=media)
    (proj / "draft_content.json").write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    (proj / "draft_meta_info.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return proj, project, sorted(p.name for p in proj.iterdir())


def safe_project_name(s, default="쇼핑쇼츠"):
    # 한글·영숫자는 isalnum()이 True(파이썬 str). 공백·_- 만 추가 허용.
    s = "".join(c for c in (s or "") if c.isalnum() or c in " _-").strip()
    return (s or default)[:50]


_AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")


def _media_entry(item):
    """미디어 보관함 항목 1개.

    ★형식은 실제 캡컷 프로젝트에서 실측했다(2026-08-23, 추측 아님):
      `%LOCALAPPDATA%/CapCut/User Data/Projects/com.lveditor.draft/0618/draft_meta_info.json`
    """
    path = str(item.get("path") or "").replace("\\", "/")
    name = item.get("name") or path.rsplit("/", 1)[-1]
    dur = _us(item.get("dur") or 0.0)
    # mp3를 video로 등록하면 캡컷이 잘못 읽는다 — 확장자로 가른다.
    kind = "music" if name.lower().endswith(_AUDIO_EXT) else "video"
    return {
        "id": _uid(), "type": 0, "metetype": kind,
        "file_Path": path, "extra_info": name,
        "duration": dur,
        "width": int(item.get("w") or 0), "height": int(item.get("h") or 0),
        "roughcut_time_range": {"start": 0, "duration": dur},
        "sub_time_range": {"start": -1, "duration": -1},
        # 아래는 실측 항목에 있던 값 그대로(무해한 기본값).
        "item_source": 1, "create_time": 0, "import_time": 0, "import_time_ms": 0,
        "ai_group_type": "", "md5": "", "enter_from": 0,
    }


def build_meta(project_name, draft_folder, duration_us, media=None):
    """draft_meta_info.json(최소). draft_folder = 캡컷이 볼 이 프로젝트 폴더 절대경로.

    media: 캡컷 **미디어 보관함**에 띄울 파일 목록(2026-08-23 사장님 지시).
      [{"path": 절대경로, "name": 보일이름, "dur": 초, "w": 가로, "h": 세로}, ...]
      타임라인은 그대로 두고 보관함에만 넣는다 — 조각을 끌어다 장면을 갈아끼우기 위함.
      **안 주면 예전과 동일**(빈 보관함) = 회귀 0.

    ★`draft_materials`는 그룹 배열이다(실측): type 0=영상·이미지, 1~6은 다른 갈래.
      빈 그룹도 함께 있어야 캡컷이 정상으로 읽는다.
    """
    entries = [_media_entry(m) for m in (media or []) if m and m.get("path")]
    groups = [{"type": t, "value": entries if t == 0 else []} for t in range(7)]
    return {
        "draft_id": _uid(), "draft_name": project_name, "draft_fold_path": draft_folder,
        "draft_root_path": draft_folder.rsplit("/", 1)[0].rsplit("\\", 1)[0],
        "draft_removable": True, "draft_timeline_materials_size": 0, "draft_type": "",
        "tm_draft_create": 0, "tm_draft_modified": 0, "draft_deeplink_url": "",
        "draft_cover": "draft_cover.jpg", "draft_enterprise_info": {"draft_enterprise_extra": "",
        "draft_enterprise_id": "", "draft_enterprise_name": "", "enterprise_material": []},
        "draft_materials": groups, "draft_duration": duration_us,
    }
