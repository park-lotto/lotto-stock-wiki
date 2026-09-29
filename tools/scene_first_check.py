# -*- coding: utf-8 -*-
"""장면-먼저 대본 job 결과물 검사 (2026-09-30, 관제 카드 043).

서버 저장소 폴더에서(env 적재 뒤):
    python3 tools/scene_first_check.py <job_id> [<job_id> ...]
잰다(전부 결과물 기준 — 계산끼리 비교하지 않는다):
  ① 넘긴 컷 유지: script_structure.beat_sources 의 줄별 컷 == 편성(primary+alternates)
  ② 같은 장면 재사용: 렌더가 굽는 컷 계획(video_assemble.render_cut_plan)에서 같은 영상의 겹치는 구간을 두 번 읽는 컷 쌍
  ③ 완성본 반복 프레임: 1초 넘게 떨어진 두 순간이 거의 같은 그림(움직이는 중)인 쌍 — sf1627ea43ac(5초 중복)에서 5쌍을 잡는다
끝 줄: "== SFC job=… 컷유지 OK|NG · 재사용 N · 반복 N"  → 하나라도 NG/1+ 이면 종료코드 1
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".")
os.environ.setdefault("SEG_SNAP_CACHE_DIR", "/tmp/scene_first_check_snap")   # 소재 옆(고객 폴더)에 쓰지 않는다

R = Path("shopping_shorts/data").resolve()


def kept_cuts(job, plan):
    ss = job.get("script_structure") or {}
    ss = json.loads(ss) if isinstance(ss, str) else ss
    want = [list(x.get("segs") or [x.get("seg")]) for x in (ss.get("beat_sources") or [])]
    got = [[(b.get("primary") or {}).get("seg_id")] + [a.get("seg_id") for a in (b.get("alternates") or [])]
           for b in (plan.get("beats") or [])]
    return want, got


def reuse_pairs(cut_plan, min_overlap=0.3):
    rows = []
    for bp in cut_plan:
        for c in bp["clips"]:
            cl = c["clip"]
            v = cl.get("video_id") or cl.get("v")
            s = float(cl.get("start") or 0)
            rows.append((bp["idx"], v, s, s + float(c.get("play_out") or 0)))
    out = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            if a[1] == b[1] and min(a[3], b[3]) - max(a[2], b[2]) >= min_overlap:
                out.append((a, b))
    return out


def overreads(plan, cut_plan, tol=0.1):
    """④ 조각 밖 읽기 — 렌더 컷이 그 칸에 넘긴 조각(seg)의 끝을 넘어 원본을 읽은 초. 넘은 만큼은 다음 샷일 수 있다."""
    out = []
    for bp in cut_plan:
        b = bp["beat"] if isinstance(bp.get("beat"), dict) else (plan.get("beats") or [])[bp["idx"]]
        segs = [b.get("primary") or {}] + list(b.get("alternates") or [])
        for c in bp["clips"]:
            cl = c["clip"]
            v, s = cl.get("video_id") or cl.get("v"), float(cl.get("start") or 0)
            e = s + float(c.get("play_out") or 0)
            own = [x for x in segs if x.get("video_id") == v and float(x.get("start") or 0) - 0.05 <= s < float(x.get("end") or 0)]
            if own:
                over = e - float(own[0]["end"])
                if over > tol:
                    out.append((bp["idx"], v, round(s, 2), round(e, 2), round(over, 2)))
    return out


def repeat_frames(video, fps=5, gap=1.0, same=4.0, moving=1.5):
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", "fps=%d,scale=48:84,format=gray" % fps,
                        "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8)
    if not a.size:
        return None
    a = a.reshape(-1, 84, 48).astype(np.float32)
    k = int(gap * fps)
    return [(round(i / fps, 1), round(j / fps, 1)) for i in range(len(a)) for j in range(i + k, len(a))
            if np.abs(a[i] - a[j]).mean() < same and np.abs(a[j] - a[j - 1]).mean() > moving]


def check(jid):
    from shopping_shorts import mix_pipeline as mp, video_assemble as va
    from shopping_shorts.store import Store
    st = Store(str(R / "reference.db"))
    job = st.get_mix_job(jid)
    if not job:
        print("== SFC job=%s 없음" % jid)
        return False
    plan, paths, _base = mp.render_inputs_for(st, job, jid, R / "mix_jobs" / jid, [], job.get("customer_id") or 0,
                                              allow_clean=False)
    want, got = kept_cuts(job, plan)
    ok_keep = bool(want) and want == got
    if not ok_keep:
        print("  ① 넘긴 컷:", want, "\n     편성:  ", got)
    cp = va.render_cut_plan(plan, mp.tts_paths_of(plan), paths)
    reuse = reuse_pairs(cp)
    for a, b in reuse:
        print("  ② 재사용: 칸%d %s %.2f~%.2f  ↔  칸%d %s %.2f~%.2f" % (a[0], a[1], a[2], a[3], b[0], b[1], b[2], b[3]))
    over = overreads(plan, cp)
    for x in over:
        print("  ④ 조각 밖: 칸%d %s %.2f~%.2f (%.2f초 넘음)" % x)
    video = job.get("video_path") or ""
    if not (video and Path(video).exists()):
        video = str(R / "mix_jobs" / jid / "final.mp4")
    rep = repeat_frames(video) if Path(video).exists() else None
    if rep:
        print("  ③ 반복 프레임:", rep[:12])
    print("== SFC job=%s 컷유지 %s · 재사용 %d · 반복 %s · 조각밖 %d컷 %.2f초" % (
        jid, "OK" if ok_keep else "NG", len(reuse), "영상없음" if rep is None else len(rep),
        len(over), sum(x[4] for x in over)), flush=True)
    return ok_keep and not reuse and rep == [] and not over


if __name__ == "__main__":
    oks = [check(j) for j in sys.argv[1:]]
    sys.exit(0 if oks and all(oks) else 1)
