import subprocess

import pytest
from shopping_shorts import scene_assets, scene_cut


def _fake_run_ok(created=None):
    """ffmpeg 성공 시뮬 — 실제로 만들었을 파일을 테스트가 대신 생성.

    **kwargs로 받는 이유: scene_assets.subprocess와 scene_cut.subprocess는 같은
    subprocess 모듈 객체를 가리키므로(둘 다 import subprocess), 여기서
    monkeypatch.setattr(scene_assets.subprocess, "run", ...)를 하면 scene_cut의
    _ffprobe(text=True, stdin=...)도 이 fake를 탄다. 위치/제한 키워드만 받으면
    TypeError로 죽는다."""
    calls = []

    def run(cmd, capture_output=True, check=False, **kwargs):
        calls.append(cmd)
        if created:
            created.write_bytes(b"out")

        class R:
            returncode = 0
            stderr = b""
            stdout = ""
        return R()
    run.calls = calls
    return run


def _fake_run_fail(cmd, capture_output=True, check=False, **kwargs):
    class R:
        returncode = 1
        stderr = b"ffmpeg: error"
        stdout = ""
    return R()


def test_make_clip_cuts_segment_and_normalizes_spec(monkeypatch, tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"fake")
    out = tmp_path / "clip.mp4"
    run = _fake_run_ok(created=out)
    # video_fps는 scene_cut을 통해 진짜 subprocess.run(text=/stdin= 사용)을 부르므로
    # 이 파일의 단순 fake run(위치/제한된 키워드 인자만 받음)으로는 흉내낼 수 없다 —
    # ffprobe 왕복 자체를 건너뛰도록 fps를 직접 고정한다(30.0, 3.0/5.5초가 정확히
    # 프레임 경계라 -ss/프레임수 계산이 옛 값과 동일하게 떨어진다).
    monkeypatch.setattr(scene_assets.scene_cut, "video_fps", lambda p: 30.0)
    monkeypatch.setattr(scene_assets.subprocess, "run", run)

    result = scene_assets.make_clip(src, 3.0, 5.5, out)

    assert result == out and out.exists()
    cmd = run.calls[0]
    joined = " ".join(str(x) for x in cmd)
    assert "-ss" in cmd and "3.000000" in joined       # 시작점(프레임 정렬, 90/30)
    # ★프레임 절단 — 초 길이(-t)가 아니라 프레임 수(-frames:v)로 자른다(설계 §3.4).
    # 90프레임(3.0s)~165프레임(5.5s) 직전 = 75프레임.
    assert "-frames:v" in cmd and "75" in joined
    assert "-t" not in cmd
    # 페이즈2 concat이 -c copy라 규격이 다르면 안 붙는다 — 1080x1920/30fps/libx264/aac 고정
    assert "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" in joined
    assert "-r" in cmd and "30" in cmd
    assert "libx264" in cmd and "aac" in cmd and "yuv420p" in cmd


def test_make_clip_raises_on_ffmpeg_failure(monkeypatch, tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"fake")
    # 위와 같은 이유로 fps 조회는 고정하고, 실제 컷 단계에서만 ffmpeg 실패를 흉내낸다.
    monkeypatch.setattr(scene_assets.scene_cut, "video_fps", lambda p: 30.0)
    monkeypatch.setattr(scene_assets.subprocess, "run", _fake_run_fail)

    with pytest.raises(RuntimeError, match="ffmpeg"):
        scene_assets.make_clip(src, 0, 2, tmp_path / "clip.mp4")


def test_make_clip_rejects_non_positive_span(tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"fake")

    with pytest.raises(ValueError, match="구간"):
        scene_assets.make_clip(src, 5.0, 5.0, tmp_path / "clip.mp4")
    with pytest.raises(ValueError, match="구간"):
        scene_assets.make_clip(src, 5.0, 2.0, tmp_path / "clip.mp4")


def test_extract_audio_produces_mp3(monkeypatch, tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")
    out = tmp_path / "sfx.mp3"
    run = _fake_run_ok(created=out)
    monkeypatch.setattr(scene_assets.subprocess, "run", run)

    result = scene_assets.extract_audio(clip, out)

    assert result == out and out.exists()
    cmd = run.calls[0]
    assert "-vn" in cmd                       # 영상 버리고 오디오만
    assert "libmp3lame" in " ".join(str(x) for x in cmd)


def test_extract_audio_raises_on_failure(monkeypatch, tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")
    monkeypatch.setattr(scene_assets.subprocess, "run", _fake_run_fail)

    with pytest.raises(RuntimeError, match="ffmpeg"):
        scene_assets.extract_audio(clip, tmp_path / "sfx.mp3")


def test_make_poster_delegates_to_frame_extract(monkeypatch, tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake")
    out = tmp_path / "poster.jpg"
    seen = {}

    def fake_extract(video_path, dest_dir, timestamp_sec, filename="frame_hint.jpg"):
        seen.update(video_path=video_path, dest_dir=dest_dir,
                    timestamp_sec=timestamp_sec, filename=filename)
        out.write_bytes(b"jpg")
        return out
    monkeypatch.setattr(scene_assets.frame_extract, "extract_frame_at", fake_extract)

    result = scene_assets.make_poster(media, out)

    assert result == out
    assert seen["video_path"] == media
    assert seen["dest_dir"] == tmp_path
    assert seen["timestamp_sec"] == 0
    assert seen["filename"] == "poster.jpg"


def test_make_poster_returns_none_on_failure(monkeypatch, tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake")
    monkeypatch.setattr(scene_assets.frame_extract, "extract_frame_at",
                        lambda *a, **k: None)

    # 썸네일은 없어도 되는 것 — 예외 대신 None으로 파이프라인 유지
    assert scene_assets.make_poster(media, tmp_path / "poster.jpg") is None


# ── 리뷰 Important I-3 회귀 테스트 (2026-07-15) ──
# `-ss 0` 위치탐색이 image2 디먹서(png/jpg/jpeg)에서 0프레임을 내 항상 실패했다(ffmpeg 8.1.1
# 실증). 정지이미지는 frame_extract.extract_frame_at(=-ss 0 경로)를 아예 타지 않고 별도
# 경로로 처리돼야 한다.

def test_make_poster_still_image_does_not_delegate_to_frame_extract(monkeypatch, tmp_path):
    media = tmp_path / "arrow.jpg"
    media.write_bytes(b"fake-jpg")
    out = tmp_path / "poster.jpg"

    def boom(*a, **k):
        raise AssertionError("정지이미지는 -ss 0 경로(extract_frame_at)를 타면 안 된다")
    monkeypatch.setattr(scene_assets.frame_extract, "extract_frame_at", boom)

    seen_cmd = {}
    def fake_run(cmd, capture_output=True, check=False):
        seen_cmd["cmd"] = cmd
        out.write_bytes(b"poster-bytes")
        class R:
            returncode = 0
            stderr = b""
        return R()
    monkeypatch.setattr(scene_assets.subprocess, "run", fake_run)

    result = scene_assets.make_poster(media, out)

    assert result == out
    assert result.exists()
    assert "-ss" not in seen_cmd["cmd"]        # 버그의 직접 원인이었던 플래그가 빠졌는지 확인
    assert str(media) in seen_cmd["cmd"]


@pytest.mark.parametrize("ext", [".png", ".jpg", ".jpeg"])
def test_make_poster_still_image_covers_all_broken_extensions(monkeypatch, tmp_path, ext):
    media = tmp_path / f"arrow{ext}"
    media.write_bytes(b"fake-image")
    out = tmp_path / "poster.jpg"
    monkeypatch.setattr(scene_assets.frame_extract, "extract_frame_at",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("잘못된 경로")))
    monkeypatch.setattr(scene_assets.subprocess, "run", _fake_run_ok(out))

    assert scene_assets.make_poster(media, out) == out


def test_make_poster_still_image_returns_none_on_ffmpeg_failure(monkeypatch, tmp_path):
    media = tmp_path / "arrow.png"
    media.write_bytes(b"fake-png")

    def fake_run(cmd, capture_output=True, check=False):
        class R:
            returncode = 1
            stderr = b"ffmpeg: error"
        return R()
    monkeypatch.setattr(scene_assets.subprocess, "run", fake_run)

    assert scene_assets.make_poster(media, tmp_path / "poster.jpg") is None


def test_make_poster_still_gif_and_webp_keep_using_frame_extract(monkeypatch, tmp_path):
    # gif/webp는 -ss 0으로도 정상(다른 디먹서, 리뷰 실증) — 회귀 방지로 기존 경로 유지 확인.
    for ext in (".gif", ".webp"):
        media = tmp_path / f"anim{ext}"
        media.write_bytes(b"fake-anim")
        out = tmp_path / "poster.jpg"
        seen = {}

        def fake_extract(video_path, dest_dir, timestamp_sec, filename="frame_hint.jpg"):
            seen["called"] = True
            out.write_bytes(b"jpg")
            return out
        monkeypatch.setattr(scene_assets.frame_extract, "extract_frame_at", fake_extract)

        result = scene_assets.make_poster(media, out)

        assert result == out
        assert seen.get("called") is True


def test_probe_duration_parses_ffprobe(monkeypatch, tmp_path):
    def fake_run(cmd, capture_output=True, check=False):
        assert "ffprobe" in cmd[0]

        class R:
            returncode = 0
            stdout = b"2.53\n"
            stderr = b""
        return R()
    monkeypatch.setattr(scene_assets.subprocess, "run", fake_run)

    assert scene_assets.probe_duration(tmp_path / "x.mp4") == 2.53


def test_probe_duration_returns_zero_on_failure(monkeypatch, tmp_path):
    def fake_run(cmd, capture_output=True, check=False):
        class R:
            returncode = 1
            stdout = b""
            stderr = b"err"
        return R()
    monkeypatch.setattr(scene_assets.subprocess, "run", fake_run)

    assert scene_assets.probe_duration(tmp_path / "x.mp4") == 0.0


def test_probe_duration_survives_missing_ffprobe(monkeypatch, tmp_path):
    # ffprobe가 없으면 run은 returncode가 아니라 FileNotFoundError를 던진다.
    # 길이는 표시용이므로 저장 자체가 터지면 안 된다.
    def boom(cmd, capture_output=True, check=False):
        raise FileNotFoundError("ffprobe")
    monkeypatch.setattr(scene_assets.subprocess, "run", boom)

    assert scene_assets.probe_duration(tmp_path / "x.mp4") == 0.0


def test_output_dimensions_match_video_assemble():
    """scene_assets와 video_assemble의 출력 규격이 일치해야 한다.
    페이즈2에서 concat -c copy로 자산 클립을 비트 클립과 붙이기 때문에
    규격이 어긋나면 렌더가 깨진다."""
    from shopping_shorts import video_assemble

    assert scene_assets._OUT_W == video_assemble._OUT_W
    assert scene_assets._OUT_H == video_assemble._OUT_H


def test_autotag_returns_draft_from_gemini(monkeypatch, tmp_path):
    f1 = tmp_path / "f1.jpg"
    f1.write_bytes(b"jpgbytes")
    seen = {}

    def fake_vault_call(prompt, schema, max_tries=4):
        seen["prompt"] = prompt
        seen["schema"] = schema
        return {"scene_desc": "흰 가루를 숟가락으로 떠 그릇에 넣음", "role": "비법공개",
                "subject": "가루(밀가루·설탕류)", "tone": "비밀스러운·궁금",
                "keywords": ["숟가락", "가루"]}
    monkeypatch.setattr(scene_assets.edit_plan, "_vault_call", fake_vault_call)

    got = scene_assets.autotag([f1], {"category": "레시피", "caption": "이거 한 스푼이면 끝"})

    assert got["scene_desc"] == "흰 가루를 숟가락으로 떠 그릇에 넣음"
    assert got["role"] == "비법공개"
    assert got["subject"] == "가루(밀가루·설탕류)"
    assert got["keywords"] == ["숟가락", "가루"]
    # 프레임을 실제로 실어보냈는지(멀티모달) — contents가 파츠 리스트여야 한다
    assert isinstance(seen["prompt"], list)
    assert any(not isinstance(p, str) for p in seen["prompt"])   # 이미지 파트 존재
    assert any(isinstance(p, str) and "레시피" in p for p in seen["prompt"])  # 맥락 주입
    # 필드 생략 방지 — mime_type만으론 Gemini가 필드를 빠뜨린다(video_analysis.py:26)
    assert set(seen["schema"]["required"]) == {"scene_desc", "role", "subject", "tone", "keywords"}


def test_autotag_returns_shaped_empty_when_no_key(monkeypatch, tmp_path):
    f1 = tmp_path / "f1.jpg"
    f1.write_bytes(b"jpgbytes")
    monkeypatch.setattr(scene_assets.edit_plan, "_vault_call", lambda *a, **k: None)

    got = scene_assets.autotag([f1], {"category": "레시피"})

    # 무키/실패여도 예외 아님 — 사람이 수기 입력할 수 있게 형태만 온전한 빈 값
    assert got == {"scene_desc": "", "role": "", "subject": "", "tone": "", "keywords": []}


def test_autotag_with_no_frames_skips_gemini(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(scene_assets.edit_plan, "_vault_call",
                        lambda *a, **k: called.append(1) or {})

    got = scene_assets.autotag([], {"category": "레시피"})

    assert called == []   # 보낼 화면이 없으면 호출 자체를 안 함(비용 절약)
    assert got["keywords"] == []


def test_autotag_clamps_role_to_controlled_vocabulary(monkeypatch, tmp_path):
    f1 = tmp_path / "f1.jpg"
    f1.write_bytes(b"jpgbytes")
    monkeypatch.setattr(scene_assets.edit_plan, "_vault_call",
                        lambda *a, **k: {"scene_desc": "x", "role": "아무말역할",
                                         "subject": "s", "tone": "t", "keywords": "a,b"})

    got = scene_assets.autotag([f1], {})

    assert got["role"] == ""            # 통제어휘 밖은 버림(사람이 고르게)
    assert got["keywords"] == ["a", "b"]  # 문자열로 와도 list로 정규화


def test_autotag_handles_non_dict_from_vault_call(monkeypatch, tmp_path):
    """_vault_call이 dict가 아닌 값(list/str/int)을 반환해도 예외 없이 형태만 온전한 빈 값 반환.

    Task4의 /api/scene/save/prepare 라우트가 예외처리 없이 autotag 결과를 쓰므로,
    비-dict 반환 시 AttributeError 대신 반드시 형태가 온전한 빈 값을 보장해야 한다.
    """
    f1 = tmp_path / "f1.jpg"
    f1.write_bytes(b"jpgbytes")

    for non_dict in [[], "string", 5]:  # list, str, int 세 경우
        monkeypatch.setattr(scene_assets.edit_plan, "_vault_call",
                          lambda *a, **k: non_dict)
        got = scene_assets.autotag([f1], {"category": "테스트"})
        # 어떤 비-dict가 와도 항상 형태가 온전한 빈 값
        assert got == {"scene_desc": "", "role": "", "subject": "", "tone": "", "keywords": []}


def test_autotag_prompt_separates_evidence_for_desc_and_role():
    p = scene_assets._AUTOTAG_PROMPT
    assert "자막" in p                      # role의 근거가 자막임을 명시
    assert "나쁜 예" in p                   # scene_desc의 추측 금지는 유지
    assert "한 스푼" in p                   # subject 모호금지 규칙 유지(적대적 검증 통과분)
    assert "자막이 없으면" in p             # 자막 없으면 role 공란


def test_autotag_prompt_keeps_controlled_roles():
    p = scene_assets._AUTOTAG_PROMPT.format(
        category="레시피", caption="c", script="s", roles="|".join(scene_assets._ROLES))
    assert "비법공개" in p and "CTA" in p


def _count_frames(p):
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-count_frames", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True,
                       stdin=subprocess.DEVNULL)
    return int(r.stdout.strip())


def test_make_clip_cuts_exact_frame_count_on_unaligned_start(tmp_path):
    """★4.13초처럼 프레임 경계가 아닌 시각을 줘도 프레임이 새지 않아야 한다.
    실측 결함: -ss 4.13 → ffmpeg가 4.1333에 붙고 -t 1.47을 더해 5.6033이 되어
    5.600의 다음 컷 첫 프레임이 1장 딸려 들어왔다(설계 §3.4)."""
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=320x568:rate=30:duration=8",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)
    out = tmp_path / "clip.mp4"
    scene_assets.make_clip(src, 4.13, 5.60, out)
    # 프레임 124(=round(4.1333*30))부터 168(=round(5.60*30)) 직전까지 = 44프레임
    assert _count_frames(out) == 44
