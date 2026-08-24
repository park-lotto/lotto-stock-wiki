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
    name = os.path.basename(plan.get("videoSrc") or "job_src.mp4")
    if name in ("", ".", ".."):
        name = "job_src.mp4"
    safe_plan = {**plan, "videoSrc": name}
    dest = os.path.join(pub, name)
    if os.path.abspath(dest) != os.path.abspath(video_path):
        shutil.copy(video_path, dest)
    noaudio = out_path + ".noaudio.mp4"
    # ★타임아웃 필수 — 없으면 node가 멈췄을 때 이 스레드가 영원히 붙잡힌다.
    #   렌더 워커는 개수가 정해져 있어서, 하나가 물리면 뒤 작업이 통째로 굶는다.
    from shopping_shorts import config as _cfg
    try:
        r = subprocess.run(
            ["node", "src/render-scene.mjs", "FullReel", json.dumps(safe_plan, ensure_ascii=False), noaudio],
            cwd=MOTION, capture_output=True, text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL, timeout=_cfg.REMOTION_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"remotion 렌더가 {_cfg.REMOTION_TIMEOUT_SEC}초를 넘겨 중단했습니다") from None
    if r.returncode != 0 or not os.path.isfile(noaudio):
        raise RuntimeError("remotion 렌더 실패: " + (r.stderr or "")[-500:])
    # 원본 오디오 mux
    try:
        r2 = subprocess.run(
            ["ffmpeg", "-y", "-i", noaudio, "-i", video_path, "-c:v", "copy", "-c:a", "aac",
             "-map", "0:v:0", "-map", "1:a:0?", "-shortest", "-movflags", "+faststart", out_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL, timeout=_cfg.MEDIA_CLIP_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        if os.path.isfile(noaudio):
            os.remove(noaudio)
        raise RuntimeError(
            f"오디오 mux가 {_cfg.MEDIA_CLIP_TIMEOUT_SEC}초를 넘겨 중단했습니다") from None
    os.remove(noaudio)
    if r2.returncode != 0 or not os.path.isfile(out_path):
        raise RuntimeError("오디오 mux 실패: " + (r2.stderr or "")[-500:])
    return out_path
