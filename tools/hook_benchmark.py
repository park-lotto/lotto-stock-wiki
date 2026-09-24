# -*- coding: utf-8 -*-
"""터진 영상의 **훅 장면**이 안 터진 영상과 뭐가 다른가를 잰다 (2026-09-24).

왜 있나: 사장님 지시 — "훅이 뭐가 좋을지는 터진 영상 위주로 벤치마킹해서 규칙을 만들어라,
직접 생각하게 하지 마라." 그래서 이 도구는 아무것도 지어내지 않는다. 태깅된 영상의
**첫 장면**만 뽑아 조회수 상위군과 하위군을 대조한다.

★대조군이 핵심이다. 터진 것만 보면 "첫 컷이 1초다" 같은 말이 나오는데, 안 터진 것도
  1초면 아무 의미가 없다. 차이가 나는 것만 규칙이 된다(CLAUDE.md 0순위-A1b).

    python3 tools/hook_benchmark.py [--db 경로] [--top 10] [--bottom 50] [--exclude 채널]

출력: 첫 컷 길이·첫 3초 컷 수·훅 축 분포·첫 장면 어휘 리프트(상위군/하위군 비율).
"""
import argparse
import json
import re
import sqlite3
from collections import Counter

JOSA = ("에서", "으로", "에게", "이라", "라고", "까지", "부터", "처럼", "보다",
        "은", "는", "이", "가", "을", "를", "에", "로", "와", "과", "의", "도", "만", "랑")


def norm(tok):
    """어절에서 흔한 조사를 떼어 낸다. 형태소 분석기 없이 셀 수 있을 만큼만."""
    t = re.sub(r"[^가-힣a-zA-Z0-9]", "", tok)
    for j in JOSA:
        if len(t) > len(j) + 1 and t.endswith(j):
            return t[: -len(j)]
    return t


def rows(db, exclude):
    q = ("select a.username, a.views, e.hook_axis, e.script_json "
         "from script_extracts e join channel_archive a on a.shortcode = e.shortcode "
         "where a.views > 0 and e.script_json is not null")
    c = sqlite3.connect(db)
    out = []
    for username, views, axis, sj in c.execute(q):
        if exclude and username in exclude:
            continue
        try:
            segs = (json.loads(sj) or {}).get("segments") or []
        except Exception:                      # noqa: BLE001 — 깨진 행은 버린다
            continue
        if not segs:
            continue
        def f(v, d=0.0):
            try:
                return float(v)
            except (TypeError, ValueError):
                return d
        first = segs[0]
        dur = f(first.get("end")) - f(first.get("start"))
        in3 = sum(1 for s in segs if f(s.get("start")) < 3.0)
        out.append({"views": int(views), "axis": axis or "(없음)",
                    "first_dur": round(dur, 2), "cuts_in_3s": in3,
                    "desc": str(first.get("scene_desc") or ""),
                    "text": str(first.get("text") or "")})
    return out


def dist(vals, label):
    vals = sorted(v for v in vals if v > 0)
    if not vals:
        return f"  {label}: 없음"
    n = len(vals)
    q = lambda p: vals[min(n - 1, int(n * p))]
    return ("  %-6s 편수 %4d · 중앙값 %.2f · 하위25%% %.2f · 상위25%% %.2f"
            % (label, n, q(0.5), q(0.25), q(0.75)))


def lift(hit, rest, key, minimum=6, top=18):
    """상위군에서 하위군보다 몇 배 자주 나온 말인가."""
    ch, cr = Counter(), Counter()
    for r in hit:
        for t in {norm(x) for x in r[key].split()}:
            if len(t) >= 2:
                ch[t] += 1
    for r in rest:
        for t in {norm(x) for x in r[key].split()}:
            if len(t) >= 2:
                cr[t] += 1
    nh, nr = max(1, len(hit)), max(1, len(rest))
    out = []
    for t, k in ch.items():
        if k < minimum:
            continue
        ph, pr = k / nh, (cr.get(t, 0) + 0.5) / nr
        out.append((ph / pr, k, round(ph * 100, 1), round(pr * 100, 1), t))
    out.sort(reverse=True)
    return out[:top]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="shopping_shorts/data/reference.db")
    ap.add_argument("--top", type=int, default=10, help="상위 몇 %%를 '터진'으로 볼지")
    ap.add_argument("--bottom", type=int, default=50, help="하위 몇 %%를 대조군으로 볼지")
    ap.add_argument("--exclude", default="", help="뺄 채널(쉼표)")
    a = ap.parse_args()

    rs = rows(a.db, {x.strip() for x in a.exclude.split(",") if x.strip()})
    rs.sort(key=lambda r: -r["views"])
    n = len(rs)
    hit = rs[: max(1, n * a.top // 100)]
    rest = rs[-max(1, n * a.bottom // 100):]
    print("표본 %d편 · 터진(상위%d%%) %d편 [%s회 이상] · 대조(하위%d%%) %d편 [%s회 이하]"
          % (n, a.top, len(hit), f"{hit[-1]['views']:,}", a.bottom, len(rest), f"{rest[0]['views']:,}"))

    print("\n■ 첫 장면 길이(초)")
    print(dist([r["first_dur"] for r in hit], "터진"))
    print(dist([r["first_dur"] for r in rest], "대조"))

    print("\n■ 첫 3초 안 컷 수")
    print(dist([r["cuts_in_3s"] for r in hit], "터진"))
    print(dist([r["cuts_in_3s"] for r in rest], "대조"))

    print("\n■ 훅 축(hook_axis) — 터진 쪽 비율 / 대조 비율")
    ah, ar = Counter(r["axis"] for r in hit), Counter(r["axis"] for r in rest)
    for k, v in ah.most_common(10):
        print("  %-10s %5.1f%%  vs %5.1f%%" % (k, v / len(hit) * 100, ar.get(k, 0) / len(rest) * 100))

    print("\n■ 첫 장면 설명에 더 자주 나온 말 (배수 · 터진%% · 대조%%)")
    for mul, k, ph, pr, t in lift(hit, rest, "desc"):
        print("  %-12s %4.1f배  %5.1f%% vs %5.1f%%  (%d편)" % (t, mul, ph, pr, k))

    print("\n■ 첫 대사에 더 자주 나온 말")
    for mul, k, ph, pr, t in lift(hit, rest, "text", minimum=5, top=12):
        print("  %-12s %4.1f배  %5.1f%% vs %5.1f%%  (%d편)" % (t, mul, ph, pr, k))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
