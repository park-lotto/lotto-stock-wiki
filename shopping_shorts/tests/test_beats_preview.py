from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


def _beats():
    return [
        {"beat_idx": 0, "narration": "이거 만들어줬더니", "primary": {"video_id": "s0", "start": 0.0, "end": 2.0}},
        {"beat_idx": 1, "narration": "딱 한 뼘이면 OK", "primary": {"video_id": "s0", "start": 2.0, "end": 4.0}},
    ]


def test_beats_preview_lists_captions(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j1", ["u0"], 20, "free")
    store.update_mix_job("j1", status="ready_for_review", edit_plan={"beats": _beats()})
    r = client.get("/api/produce/mix/beats_preview/j1")
    assert r.status_code == 200
    beats = r.json()["beats"]
    assert [b["caption"] for b in beats] == ["이거 만들어줬더니", "딱 한 뼘이면 OK"]
    assert beats[0]["total"] == 2 and beats[0]["i"] == 0


def test_beats_preview_empty_when_no_edit_plan(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j2", ["u0"], 20, "free")
    r = client.get("/api/produce/mix/beats_preview/j2")
    assert r.status_code == 200
    assert r.json() == {"beats": []}


import subprocess as _sp
from pathlib import Path


def test_extract_beat_frame_real_ffmpeg(tmp_path):
    from shopping_shorts import app as app_module
    work = tmp_path / "job"
    (work / "s0").mkdir(parents=True)
    src = work / "s0" / "clip.mp4"
    # 2초짜리 teal 세로 클립 생성(테스트 픽스처)
    _sp.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=teal:s=1080x1920:d=2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
            capture_output=True, stdin=_sp.DEVNULL)
    out = work / "beatframes" / "0.jpg"
    ok = app_module._extract_beat_frame(work, {"primary": {"video_id": "s0", "start": 0.5}}, out)
    assert ok and out.exists() and out.stat().st_size > 0


def test_extract_beat_frame_prefers_clean_source(tmp_path):
    """2단계 자막제거 청소본이 있으면 원본이 아니라 청소본에서 프레임을 뜬다.
    (2026-07-21 버그: 꾸미기 미리보기가 원본 glob만 써서 지운 자막이 살아있었다.)"""
    from shopping_shorts import app as app_module
    work = tmp_path / "job"
    (work / "s0").mkdir(parents=True)
    # 원본=teal, 청소본=maroon. 프레임 색으로 어느 소스를 썼는지 판별한다.
    orig = work / "s0" / "clip.mp4"
    clean = tmp_path / "s0_clean.mp4"
    for path, color in ((orig, "teal"), (clean, "maroon")):
        _sp.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=1080x1920:d=1",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
                capture_output=True, stdin=_sp.DEVNULL)
    out = work / "beatframes" / "0_clean.jpg"
    ok = app_module._extract_beat_frame(
        work, {"primary": {"video_id": "s0", "start": 0.3}}, out,
        clean_sources={"s0": str(clean)})
    assert ok and out.exists()
    # 뽑은 프레임의 평균색이 maroon(청소본)에 가까운지 = R이 G/B보다 확실히 큼.
    probe = _sp.run(["ffmpeg", "-i", str(out), "-vf",
                     "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                    capture_output=True, stdin=_sp.DEVNULL)
    rgb = probe.stdout[:3]
    assert len(rgb) == 3, "프레임 픽셀 추출 실패"
    r, g, b = rgb[0], rgb[1], rgb[2]
    assert r > g + 40 and r > b + 40, f"청소본(maroon) 대신 원본(teal)을 씀: rgb={r},{g},{b}"


def test_beats_preview_gives_segments_like_real_render(tmp_path, monkeypatch):
    """★자막 미리보기≠실제렌더 seam 봉인(2026-07-18 사장님 실측).

    예전엔 caption(narration 통째)만 줘서 미리보기가 문장 통째로 떴다. 실제 영상은
    _caption_segments로 2~3어절씩 쪼갠다 → "미리보기는 안 끊기는데 실제론 끊긴다".
    이제 실제 렌더와 같은 구절 분할(segs)과 있으면 실제 표시시간(durs)을 함께 준다.
    """
    from shopping_shorts import video_assemble
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j1", ["u0"], 20, "free")
    narr = "얼마 전 시댁 갔더니 어머님이 제 얼굴 보시곤 비싼 관리받았냐고"
    store.update_mix_job("j1", status="ready_for_review",
                         edit_plan={"beats": [{"beat_idx": 0, "narration": narr,
                                               "cap_durs": [0.8, 1.0, 1.1, 0.9],
                                               "primary": {"video_id": "s0", "start": 0.0, "end": 4.0}}]})
    b = client.get("/api/produce/mix/beats_preview/j1").json()["beats"][0]
    # segs가 실제 렌더가 쓰는 분할과 정확히 같아야 한다(같은 함수를 써야 미리보기가 안 거짓말한다).
    assert b["segs"] == video_assemble._caption_segments(narr)
    assert len(b["segs"]) >= 2                     # 문장이 통째로 안 나오고 쪼개졌다
    assert b["durs"] == [0.8, 1.0, 1.1, 0.9]       # 실제 표시시간도 함께 내린다
    assert b["caption"] == narr                    # 폴백용 통째는 유지(하위호환)


def test_beats_preview_durs_none_when_no_cap_durs(tmp_path, monkeypatch):
    """ASR 없어 cap_durs가 없으면 durs=None(미리보기는 균등 간격으로 폴백)."""
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j1", ["u0"], 20, "free")
    store.update_mix_job("j1", status="ready_for_review", edit_plan={"beats": _beats()})
    b = client.get("/api/produce/mix/beats_preview/j1").json()["beats"][0]
    assert b["durs"] is None
    assert len(b["segs"]) >= 1
