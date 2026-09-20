"""3단계 통합 속도가 미리보기·렌더·캡컷에서 갈리지 않는지 검증."""
import inspect
import re
import shutil
import subprocess

import pytest

from shopping_shorts import capcut_draft
from shopping_shorts import mix_pipeline
from shopping_shorts import video_assemble


def _beat(speed=1.2):
    return {
        "beat_idx": 0,
        "narration": "테스트 문장",
        "sync_speed": speed,
        "primary": {"video_id": "v", "seg_id": "v-0", "start": 0.0, "end": 10.0},
    }


def test_통합속도는_같은_원본구간을_빠르게_재생한다():
    clips = video_assemble.plan_beat_clips_for(_beat(1.2), 2.0, {"v": 30.0})
    assert sum(c["out_dur"] for c in clips) == pytest.approx(2.0)
    assert sum(c["src_dur"] for c in clips) == pytest.approx(2.4)
    assert clips[0]["src_dur"] / clips[0]["out_dur"] == pytest.approx(1.2)


def test_기본속도는_기존_1배속과_같다():
    clips = video_assemble.plan_beat_clips_for(_beat(1.0), 2.0, {"v": 30.0})
    assert sum(c["out_dur"] for c in clips) == pytest.approx(2.0)
    assert sum(c["src_dur"] for c in clips) == pytest.approx(2.0)


def test_tts도_잡기본속도에_상대배속을_한번만_곱한다():
    got = mix_pipeline.voice_for_beat({"voice_id": "a", "speed": 1.5}, _beat(1.2))
    assert got["voice_id"] == "a"
    assert got["speed"] == pytest.approx(1.8)


def test_음성스냅샷없는_옛작업도_실제기본속도에_상대배속한다():
    beat = _beat(1.4)
    base = mix_pipeline.base_voice_for_beat(None, beat)
    assert base["speed"] == pytest.approx(mix_pipeline._DEFAULT_VOICE["speed"])
    got = mix_pipeline.voice_for_beat(base, beat)
    assert got["speed"] == pytest.approx(mix_pipeline._DEFAULT_VOICE["speed"] * 1.4)


def test_절대값처럼_잘못저장된_첫배포_기본속도를_복구한다():
    beat = _beat(1.4)
    beat["voice_override"] = {"speed": 1.4}
    base = mix_pipeline.base_voice_for_beat(None, beat)
    assert base["speed"] == pytest.approx(mix_pipeline._DEFAULT_VOICE["speed"])
    assert mix_pipeline.voice_for_beat(base, beat)["speed"] == pytest.approx(2.24)


def test_저장된_칸별_성우톤은_배속을_바꿔도_보존되고_중복가속하지_않는다():
    beat = _beat(1.2)
    beat["voice_override"] = {
        "voice_id": "picked", "settings": {"style": 0.4}, "speed": 1.32,
    }
    base = mix_pipeline.base_voice_for_beat(
        {"voice_id": "default", "speed": 1.0}, beat)
    assert base == {
        "voice_id": "picked", "settings": {"style": 0.4}, "speed": 1.1,
    }
    beat["sync_speed"] = 1.3
    assert mix_pipeline.voice_for_beat(base, beat)["speed"] == pytest.approx(1.43)


def test_캡컷_speed_material도_공용계획의_배속을_쓴다():
    src, tts = "/real/v.mp4", "/real/b.mp3"
    draft, _ = capcut_draft.build_draft(
        plan={"beats": [_beat(1.2)]},
        timeline=[{"beat_idx": 0, "t0": 0.0, "dur": 2.0,
                   "narration": "테스트 문장"}],
        source_video_paths={"v": src}, tts_paths={0: tts},
        asset_paths={src: "C:/draft/v.mp4", tts: "C:/draft/b.mp3"},
        video_durs={src: 30.0}, project_name="speed")
    video_track = next(t for t in draft["tracks"] if t["type"] == "video")
    refs = set(video_track["segments"][0]["extra_material_refs"])
    speed_mat = next(m for m in draft["materials"]["speeds"] if m["id"] in refs)
    assert speed_mat["speed"] == pytest.approx(1.2)


def test_이미_렌더된_청소조각은_캡컷에서_이중가속하지_않는다():
    plan = {"beats": [_beat(1.2)]}
    out = mix_pipeline.plan_using_beat_clips(
        plan, {"cc0": "/tmp/cc0.mp4"}, [{"beat_idx": 0, "dur": 2.0}])
    assert "sync_speed" not in out["beats"][0]


def test_역변환한_청소조각은_캡컷_배속값을_보존한다():
    src, tts = "/tmp/cc0.mp4", "/tmp/b.mp3"
    plan = mix_pipeline.plan_using_beat_clips(
        {"beats": [_beat(0.8)]}, {"cc0": src},
        [{"beat_idx": 0, "dur": 2.0}], preserve_capcut_speed=True)
    beat = plan["beats"][0]
    assert beat["_capcut_baked_speed"] == pytest.approx(0.8)
    assert beat["primary"]["end"] == pytest.approx(1.6)
    assert "sync_speed" not in beat
    draft, _ = capcut_draft.build_draft(
        plan=plan,
        timeline=[{"beat_idx": 0, "t0": 0.0, "dur": 2.0,
                   "narration": "테스트 문장"}],
        source_video_paths={"cc0": src}, tts_paths={0: tts},
        asset_paths={src: "C:/draft/cc0.mp4", tts: "C:/draft/b.mp3"},
        video_durs={src: 1.6}, project_name="speed-clean")
    video_track = next(t for t in draft["tracks"] if t["type"] == "video")
    refs = set(video_track["segments"][0]["extra_material_refs"])
    speed_mat = next(m for m in draft["materials"]["speeds"] if m["id"] in refs)
    assert speed_mat["speed"] == pytest.approx(0.8)
    assert video_track["segments"][0]["target_timerange"]["duration"] == 2_000_000
    assert video_track["segments"][0]["source_timerange"]["duration"] == 1_600_000


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_구워진_청소조각을_캡컷_배속용_길이로_역변환한다(tmp_path):
    src = tmp_path / "cc0.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
        "-i", "testsrc2=s=160x284:r=30:d=2.0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ], check=True, stdin=subprocess.DEVNULL)
    clips = mix_pipeline.normalize_baked_clips_for_capcut(
        {"beats": [_beat(0.8)]}, {"cc0": str(src)},
        [{"beat_idx": 0, "dur": 2.0}], tmp_path)
    assert clips["cc0"] != str(src)
    assert video_assemble._probe_duration(clips["cc0"]) == pytest.approx(1.6, abs=0.08)


def test_렌더는_빠른_setpts도_적용한다():
    src = inspect.getsource(video_assemble._render_mix)
    assert "abs(factor - 1.0)" in src


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
def test_real_render_plays_scene_at_1_4x(tmp_path):
    src = tmp_path / "source.mp4"
    tts = tmp_path / "tts.wav"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=red:s=360x640:r=30:d=0.7",
        "-f", "lavfi", "-i", "color=green:s=360x640:r=30:d=0.7",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ], check=True, stdin=subprocess.DEVNULL)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo", "-t", "1.0", str(tts),
    ], check=True, stdin=subprocess.DEVNULL)
    plan = {"beats": [{
        **_beat(1.4), "target_seconds": 1.0,
        "primary": {"video_id": "v", "seg_id": "v-0", "start": 0.0, "end": 1.4},
    }]}
    out = video_assemble._render_mix(plan, {0: str(tts)}, {"v": str(src)}, tmp_path)
    # 출력 0.6초는 원본 약 0.84초이므로 빨강(0~0.7)을 지나 초록이어야 한다.
    stats = subprocess.run([
        "ffmpeg", "-v", "error", "-ss", "0.6", "-i", str(out),
        "-frames:v", "1", "-vf", "signalstats,metadata=print:file=-",
        "-f", "null", "-",
    ], check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    vavg = re.search(r"VAVG=(-?\d+)", stats)
    assert vavg and int(vavg.group(1)) < 150, "빠른 setpts가 빠져 아직 빨강 프레임임"
    assert video_assemble._probe_duration(out) == pytest.approx(
        1.0 + video_assemble._LAST_RUNOUT, abs=0.2)
