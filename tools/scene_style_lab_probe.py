"""두 비트 청소본으로 LAB MP4·CapCut 초안을 실제 생성해 경계를 검증한다."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts import scene_style, scene_style_lab, video_assemble  # noqa: E402


def _run(command):
    subprocess.run(command, check=True, cwd=ROOT, stdin=subprocess.DEVNULL)


def _audio(path: Path, seconds: float):
    frames = round(seconds * 16_000)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b"\0\0" * frames)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))

    clean = output / "clean-source.mp4"
    _run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=0x193449:s=1080x1920:r=30:d=4",
        "-vf", "drawbox=x=80:y=300:w=920:h=900:color=0x2e6b78:t=fill",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clean),
    ])
    plan = fixture["edit_plan"]
    for beat in plan["beats"]:
        tts = output / f"beat-{int(beat['beat_idx']):02d}.wav"
        _audio(tts, float(beat["target_seconds"]))
        beat["tts_path"] = str(tts)

    job = {
        "job_id": "scene-style-local-probe",
        "edit_plan": plan,
        "clean_sources": {"clean": str(clean)},
        "headcopy": fixture.get("headcopy"),
        "caption_style": {},
        "deco": {},
    }
    work_root = output / "jobs"
    manifest = scene_style_lab.create_copy(job["job_id"], job, work_root)
    scene_style_lab.save_snapshot(
        work_root, manifest["lab_id"], fixture["scene_style"]
    )
    manifest = scene_style_lab.read_manifest(work_root, manifest["lab_id"])
    final = scene_style_lab.render_copy(manifest, job, work_root)
    capcut = scene_style_lab.build_capcut_copy(
        manifest, job, work_root, str((output / "CapCut Drafts").resolve())
    )
    copied_final = output / "lab-final.mp4"
    copied_final.write_bytes(final.read_bytes())
    timeline = video_assemble._beat_timeline(plan, scene_style_lab._tts_paths(plan))
    context = scene_style.context_for(timeline, job["headcopy"], manifest["scene_style"])
    result = {
        "lab_id": manifest["lab_id"],
        "work_root": str(work_root),
        "mp4": str(copied_final),
        "capcut": str(capcut),
        "contract": scene_style_lab.contract_from_context(
            context, manifest["clean"]["signature"]
        ),
    }
    (output / "probe-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
