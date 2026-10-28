# -*- coding: utf-8 -*-
"""자막제거 뒤 원본이 다시 뜨는 칸 전수 점검 (관제 135, 2026-10-06 황선희님 d20c9f3d6a54).

무엇을 재나 — 청소 정본(clean_base.json)이 있는 작업마다:
  ① 안 덮인 칸        렌더와 같은 판정(mix_pipeline.clean_base_judge)이 '원본 재료'로 돌린 칸
  ② 그중 편성 그대로   그 칸이 정본을 만들 때의 편성 스냅샷과 똑같은가 — 같은데 안 덮였으면 **결함**(고객은 아무것도 안 바꿨다)
  ③ 컷 어긋남         편성이 그대로인 칸에서 지금 화면 컷(서버 러너 = 편집 화면과 같은 JS)이 정본에 기록된 청소 당시 컷과 다른 칸
  ④ 안전망 발동        편성 그대로인데 컷이 벗어나 청소 당시 컷으로 재생한 칸(clean_frozen) — 0이 정상, 있으면 컷 계산이 어긋난 것

됐다의 기준: ②가 0. (속도 불일치로 기록을 못 믿는 옛 정본 칸은 '옛 정본'으로 따로 센다.)

서버에서:  cd /home/ubuntu/lotto-stock-wiki && set -a && . <(sudo cat /etc/shopping-shorts.env) && set +a && \\
          python3 tools/clean_uncovered_sweep.py [--days 7] [--job ID] [--json /tmp/out.json]
패치 검증: 고친 코드 폴더에서 같은 명령(작업 폴더는 --jobs-dir 로 라이브 것을 가리킨다).
끝 코드: ②가 있으면 1, 없으면 0.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "shopping_shorts").is_dir():
    ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

TOL = 0.06


def _run(sc, data):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, default=str))
        tmp = f.name
    try:
        o = subprocess.run(["node", str(sc._RUNNER), str(sc._SCENE_PLAY), tmp], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(tmp)
    if o.returncode != 0:
        raise RuntimeError("node rc=%s %s" % (o.returncode, (o.stderr or "")[-200:]))
    return json.loads(o.stdout)


def _same(rc, bc):
    if rc is None or len(rc) != len(bc):
        return False
    return all(str(a["v"]) == str(b["video_id"]) and abs(float(a["s"]) - float(b["src"])) <= TOL
               and abs(float(a.get("sd") or a["d"]) - float(b.get("sdur") or b["dur"])) <= TOL for a, b in zip(rc, bc))


def check_job(store, mp, cb, sc, work):
    J = work.name
    raw = json.loads((work / "clean_base.json").read_text(encoding="utf-8"))
    if raw.get("calibrated") != cb.CAL_VERSION:
        return {"job": J, "skip": "보정 전 정본(판정이 정본을 다시 쓴다 — 건드리지 않는다)"}
    job = store.get_mix_job(J)
    if not job or not (job.get("edit_plan") or {}).get("beats"):
        return {"job": J, "skip": "편성 없음"}
    j = mp.clean_base_judge(store, job, work)
    if j is None:
        return {"job": J, "skip": "판정 없음(스위치 꺼짐)"}
    base, plan = j["base"], job["edit_plan"]
    unc = list(j["uncovered"])
    need = j["plan2"].get("_clean_need") or {}
    same = [int(b["beat_idx"]) for b in plan["beats"] if cb.unchanged_since_clean(base, b)]
    # 옛 정본 = 읽은 길이(sdur) 기록이 없거나(09-26 전 형식) 속도 불일치로 좌표를 못 믿는 컷이 낀 칸 — 청소 당시 컷으로도 못 튼다
    old = [bi for bi in unc if bi in same and any(cb._speed_bad(c) or c.get("sdur") is None for c in cb._cuts_of(base, bi))]
    frozen = [int(b["beat_idx"]) for b in j["plan2"]["beats"] if b.get("clean_frozen")]
    drift = []
    try:
        data = sc._scene_data(J)
        if data and data.get("beats"):
            res = _run(sc, data)
            for i, b in enumerate(plan["beats"]):
                bi = int(b["beat_idx"])
                bc = cb._cuts_of(base, bi)
                if bi in same and bc and float(j["tts_durs"].get(bi) or 0) > 0 and not _same((res[i] or {}).get("c"), bc):
                    drift.append(bi)
    except Exception as e:      # noqa: BLE001 — 화면 컷을 못 재면 그 사실을 적는다(조용히 0으로 두지 않는다)
        drift = ["못 잼: %s" % type(e).__name__]
    return {"job": J, "cid": job.get("customer_id"), "status": job.get("status"), "partial": bool(base.get("partial")),
            "beats": len(plan["beats"]), "same_plan": len(same), "uncovered": unc,
            "uncovered_same_plan": [bi for bi in unc if bi in same and bi not in old], "uncovered_old_base": old,
            "need_secs": round(sum(float(x["end"]) - float(x["start"]) for v in need.values() for x in v), 2),
            "drift": drift, "frozen": frozen,
            "base_at": time.strftime("%m-%d %H:%M", time.localtime((work / "clean_base.json").stat().st_mtime))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--job")
    ap.add_argument("--jobs-dir")
    ap.add_argument("--json")
    ap.add_argument("--no-net", action="store_true", help="안전망을 끄고 잰다 — 이 점검이 결함을 잡는지 확인할 때만")
    a = ap.parse_args()
    from shopping_shorts import clean_base as cb, mix_pipeline as mp, screen_clips as sc
    if a.no_net:
        cb.frozen_cuts = lambda *_a, **_k: None
    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store
    jobs_dir = Path(a.jobs_dir) if a.jobs_dir else Path(DB_PATH).parent / "mix_jobs"
    store, now, rows = Store(DB_PATH), time.time(), []
    for p in sorted(jobs_dir.glob("*/clean_base.json"), key=lambda x: -x.stat().st_mtime):
        if a.job and p.parent.name != a.job:
            continue
        if not a.job and now - p.stat().st_mtime > a.days * 86400:
            continue
        try:
            rows.append(check_job(store, mp, cb, sc, p.parent))
        except Exception as e:      # noqa: BLE001 — 한 작업이 깨져도 나머지는 잰다. 깨진 건 결과에 남는다
            rows.append({"job": p.parent.name, "err": "%s: %s" % (type(e).__name__, str(e)[:160])})
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    ok = [r for r in rows if "uncovered" in r]
    bad = [r for r in ok if r["uncovered_same_plan"]]
    print("청소 정본 작업 %d · 판정 %d · 건너뜀 %d · 오류 %d" % (
        len(rows), len(ok), sum(1 for r in rows if "skip" in r), sum(1 for r in rows if "err" in r)))
    print("편성 그대로인 칸 %d" % sum(r["same_plan"] for r in ok))
    print("① 안 덮인 칸 있는 작업 %d" % sum(1 for r in ok if r["uncovered"]))
    print("② 편성 그대로인데 안 덮인 칸(결함) %d칸 / %d작업" % (sum(len(r["uncovered_same_plan"]) for r in bad), len(bad)))
    print("   (옛 정본 — 읽은 길이 기록이 없거나 속도 불일치인 칸 %d칸)" % sum(len(r["uncovered_old_base"]) for r in ok))
    print("③ 컷 어긋남(편성 그대로인데 화면 컷 ≠ 청소 당시 컷) %d칸 / %d작업" % (
        sum(len(r["drift"]) for r in ok), sum(1 for r in ok if r["drift"])))
    print("④ 안전망 발동(청소 당시 컷으로 재생) %d칸 / %d작업" % (
        sum(len(r["frozen"]) for r in ok), sum(1 for r in ok if r["frozen"])))
    for r in rows:
        if r.get("err") or r.get("uncovered") or r.get("frozen"):
            print(json.dumps(r, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
