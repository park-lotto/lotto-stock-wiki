# -*- coding: utf-8 -*-
"""눈 분류 결과(labels/<id>.json) + 후보 시각(x_sheets/<id>.json) + 측정(bench 결과)을 모아
레퍼런스가 실제로 쓰는 장면 효과를 센다 (관제 124). 지어낸 값 없이 센 것만 낸다.

사용: py tools/scene_fx/eye_summary.py --labels <labels폴더> --sheets <x_sheets폴더> --bench <bench결과.json> [--out 요약.json]
"""
import argparse, collections, glob, json, os, statistics, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SHOT = {"hard_cut", "jump_cut", "jump_zoom_cut", "dissolve", "zoom_blur", "whip_pan", "slide_push", "spin",
        "flash_white", "glitch", "fade_black"}
EDIT = {"jump_zoom_cut", "dissolve", "zoom_blur", "whip_pan", "slide_push", "spin", "flash_white", "glitch",
        "fade_black", "edit_punch_zoom", "edit_slow_zoom", "edit_shake"}


def zone(t, dur):
    return "hook" if t < 3.0 else ("end" if t > dur - 3.0 else "body")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--sheets", required=True)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    bench = {r["id"]: r for r in json.load(open(a.bench, encoding="utf-8")) if "error" not in r}
    vids = []
    for f in sorted(glob.glob(os.path.join(a.labels, "*.json"))):
        vid = os.path.splitext(os.path.basename(f))[0]
        lab = json.load(open(f, encoding="utf-8"))
        cand = {c["n"]: c for c in json.load(open(os.path.join(a.sheets, vid + ".json"), encoding="utf-8"))}
        b = bench.get(vid, {})
        dur = b.get("dur", 0)
        items = []
        for x in lab.get("items", []):
            c = cand.get(x["n"])
            if c is None:
                continue
            items.append({**x, "t": c["t"], "zone": zone(c["t"], dur)})
        # 같은 컷이 이웃 후보 두 줄(0.3초 안)에 같이 잡혀 둘 다 컷으로 적힌 경우가 있다(첫 배치 실측) — 하나로 합친다
        shots = []
        for t in sorted(x["t"] for x in items if x["label"] in SHOT):
            if not shots or t - shots[-1] > 0.35:
                shots.append(t)
        vids.append({"id": vid, "channel": b.get("channel", "?"), "views": b.get("views", 0), "dur": dur,
                     "items": items, "shots": shots, "hook": lab.get("hook", {})})
    n = len(vids)
    print(f"눈 분류 영상 {n}편 · 채널 {len({v['channel'] for v in vids})}개")
    # 1) 장면 전환 방식
    tot = collections.Counter(x["label"] for v in vids for x in v["items"])
    used = collections.Counter(l for v in vids for l in {x["label"] for x in v["items"]})
    print("\n라벨           개수   쓰는 영상")
    for l, c in tot.most_common():
        print(f"  {l:16s} {c:5d}   {used[l]:3d}/{n}")
    # 2) 컷 간격(장면 길이) — 장면 전환 시각 사이
    gaps = []
    for v in vids:
        s = [0.0] + v["shots"] + ([v["dur"]] if v["dur"] else [])
        gaps += [b - a for a, b in zip(s, s[1:]) if b - a > 0.15]
    if gaps:
        q = statistics.quantiles(gaps, n=4)
        print(f"\n장면 길이(초): 중앙 {statistics.median(gaps):.2f} · 사분위 {q[0]:.2f}~{q[2]:.2f} · 장면 {len(gaps)}개")
    # 3) 편집 효과 목록 (구간·배율·칸)
    eds = [(v["channel"], v["id"], x) for v in vids for x in v["items"] if x["label"] in EDIT]
    print(f"\n편집 효과 {len(eds)}건 · 쓰는 영상 {len({e[1] for e in eds})}/{n}")
    z = collections.Counter((x["label"], x["zone"]) for _, _, x in eds)
    for l in sorted({x["label"] for _, _, x in eds}):
        sc = [x.get("scale") for _, _, x in eds if x["label"] == l and x.get("scale")]
        fr = [x.get("frames") for _, _, x in eds if x["label"] == l and x.get("frames")]
        print(f"  {l:16s} 훅 {z[(l,'hook')]:3d} · 본문 {z[(l,'body')]:3d} · 끝 {z[(l,'end')]:3d}"
              + (f" · 배율 중앙 {statistics.median(sc):.2f} ({min(sc)}~{max(sc)})" if sc else "")
              + (f" · 겹침 칸 중앙 {statistics.median(fr)}" if fr else ""))
    # 4) 채널별 스타일
    print("\n채널별: 편수 · 장면 길이 중앙 · 편집 효과(라벨:건)")
    by = collections.defaultdict(list)
    for v in vids:
        by[v["channel"]].append(v)
    for ch, vs in sorted(by.items(), key=lambda x: -len(x[1])):
        g = []
        for v in vs:
            s = [0.0] + v["shots"] + ([v["dur"]] if v["dur"] else [])
            g += [b - a for a, b in zip(s, s[1:]) if b - a > 0.15]
        ec = collections.Counter(x["label"] for v in vs for x in v["items"] if x["label"] in EDIT)
        print(f"  {ch:14s} {len(vs):2d}편 · {statistics.median(g) if g else 0:.2f}초 · {dict(ec)}")
    # 5) 훅
    hc = [v["hook"].get("hook_cuts") for v in vids if isinstance(v["hook"].get("hook_cuts"), (int, float))]
    hz = [v for v in vids if v["hook"].get("hook_zoom")]
    if hc:
        print(f"\n훅(첫 3초) 장면 전환 수: 중앙 {statistics.median(hc)} · 분포 {dict(sorted(collections.Counter(hc).items()))}")
    print(f"훅에서 확대 쓰는 영상 {len(hz)}/{n}: " + "; ".join(f'{v["channel"]}:{v["hook"]["hook_zoom"]}' for v in hz[:12]))
    if a.out:
        json.dump(vids, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
