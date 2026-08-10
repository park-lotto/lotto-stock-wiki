import tempfile
from pathlib import Path
from shopping_shorts import mix_pipeline
from shopping_shorts.store import Store


def _dbpath():
    return Path(tempfile.mkdtemp()) / "t.db"


def test_run_mix_job_happy_path(monkeypatch):
    db = _dbpath()
    work = Path(tempfile.mkdtemp())
    s = Store(db)
    s.create_mix_job("j1", ["https://www.instagram.com/reel/AAA/",
                             "https://www.instagram.com/reel/BBB/"], 20, "free")

    monkeypatch.setattr(mix_pipeline, "download_any", lambda url, d: (str(Path(d) / "v.mp4"), ""))
    monkeypatch.setattr(mix_pipeline, "extract_script",
                        lambda path, video_id, caption="": {
                            "segments": [{"seg_id": f"{video_id}-0", "start": 0.0, "end": 2.0,
                                          "text": "t", "scene_desc": "s"}],
                            "full_text": "ft"})
    monkeypatch.setattr(mix_pipeline, "build_edit_plan",
                        lambda scripts, target_seconds, structure, **k: {
                            "structure": structure,
                            "beats": [{"beat_idx": 0, "role": "훅", "narration": "n",
                                       "target_seconds": 2,
                                       "primary": {"video_id": "s0", "seg_id": "s0-0",
                                                   "start": 0.0, "end": 2.0},
                                       "alternates": [], "effect": "cut"}],
                            "plagiarism_flags": []})
    monkeypatch.setattr(mix_pipeline.tts, "synthesize_best", lambda text, out, **k: out)
    # ★TTS를 가짜로 바꿨으면 후처리도 같이 꺼야 한다(2026-08-10).
    #   위 stub은 파일을 만들지 않고 경로만 돌려준다. 그런데 synthesize_line은 그 뒤
    #   audio_post.post_process를 부르고, 이건 **진짜 ffmpeg를 실행**한다 → 없는(혹은
    #   3바이트짜리) mp3에 "Invalid data found"로 죽어 job이 failed가 됐다.
    #   ffmpeg가 고장난 게 아니다 — 실제 파일로 같은 필터체인을 돌리면 rc=0으로 통과한다(실측).
    #   같은 파일 아래쪽 test_resynth_tts_job_applies_voice는 이미 이렇게 꺼두고 있다.
    monkeypatch.setattr(mix_pipeline.audio_post, "post_process", lambda *a, **k: a[1])

    mix_pipeline.run_mix_job("j1", db, work)
    job = s.get_mix_job("j1")
    assert job["status"] == "ready_for_review"
    assert job["extract"]["s0"]["segments"][0]["seg_id"] == "s0-0"
    assert job["edit_plan"]["beats"][0]["narration"] == "n"
    assert job["edit_plan"]["beats"][0]["tts_path"]  # 렌더가 의존하는 불변식


def test_run_mix_job_empty_edl_fails(monkeypatch):
    # 빈 EDL(추출 전량 실패/키 소진)은 ready_for_review로 오보고하지 않고 failed로 종료
    db = _dbpath()
    work = Path(tempfile.mkdtemp())
    s = Store(db)
    s.create_mix_job("je", ["https://www.instagram.com/reel/AAA/"], 20, "free")

    monkeypatch.setattr(mix_pipeline, "download_any", lambda url, d: (str(Path(d) / "v.mp4"), ""))
    monkeypatch.setattr(mix_pipeline, "extract_script",
                        lambda path, video_id, caption="": {"segments": [], "full_text": ""})
    monkeypatch.setattr(mix_pipeline, "build_edit_plan",
                        lambda scripts, target_seconds, structure, **k: {
                            "structure": structure, "beats": [], "plagiarism_flags": []})

    mix_pipeline.run_mix_job("je", db, work)
    job = s.get_mix_job("je")
    assert job["status"] == "failed"
    assert "EDL 비어있음" in job["error"]


def test_run_mix_job_failure_sets_status(monkeypatch):
    db = _dbpath()
    work = Path(tempfile.mkdtemp())
    s = Store(db)
    s.create_mix_job("j2", ["https://www.instagram.com/reel/AAA/"], 20, "free")

    def boom(url, d): raise RuntimeError("다운로드 실패")
    monkeypatch.setattr(mix_pipeline, "download_any", boom)

    mix_pipeline.run_mix_job("j2", db, work)
    job = s.get_mix_job("j2")
    assert job["status"] == "failed"
    assert "다운로드 실패" in job["error"]


def test_run_mix_job_unsupported_url_fails(monkeypatch):
    # download_any가 지원하지 않는 플랫폼(인스타/유튜브/틱톡 외)이면 다운로드 단계에서
    # 실패해야 한다(media_download.download_any를 실제로 통해 검증 — 네트워크 호출 없음).
    db = _dbpath()
    work = Path(tempfile.mkdtemp())
    s = Store(db)
    s.create_mix_job("jn", ["https://example.com/video/x"], 20, "free")
    mix_pipeline.run_mix_job("jn", db, work)
    job = s.get_mix_job("jn")
    assert job["status"] == "failed"
    assert "지원하지 않는 URL" in job["error"]


def test_retype_mix_job_regenerates_with_chosen_type(monkeypatch):
    # 사용자가 유형을 바꾸면 저장된 extract로 EDL+TTS만 재생성(재다운로드 없음)
    db = _dbpath()
    work = Path(tempfile.mkdtemp())
    s = Store(db)
    s.create_mix_job("jt", ["https://www.instagram.com/reel/AAA/"], 20, "free")
    s.update_mix_job("jt", extract={"s0": {"video_id": "s0", "full_text": "ft",
                     "segments": [{"seg_id": "s0-0", "start": 0.0, "end": 2.0,
                                   "text": "t", "scene_desc": "sc"}]}}, status="ready_for_review")

    got = {}
    def fake_build(scripts, target_seconds, structure, video_type=None, **k):
        got["video_type"] = video_type
        return {"structure": structure, "detected_type": video_type, "affiliate_target": "소금",
                "beats": [{"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
                           "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
                           "alternates": [], "effect": "cut"}], "plagiarism_flags": []}
    monkeypatch.setattr(mix_pipeline, "build_edit_plan", fake_build)
    monkeypatch.setattr(mix_pipeline.tts, "synthesize_best", lambda text, out, **k: out)
    # ★TTS를 가짜로 바꿨으면 후처리도 같이 꺼야 한다(2026-08-10).
    #   위 stub은 파일을 만들지 않고 경로만 돌려준다. 그런데 synthesize_line은 그 뒤
    #   audio_post.post_process를 부르고, 이건 **진짜 ffmpeg를 실행**한다 → 없는(혹은
    #   3바이트짜리) mp3에 "Invalid data found"로 죽어 job이 failed가 됐다.
    #   ffmpeg가 고장난 게 아니다 — 실제 파일로 같은 필터체인을 돌리면 rc=0으로 통과한다(실측).
    #   같은 파일 아래쪽 test_resynth_tts_job_applies_voice는 이미 이렇게 꺼두고 있다.
    monkeypatch.setattr(mix_pipeline.audio_post, "post_process", lambda *a, **k: a[1])

    mix_pipeline.retype_mix_job("jt", "recipe_secret", db, work)
    job = s.get_mix_job("jt")
    assert got["video_type"] == "recipe_secret"       # 사용자 선택 유형 명시 전달
    assert job["status"] == "ready_for_review"
    assert job["edit_plan"]["detected_type"] == "recipe_secret"
    assert job["edit_plan"]["beats"][0]["tts_path"]   # TTS 재생성됨


def test_retype_mix_job_no_extract_noop(monkeypatch):
    db = _dbpath()
    work = Path(tempfile.mkdtemp())
    s = Store(db)
    s.create_mix_job("jx", ["https://www.instagram.com/reel/AAA/"], 20, "free")
    # extract 없음 → 조용히 무시(상태 그대로)
    mix_pipeline.retype_mix_job("jx", "recipe_secret", db, work)
    assert s.get_mix_job("jx")["status"] == "downloading"


def test_source_video_id():
    assert mix_pipeline._source_video_id(0) == "s0"
    assert mix_pipeline._source_video_id(2) == "s2"


def test_run_render_happy_path(monkeypatch):
    db = _dbpath()
    work = Path(tempfile.mkdtemp())
    s = Store(db)
    s.create_mix_job("j3", ["url0"], 20, "free")

    edit_plan = {
        "structure": "free",
        "beats": [{"beat_idx": 0, "role": "훅", "narration": "n",
                   "target_seconds": 2,
                   "primary": {"video_id": "s0", "seg_id": "s0-0",
                               "start": 0.0, "end": 2.0},
                   "alternates": [], "effect": "cut",
                   "tts_path": str(work / "j3" / "tts" / "beat_0.mp3")}],
        "plagiarism_flags": [],
    }
    s.update_mix_job("j3", status="ready_for_review", edit_plan=edit_plan)

    # 소스 mp4 배치 (run_render가 glob으로 찾아야 함)
    src_dir = work / "j3" / "s0"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "vid.mp4").write_bytes(b"")

    captured = {}
    # **kw로 받는 이유(2026-08-10): run_render는 그동안 assemble에 인자를 계속 늘려왔다
    # (headcopy·caption_style·deco·cutaway_paths·sfx_paths). 고정 시그니처로 두면 인자가
    # 하나 늘 때마다 이 테스트가 TypeError로 죽는다 — 실제로 headcopy가 추가되며 죽어 있었다.
    # 이 테스트의 관심사는 '핵심 4개가 제대로 전달되는가'지 인자 개수가 아니므로 나머지는 흡수한다.
    def fake_assemble(plan, tts_paths, source_video_paths, out_path, clean_fn=None, **kw):
        captured["plan"] = plan
        captured["tts_paths"] = tts_paths
        captured["source_video_paths"] = source_video_paths
        captured["out_path"] = out_path
        captured["kw"] = kw
        Path(out_path).write_bytes(b"")
        return out_path
    monkeypatch.setattr(mix_pipeline, "assemble", fake_assemble)

    mix_pipeline.run_render("j3", db, work)

    job = s.get_mix_job("j3")
    assert job["status"] == "done"
    assert job["video_path"]

    # 파일명은 나레이션 **내용 해시**로 키잉된다(_beat_tts_path, 2026-07-27 실사고 대응:
    # B로 만들고 A로 고치면 자막은 A인데 음성은 B로 나갔다). 그래서 beat_0.mp3가 아니라
    # beat_0_<md5앞10>.mp3다. 여기에 해시를 손으로 박으면 나레이션 한 글자만 바뀌어도
    # 테스트가 깨지므로, **같은 함수로 기대값을 만들어** 규칙 자체를 고정한다.
    expected_tts = mix_pipeline._beat_tts_path(work / "j3" / "tts",
                                               edit_plan["beats"][0])
    assert captured["tts_paths"] == {0: expected_tts}
    # 규칙이 실제로 '내용 해시 키잉'인지도 같이 못박는다(옛 beat_0.mp3로 되돌아가면 잡힌다).
    assert Path(expected_tts).name.startswith("beat_0_")
    assert captured["source_video_paths"] == {"s0": str(src_dir / "vid.mp4")}


def test_mix_accepts_youtube_url(monkeypatch, tmp_path):
    from shopping_shorts import mix_pipeline as mp
    got = {}
    monkeypatch.setattr(mp, "download_any", lambda url, d: got.setdefault("urls", []).append(url) or (str(tmp_path / "x.mp4"), ""))
    # _prepare_sources 만 단위 검증(전체 잡 아님): youtube URL도 통과해야 함
    urls = ["https://www.youtube.com/watch?v=a", "https://www.tiktok.com/@u/video/1"]
    paths, captions, skipped = mp._prepare_sources(urls, tmp_path)
    assert len(paths) == 2 and got["urls"] == urls
    assert captions == {"s0": "", "s1": ""}
    assert skipped == []


def test_prepare_sources_carries_instagram_caption(monkeypatch, tmp_path):
    # 인스타 캡션 회귀 수정: download_any가 (path, caption)을 반환하면
    # _prepare_sources가 captions 딕셔너리에 그대로 실어야 한다(최종리뷰 IMPORTANT).
    from shopping_shorts import mix_pipeline as mp

    def fake_download(url, d):
        if "instagram" in url:
            return str(tmp_path / "ig.mp4"), "인스타 원본 캡션"
        return str(tmp_path / "yt.mp4"), ""
    monkeypatch.setattr(mp, "download_any", fake_download)

    urls = ["https://www.instagram.com/reel/AAA/", "https://www.youtube.com/watch?v=a"]
    paths, captions, skipped = mp._prepare_sources(urls, tmp_path)
    assert captions["s0"] == "인스타 원본 캡션"
    assert captions["s1"] == ""


def test_resynth_tts_job_applies_voice(monkeypatch, tmp_path):
    from shopping_shorts import mix_pipeline
    from shopping_shorts.store import Store

    captured = {}
    def fake_synth(text, out, **kw):
        captured["kw"] = kw
        from pathlib import Path
        Path(out).write_bytes(b"ID3"); return out
    monkeypatch.setattr(mix_pipeline.tts, "synthesize_best", fake_synth)
    monkeypatch.setattr(mix_pipeline.audio_post, "post_process", lambda *a, **k: a[1])

    db = tmp_path / "t.db"; s = Store(db)
    s.create_mix_job("j1", ["u"], 30, "구조")
    s.update_mix_job("j1", edit_plan={"structure": "구조", "beats": [
        {"beat_idx": 0, "narration": "안녕", "primary": {}}]})
    s.update_mix_job("j1", voice={"voice_id": "vZ",
        "settings": {"stability": 0.4, "similarity_boost": 0.75, "style": 0.3, "use_speaker_boost": True},
        "speed": 1.3, "silence_trim": "strong"})

    mix_pipeline.resynth_tts_job("j1", str(db), str(tmp_path / "work"))

    assert captured["kw"]["voice_id"] == "vZ"
    assert captured["kw"]["voice_settings"]["style"] == 0.3
    assert captured["kw"]["speed"] == 1.3
    assert s.get_mix_job("j1")["status"] == "ready_for_review"


def test_voice_params_extracts_pace_mode():
    """_voice_params가 voice 스냅샷의 pace_mode를 8번째로 실어 보낸다."""
    from shopping_shorts.mix_pipeline import _voice_params, _DEFAULT_VOICE
    on = _voice_params({"pace_mode": True})
    assert on[7] is True
    # 스냅샷에 명시하면 그 값이 그대로 간다 — 끄는 것도 반드시 먹혀야 한다.
    assert _voice_params({"pace_mode": False})[7] is False

    # ★빈 dict({})는 '미지정'이 아니라 **_DEFAULT_VOICE로 폴백**이다(mix_pipeline.py:118).
    #   그리고 그 기본 프리셋은 2026-07-25부터 pace_mode=True다(사장님 지시 —
    #   미리보기도 4단계 UI 기본처럼 ⚡속도감 모드를 켠다). 즉 여기서 True가 맞다.
    #   옛 테스트는 그 전 동작(False)을 그대로 들고 있어 실패했다 — 코드가 아니라
    #   테스트가 낡은 것이다. 기본값을 손으로 박아두면 프리셋을 바꿀 때 또 어긋나므로
    #   _DEFAULT_VOICE를 진실로 삼아 대조한다.
    assert _voice_params({})[7] is _DEFAULT_VOICE["pace_mode"]
    # voice 자체가 None일 때도 같은 기본으로 간다(스냅샷 없는 옛 job).
    assert _voice_params(None)[7] is _DEFAULT_VOICE["pace_mode"]
