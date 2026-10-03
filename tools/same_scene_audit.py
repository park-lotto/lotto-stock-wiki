# -*- coding: utf-8 -*-
"""[서버용·읽기 전용] 한 칸에 같은 장면이 이어지는 꼴 전수 집계 (2026-10-02 사장님 "같은 장면 계속 쓴다 / 같은 것 많아").

칸마다 3단계 화면 목록(scene_lab.beats[i].list)을 보고:
  · 한장면 = 칸의 컷이 전부 **원본 한 구간**에서 나왔다(film_조각이 한 장면을 구절별로 자른 것 포함)
  · 대사 길이(target_seconds) 2.5초 이상인데 한장면이면 '길게 같은 장면'
  · 같은 원본 구간이 **다른 칸**에도 또 나오면 '칸 넘어 반복'
사용(서버): cd /home/ubuntu/lotto-stock-wiki && python3 tools/same_scene_audit.py [시간=24]
"""
import json, re, sqlite3, sys, time
from collections import Counter

DB = "shopping_shorts/data/reference.db"


def _span(seg_id, extract):
    """seg_id → (영상, 시작, 끝). film_s0_6.83_8.23 은 그대로, 원본 seg 는 extract 에서 찾는다."""
    m = re.match(r"film_(s\d+)_([\d.]+)_([\d.]+)", seg_id or "")
    if m:
        return m.group(1), float(m.group(2)), float(m.group(3))
    for vid, ex in (extract or {}).items():
        for s in (ex or {}).get("segments") or []:
            if s.get("seg_id") == seg_id:
                return vid, float(s.get("start") or 0), float(s.get("end") or 0)
    return None


def _same_shot(spans):
    """구간들이 한 영상의 이어진 한 장면인가(사이 틈 0.3초 이하)."""
    spans = sorted(s for s in spans if s)
    if not spans or len({s[0] for s in spans}) > 1:
        return False
    for a, b in zip(spans, spans[1:]):
        if b[1] - a[2] > 0.3:
            return False
    return True


def main(hours=24):
    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    cols = [r[1] for r in db.execute("pragma table_info(mix_jobs)")]
    since = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - hours * 3600))
    rows = db.execute("select * from mix_jobs where updated_at > ? order by updated_at desc", (since,)).fetchall()
    tot_beats = long_one = jobs = 0
    cross = 0
    worst = []
    for row in rows:
        r = dict(zip(cols, row))
        try:
            plan = json.loads(r.get("edit_plan_json") or "{}")
            ex = json.loads(r.get("extract_json") or "{}")
        except Exception:
            continue
        sl = (plan.get("scene_lab") or {}).get("beats")
        beats = plan.get("beats") or []
        if not beats:
            continue
        jobs += 1
        used = Counter()
        n_long = 0
        for i, b in enumerate(beats):
            lst = None
            if isinstance(sl, list) and i < len(sl) and isinstance(sl[i], dict):
                lst = sl[i].get("list")
            if not lst:
                p = (b.get("primary") or {}).get("seg_id")
                lst = [p] if p else []
            spans = [_span(s, ex) for s in lst]
            tot_beats += 1
            sec = float(b.get("target_seconds") or 0)
            if spans and _same_shot(spans) and sec >= 2.5:
                long_one += 1; n_long += 1
            for s in {x for x in spans if x}:
                used[(s[0], round(s[1]))] += 1
        rep = sum(c - 1 for c in used.values() if c > 1)
        cross += rep
        worst.append((n_long + rep, r["job_id"], len(beats), n_long, rep))
    print("최근 %d시간 작업 %d개 · 칸 %d" % (hours, jobs, tot_beats))
    print("  2.5초 이상 칸인데 한 장면만 이어짐: %d칸 (%.0f%%)" % (long_one, 100.0 * long_one / max(1, tot_beats)))
    print("  같은 원본 장면이 다른 칸에 또 나옴: %d번" % cross)
    for w in sorted(worst, reverse=True)[:8]:
        print("   작업 %s · 칸 %d · 한장면 %d · 칸넘어반복 %d" % (w[1], w[2], w[3], w[4]))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 24)
