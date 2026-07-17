"""플랜 + 조립본 → 리모션 최종 렌더. node subprocess. stdin=DEVNULL 필수(repo 규약)."""
import json
import os
import shutil
import subprocess

MOTION = os.path.join(os.path.dirname(__file__), "motion")


class RemotionUnavailable(RuntimeError):
    pass


def _motion_ready():
    return bool(shutil.which("node")) and os.path.isdir(os.path.join(MOTION, "node_modules"))


def render(plan, video_path, out_path):
    if not _motion_ready():
        raise RemotionUnavailable("node/remotion 미설치")
    out_path = os.path.abspath(out_path)
    pub = os.path.join(MOTION, "public")
    os.makedirs(pub, exist_ok=True)
    name = plan.get("videoSrc") or "job_src.mp4"
    dest = os.path.join(pub, name)
    if os.path.abspath(dest) != os.path.abspath(video_path):
        shutil.copy(video_path, dest)
    noaudio = out_path + ".noaudio.mp4"
    r = subprocess.run(
        ["node", "src/render-scene.mjs", "FullReel", json.dumps(plan, ensure_ascii=False), noaudio],
        cwd=MOTION, capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL)
    if r.returncode != 0 or not os.path.isfile(noaudio):
        raise RuntimeError("remotion 렌더 실패: " + (r.stderr or "")[-500:])
    # 원본 오디오 mux
    r2 = subprocess.run(
        ["ffmpeg", "-y", "-i", noaudio, "-i", video_path, "-c:v", "copy", "-c:a", "aac",
         "-map", "0:v:0", "-map", "1:a:0?", "-shortest", "-movflags", "+faststart", out_path],
        capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    os.remove(noaudio)
    if r2.returncode != 0 or not os.path.isfile(out_path):
        raise RuntimeError("오디오 mux 실패: " + (r2.stderr or "")[-500:])
    return out_path
