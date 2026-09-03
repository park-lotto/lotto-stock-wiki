"""CapCut draft 생성기 구조 검증 (설계 부록A). 실제 열림 여부는 캡컷 육안(자동 불가)."""
import json
import subprocess
from pathlib import Path

from shopping_shorts import capcut_draft as cd


_PLAN = {"beats": [
    {"beat_idx": 0, "role": "훅", "narration": "첫 장면",
     "primary": {"video_id": "s0", "start": 0.0, "end": 2.0}},
    {"beat_idx": 1, "role": "본문", "narration": "둘째 장면",
     "primary": {"video_id": "s0", "start": 2.0, "end": 3.5}}]}
_TIMELINE = [
    {"beat_idx": 0, "t0": 0.0, "dur": 2.0, "narration": "첫 장면", "role": "훅"},
    {"beat_idx": 1, "t0": 2.0, "dur": 1.5, "narration": "둘째 장면", "role": "본문"}]
_SRC = {"s0": r"C:\real\src.mp4"}
_TTS = {0: r"C:\real\b0.mp3", 1: r"C:\real\b1.mp3"}
_ASSET = {r"C:\real\src.mp4": r"C:\cap\p\src.mp4",
          r"C:\real\b0.mp3": r"C:\cap\p\b0.mp3", r"C:\real\b1.mp3": r"C:\cap\p\b1.mp3"}


def _build():
    return cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                          tts_paths=_TTS, asset_paths=_ASSET, project_name="테스트")


def test_us_conversion():
    assert cd._us(1) == 1_000_000
    assert cd._us(2.5) == 2_500_000
    assert cd._us(-1) == 0


def test_three_tracks_with_segments():
    draft, _ = _build()
    types = {t["type"]: len(t["segments"]) for t in draft["tracks"]}
    assert types == {"video": 2, "audio": 2, "text": 2}


def test_timeline_microseconds():
    draft, _ = _build()
    txt = next(t for t in draft["tracks"] if t["type"] == "text")
    # 둘째 자막은 t0=2.0s → 2_000_000μs 에서 시작, 길이 1.5s
    seg1 = txt["segments"][1]
    # 마지막 비트의 마지막 구절은 렌더처럼 0.5초 여운(caption_schedule tail) → 1.5+0.5
    assert seg1["target_timerange"] == {"start": 2_000_000, "duration": 2_000_000}
    assert seg1["source_timerange"] is None   # 텍스트는 source 없음
    assert draft["duration"] == 3_500_000     # 전체 = 마지막 끝


def test_extra_material_refs_resolve():
    """세그먼트가 참조하는 동반 material이 실제로 materials에 있어야 캡컷이 연다."""
    draft, _ = _build()
    ids = set()
    for arr in draft["materials"].values():
        for m in arr:
            ids.add(m["id"])
    for tr in draft["tracks"]:
        for seg in tr["segments"]:
            assert seg["material_id"] in ids, f"material_id 미해결: {seg['material_id']}"
            for ref in seg["extra_material_refs"]:
                assert ref in ids, f"extra_material_ref 미해결: {ref}"


def test_audio_has_five_companions_text_one():
    draft, _ = _build()
    aud = next(t for t in draft["tracks"] if t["type"] == "audio")
    txt = next(t for t in draft["tracks"] if t["type"] == "text")
    assert len(aud["segments"][0]["extra_material_refs"]) == 5   # 실측: speed·ph·beat·scm·vs
    assert len(txt["segments"][0]["extra_material_refs"]) == 1   # material_animation


def test_assets_to_copy_listed():
    _, assets = _build()
    reals = {r for r, _ in assets}
    assert reals == {r"C:\real\src.mp4", r"C:\real\b0.mp3", r"C:\real\b1.mp3"}


def test_text_content_is_json_string_with_text():
    draft, _ = _build()
    tm = draft["materials"]["texts"][0]
    assert isinstance(tm["content"], str) and '"text": "첫 장면"' in tm["content"]


def test_canvas_vertical_default():
    draft, _ = _build()
    assert draft["canvas_config"]["width"] == 1080 and draft["canvas_config"]["height"] == 1920


def test_safe_project_name_keeps_korean():
    assert cd.safe_project_name("쇼핑쇼츠_0720") == "쇼핑쇼츠_0720"
    assert cd.safe_project_name("a/b:c*") == "abc"
    assert cd.safe_project_name("") == "쇼핑쇼츠"


def _mk_video(p, dur=4):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"color=c=red:s=1080x1920:r=30:d={dur}", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(p)], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


def _mk_audio(p, dur=2.0):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"sine=frequency=440:duration={dur}", "-c:a", "libmp3lame", str(p)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def test_assemble_folder_copies_assets_and_writes_draft(tmp_path):
    src = tmp_path / "src.mp4"; _mk_video(src, 4)
    b0 = tmp_path / "b0.mp3"; _mk_audio(b0, 2.0)
    b1 = tmp_path / "b1.mp3"; _mk_audio(b1, 1.5)
    out = tmp_path / "drafts"
    proj, name, files = cd.assemble_draft_folder(
        out, "C:/cap/CapCut Drafts", plan=_PLAN, timeline=_TIMELINE,
        source_video_paths={"s0": str(src)}, tts_paths={0: str(b0), 1: str(b1)},
        project_name="쇼핑쇼츠_j1")
    # 파일이 실제로 복사됐나
    assert "draft_content.json" in files and "draft_meta_info.json" in files
    assert "src_s0.mp4" in files and "beat_00.mp3" in files and "beat_01.mp3" in files
    # draft가 base 절대경로로 에셋을 참조하나(캡컷이 찾을 수 있게)
    draft = json.loads((proj / "draft_content.json").read_text(encoding="utf-8"))
    vpath = draft["materials"]["videos"][0]["path"]
    assert vpath == "C:/cap/CapCut Drafts/쇼핑쇼츠_j1/src_s0.mp4"
    # 비디오 material 길이가 실제 소스(4s≈4_000_000μs) 반영(placeholder 아님)
    assert abs(draft["materials"]["videos"][0]["duration"] - 4_000_000) < 200_000


def test_missing_source_skips_video_but_keeps_audio_text():
    plan = {"beats": [{"beat_idx": 0, "role": "훅", "narration": "장면",
                       "primary": {"video_id": "gone", "start": 0.0, "end": 2.0}}]}
    draft, _ = cd.build_draft(plan=plan, timeline=[{"beat_idx": 0, "t0": 0.0, "dur": 2.0,
                              "narration": "장면", "role": "훅"}],
                              source_video_paths={}, tts_paths=_TTS, asset_paths=_ASSET,
                              project_name="x")
    types = {t["type"] for t in draft["tracks"]}
    assert "video" not in types and "audio" in types and "text" in types


def test_capcut_project_name_uses_headcopy_for_findability():
    """캡컷 목록에서 알아보게 헤드카피를 앞에 둔다(2026-07-21 제보: job-id 해시만으론
    '쇼핑쇼츠_...169a1'처럼 잘려 구분 불가). 없으면 첫 대사, 그것도 없으면 옛 폴백."""
    from shopping_shorts import app as a
    n = a._capcut_project_name("454169a1zzzz", {"headcopy": {"text": "써보면 놀라는 이것"}}, {})
    assert n.startswith("써보면 놀라는 이것") and " 4541 " in n           # 제목 앞, 짧은 id
    assert n.split()[-1].isdigit() and len(n.split()[-1]) == 4            # 보낸 시각(HHMM) — 매번 새 프로젝트
    n2 = a._capcut_project_name("454169a1zzzz", {}, {"beats": [{"narration": "딱 한 뼘이면 OK"}]})
    assert n2.startswith("딱 한 뼘이면 OK")                          # 헤드카피 없으면 첫 대사
    n3 = a._capcut_project_name("454169a1zzzz", {}, {})
    assert n3.startswith("쇼핑쇼츠_454169a1")                         # 둘 다 없으면 옛 폴백(+시각)


def test_capcut_audio_reflects_head_trim():
    from shopping_shorts.capcut_draft import build_draft, _us
    plan = {"beats": [{"beat_idx": 0, "narration": "가",
                       "primary": {"video_id": "v1", "start": 0}, "head_trim": 0.5}]}
    timeline = [{"beat_idx": 0, "t0": 0.0, "dur": 4.0, "narration": "가", "head_trim": 0.5}]
    draft, _ = build_draft(
        plan=plan, timeline=timeline,
        source_video_paths={"v1": "/x/v1.mp4"}, tts_paths={0: "/x/b0.mp3"},
        asset_paths={"/x/v1.mp4": "C:/d/v1.mp4", "/x/b0.mp3": "C:/d/b0.mp3"},
        project_name="t")
    aud_track = next(t for t in draft["tracks"] if t["type"] == "audio")
    seg = aud_track["segments"][0]
    assert seg["source_timerange"]["start"] == _us(0.5)   # 앞트림이 source_start로
    assert seg["source_timerange"]["duration"] == _us(4.0)


# ── 자막은 '캡션(subtitle)'으로 나가야 한다 (2026-08-26 고객 요청) ──────────────
# ★고객 제보(진진님): "캡컷에 보내보니 자막이 **텍스트**로 붙더라. 캡션으로 붙게 해주시면
#   좋겠다. 텍스트로 오니 (숏템에서 맞춘 게 틀어져) 일일이 조정해야 해서 시간이 걸린다."
# ★기준값은 전부 **실측**이다 — 사장님 캡컷 프로젝트('곰팡이 방지 실리콘' 등 5개)에서
#   캡컷이 직접 저장한 draft_content.json을 읽어 대조했다(추측한 값이 하나도 없다).
#     캡션 : type='subtitle' · check_flag=31 · line_max_width=10.0 · border_width=0.24
#     텍스트: type='text'    · check_flag=7  · line_max_width=0.82
#   ★트랙 타입은 캡션도 'text'다 — 여기를 바꾸면 오히려 캡컷이 못 읽는다.
def test_자막_머티리얼은_캡션타입이다():
    draft, _ = _build()
    texts = draft["materials"]["texts"]
    assert texts, "자막 머티리얼이 없다"
    for t in texts:
        assert t["type"] == "subtitle", (
            f"자막이 '{t['type']}'로 나간다 — 캡컷에서 텍스트로 붙어 일일이 고쳐야 한다")


def test_캡션_판정필드가_실측값과_같다():
    """캡컷이 자막 패널에서 다루려면 이 값들을 본다 — 하나만 어긋나도 텍스트로 취급된다."""
    t = _build()[0]["materials"]["texts"][0]
    assert t["check_flag"] == 31, f"check_flag={t['check_flag']} (캡컷 캡션은 31)"
    assert t["line_max_width"] == 10.0
    assert t["recognize_type"] == 0
    assert "recognize_task_id" in t and "base_content" in t


def test_트랙타입은_그대로_text다():
    """★캡션이라고 트랙까지 subtitle로 바꾸면 안 된다 — 실측상 캡컷도 트랙은 text다."""
    draft, _ = _build()
    kinds = [tr["type"] for tr in draft["tracks"]]
    assert "text" in kinds and "subtitle" not in kinds, kinds


def test_세그먼트_렌더인덱스가_캡션기준이다():
    draft, _ = _build()
    seg = [tr for tr in draft["tracks"] if tr["type"] == "text"][0]["segments"][0]
    assert seg["render_index"] == 0, "텍스트 관례(14000)가 남아 있다"
    assert seg["track_render_index"] == 3     # 소스0·머리카피1·틀2 위


# ── 자막 스타일이 캡컷으로 따라간다(2026-08-28 고객 제보) ────────────────────
# 제보: "캡컷으로 보내니 템플릿은 안 따라온다"
# 실측 원인: capcut_draft가 caption_style_json을 **한 번도 참조하지 않았다**(grep 0건).
#   색·크기·외곽선·그림자가 전부 고정값이라 캡컷엔 늘 흰색 기본 자막만 갔다.
_STYLE = {"font": "GmarketSansBold.otf", "color": "#ffcc00", "size": 70,
          "outline": True, "outline_color": "#000000", "outline_w": 9,
          "shadow": True, "shadow_color": "#111111", "shadow_d": 4,
          "y_pct": 32, "x_pct": 50}


def _texts(draft):
    return draft["materials"]["texts"]


def test_caption_style_reaches_draft():
    """★뿌리: 고른 색·크기·외곽선·그림자가 draft에 실제로 실린다."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                              caption_style=_STYLE)
    t = _texts(draft)[0]
    assert t["text_color"] == "#ffcc00", f"글자색이 안 갔다: {t['text_color']}"
    assert t["font_size"] > cd._CC_BASE_FONT_SIZE, f"크기(70)가 기본 그대로다: {t['font_size']}"
    assert t["border_color"] == "#000000" and t["border_width"] > 0, "외곽선이 안 갔다"
    assert t["has_shadow"] is True and t["shadow_color"] == "#111111", "그림자가 안 갔다"
    # content(0~1 RGB)에도 같은 색이 들어가야 한다 — 캡컷은 둘 다 본다
    rgb = json.loads(t["content"])["styles"][0]["fill"]["content"]["solid"]["color"]
    assert rgb[0] == 1.0 and abs(rgb[1] - 0.8) < 0.01 and rgb[2] == 0.0, rgb


def test_no_style_keeps_old_output():
    """★회귀 0: 스타일을 안 주면 종전과 똑같은 기본 자막이다."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t")
    t = _texts(draft)[0]
    assert t["text_color"] == "#ffffff" and t["font_size"] == round(cd._CC_BASE_FONT_SIZE, 2)
    assert t["background_style"] == 0 and t["background_alpha"] == 0.0
    assert t["border_color"] == "" and t["has_shadow"] is False


def test_caption_stays_subtitle_type():
    """★스타일을 넣어도 **캡션(subtitle)**이어야 한다 — 텍스트로 바뀌면 2026-08-26 제보가 재발한다."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                              caption_style=_STYLE)
    t = _texts(draft)[0]
    assert t["type"] == "subtitle" and t["check_flag"] == 31, "캡션이 아니라 텍스트가 됐다"


def test_junk_style_does_not_break_export():
    """★이상한 값이 와도 내보내기는 된다 — 스타일은 부가물이지 관문이 아니다."""
    for bad in (None, {}, {"color": "zzz", "size": "많이", "outline_w": None},
                {"color": None, "shadow": True, "shadow_d": "x"}):
        draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                                  tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                                  caption_style=bad)
        t = _texts(draft)[0]
        assert t["text_color"].startswith("#") and t["font_size"] > 0, bad


def test_size_is_clamped():
    """터무니없는 크기는 잘라낸다 — 캡컷에서 글자가 화면을 덮으면 못 쓴다."""
    big, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                            tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                            caption_style={"size": 99999})
    tiny, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                             tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                             caption_style={"size": 1})
    assert _texts(big)[0]["font_size"] <= cd._CC_BASE_FONT_SIZE * 3
    assert _texts(tiny)[0]["font_size"] >= round(cd._CC_BASE_FONT_SIZE * 0.3, 2)


def test_font_size_matches_render_pixels():
    """★2026-09-03 고객 제보: 캡컷 글자가 렌더보다 1.7배 컸다. 렌더 px(UI×1.5)를 캡컷 단위로
    나눈 값이어야 하고, 종전 값(UI 50→16)보다 확실히 작아야 한다."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                              caption_style={"size": 44})
    fs = _texts(draft)[0]["font_size"]
    assert abs(fs - round(44 * 1080 / 720 / cd._CC_PX_PER_UNIT, 2)) < 0.02, fs
    assert fs < 16.0 * 44 / 50, f"종전 비례식 그대로다: {fs}"


def test_caption_box_reaches_draft():
    """★2026-09-03 고객 제보 "바탕(배경박스)이 없다": box=True면 캡컷 캡션의 배경 필드
    (background_style=1·color·alpha)가 실린다 — 실물 캡컷 캡션 파일과 같은 형태."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                              caption_style={"box": True, "box_color": "#ffffff",
                                             "box_opacity": 80, "box_pad": 12})
    t = _texts(draft)[0]
    assert t["background_style"] == 1, "배경박스가 안 갔다"
    assert t["background_color"] == "#ffffff" and abs(t["background_alpha"] - 0.8) < 0.001, t
    # 캡션(subtitle) 타입은 그대로여야 한다
    assert t["type"] == "subtitle"
    # 끄면 안 간다
    off, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                            tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                            caption_style={"box": False, "box_color": "#ffffff"})
    assert _texts(off)[0]["background_style"] == 0 and _texts(off)[0]["background_alpha"] == 0.0


# ── 워터마크(채널 닉네임)도 따라간다 — 고객 제보 2단계 ─────────────────────
_WM = {"watermark": {"text": "캡틴살림꾼", "color": "#ffffff", "size": 30,
                     "alpha": 0.6, "outline": True, "outline_color": "#000000",
                     "outline_w": 3}}


def _wm_mats(draft):
    return [m for m in draft["materials"]["texts"] if m["type"] == "text"]


def test_watermark_reaches_draft():
    """★워터마크가 캡컷에 실린다(종전엔 아예 안 갔다)."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t", deco=_WM)
    wm = _wm_mats(draft)
    assert len(wm) == 1, f"워터마크가 없거나 여러 개다: {len(wm)}"
    assert "캡틴살림꾼" in wm[0]["content"]
    assert abs(wm[0]["text_alpha"] - 0.6) < 0.01, "투명도가 안 갔다"


def test_watermark_is_text_not_caption():
    """★워터마크는 **텍스트**다 — 캡션으로 넣으면 자막 패널에서 대사와 섞인다."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t", deco=_WM)
    wm = _wm_mats(draft)[0]
    assert wm["type"] == "text" and wm["check_flag"] == 7 and wm["line_max_width"] == 0.82
    # 대사 자막은 그대로 캡션이어야 한다
    caps = [m for m in draft["materials"]["texts"] if m["type"] == "subtitle"]
    assert caps and caps[0]["check_flag"] == 31


def test_watermark_gets_its_own_track():
    """★자막과 **다른 트랙**이어야 한다 — 같은 트랙이면 시간이 겹쳐 하나가 밀려난다."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t", deco=_WM)
    text_tracks = [t for t in draft["tracks"] if t["type"] == "text"]
    assert len(text_tracks) == 2, f"텍스트 트랙이 {len(text_tracks)}개다(자막+워터마크=2)"
    # 워터마크는 영상 전체 길이를 덮는다
    total = draft["duration"]
    wm_track = [t for t in text_tracks if len(t["segments"]) == 1
                and t["segments"][0]["target_timerange"]["duration"] == total]
    assert wm_track, "워터마크가 영상 전체에 안 깔린다"


def test_no_watermark_keeps_old_tracks():
    """★회귀 0: 워터마크가 없으면 트랙 구성이 종전 그대로다."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t")
    assert [t["type"] for t in draft["tracks"]] == ["video", "audio", "text"]
    for bad in (None, {}, {"watermark": None}, {"watermark": {"text": "  "}}):
        d2, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                               tts_paths=_TTS, asset_paths=_ASSET, project_name="t", deco=bad)
        assert [t["type"] for t in d2["tracks"]] == ["video", "audio", "text"], bad


# ── 🖼 꾸미기 틀(템플릿)도 따라간다 — 고객 제보 3단계 ──────────────────────
def _tpl_deco(span="full", alpha=1):
    return {"template": {"_capcut_path": "C:/cap/p/deco_frame.png",
                         "span": span, "alpha": alpha}}


def _photos(draft):
    return [m for m in draft["materials"]["videos"] if m["type"] == "photo"]


def test_template_frame_reaches_draft():
    """★뿌리: 꾸미기 틀 PNG가 캡컷 타임라인에 실제로 얹힌다(종전엔 아예 안 갔다)."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                              deco=_tpl_deco())
    ph = _photos(draft)
    assert len(ph) == 1, f"틀 이미지가 없거나 여러 개다: {len(ph)}"
    assert ph[0]["path"].endswith("deco_frame.png")
    assert ph[0]["has_audio"] is False, "이미지에 오디오가 붙으면 캡컷이 이상하게 다룬다"


def test_template_is_above_video_below_caption():
    """★쌓임 순서: 소스 영상 위 · 자막 아래. 자막을 덮으면 글자가 안 보인다."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                              deco=_tpl_deco())
    vid_tracks = [t for t in draft["tracks"] if t["type"] == "video"]
    assert len(vid_tracks) == 2, "틀이 별도 영상 트랙으로 안 올라갔다"
    tpl_seg = vid_tracks[1]["segments"][0]
    src_seg = vid_tracks[0]["segments"][0]
    cap_seg = [t for t in draft["tracks"] if t["type"] == "text"][0]["segments"][0]
    assert src_seg["track_render_index"] < tpl_seg["track_render_index"] < \
        cap_seg["track_render_index"], "쌓임 순서가 어긋났다(영상 < 틀 < 자막)"


def test_template_span_first_covers_only_first_beat():
    """★span='first'는 첫 비트만 덮는다 — 우리 렌더와 같은 규칙이어야 한다."""
    full, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                             tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                             deco=_tpl_deco("full"))
    first, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                              deco=_tpl_deco("first"))
    dur_full = [t for t in full["tracks"] if t["type"] == "video"][1]["segments"][0]
    dur_first = [t for t in first["tracks"] if t["type"] == "video"][1]["segments"][0]
    assert dur_full["target_timerange"]["duration"] == full["duration"]
    assert dur_first["target_timerange"]["duration"] == cd._us(_TIMELINE[0]["dur"])
    assert dur_first["target_timerange"]["duration"] < dur_full["target_timerange"]["duration"]


def test_template_alpha_applies():
    """투명도를 주면 그대로 반영된다."""
    draft, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t",
                              deco=_tpl_deco(alpha=0.5))
    seg = [t for t in draft["tracks"] if t["type"] == "video"][1]["segments"][0]
    assert abs(seg["clip"]["alpha"] - 0.5) < 0.01


def test_no_template_keeps_old_tracks():
    """★회귀 0: 틀이 없으면 트랙 구성이 종전 그대로다."""
    for bad in (None, {}, {"template": None}, {"template": {}},
                {"template": {"span": "full"}}):        # _capcut_path 없음
        d, _ = cd.build_draft(plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t", deco=bad)
        assert [t["type"] for t in d["tracks"]] == ["video", "audio", "text"], bad
        assert not _photos(d)


# ── 최종렌더에 있던 것이 캡컷에도 간다(2026-08-30 전구간 점검) ────────────────
# 점검 실측: 머리카피·BGM·효과음·컷어웨이·장면확대가 capcut_draft에 **grep 0건**이었다.
# 즉 완성본과 캡컷이 서로 다른 영상이었다. 아래는 각 재료가 실제로 트랙에 얹히는지 본다.

def _tracks_of(draft, kind):
    return [t for t in draft["tracks"] if t["type"] == kind]


def test_머리카피_PNG가_영상트랙에_얹힌다():
    draft, _ = cd.build_draft(
        plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC, tts_paths=_TTS,
        asset_paths=_ASSET, project_name="테스트",
        headcopy_layer={"_capcut_path": "C:/cap/p/headcopy.png", "t0": 0.0, "dur": 2.0})
    photos = [m for m in draft["materials"]["videos"] if m.get("type") == "photo"]
    assert any(m["path"].endswith("headcopy.png") for m in photos), "머리카피 PNG가 없다"
    seg = next(s for t in _tracks_of(draft, "video") for s in t["segments"]
               if s["material_id"] in {m["id"] for m in photos})
    assert seg["target_timerange"] == {"start": 0, "duration": 2_000_000}
    assert seg["track_render_index"] == 1, "틀(2) 아래·소스(0) 위여야 한다(렌더 쌓임과 동일)"


def test_머리카피_구간은_렌더규칙과_같다():
    """마지막 비트 전까지만 — video_assemble.headcopy_span 한 곳이 정한다."""
    from shopping_shorts import video_assemble as va
    assert va.headcopy_span(_TIMELINE) == (0.0, 2.0)      # 마지막 비트 t0=2.0
    assert va.headcopy_span(_TIMELINE[:1]) == (0.0, 2.0)  # 비트 1개면 전체


def test_BGM이_자기_오디오트랙에_붙는다():
    draft, _ = cd.build_draft(
        plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC, tts_paths=_TTS,
        asset_paths=_ASSET, project_name="테스트",
        bgm_layer={"_capcut_path": "C:/cap/p/bgm.mp3", "dur": 60.0, "volume": 20})
    bgm = next(m for m in draft["materials"]["audios"] if m["path"].endswith("bgm.mp3"))
    segs = [s for t in _tracks_of(draft, "audio") for s in t["segments"]
            if s["material_id"] == bgm["id"]]
    assert len(segs) == 1
    assert segs[0]["volume"] == 0.2, "제작소 볼륨(20%)이 안 따라갔다"
    # 영상 전체(3.5초)를 넘지 않는다 — 60초 음원이 타임라인을 늘리면 안 된다
    assert segs[0]["target_timerange"]["duration"] == 3_500_000
    assert draft["duration"] == 3_500_000
    # TTS와 **다른 트랙**이어야 한다(같은 트랙이면 캡컷이 하나를 밀어낸다)
    tts_track = next(t for t in _tracks_of(draft, "audio")
                     if any(s["material_id"] != bgm["id"] for s in t["segments"]))
    assert bgm["id"] not in {s["material_id"] for s in tts_track["segments"]}


def test_효과음이_타점에_꽂힌다():
    draft, _ = cd.build_draft(
        plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC, tts_paths=_TTS,
        asset_paths=_ASSET, project_name="테스트",
        sfx_layers=[{"_capcut_path": "C:/cap/p/sfx_00.mp3", "at": 2.0, "dur": 0.8,
                     "volume": 60}])
    sfx = next(m for m in draft["materials"]["audios"] if m["path"].endswith("sfx_00.mp3"))
    seg = next(s for t in _tracks_of(draft, "audio") for s in t["segments"]
               if s["material_id"] == sfx["id"])
    assert seg["target_timerange"] == {"start": 2_000_000, "duration": 800_000}
    assert seg["volume"] == 0.6


def test_효과음_타점은_렌더와_같은_함수가_준다():
    """position 3종(first/last/transition)을 렌더와 한 곳에서 계산한다."""
    from shopping_shorts import video_assemble as va
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": 2.0, "narration": "첫 장면",
           "sfx": {"position": "transition"}},
          {"beat_idx": 1, "t0": 2.0, "dur": 1.5, "narration": "둘째 장면",
           "sfx": {"position": "first"}}]
    ev = va.sfx_events_for(tl, {0: "a.mp3", 1: "b.mp3"})
    assert ev[0] == ("a.mp3", 2.0)     # transition = 칸이 끝나는 순간
    assert ev[1] == ("b.mp3", 2.0)     # first = 칸 시작
    assert va.sfx_events_for(tl, {}) == []      # 경로 없으면 안 넣는다


def test_컷어웨이가_비트_위에_얹힌다():
    draft, _ = cd.build_draft(
        plan=_PLAN, timeline=_TIMELINE, source_video_paths=_SRC, tts_paths=_TTS,
        asset_paths=_ASSET, project_name="테스트",
        cutaway_layers={1: {"_capcut_path": "C:/cap/p/cutaway_01.mp4", "dur": 5.0}})
    mat = next(m for m in draft["materials"]["videos"]
               if m["path"].endswith("cutaway_01.mp4"))
    seg = next(s for t in _tracks_of(draft, "video") for s in t["segments"]
               if s["material_id"] == mat["id"])
    # 창 = [비트 t0, min(자산길이, 비트길이)] — 렌더(_render_mix)와 같은 규칙
    assert seg["target_timerange"] == {"start": 2_000_000, "duration": 1_500_000}
    assert seg["track_render_index"] == 1
    assert seg["volume"] == 0.0, "b-roll은 소리를 버린다"


def test_장면확대가_세그먼트_배율로_간다():
    plan = json.loads(json.dumps(_PLAN))
    plan["beats"][0]["scene_zoom"] = 1.6
    draft, _ = cd.build_draft(
        plan=plan, timeline=_TIMELINE, source_video_paths=_SRC, tts_paths=_TTS,
        asset_paths=_ASSET, project_name="테스트")
    vids = [m for m in draft["materials"]["videos"] if m.get("type") == "video"]
    segs = [s for t in _tracks_of(draft, "video") for s in t["segments"]
            if s["material_id"] in {m["id"] for m in vids}]
    assert segs[0]["clip"]["scale"] == {"x": 1.6, "y": 1.6}
    assert segs[1]["clip"]["scale"] == {"x": 1.0, "y": 1.0}, "확대 없는 비트는 그대로"


def test_재료가_없으면_트랙도_안_생긴다():
    """빈 트랙을 넣으면 캡컷이 draft를 못 읽을 수 있다 — 종전 동작 유지 확인."""
    draft, _ = _build()
    assert {t["type"]: len(t["segments"]) for t in draft["tracks"]} == {
        "video": 2, "audio": 2, "text": 2}


def test_caption_split_into_phrases_like_render():
    """★2026-09-03 실물: 캡컷엔 비트 문장이 통째로 한 줄이라 화면 밖으로 넘쳤다.
    렌더와 같은 규칙(video_assemble.caption_schedule)으로 구절을 쪼개 순차 세그먼트로 싣는다."""
    from shopping_shorts.video_assemble import caption_schedule
    long_tl = [{"beat_idx": 0, "t0": 0.0, "dur": 6.0,
                "narration": "요즘 사람들 사이에서 엉뚱한 용도로 대박 난 물건이 하나 있음 원래대로라면 의류 상표나 택을 붙이는 용도로 쓰는 게 정석이었음"}]
    long_plan = {"beats": [{"beat_idx": 0, "narration": long_tl[0]["narration"],
                            "primary": {"video_id": "s0", "start": 0, "end": 6.0}}]}
    draft, _ = cd.build_draft(plan=long_plan, timeline=long_tl, source_video_paths=_SRC,
                              tts_paths=_TTS, asset_paths=_ASSET, project_name="t")
    txt = next(t for t in draft["tracks"] if t["type"] == "text")
    sched = caption_schedule(long_tl[0], tail=0.5)
    assert len(sched) >= 2, "긴 문장이 안 쪼개졌다"
    assert len(txt["segments"]) == len(sched), "캡컷 세그먼트 수 ≠ 렌더 구절 수"
    starts = [s["target_timerange"]["start"] for s in txt["segments"]]
    assert starts == sorted(starts) and starts[0] == 0
    for s, (phrase, st, en) in zip(txt["segments"], sched):
        assert s["target_timerange"]["start"] == cd._us(st)
        assert s["target_timerange"]["duration"] == cd._us(en - st)
    texts = {m["id"]: json.loads(m["content"])["text"] for m in draft["materials"]["texts"]}
    assert " ".join(texts[s["material_id"]] for s in txt["segments"]).replace(" ", "") \
        == "".join(p for p, _, _ in sched).replace(" ", "")
