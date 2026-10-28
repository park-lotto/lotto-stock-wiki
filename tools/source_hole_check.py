# -*- coding: utf-8 -*-
"""소스 영상의 화면 구멍(패킷 없는 구간) 점검 — 관제 176 (2026-10-09 김성현님 2aa06a122f21).

무엇을 재나:
  ① 전수(--days N): 최근 N일 작업의 소스 영상마다 화면 구멍(media_download.video_holes — 받는 문과 같은 함수)을 센다.
  ② 작업(job ...):  그 작업을 **원본 소스로 실제 조립**(video_assemble._render_mix — 완성본과 같은 함수)해
                    칸마다 조립된 프레임 수 = 계획(render_cut_plan)인지, 조립본 옆 컷 지도가 남았는지 본다.
                    컷 지도가 안 남으면 자막제거가 시작되지 않는다(mix_pipeline._final_clean_fn).

됐다의 기준: ②에서 구멍 난 소스를 쓰는 작업도 '프레임 부족 칸 0 · 컷 지도 기록됨'.
★고객 파일을 바꾸지 않는다 — 조립은 /tmp/hole176/<job>/ 에서 하고 끝나면 지운다(HOLE_KEEP=1 이면 남긴다).

서버: cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \\
      [PATCH_DIR=/tmp/patch176] python3 tools/source_hole_check.py [--days 14] [job_id ...]
끝 코드: ②에서 프레임 부족·지도 없음이 하나라도 있으면 1.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
os.environ.setdefault("SEG_SNAP_CACHE_DIR", "/tmp/evf_snapcache")       # 도구는 고객 폴더에 캐시를 쓰지 않는다
if os.getenv("PATCH_DIR"):          # 배포 전 대조: 고친 모듈을 먼저 얹는다(목록·경로 되돌리기 = gate_modules)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gate_modules
    gate_modules.load_patch_modules()

OUT = Path("/tmp/hole176")
JOBS = Path("shopping_shorts/data/mix_jobs")


def _holes_fn():
    """구멍 판정 = 받는 문(media_download.video_holes). PATCH_DIR 에 고친 media_download.py 가 있으면 그것(배포 전 대조)."""
    pd = os.getenv("PATCH_DIR")
    if pd and (Path(pd) / "media_download.py").exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("_md176", str(Path(pd) / "media_download.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m.video_holes
    from shopping_shorts import media_download as md
    return md.video_holes


def scan(days):
    holes_of = _holes_fn()
    now, jobs, files, hits = time.time(), 0, 0, []
    for d in sorted(glob.glob(str(JOBS / "*"))):
        if not os.path.isdir(d) or now - os.path.getmtime(d) > days * 86400:
            continue
        jobs += 1
        for f in glob.glob(d + "/s*/*.mp4"):
            files += 1
            h = holes_of(f)
            if h:
                hits.append((os.path.basename(d), os.path.basename(os.path.dirname(f)), h))
    print("== 전수 %g일: 작업 %d · 소스 %d · 화면 구멍 있는 소스 %d" % (days, jobs, files, len(hits)))
    for j, v, h in hits:
        print("   %s %s 구멍 %s" % (j, v, h))
    return hits


def _nframes(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                        "stream=nb_read_packets", "-of", "csv=p=0", str(p)], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL).stdout.strip().strip(",")
    return int(o) if o.isdigit() else -1


def check_job(jid):
    from shopping_shorts import mix_pipeline as mp, video_assemble as va, screen_clips as sc
    from shopping_shorts.store import Store
    holes_of = _holes_fn()
    st = Store("shopping_shorts/data/reference.db")
    job = st.get_mix_job(jid)
    plan = (job or {}).get("edit_plan") or {}
    w = JOBS / jid
    tts = {int(b["beat_idx"]): b["tts_path"] for b in plan.get("beats") or [] if b.get("tts_path") and Path(b["tts_path"]).exists()}
    if not tts:
        print("%s 건너뜀: 음성 없음" % jid)
        return None
    srcs = dict(mp._resolve_sources(job, w) or {})
    if any(va.meme_cutaway(b) for b in plan.get("beats") or []):
        srcs.update(mp.job_meme_sources(st, job, plan))            # 짤 컷도 보통 컷처럼(편집 화면 합본과 같은 함수)
    srcs = {k: v for k, v in srcs.items() if v and Path(v).exists()}
    holes = {k: holes_of(v) for k, v in srcs.items() if not str(k).startswith("meme_")}
    holes = {k: v for k, v in holes.items() if v}
    if sc.warm(job) <= 0:
        print("%s 건너뜀: 화면 컷 계산 실패" % jid)
        return None
    cplan = va.render_cut_plan(plan, tts, srcs)
    want = {int(bp["idx"]): int(bp["nfr"]) for bp in cplan}
    wd = OUT / jid
    shutil.rmtree(wd, ignore_errors=True)
    wd.mkdir(parents=True)
    try:
        with mp.preview_preset():
            mix_raw = Path(va._render_mix(plan, tts, srcs, wd))
        got = {bi: _nframes(wd / ("beat_%d.mp4" % bi)) for bi in want}
        short = {bi: (got[bi], want[bi]) for bi in want if got[bi] != want[bi]}
        has_map = va.read_cut_map(mix_raw) is not None
        total = _nframes(mix_raw)
    finally:
        if not os.getenv("HOLE_KEEP"):
            shutil.rmtree(wd, ignore_errors=True)
    ok = not short and has_map
    print("%s %s | 구멍 난 소스 %s | 칸 %d · 조립 %d프레임(계획 %d) · 프레임 다른 칸 %s · 컷 지도 %s" % (
        jid, "통과" if ok else "실패", json.dumps(holes, ensure_ascii=False) if holes else "없음", len(want), total,
        sum(want.values()), {k: "%d≠%d" % v for k, v in short.items()} or "없음", "기록됨" if has_map else "없음"))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=0)
    ap.add_argument("jobs", nargs="*")
    a = ap.parse_args()
    jobs = list(a.jobs)
    if a.days:
        jobs += [j for j, _v, _h in scan(a.days) if j not in jobs]
    bad = [j for j in jobs if check_job(j) is False]
    if jobs:
        print("== 작업 %d · 실패 %d %s" % (len(jobs), len(bad), bad or ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
