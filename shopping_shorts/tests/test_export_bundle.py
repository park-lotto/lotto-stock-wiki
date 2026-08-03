"""내보내기 번들(캡컷 편집용) — SRT·스크립트·SEO 텍스트 + ZIP 조립 (설계 2026-07-20 §2)."""
import subprocess
import zipfile
from pathlib import Path

import pytest

from shopping_shorts import export_bundle as eb


# ── 순수 텍스트 로직 ──────────────────────────────────
def test_srt_ts_format():
    assert eb._srt_ts(0) == "00:00:00,000"
    assert eb._srt_ts(1.5) == "00:00:01,500"
    assert eb._srt_ts(3661.234) == "01:01:01,234"
    assert eb._srt_ts(-1) == "00:00:00,000"   # 음수는 0으로


_TIMELINE = [
    {"beat_idx": 0, "t0": 0.0, "dur": 2.5, "narration": "첫 문장이에요", "role": "훅"},
    {"beat_idx": 1, "t0": 2.5, "dur": 3.0, "narration": "  ", "role": "본문"},   # 빈 → 건너뜀
    {"beat_idx": 2, "t0": 5.5, "dur": 2.0, "narration": "마지막 문장", "role": "CTA"},
]


def test_build_srt_beat_cues_and_skip_empty():
    srt = eb.build_srt(_TIMELINE)
    # 빈 나레이션 비트는 큐로 안 나온다 → 번호는 1,2만
    assert "1\n00:00:00,000 --> 00:00:02,500\n첫 문장이에요" in srt
    assert "2\n00:00:05,500 --> 00:00:07,500\n마지막 문장" in srt
    assert "본문" not in srt and "3\n" not in srt.split("마지막")[0]


def test_build_srt_timing_uses_t0_and_dur():
    srt = eb.build_srt([{"beat_idx": 0, "t0": 10.0, "dur": 4.25, "narration": "x", "role": ""}])
    assert "00:00:10,000 --> 00:00:14,250" in srt


def test_build_script_text_roles():
    s = eb.build_script_text(_TIMELINE)
    assert "[훅] 첫 문장이에요" in s
    assert "[CTA] 마지막 문장" in s
    assert "본문" not in s   # 빈 나레이션 비트 제외


def test_build_seo_text():
    assert eb.build_seo_text(None) == ""
    assert eb.build_seo_text({}) == ""
    txt = eb.build_seo_text({"title": "제목이다", "tags": ["#a", "#b"], "description": "설명"})
    assert "[제목]\n제목이다" in txt and "#a #b" in txt and "[설명]\n설명" in txt


def test_safe_name():
    assert eb.safe_name("훅 scene!!") == "훅 scene"
    assert eb.safe_name("") == "export"
    assert eb.safe_name("", default="scene") == "scene"


# ── ZIP 조립 (실 ffmpeg 픽스처) ────────────────────────
def _mk_video(path, dur=4):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"color=c=red:s=320x568:r=30:d={dur}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def _mk_audio(path, dur=2.0):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"sine=frequency=440:duration={dur}",
                    "-c:a", "libmp3lame", str(path)], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


@pytest.fixture
def _job_assets(tmp_path):
    src = tmp_path / "src.mp4"; _mk_video(src, 6)
    t0 = tmp_path / "b0.mp3"; _mk_audio(t0, 2.0)
    t1 = tmp_path / "b1.mp3"; _mk_audio(t1, 1.5)
    final = tmp_path / "final.mp4"; _mk_video(final, 4)
    plan = {"beats": [
        {"beat_idx": 0, "role": "훅", "narration": "첫 장면",
         "primary": {"video_id": "s1", "start": 0.0, "end": 2.0}},
        {"beat_idx": 1, "role": "본문", "narration": "둘째 장면",
         "primary": {"video_id": "s1", "start": 2.0, "end": 3.5}},
    ]}
    timeline = [
        {"beat_idx": 0, "t0": 0.0, "dur": 2.0, "narration": "첫 장면", "role": "훅"},
        {"beat_idx": 1, "t0": 2.0, "dur": 1.5, "narration": "둘째 장면", "role": "본문"},
    ]
    return dict(plan=plan, timeline=timeline,
                source_video_paths={"s1": str(src)},
                tts_paths={0: str(t0), 1: str(t1)},
                final_video=str(final), seo={"title": "제목", "tags": ["#t"]})


def test_full_zip_has_all_expected_entries(tmp_path, _job_assets):
    out = tmp_path / "export.zip"
    written = eb.build_export_zip(out, **_job_assets)
    names = set(zipfile.ZipFile(out).namelist())
    assert "final.mp4" in names
    assert "sources/beat_00_훅.mp4" in names and "sources/beat_01_본문.mp4" in names
    assert "tts/beat_00.mp3" in names and "tts/beat_01.mp3" in names
    assert "captions.srt" in names and "script.txt" in names
    assert "seo.txt" in names and "README.txt" in names
    # 잘린 소스가 실제 재생 가능한 mp4인지(0바이트·깨진 파일 아님)
    with zipfile.ZipFile(out) as zf:
        assert zf.getinfo("sources/beat_00_훅.mp4").file_size > 0


def test_part_srt_only(tmp_path, _job_assets):
    out = tmp_path / "srt.zip"
    eb.build_export_zip(out, parts=["srt"], **_job_assets)
    names = set(zipfile.ZipFile(out).namelist())
    assert names == {"captions.srt"}   # 개별 다운로드는 그것만


def test_missing_source_is_skipped_not_crash(tmp_path, _job_assets):
    # 소스 mp4 경로를 없는 것으로 → sources 비어도 zip은 성립(500 금지)
    _job_assets["source_video_paths"] = {"s1": str(tmp_path / "nope.mp4")}
    out = tmp_path / "export.zip"
    written = eb.build_export_zip(out, **_job_assets)
    names = set(zipfile.ZipFile(out).namelist())
    assert not any(n.startswith("sources/") for n in names)
    assert "captions.srt" in names   # 나머지는 정상
