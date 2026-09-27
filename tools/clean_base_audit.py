# -*- coding: utf-8 -*-
"""청소본 정본 전수 점검 — 완성본(청소본 조립)이 편집 화면(원본 조립)과 **같은 장면**을 내는가 (2026-09-26).

왜: 강규봉님 job 7bbb1329aff0 — '완성본 만들기'가 미리보기와 다른 장면. 청소본 재배치(clean_base.remap_plan)가
손으로 정한 컷을 모르고 옛 컷 배치로 조립했다. 한 편만 보고 끝내지 말고 전 job에서 같은 꼴을 센다(0순위-A1b).

판정: 칸마다 원본 경로 컷 계획(plan_beat_clips_for, 원본 소스)과 청소본 경로 컷 계획(remap_plan 뒤 같은 함수)을
원본 좌표로 되돌려 비교한다. 컷 수·영상·시작(0.15초)·길이(0.15초) 중 하나라도 다르면 불일치.
증분 조각(cb*)은 원본 위치를 모르므로 '지운 새 조각'으로 보고 길이만 본다. uncovered 칸은 원본 그대로라 일치.

서버에서:  cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && \
          python3 tools/clean_base_audit.py [--days 7] [--job ID] [--verbose]
(패치 검증은 PYTHONPATH로 고친 모듈 폴더를 앞에 세워 같은 명령을 돌린다)
"""
import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "shopping_shorts").is_dir():      # /tmp 등에서 부르면 현재 폴더(저장소)를 쓴다
    ROOT = Path.cwd()
sys.path.insert(1, str(ROOT))

TOL = 0.15


def _dur(p, cache={}):
    if p not in cache:
        try:
            cache[p] = float(subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                timeout=30).strip())
        except Exception:      # noqa: BLE001
            cache[p] = 0.0
    return cache[p]


def _to_src(base, clip):
    """청소본 조립 컷 → (영상, 원본 시작, 원본 길이). 증분 조각은 ('extra', 0, 길이)."""
    from shopping_shorts import clean_base as cb
    vid = clip["video_id"]
    if vid != cb.CLEAN_VID:
        return ("extra", 0.0, float(clip.get("src_dur") or clip["out_dur"]))
    t = float(clip["start"])
    best = None
    for c in base.get("cuts") or []:
        fin, dur = float(c["fin"]), float(c["dur"])
        if fin - 1e-3 <= t < fin + dur - 1e-3:
            best = c
            break
    if best is None:
        return ("?", t, float(clip.get("src_dur") or clip["out_dur"]))
    if hasattr(cb, "_cut_geom"):
        cs, _ce, fin, k = cb._cut_geom(best)
    else:                      # 옛 코드(라이브 대조용): 원본 길이 = 완성본 길이
        cs, fin, k = float(best["src"]), float(best["fin"]), 1.0
    return (best["video_id"], cs + (t - fin) / k, float(clip.get("src_dur") or clip["out_dur"]) / k)


def _merge(L):
    """원본에서 이어지는 조각(같은 영상·앞 끝=뒤 시작)은 한 컷이다 — 청소본 조각 두 개로 나뉘어도 같은 장면."""
    out = []
    for v, s, l in L:
        if out and v != "extra" and out[-1][0] == v and abs(out[-1][1] + out[-1][2] - s) <= TOL:
            out[-1] = (v, out[-1][1], s + l - out[-1][1])
        else:
            out.append((v, s, l))
    return out


def _manual(va, b):
    f = getattr(va, "manual_cut_spans", None)
    if f:
        return f(b)
    return b.get("manual_cuts") if b.get("phrase_sync") is False else []   # 옛 코드엔 함수가 없다


def audit_job(store, job, work_root, verbose=False):
    from shopping_shorts import clean_base as cb, mix_pipeline as mp, video_assemble as va
    work = Path(work_root) / job["job_id"]
    base = cb.load_base(work)
    plan = job.get("edit_plan") or {}
    if base is None or not plan.get("beats"):
        return None
    tts = {}
    for b in plan["beats"]:
        tp = b.get("tts_path")
        try:
            tts[int(b["beat_idx"])] = float(va._beat_effective_dur(b, tp)) if tp and Path(tp).exists() else float(b.get("target_seconds") or 0)
        except Exception:      # noqa: BLE001
            tts[int(b["beat_idx"])] = float(b.get("target_seconds") or 0)
    srcs = mp._resolve_sources(job, work)
    sd = {k: _dur(str(v)) for k, v in srcs.items()}
    import inspect
    if "src_durs" in inspect.signature(cb.remap_plan).parameters:     # 렌더 컷 재생(2026-09-26~)
        plan2, unc, _ext = cb.remap_plan(plan, base, tts_durs=tts, src_durs=sd)
    else:
        plan2, unc, _ext = cb.remap_plan(plan, base, tts_durs=tts)
    cd = {k: _dur(str(v)) for k, v in cb.source_paths(base).items()}
    cd.update({k: v for k, v in sd.items() if k not in cd})   # uncovered 칸은 원본 소스도 같이 넘긴다(render_inputs_for와 같음)
    bad = []
    for b, b2 in zip(plan["beats"], plan2["beats"]):
        bi = int(b["beat_idx"])
        if bi in unc or tts.get(bi, 0) <= 0:
            continue
        a = va.plan_beat_clips_for(b, tts[bi], sd)
        c = va.plan_beat_clips_for(b2, tts[bi], cd)
        A = [(x["video_id"], float(x["start"]), float(x.get("src_dur") or x["out_dur"])) for x in a]
        C = [_to_src(base, x) for x in c]
        A, C = _merge(A), _merge(C)
        ok = len(A) == len(C) and all(
            (cv == "extra" or (cv == av and abs(cs - as_) <= TOL)) and abs(cl - al) <= TOL
            for (av, as_, al), (cv, cs, cl) in zip(A, C))
        if not ok:
            bad.append(bi)
            if verbose:
                f = lambda L: [(v, round(s, 2), round(l, 2)) for v, s, l in L]
                print("   칸%d manual=%s 원본%s" % (bi, bool(_manual(va, b)), f(A)))
                print("        청소본%s" % f(C))
    need = plan2.get("_clean_need") or {}
    beats_by = {int(b["beat_idx"]): b for b in plan["beats"]}
    unc_sec = sum(sum(float(m["end"]) - float(m["start"]) for m in (need.get(str(bi)) or mp._beat_materials(beats_by[bi])))
                  for bi in unc)
    return {"job": job["job_id"], "beats": len(plan["beats"]), "bad": bad, "uncovered": unc, "unc_sec": unc_sec,
            "manual": sum(1 for b in plan["beats"] if _manual(va, b))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--job")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--patch", help="고친 모듈(video_assemble·mix_pipeline·clean_base .py)이 든 폴더 — 배포 전 대조용")
    a = ap.parse_args()
    if a.patch:
        import importlib.util
        for name in ("video_assemble", "mix_pipeline", "clean_base"):
            f = Path(a.patch) / (name + ".py")
            if f.exists():
                spec = importlib.util.spec_from_file_location("shopping_shorts." + name, f)
                mod = importlib.util.module_from_spec(spec)
                sys.modules["shopping_shorts." + name] = mod
                spec.loader.exec_module(mod)
                import shopping_shorts
                setattr(shopping_shorts, name, mod)
    from shopping_shorts import config
    from shopping_shorts.store import Store
    db = getattr(config, "DB_PATH", str(ROOT / "shopping_shorts/data/reference.db"))
    work_root = ROOT / "shopping_shorts/data/mix_jobs"
    st = Store(db)
    con = sqlite3.connect(db)
    if a.job:
        ids = [a.job]
    else:
        since = (datetime.now(timezone.utc) - timedelta(days=a.days)).isoformat()
        ids = [r[0] for r in con.execute("select job_id from mix_jobs where updated_at>=? order by updated_at desc", (since,))]
        ids = [i for i in ids if (work_root / i / "clean_base.json").exists()]
    tot = nbad = nbeats = nbadbeats = nunc = nuncjobs = 0
    unc_sec = 0.0
    for jid in ids:
        job = st.get_mix_job(jid)
        if not job:
            continue
        try:
            r = audit_job(st, job, work_root, a.verbose)
        except Exception as e:      # noqa: BLE001
            print("%s 점검실패 %s: %s" % (jid, type(e).__name__, e))
            continue
        if r is None:
            continue
        tot += 1
        nbeats += r["beats"]
        nbadbeats += len(r["bad"])
        nunc += len(r["uncovered"]); unc_sec += r["unc_sec"]; nuncjobs += bool(r["uncovered"])
        if r["bad"]:
            nbad += 1
            print("%s 불일치칸 %s / 바뀐장면 %s / 손컷칸 %d/%d" % (jid, r["bad"], r["uncovered"], r["manual"], r["beats"]))
    print("== 청소본 job %d개 중 불일치 %d개 · 칸 %d개 중 %d개" % (tot, nbad, nbeats, nbadbeats))
    print("== 재청소 대상(바뀐 장면) job %d개 · 칸 %d개 · %.1f초" % (nuncjobs, nunc, unc_sec))


if __name__ == "__main__":
    main()
