# -*- coding: utf-8 -*-
"""verify_scene_fx.py 의 작업 폴더(w1 = 효과 있음 렌더)로 **진짜 캡컷 초안 폴더**를 만든다 (관제 124).
캡컷 앱에서 열어 점프 줌(1.35배 조각)·어둡게 막(시작 0.13초, 장면 2)이 보이는지 눈으로 확인하기 위한 것.

사용: py tools/scene_fx/capcut_trial.py --work <verify 작업 폴더> [--drafts <캡컷 초안 폴더>]
"""
import argparse, json, os, subprocess, sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_scene_fx import TIMELINE  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--drafts", default=os.path.expandvars(r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft"))
    ap.add_argument("--name", default="QA_장면효과팩")
    a = ap.parse_args()
    from shopping_shorts import scene_style, capcut_draft
    work = Path(a.work)
    ed = json.loads((work / "editor-out.json").read_text(encoding="utf-8"))
    snap = {"version": 1, "mode": "story", "presetId": "t11", "hookMotion": "pop", "effects": ed["snapshot"]["effects"]}
    layers = json.loads((work / "w1" / "scene-style-layers.json").read_text(encoding="utf-8"))
    scenes = scene_style.context_for(TIMELINE, {"text": "주방 정리\n끝판왕"}, snap, "qa")["scenes"]
    overlays = scene_style.overlay_spans(scenes, layers, work / "w1")
    dims = scene_style.dim_spans(scenes, snap, layers, work / "w1")
    zooms = scene_style.zoom_spans(scenes, snap)
    tts = {}
    for b in TIMELINE:
        p = work / f"tts{b['beat_idx']}.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(b["dur"]), str(p)], check=True)
        tts[b["beat_idx"]] = str(p)
    plan = {"beats": [{"beat_idx": b["beat_idx"], "role": b["role"], "narration": b["narration"],
                       "primary": {"video_id": "v0", "start": b["t0"], "end": b["t0"] + b["dur"]}} for b in TIMELINE]}
    drafts = Path(a.drafts)
    project, name, files = capcut_draft.assemble_draft_folder(
        drafts, str(drafts).replace("\\", "/"), plan=plan, timeline=TIMELINE,
        source_video_paths={"v0": str(work / "base.mp4")}, tts_paths=tts, project_name=a.name,
        scene_overlay_layers=overlays, scene_dim_layers=dims, scene_zoom_spans=zooms)
    print("캡컷 초안:", project, "파일", len(files))
    print("확대 구간:", zooms)
    print("어둡게 구간:", [(round(d["start"], 3), round(d["end"], 3)) for d in dims])


if __name__ == "__main__":
    main()
