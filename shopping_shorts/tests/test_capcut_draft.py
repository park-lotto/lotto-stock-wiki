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
    assert seg1["target_timerange"] == {"start": 2_000_000, "duration": 1_500_000}
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
    assert n.startswith("써보면 놀라는 이것") and n.endswith("4541")   # 제목 앞, 짧은 id 접미
    n2 = a._capcut_project_name("454169a1zzzz", {}, {"beats": [{"narration": "딱 한 뼘이면 OK"}]})
    assert n2.startswith("딱 한 뼘이면 OK")                          # 헤드카피 없으면 첫 대사
    n3 = a._capcut_project_name("454169a1zzzz", {}, {})
    assert n3 == "쇼핑쇼츠_454169a1"                                  # 둘 다 없으면 옛 폴백


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
    assert seg["track_render_index"] == 2


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
    assert t["font_size"] > 16.0, f"크기(70)가 기본(16) 그대로다: {t['font_size']}"
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
    assert t["text_color"] == "#ffffff" and t["font_size"] == 16.0
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
    assert _texts(big)[0]["font_size"] <= 16.0 * 3
    assert _texts(tiny)[0]["font_size"] >= 16.0 * 0.3
