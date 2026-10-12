"""구절 맞춤 결과물 검사(관제 106) — 장면 전환이 자막 경계에 맞는가.

서버에서 돌린다(작업 데이터가 서버에만 있다). 화면 컷 계산기(scene_play.js)를 서버 러너로 그대로 돌려 잰다.

    python3 tools/phrase_boundary_check.py                 # 최근 새 규칙(scenes_v2) 작업 20개
    python3 tools/phrase_boundary_check.py --jobs 49e10cb2c30b
    python3 tools/phrase_boundary_check.py --play /tmp/new_scene_play.js --runner /tmp/new_runner.js \
                                           --base-play shopping_shorts/static/scene_play.js

재는 것
  ① 구절 맞춤(전 칸에 phrase_exact 를 켠 흉내): 컷 수 ≤ 자막 줄 수인 칸에서, 전환마다 가장 가까운 자막 경계와의 차이.
     0.05초를 넘는 전환이 하나라도 있으면 실패.
  ② 컷 리듬(저장된 그대로): --base-play 를 주면 그 계산기와 컷이 한 글자도 안 다른지(기본 동작 회귀 0).
읽기 전용 — 작업을 고치지 않는다.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TOL = 0.05


def _recent_v2_jobs(n):
    db = ROOT / "shopping_shorts" / "data" / "reference.db"
    c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    rows = c.execute("select job_id from mix_jobs where instr(edit_plan_json, 'scenes_v2') "
                     "order by updated_at desc limit ?", (n,)).fetchall()
    return [r[0] for r in rows]


def _run(runner, play, data):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)
        tmp = f.name
    try:
        out = subprocess.run(["node", str(runner), str(play), tmp], capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(tmp)
    if out.returncode != 0:
        raise RuntimeError("node rc=%s %s" % (out.returncode, (out.stderr or "")[-300:]))
    return json.loads(out.stdout)


def _exact(data):
    d = json.loads(json.dumps(data, default=str))
    for b in d.get("beats") or []:
        b["phrase_sync"] = True
        b["phrase_exact"] = True
        for k in ("manual_cuts", "slow", "stretch_fill"):
            b.pop(k, None)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", nargs="*")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--play")
    ap.add_argument("--runner")
    ap.add_argument("--base-play")
    ap.add_argument("--base-runner")
    a = ap.parse_args()
    from shopping_shorts import screen_clips as sc
    play = a.play or sc._SCENE_PLAY
    runner = a.runner or sc._RUNNER
    jobs = a.jobs or _recent_v2_jobs(a.n)
    tot = {"jobs": 0, "beats": 0, "checked": 0, "trans": 0, "off": 0, "more_scenes": 0, "same_fail": 0, "slow_over": 0}
    worst, max_slow = [], 1.0
    for jid in jobs:
        try:
            data = sc._scene_data(jid)
        except Exception as e:      # noqa: BLE001
            print("  %s 화면 데이터 실패 %s" % (jid, type(e).__name__))
            continue
        if not data or not data.get("beats") or data.get("cut_rule") != "scenes_v2":
            continue
        tot["jobs"] += 1
        res = _run(runner, play, _exact(data))
        beats = data["beats"]
        for i, r in enumerate(res):
            caps = (data.get("captions") or {}).get(str(beats[i].get("beat_idx", i))) or []
            bounds = [float(c["start"]) for c in caps[1:]]
            clips = r.get("c") or []
            tot["beats"] += 1
            for c in clips:
                if c.get("sd") and c["d"] > 0:
                    rate = c["d"] / c["sd"]
                    max_slow = max(max_slow, rate)
                    if rate > 1.2 + 1e-3:
                        tot["slow_over"] += 1
            if len(clips) < 2 or not bounds:
                continue
            if len(clips) > len(caps):
                tot["more_scenes"] += 1          # 장면이 자막 줄보다 많다 — 전환을 다 경계에 놓을 수 없다(규칙상 허용)
                continue
            tot["checked"] += 1
            t = 0.0
            for c in clips[:-1]:
                t += c["d"]
                tot["trans"] += 1
                gap = min(abs(t - x) for x in bounds)
                if gap > TOL:
                    tot["off"] += 1
                    worst.append((round(gap, 3), jid, i, round(t, 3)))
        if a.base_play:
            new = _run(runner, play, data)
            old = _run(a.base_runner or sc._RUNNER, a.base_play, data)
            if json.dumps(new, sort_keys=True) != json.dumps(old, sort_keys=True):
                tot["same_fail"] += 1
                print("  ✗ %s 기본 동작(저장된 그대로)이 기준 계산기와 다르다" % jid)
    print(json.dumps(tot, ensure_ascii=False))
    print("구절 맞춤: 검사 칸 %d · 전환 %d · 자막 경계에서 %.2f초 넘게 벗어난 전환 %d · 장면>자막 줄 칸 %d(제외)"
          % (tot["checked"], tot["trans"], TOL, tot["off"], tot["more_scenes"]))
    print("느리게: 최대 %.2f배 · 1.2배 넘는 컷 %d개" % (max_slow, tot["slow_over"]))
    for w in sorted(worst, reverse=True)[:10]:
        print("  벗어남 %.3f초 job=%s 칸=%d 전환=%.3f초" % w)
    if a.base_play:
        print("컷 리듬(기본) 회귀: 다른 작업 %d / %d" % (tot["same_fail"], tot["jobs"]))
    bad = tot["off"] or tot["same_fail"] or not tot["jobs"]
    print("결과:", "실패" if bad else "통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
