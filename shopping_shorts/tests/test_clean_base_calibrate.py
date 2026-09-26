# -*- coding: utf-8 -*-
"""옛 청소본 컷별 밀림 보정 v3 (clean_base.calibrate) · 정본 경로 절대화 (2026-09-27).

v2(회색 절대차·프레임 1장)는 job 62ed6bf66eb9 9번 칸에서 -0.333초를 남겼다. v3는 영상 비교 도구와 같은
특징(frame_match)으로 컷 안 세 지점을 찾는다. 여기선 **정답을 아는 가짜 청소본**을 만들어 잰다:
  원본 = 프레임마다 다른 무늬(10x10 칸 무작위 회색) 30fps.
  가짜 청소본 = 원본 컷 세 개를 컷 지도(fin)보다 3·7·11프레임 늦게 이어 붙이고 빈 자리는 딴 무늬로 채운 것.
★원본은 lavfi 대신 numpy 무늬를 ffmpeg(rawvideo 입력)로 굽는다 — lavfi 단색·색 변화 화면은 특징이 z정규화로
  0이 돼(단색 = 무늬 없음) 밀림을 잴 수 없다. 실제 영상처럼 칸마다 무늬가 다른 화면이 필요하다.
"""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from shopping_shorts import clean_base as cb
from shopping_shorts import frame_match as fm

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")

FPS = 30


def _pattern(rng):
    """90x160 한 장 — 16x9 칸 무작위 회색(칸 10px)."""
    g = rng.integers(0, 256, size=(16, 9), dtype=np.uint8)
    img = np.kron(g, np.ones((10, 10), np.uint8))          # 160x90
    return np.repeat(img[:, :, None], 3, axis=2)


def _encode(frames, path):
    h, w = frames.shape[1:3]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
                    "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12", "-g", "1", "-pix_fmt", "yuv444p",
                    str(path)], input=frames.tobytes(), check=True, timeout=60)


# (원본 시작초, 원본 읽는 길이 sdur, 완성본 길이 dur, 늦춘 프레임, 지웠나)
CUTS = [(0.0, 0.8, 0.8, 3, True),
        (1.0, 0.8, 0.8, 7, False),          # 부분 청소 정본의 안 지운 컷도 같은 조립본에서 왔다 — 똑같이 잰다
        (2.0, 0.6, 0.66, 11, True)]         # 느리게(1.1배) 늘린 컷


@pytest.fixture
def fake(tmp_path):
    rng = np.random.default_rng(7)
    src = np.stack([_pattern(rng) for _ in range(int(3.5 * FPS))])
    _encode(src, tmp_path / "src.mp4")
    fins, t = [], 0.0
    for c in CUTS:
        fins.append(t)
        t += c[2]
    n = int(round((t + 0.6) * FPS))
    clean = np.stack([_pattern(rng) for _ in range(n)])     # 빈 자리 = 원본에 없는 무늬
    for (s0, sd, dur, lag, _cl), fin in zip(CUTS, fins):
        k = dur / sd
        for i in range(int(round(dur * FPS))):
            clean[int(round(fin * FPS)) + lag + i] = src[int(round(s0 * FPS)) + min(int(i / k), int(sd * FPS) - 1)]
    _encode(clean, tmp_path / "final_clean_x.mp4")
    cuts = [{"beat_idx": i, "video_id": "v", "src": s0, "sdur": sd, "dur": dur, "fin": round(fin, 3), "cleaned": cl}
            for i, ((s0, sd, dur, _lag, cl), fin) in enumerate(zip(CUTS, fins))]
    base = {"sig": "x", "path": str(tmp_path / "final_clean_x.mp4"), "cuts": cuts, "beat_keys": {}, "extras": {},
            "partial": True, "calibrated": 2}
    return tmp_path, base


def test_v3_measures_each_cut_offset_within_one_frame(fake):
    work, base = fake
    out = cb.calibrate(work, base, {"v": str(work / "src.mp4")})
    assert out["calibrated"] == cb.CAL_VERSION == 4
    got = [c.get("off", 0.0) for c in out["cuts"]]
    want = [lag / FPS for (_s, _sd, _d, lag, _c) in CUTS]
    for g, w in zip(got, want):
        assert abs(g - w) <= 1.0 / FPS + 1e-6, (got, want)
    assert out["cal_unsure"] == 0 and not any(c.get("cal_unsure") for c in out["cuts"])
    saved = json.loads((work / cb.BASE_FILE).read_text(encoding="utf-8"))
    assert [c.get("off") for c in saved["cuts"]] == [c.get("off") for c in out["cuts"]]
    # _cut_geom 이 fin+off 로 읽는다 → 청소본 좌표가 실제 장면 자리
    assert abs(cb._cut_geom(out["cuts"][2])[2] - (out["cuts"][2]["fin"] + 11 / FPS)) <= 1.0 / FPS + 1e-6


def test_constant_features_cannot_confirm_offsets(fake, monkeypatch):
    """사보타주: 특징이 상수면(어디든 닮았다) 세 지점이 한 밀림을 가리키지 못한다 → 못 잰 컷(cal_unsure),
    밀림은 이론값(여기선 0)만 남는다. 정답 3·7·11프레임과 달라진다."""
    monkeypatch.setattr(fm, "feats", lambda fr: np.zeros((len(fr), 12, 18), np.float32))
    work, base = fake
    out = cb.calibrate(work, base, {"v": str(work / "src.mp4")})
    assert out["cal_unsure"] == len(CUTS)
    assert all(c.get("cal_unsure") for c in out["cuts"])
    assert all(abs(c.get("off", 0.0) - lag / FPS) > 1.0 / FPS for c, (_s, _sd, _d, lag, _c) in zip(out["cuts"], CUTS))


def test_missing_source_inherits_prior_and_marks_unsure(fake):
    work, base = fake
    out = cb.calibrate(work, base, {})
    assert out["cal_unsure"] == len(CUTS) and "off" not in out["cuts"][0]


def test_old_frame_lag_theory():
    """옛 조립: 칸마다 ceil(tts*30)/30 - tts, 칸 안 컷마다 ceil(dur*30)/30 - dur 가 쌓인다."""
    cuts = [{"beat_idx": 0, "dur": 0.51, "fin": 0.0}, {"beat_idx": 0, "dur": 0.5, "fin": 0.51},
            {"beat_idx": 1, "dur": 1.0, "fin": 1.01}]
    lag = cb.old_frame_lag(cuts)
    assert lag[0] == 0.0
    assert abs(lag[1] - (16 / 30 - 0.51)) < 1e-9            # 0.51초 = 15.3프레임 → 16프레임
    assert abs(lag[2] - (31 / 30 - 1.01)) < 1e-9            # 칸 1.01초 = 30.3프레임 → 31프레임


def test_relative_base_path_resolves_from_repo_root(tmp_path, monkeypatch):
    """정본 경로가 'shopping_shorts/data/…' 상대경로여도 cwd 와 무관하게 저장소 루트 기준으로 읽는다."""
    root = tmp_path / "repo"
    f = root / "shopping_shorts" / "data" / "mix_jobs" / "j" / "final_clean_x.mp4"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"c" * 4096)
    ex = f.parent / "cb0_0.mp4"
    ex.write_bytes(b"c" * 4096)
    monkeypatch.setattr(cb, "_ROOT", root)
    rel = "shopping_shorts/data/mix_jobs/j/final_clean_x.mp4"
    (f.parent / cb.BASE_FILE).write_text(json.dumps({"sig": "x", "path": rel, "cuts": [],
                                                     "extras": {"cb0_0": {"path": "shopping_shorts/data/mix_jobs/j/cb0_0.mp4"}}}),
                                         encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    base = cb.load_base(f.parent)
    assert base is not None
    assert Path(base["path"]).is_absolute() and Path(base["path"]) == f
    assert Path(base["extras"]["cb0_0"]["path"]) == ex
    # 저장은 늘 절대경로
    cb._write(f.parent, {"sig": "x", "path": rel, "cuts": []})
    saved = json.loads((f.parent / cb.BASE_FILE).read_text(encoding="utf-8"))
    assert Path(saved["path"]).is_absolute() and Path(saved["path"]) == f


@pytest.fixture
def fake_short_piece(tmp_path):
    """옛 청소본 조각이 지도보다 짧은 경우(2026-09-27 a90253dd235b 3→4칸 경계):
    A 지도 fin 0·dur 1.2 인데 파일 안 A 는 3프레임 늦게 시작해 31프레임(1.033초, 0.167초 짧음)만 있고
    바로 다음 프레임(34)부터 B(지도 fin 1.2 = 36프레임)가 시작한다."""
    rng = np.random.default_rng(11)
    src = np.stack([_pattern(rng) for _ in range(int(3.5 * FPS))])
    _encode(src, tmp_path / "src.mp4")
    clean = np.stack([_pattern(rng) for _ in range(72)])
    clean[3:34] = src[0:31]                 # A: 원본 0~30프레임
    clean[34:58] = src[60:84]               # B: 원본 2.0초부터 0.8초
    _encode(clean, tmp_path / "final_clean_x.mp4")
    cuts = [{"beat_idx": 0, "video_id": "v", "src": 0.0, "sdur": 1.2, "dur": 1.2, "fin": 0.0},
            {"beat_idx": 1, "video_id": "v", "src": 2.0, "sdur": 0.8, "dur": 0.8, "fin": 1.2}]
    base = {"sig": "x", "path": str(tmp_path / "final_clean_x.mp4"), "cuts": cuts, "beat_keys": {}, "extras": {}}
    return tmp_path, base, src


def test_short_old_piece_never_reads_next_piece(fake_short_piece):
    """보정 뒤 A 컷을 렌더 컷 재생(replay_clips)으로 옮기면 청소본에서 읽는 프레임이 **전부 A 장면**이어야 한다.
    ★사보타주: _cut_geom 의 '다음 컷 시작에서 자르기'를 빼면 34~38프레임(B 장면)을 읽어 빨강."""
    work, base, src = fake_short_piece
    out = cb.calibrate(work, base, {"v": str(work / "src.mp4")})
    a, b = out["cuts"]
    assert abs(a["off"] - 3 / FPS) <= 1.0 / FPS + 1e-6 and abs(b["off"] - (-2 / FPS)) <= 1.0 / FPS + 1e-6, out["cuts"]
    cuts, miss = cb.replay_clips(out, [{"video_id": "v", "start": 0.0, "out_dur": 1.2, "src_dur": 1.2}])
    assert cuts and not miss
    ff = fm.feats(fm.frames(work / "final_clean_x.mp4"))
    fa = fm.feats(fm.frames(work / "src.mp4"))[0:36]
    fb = fm.feats(fm.frames(work / "src.mp4"))[60:84]
    js = [j for c in cuts for j in range(int(round(c["start"] * FPS)), int(round((c["start"] + c["sdur"]) * FPS)))]
    assert js and min(js) >= 3
    for j in js:
        da = np.abs(fa - ff[j]).mean(axis=(1, 2)).min()
        dbb = np.abs(fb - ff[j]).mean(axis=(1, 2)).min()
        assert da < dbb and da < 0.2, ("청소본 %d프레임은 A 장면이 아니다" % j, da, dbb, cuts)


def test_cut_geom_clamps_at_next_start_even_without_measure():
    """끝을 못 잰 컷(off_end 없음)도 다음 컷 청소본 시작에서 잘린다 — 원본 끝도 그만큼 당겨진다."""
    base = {"cuts": [{"video_id": "v", "src": 0.0, "sdur": 1.2, "dur": 1.2, "fin": 0.0, "off": 0.1, "cleaned": True},
                     {"video_id": "w", "src": 5.0, "sdur": 0.8, "dur": 0.8, "fin": 1.2, "off": -0.067, "cleaned": True}],
            "extras": {}}
    r = [x for x in cb._regions(base) if x[2] == "v"][0]
    assert abs(r[5] + (r[4] - r[3]) * r[6] - (1.2 - 0.067)) < 1e-6      # 청소본 끝 = B 시작
    assert cb.span_map(base, {"video_id": "v", "start": 0.0, "end": 1.2}) is None     # 없는 꼬리를 덮었다고 하지 않는다
