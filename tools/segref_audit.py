# -*- coding: utf-8 -*-
"""장면 참조 점검 — 편성이 가리키는 장면 id 가 화면 장면 표(edit_plan.scene_table)에서 **같은 구간으로** 풀리나(관제 141).

왜(2026-10-06 영상점검 다른 장면 9칸): 자동 편성이 만든 `…#2` 조각이 화면 표에 없어 화면 컷 0개 → 완성본만 그 칸을 채워
뒤 칸이 한 컷씩 밀렸다. 같은 id 로 구간만 줄인 조각은 화면(id→표)과 렌더·청소(비트 사본)가 다른 구간을 본다.

세는 것(작업 수·참조 수):
  missing      편성 id 가 표에 없다 → 화면 컷 0개(사고 모양). 고친 뒤 0 이어야 한다
  span_diff    같은 id 인데 비트 사본 구간 ≠ 표 구간(관제 141 2단계 — 청소 과금 범위와 얽혀 따로 센다)
  screen_empty (--screen) 화면 컷 러너를 실제로 돌려 길이 있는 칸이 컷 0개인 수 — 결과물 쪽 증상

사용(서버, 저장소 폴더):
  set -a && . /etc/shopping-shorts.env && set +a
  python3 tools/segref_audit.py --since 2026-09-22            # 표 대조만(빠름)
  python3 tools/segref_audit.py --job 8baf28dc4794 --screen   # 한 작업 + 화면 컷 러너
  python3 tools/segref_audit.py --since 2026-10-06 --screen --limit 40
종료코드: 0 missing·screen_empty 0 / 1 있음
"""
import argparse
import collections
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
DB_REL = "shopping_shorts/data/reference.db"


def refs_of(beat):
    """화면이 그 칸에서 읽는 참조 — 편성(scene_override)이 있으면 그것만, 없으면 primary + alternates(_beat_material 과 같은 규칙)."""
    ov = beat.get("scene_override") or []
    src = ov if ov else [beat.get("primary")] + list(beat.get("alternates") or [])
    return [s for s in src if isinstance(s, dict) and s.get("seg_id")]


def check_plan(extract, plan, table=None):
    """{missing: [(칸, id)], span_diff: [(칸, id, 사본, 표)]}."""
    from shopping_shorts import edit_plan as ep
    t = table if table is not None else ep.scene_table(extract, plan)
    out = {"missing": [], "span_diff": []}
    for i, b in enumerate(plan.get("beats") or []):
        for s in refs_of(b):
            g = t.get(s["seg_id"])
            if not g:
                out["missing"].append((i, s["seg_id"]))
                continue
            try:
                d = abs(float(s.get("start")) - float(g["start"])) + abs(float(s.get("end")) - float(g["end"]))
            except (TypeError, ValueError):
                continue
            if d > 0.05:
                out["span_diff"].append((i, s["seg_id"], (s.get("start"), s.get("end")), (g["start"], g["end"])))
    return out


def screen_empty(job_id):
    """화면 컷 러너(screen_clips 와 같은 입력)를 실제로 돌려 길이 있는 칸 중 컷 0개인 칸 번호."""
    from shopping_shorts import screen_clips as sc
    d = sc._scene_data(job_id)
    if not d or not d.get("beats"):
        return None
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    try:
        f.write(json.dumps(d, ensure_ascii=False, default=str))
        f.close()
        o = subprocess.run(["node", str(sc._RUNNER), str(sc._SCENE_PLAY), f.name], capture_output=True, text=True, timeout=90)
    finally:
        os.unlink(f.name)
    if o.returncode != 0:
        raise RuntimeError("node rc=%s %s" % (o.returncode, o.stderr[-200:]))
    return [i for i, r in enumerate(json.loads(o.stdout)) if float(r.get("t") or 0) > 0.05 and not r.get("c")]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None)
    ap.add_argument("--job", action="append", default=[])
    ap.add_argument("--screen", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--db", default=str(REPO / DB_REL))
    a = ap.parse_args(argv)
    con = sqlite3.connect("file:%s?mode=ro" % a.db, uri=True)
    q = "select job_id, created_at, extract_json, edit_plan_json from mix_jobs where edit_plan_json is not null and extract_json is not null"
    args = []
    if a.job:
        q += " and job_id in (%s)" % ",".join("?" * len(a.job))
        args += a.job
    if a.since:
        q += " and created_at >= ?"
        args.append(a.since)
    q += " order by created_at desc"
    if a.limit:
        q += " limit %d" % a.limit
    C = collections.Counter()
    jobs = collections.defaultdict(set)
    ex = collections.defaultdict(list)
    for jid, ca, exj, epj in con.execute(q, args):
        try:
            extract, plan = json.loads(exj), json.loads(epj)
        except ValueError:
            continue
        C["jobs"] += 1
        r = check_plan(extract, plan)
        for k in ("missing", "span_diff"):
            if r[k]:
                C[k] += len(r[k])
                jobs[k].add(jid)
                if len(ex[k]) < 5:
                    ex[k].append((jid, ca[:10], r[k][0]))
        if a.screen:
            try:
                e = screen_empty(jid)
            except Exception as err:      # noqa: BLE001 — 못 잰 작업은 따로 센다(조용히 넘기지 않는다)
                C["screen_fail"] += 1
                if len(ex["screen_fail"]) < 3:
                    ex["screen_fail"].append((jid, str(err)[:120]))
                continue
            if e:
                C["screen_empty"] += len(e)
                jobs["screen_empty"].add(jid)
                if len(ex["screen_empty"]) < 5:
                    ex["screen_empty"].append((jid, ca[:10], e))
    print("작업 %d · 표에 없는 참조 %d(작업 %d) · 같은 id 다른 구간 %d(작업 %d)%s" % (
        C["jobs"], C["missing"], len(jobs["missing"]), C["span_diff"], len(jobs["span_diff"]),
        (" · 화면 컷 0개 칸 %d(작업 %d) · 못 잼 %d" % (C["screen_empty"], len(jobs["screen_empty"]), C["screen_fail"]))
        if a.screen else ""))
    for k, v in ex.items():
        for e in v:
            print("  [%s] %s" % (k, e))
    return 1 if (C["missing"] or C["screen_empty"]) else 0


if __name__ == "__main__":
    sys.exit(main())
