# -*- coding: utf-8 -*-
"""효과음팩 실렌더 검증 — 진짜 렌더 함수(_burn_captions)에 진짜 음성·진짜 자막으로 돌린다.

사용:
  py tools/sfx_bench/render_check.py --video <이븐쇼핑.mp4> --vocals <그 영상 vocals.wav> \
        --prep <prep.json> --vid <영상ID> --out <작업폴더> [--cid 7]

하는 일:
  1) 영상의 whisper 문장 = 칸(beat), 목소리 조각 = TTS 파일로 edit_plan을 만든다
  2) 검정 1080x1920 배경 위에 _burn_captions로 자막+효과음을 굽는다
     (팩은 mix_pipeline._resolve_sfx_paths(job=...) 실제 연결 경로로 받는다)
  3) 계획(sfx_pack.plan_events)을 JSON으로 남긴다 → 검출 대조는 check_render.py
"""
import argparse, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from shopping_shorts import video_assemble as va, mix_pipeline, sfx_pack   # noqa: E402


class _Store:
    def get_setting(self, k, d=""):
        return "1" if k == "sfx_pack_enabled" else d

    def get_scene_asset(self, *a, **k):
        return None


def main():
    ap = argparse.ArgumentParser()
    for k in ("video", "vocals", "prep", "vid", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--cid", type=int, default=7)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    segs = json.load(open(a.prep, encoding="utf-8"))[a.vid]["segs"]
    beats, tts = [], {}
    for i, s in enumerate(segs):
        end = segs[i + 1]["s"] if i + 1 < len(segs) else s["e"] + 0.3
        p = out / f"tts_{i}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.vocals, "-ss", f"{s['s']:.3f}",
                        "-to", f"{end:.3f}", "-ac", "1", "-ar", "44100", str(p)], check=True)
        beats.append({"beat_idx": i, "narration": s["t"], "role": "hook" if i == 0 else "body"})
        tts[i] = str(p)
    plan = {"beats": beats}
    total = sum(va._probe_duration(p) for p in tts.values())
    narr = out / "narr.wav"
    lst = out / "tts.txt"
    lst.write_text("".join(f"file '{Path(tts[i]).as_posix()}'\n" for i in range(len(beats))), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(narr)], check=True)
    base = out / "base.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x303030:s=1080x1920:r=30:d={total:.3f}",
                    "-i", str(narr), "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(base)], check=True)
    job = {"customer_id": a.cid, "deco": {"scene_style": {"presetId": "check"}}}
    sfx_paths = mix_pipeline._resolve_sfx_paths(_Store(), plan, a.cid, job=job)
    assert sfx_paths.get("_pack"), "팩이 안 잡혔다"
    work = out / "work"; work.mkdir(exist_ok=True)
    final = out / "final.mp4"
    va._burn_captions(str(base), plan, tts, str(final), work, deco={}, sfx_paths=sfx_paths)
    tl = va._beat_timeline(plan, tts)
    ev = sfx_pack.plan_events(tl)
    caps = [(seg, st) for b in tl for seg, st, _ in va.caption_schedule(b)]
    json.dump({"pack": sfx_paths["_pack"]["name"], "total": total, "events": ev, "captions": caps},
              open(out / "plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("팩", sfx_paths["_pack"]["name"], "· 길이", round(total, 2), "초 · 계획 효과음", len(ev), "발 · 자막", len(caps), "줄")
    print("완성본", final)


if __name__ == "__main__":
    main()
