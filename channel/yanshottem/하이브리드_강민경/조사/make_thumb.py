# -*- coding: utf-8 -*-
"""업로드용 썸네일(1080×1920 JPG) — 얜샷템 틀 그대로(제목 2줄 + 출처) + 창 안 강민경 얼굴 한 장면 (사장님 규칙 10-18 '썸네일 = 연예인').
엔진은 부르기만: 틀 = 잇썸홈판 frame_강민경.json(make_render.frame_a 가 제목·출처를 넣은 것) → calcopy_frame.to_snapshot → scene_style.compose.
    PYTHONUTF8=1 py make_thumb.py
출력: 바탕화면 하이브리드 폴더에 영상과 같은 이름 .jpg (+ C:/숏템_칼카피/yanshottem/하이브리드_강민경/thumb/ 사본)
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
ROOT = D.parents[3]
sys.path.insert(0, str(ROOT))
K = "C:/숏템_칼카피/yanshottem/강민경_피부/src/kmk_WmEjrZFVRB4.mp4"
FRAME = D.parent / "잇썸홈판/frame_강민경.json"
OUT = Path("C:/숏템_칼카피/yanshottem/하이브리드_강민경/thumb")
DESK = Path("C:/Users/CH/Desktop/칼카피영상/얜샷템/하이브리드")
# 판 → (원본 초, 크롭 [x,y,w,h]) — 1초 시트·후보 시트(src/fr/thumb_cands.jpg)에서 고른 표정
THUMBS = {
    "칼카피_얜샷템_강민경포트레틴트_잇썸홈판": (632.3, [575, 0, 800, 800]),    # 목에 바른 뒤 놀라 입 벌린 정면(가운데·눈·입)
    "칼카피_얜샷템_강민경포트레틴트_재미썸홈판": (641.0, [555, 0, 780, 780]),  # 정면 눈 크게 뜬 얼굴(원음 O1 "이거는 카메라로도" 구간 화면)
}


def main():
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    fr = json.loads(FRAME.read_text(encoding="utf-8"))
    title = next(l for l in fr["layers"] if l.get("role") == "title")["text"]
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(fr))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (t, (x, y, w, h)) in THUMBS.items():
        clip = OUT / f"{name}_src.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", K, "-an", "-frames:v", "30", "-vf",
                        f"crop={w}:{h}:{x}:{y},scale=1080:1080:flags=lanczos,setsar=1,loop=29:1:0,fps=30", "-c:v", "libx264", "-crf", "12",
                        "-pix_fmt", "yuv420p", str(clip)], check=True)
        tl = [{"beat_idx": 0, "t0": 0.0, "dur": 1.0, "narration": "", "caption_lines": [], "role": "hook",
               "primary": {"video_id": "s0", "start": 0.0, "end": 1.0}}]
        seg = OUT / f"{name}_seg.mp4"
        shutil.rmtree(OUT / f"work_{name}", ignore_errors=True)
        scene_style.compose(str(clip), tl, snap, str(seg), OUT / f"work_{name}", {"text": title})
        jpg = OUT / f"{name}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", str(seg), "-frames:v", "1", "-q:v", "2", str(jpg)], check=True)
        DESK.mkdir(parents=True, exist_ok=True)
        shutil.copy(jpg, DESK / jpg.name)
        print(jpg, "→", DESK / jpg.name)


if __name__ == "__main__":
    main()
