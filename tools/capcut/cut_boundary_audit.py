# -*- coding: utf-8 -*-
"""캡컷 draft의 **컷 경계가 완성본과 같은가** — 자막제거 뒤(완성본 조각) 경로 실측 도구.

2026-09-21 이윤정님 제보: 캡컷에 `cc1` 한 덩이(5초20)로 가서 본인이 자른 장면 컷이 사라졌다.
이 도구는 진짜 ffmpeg로 완성본을 만들고, 라이브와 같은 순서
(split_final_into_beat_clips → normalize → plan_using_beat_clips → assemble_draft_folder)로
draft를 조립한 뒤, draft_content.json의 영상 세그먼트 경계를 렌더 계획과 대조한다.

    py tools/capcut/cut_boundary_audit.py            # 통과 0 / 어긋남 1
    py tools/capcut/cut_boundary_audit.py --old      # 컷 정보를 안 넘긴 종전 동작(실패해야 정상)
"""
import json, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shopping_shorts import capcut_draft as cd, mix_pipeline as mp, video_assemble as va  # noqa: E402


def _mk(path, color, dur):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"color=c={color}:s=270x480:r=30:d={dur}", "-f", "lavfi", "-i",
                    f"anullsrc=r=48000:cl=stereo", "-t", str(dur), "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(path)], check=True)


def _mk_tts(path, dur):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"sine=f=440:d={dur}", str(path)], check=True)


def main(old=False):
    w = Path(tempfile.mkdtemp(prefix="cc_audit_"))
    durs = {0: 6.0, 1: 4.0}
    tts = {}
    for i, d in durs.items():
        tts[i] = str(w / f"tts{i}.mp3"); _mk_tts(tts[i], d)
    _mk(w / "a.mp4", "red", 30); _mk(w / "b.mp4", "blue", 30); _mk(w / "final.mp4", "green", 10)
    plan = {"beats": [
        {"beat_idx": 0, "narration": "첫째 말 둘째 말 셋째 말", "phrase_sync": False, "tts_path": tts[0],
         "primary": {"video_id": "a", "seg_id": "a-0", "start": 3.0, "end": 9.0},
         "alternates": [{"video_id": "b", "seg_id": "b-0", "start": 10.0, "end": 14.0}],
         "manual_cuts": [{"video_id": "a", "seg_id": "a-0", "start": 3.0, "dur": 1.5},
                         {"video_id": "b", "seg_id": "b-0", "start": 11.0, "dur": 2.0},
                         {"video_id": "a", "seg_id": "a-0", "start": 6.0, "dur": 2.5}]},
        {"beat_idx": 1, "narration": "넷째 말 다섯째 말", "sync_speed": 1.4, "tts_path": tts[1],
         "primary": {"video_id": "b", "seg_id": "b-1", "start": 1.0, "end": 9.0},
         "alternates": [{"video_id": "a", "seg_id": "a-1", "start": 12.0, "end": 20.0}]},
    ]}
    src_durs = {"a": 30.0, "b": 30.0}
    timeline = va._beat_timeline(plan, tts)
    want = [(round(c["fin"], 2), round(c["dur"], 2)) for c in mp.final_clip_pairs(plan, tts, src_durs)]
    clips = mp.split_final_into_beat_clips(str(w / "final.mp4"), timeline, w)
    clips = mp.normalize_baked_clips_for_capcut(plan, clips, timeline, w)
    cuts = None if old else mp.final_clip_pairs(plan, tts, src_durs)
    p2 = mp.plan_using_beat_clips(plan, clips, timeline, preserve_capcut_speed=True, cuts=cuts)
    tl2 = va._beat_timeline(p2, tts)
    proj, project, files = cd.assemble_draft_folder(
        w / "capcut", "C:/x", plan=p2, timeline=tl2, source_video_paths=dict(clips),
        tts_paths=tts, project_name="audit")
    draft = json.loads((Path(proj) / "draft_content.json").read_text(encoding="utf-8"))
    mats = {m["id"]: m for m in draft["materials"]["videos"]}
    speeds = {m["id"]: m.get("speed") for m in draft["materials"]["speeds"]}
    vt = max((t for t in draft["tracks"] if t["type"] == "video"), key=lambda t: len(t["segments"]))
    got = []
    print("캡컷 타임라인 영상 세그먼트:")
    for s in vt["segments"]:
        tr, sr = s["target_timerange"], s["source_timerange"]
        sp = next((speeds[r] for r in s.get("extra_material_refs", []) if r in speeds), None)
        got.append((round(tr["start"] / 1e6, 2), round(tr["duration"] / 1e6, 2)))
        print("  %-6s 타임라인 %5.2f~%5.2f | 소스 %5.2f+%5.2f | 속도 %s" % (
            mats[s["material_id"]]["material_name"], tr["start"] / 1e6,
            (tr["start"] + tr["duration"]) / 1e6, sr["start"] / 1e6, sr["duration"] / 1e6, sp))
    lib = sorted(f.name for f in Path(proj).glob("cut_*.mp4"))
    print("완성본 컷(시작,길이):", want)
    print("캡컷   컷(시작,길이):", got)
    print("보관함 조각:", lib)
    ok = (len(want) == len(got) and all(abs(a[0] - b[0]) < 0.05 and abs(a[1] - b[1]) < 0.05
                                        for a, b in zip(want, got)) and len(lib) == len(want))
    print("결과:", "일치" if ok else "★어긋남")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(old="--old" in sys.argv))
