# -*- coding: utf-8 -*-
"""썰 히트작 넓은 표본 컷 연구 — 편마다 컷 길이·자리·홀드 위치를 재고 조회수 그룹별로 비교한다 (2026-09-23 사장님
"우리가 어떻게 자를지 고민 말고 썰 채널들을 더 분석해 가장 좋은 규칙을 찾아 그에 맞추자").
  py tools/seed_analyzer/cut_study.py --ids docs/…/study_ids.json --out docs/…/cut_study.json
  py tools/seed_analyzer/cut_study.py --report docs/…/cut_study.json
편별 지표: 길이·컷 수·컷 중앙·첫 컷·3초+ 홀드 수·최장 홀드·최장 홀드가 나오는 위치(영상의 몇 %)·최장 홀드 중 말(자막)·앞 5초 컷 수·
          컷 자리 분포(낱말사이/연결어미/신호어앞/문장끝/낱말중간)·초당 컷.
"""
import argparse, json, os, sys, tempfile, statistics, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cut_rhythm import download, cut_times, probe_duration
from cut_phrase import words_with_time, classify


def study_one(vid, work):
    p = download(vid, work)
    if not p:
        return None
    dur = probe_duration(p)
    ts = cut_times(p)
    lens = [round(b - a, 2) for a, b in zip([0.0] + ts, ts + [dur])]
    lens = [x for x in lens if x > 0.04]
    if not lens or dur <= 0:
        return None
    words = words_with_time(vid, work)
    kinds = collections.Counter(classify(t, words) for t in ts) if words else collections.Counter()
    # 최장 홀드: 어디서(영상의 %), 무슨 말 위에서
    starts = [0.0] + ts
    k = max(range(len(lens)), key=lambda i: lens[i])
    h0, h1 = starts[k], starts[k] + lens[k]
    said = " ".join(w for t, w in words if h0 - 0.2 <= t <= h1) if words else ""
    return {"id": vid, "duration": round(dur, 1), "cuts": len(lens), "median": statistics.median(lens), "first": lens[0],
            "holds3": sum(1 for x in lens if x >= 3), "max": max(lens), "max_pos": round(h0 / dur, 2), "max_said": said[:80],
            "frag": sum(1 for x in lens if x < 0.5), "first5s_cuts": sum(1 for t in ts if t <= 5.0),
            "cps": round(len(lens) / dur, 2), "kinds": dict(kinds), "has_sub": bool(words), "lens": lens}


def q(vs, name):
    vs = [v for v in vs if v is not None]
    if not vs:
        return "%s -" % name
    vs = sorted(vs)
    return "%s 중앙 %.1f (25%% %.1f · 75%% %.1f)" % (name, vs[len(vs) // 2], vs[len(vs) // 4], vs[3 * len(vs) // 4])


def report(rows):
    rows = [r for r in rows if r.get("cuts")]
    rows.sort(key=lambda r: -r["views"])
    n = len(rows); g = max(1, n // 3)
    groups = [("상위 1/3", rows[:g]), ("중위 1/3", rows[g:2 * g]), ("하위 1/3", rows[2 * g:])]
    print("표본 %d편 (조회 %s ~ %s)" % (n, rows[-1]["views"], rows[0]["views"]))
    for name, G in groups:
        print("\n== %s (%d편, 조회 중앙 %s)" % (name, len(G), statistics.median([r["views"] for r in G])))
        print("  " + q([r["duration"] for r in G], "길이") + " · " + q([r["cuts"] for r in G], "컷 수") + " · " + q([r["cps"] for r in G], "초당 컷"))
        print("  " + q([r["median"] for r in G], "컷 중앙") + " · " + q([r["first"] for r in G], "첫 컷") + " · " + q([r["first5s_cuts"] for r in G], "앞5초 컷"))
        print("  " + q([r["holds3"] for r in G], "3초+ 홀드") + " · " + q([r["max"] for r in G], "최장 홀드") + " · " + q([r["max_pos"] * 100 for r in G], "최장홀드 위치%") + " · " + q([r["frag"] for r in G], "0.5초 미만 조각"))
        kinds = collections.Counter()
        for r in G:
            kinds.update(r.get("kinds") or {})
        tot = sum(kinds.values()) or 1
        print("  컷 자리: " + " · ".join("%s %d%%" % (k, 100 * v // tot) for k, v in kinds.most_common()))
    print("\n== 최장 홀드 위에서 한 말 (상위 1/3 예)")
    for r in groups[0][1][:8]:
        print("  %s %.1f초 @%d%% | %s" % (r.get("user", "")[:10], r["max"], r["max_pos"] * 100, r["max_said"][:60]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default=""); ap.add_argument("--out", default=""); ap.add_argument("--report", default="")
    a = ap.parse_args()
    if a.report:
        report(json.load(open(a.report, encoding="utf-8"))); return
    meta = json.load(open(a.ids, encoding="utf-8"))
    work = tempfile.mkdtemp(prefix="cutstudy_")
    rows = []
    for i, m in enumerate(meta):
        try:
            r = study_one(m["id"], work)
        except Exception as e:      # noqa: BLE001
            r = None; print("  실패", m["id"], repr(e)[:80])
        if r:
            r.update({"views": m["views"], "user": m.get("user", "")}); rows.append(r)
            print("%2d/%d %-12s %7d  %4.0f초 컷%2d 중앙%.1f 첫%.1f 홀드3+%d 최장%.1f" % (i + 1, len(meta), m.get("user", "")[:10], m["views"], r["duration"], r["cuts"], r["median"], r["first"], r["holds3"], r["max"]), flush=True)
        if a.out:
            json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    report(rows)


if __name__ == "__main__":
    main()
