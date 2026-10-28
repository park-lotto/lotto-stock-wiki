# -*- coding: utf-8 -*-
"""유튜브 썰채널 등급 — 문장틀은 **검증 채널 원문에서만** 수확한다 (2026-09-18 사장님 "S급 채널은 검증하고 받는거야?").

원리는 인스타 등급제(channel_tier.py: 히트 2건 이상 = A, "1건은 운, 2건이면 실력")와 같다.
유튜브는 댓글 대신 목록에 딸려 오는 조회수로 판정한다(yt-dlp flat-playlist가 view_count를 준다, API 쿼터 0).

    S  조회수 100만+ 영상 2편 이상
    A  조회수 10만+ 영상 2편 이상        ← 여기까지 '검증 채널'
    B  10만+ 1편 (운일 수 있음)
    C  10만+ 0편

입력: 채널 확장 수집의 hits_all.json(채널당 80편 목록)
출력: verified_channels.json {channel: grade, ...} + 표 출력
    py tools/spine_presets/grade_yt_channels.py raw/analysis/썰쇼핑_채널확장_2026-09-18/hits_all.json
"""
import collections
import io
import json
import os
import sys

HIT = 100_000
MEGA = 1_000_000
MIN_COUNT = 2


def grade(rows):
    by = collections.defaultdict(list)
    for r in rows:
        by[r.get("channel") or ""].append(int(r.get("views") or 0))
    out = {}
    for ch, vs in by.items():
        mega = sum(1 for v in vs if v >= MEGA)
        hit = sum(1 for v in vs if v >= HIT)
        g = "S" if mega >= MIN_COUNT else "A" if hit >= MIN_COUNT else "B" if hit == 1 else "C"
        out[ch] = {"grade": g, "videos": len(vs), "hit100k": hit, "hit1m": mega, "max": max(vs) if vs else 0}
    return out


def main():
    src = sys.argv[1]
    rows = json.load(io.open(src, encoding="utf-8"))
    g = grade(rows)
    dst = os.path.join(os.path.dirname(src), "verified_channels.json")
    json.dump(g, io.open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cnt = collections.Counter(v["grade"] for v in g.values())
    print("채널 %d곳 등급: %s" % (len(g), dict(sorted(cnt.items()))))
    for ch, v in sorted(g.items(), key=lambda kv: (-kv[1]["hit1m"], -kv[1]["hit100k"]))[:25]:
        print("  %s  %-14s 80편중 10만+ %2d · 100만+ %2d · 최고 %s" % (v["grade"], ch[:14], v["hit100k"], v["hit1m"], f"{v['max']:,}"))
    print("검증(S·A) 채널:", sum(1 for v in g.values() if v["grade"] in ("S", "A")), "→", dst)


if __name__ == "__main__":
    main()
