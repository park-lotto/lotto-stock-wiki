# -*- coding: utf-8 -*-
"""bench.py 결과(json)를 채널별·구간별(훅 0~3초 / 본문 / 끝 3초)로 모은다 (관제 124).
편집 효과(edit=True)와 원본 촬영 움직임(edit=False)을 갈라 센다 — 원본 움직임은 효과 팩 근거가 아니다.

사용: py tools/scene_fx/summarize.py <결과.json> [<결과2.json> ...]
"""
import collections, json, statistics, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KINDS = ["soft", "zoom_cut", "punch", "push", "shake", "whip", "flash", "blur"]


def main(paths):
    res, seen = [], set()
    for p in paths:
        for r in json.load(open(p, encoding="utf-8")):
            if r["id"] not in seen:
                seen.add(r["id"]); res.append(r)
    print(f"영상 {len(res)}편 · 채널 {len({r['channel'] for r in res})}개")
    cl = [r["dur"] / max(1, r["cuts"] + 1) for r in res]
    print(f"컷 평균 길이 중앙값 {statistics.median(cl):.2f}초 (영상별 범위 {min(cl):.2f}~{max(cl):.2f})")
    vids_with = collections.Counter()
    zone = collections.Counter()
    tot = collections.Counter()
    for r in res:
        k_in = set()
        for e in r["events"]:
            k = e["kind"]
            if k == "cut":
                continue
            ed = e.get("edit", None)
            if ed is False:            # 원본 촬영 움직임
                tot[(k, "원본")] += 1
                continue
            tot[(k, "편집")] += 1
            zone[(k, e["zone"])] += 1
            k_in.add(k)
        for k in k_in:
            vids_with[k] += 1
    print("\n효과        편집(개) 원본움직임(개)  쓰는 영상 수   훅/본문/끝")
    for k in KINDS:
        print(f"{k:10s} {tot[(k,'편집')]:6d} {tot[(k,'원본')]:12d} {vids_with[k]:8d}/{len(res)}"
              f"      {zone[(k,'hook')]}/{zone[(k,'body')]}/{zone[(k,'end')]}")
    print("\n채널별 (편수 · 컷 평균길이 · 편집효과 수)")
    by = collections.defaultdict(list)
    for r in res:
        by[r["channel"]].append(r)
    for ch, rs in sorted(by.items(), key=lambda x: -len(x[1])):
        cnt = collections.Counter(e["kind"] for r in rs for e in r["events"] if e["kind"] != "cut" and e.get("edit") is not False)
        cl = statistics.median(r["dur"] / max(1, r["cuts"] + 1) for r in rs)
        print(f"  {ch:14s} {len(rs)}편 컷 {cl:.2f}초  {dict(cnt)}")


if __name__ == "__main__":
    main(sys.argv[1:])
