# -*- coding: utf-8 -*-
"""전사 대상을 고른다 — ★**판정기에 안 걸린 영상**을 우선한다 (2026-09-05).

## 왜 이게 필요한가 (돌리다 발견한 것)

발굴 루프의 판정기(`categorize`)는 **이미 정의된 축만** 알아본다
(오용형·제품정체형·장비템·차량템 — 전부 라이브에 이미 있는 것).
그래서 이 루프만으로는 **새 축을 영영 못 찾는다.**

    통과 41채널 · 검사 995편 → 축에 걸린 것 292편 / **안 걸린 것 703편**

★새 축은 저 703편에 있다 — 좋은 채널이 만들었는데 판정기가 모르는 문법이다.
  기존 축에 걸린 것만 전사하면 이미 아는 것만 다시 확인하게 된다.

## 그래서 두 무리를 나눠 뽑는다

    unknown  판정기에 안 걸린 영상 (조회수 상위)  ← 새 축 후보. 여기가 본체
    known    걸린 영상 (축마다 조회수 상위)        ← 대조군. 기존 축이 자막에서
                                                 어떻게 생겼는지 비교용

대조군이 없으면 "새로 보이는 것"이 진짜 새것인지, 기존 축의 변형인지 못 가른다
(memory: 정렬률_대조군없으면과장 — 대조군 없이 재면 과장·오판한다).

실행:
    py scripts/pick_unknown.py --n-unknown 400 --n-known 120
"""
import argparse
import collections
import io
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = BASE / "out" / "sul_survey"
VIDEOS = OUT / "videos.json"
PICK = OUT / "pick.json"

from shopping_shorts import categorize as cz          # noqa: E402

AXES = (("오용형", cz._is_misuse), ("제품정체형", cz._is_hook_product),
        ("장비템", cz._is_gear), ("차량템", cz._is_car))


def axis_of(title):
    """이 제목이 걸리는 기존 축들. ★인자 순서 (name_t, cap_t) — 제목은 두 번째."""
    got = []
    for nm, fn in AXES:
        try:
            if fn("", title):
                got.append(nm)
        except Exception:
            pass
    return got


def _api_titles(ids):
    """★영상 제목을 **YouTube API**에서 받는다 (videos.list, 50개당 1 unit).

    ⚠️yt-dlp 제목은 자동번역 영어라 판정이 통째로 무력화된다 —
      실측 2,707편 중 96%가 영어였고, 그걸로 판정하니 100%가 '안 걸림'이었다.
      축 판정은 **반드시 한국어 원제목**으로 한다.
    """
    import os
    import urllib.parse
    import urllib.request

    keys = []
    env = BASE / ".env"
    vals = {}
    if env.exists():
        for ln in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    for i in range(1, 31):
        nm = "YOUTUBE_API_KEY" if i == 1 else "YOUTUBE_API_KEY_%d" % i
        v = os.environ.get(nm) or vals.get(nm, "")
        if v:
            keys.append(v)
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        for k in keys:
            u = ("https://www.googleapis.com/youtube/v3/videos?"
                 + urllib.parse.urlencode({"part": "snippet", "id": ",".join(chunk),
                                           "key": k}))
            try:
                with urllib.request.urlopen(u, timeout=30) as r:
                    d = json.load(r)
                for it in d.get("items", []):
                    out[it["id"]] = (it["snippet"] or {}).get("title") or ""
                break
            except Exception:
                continue
    return out


def main(n_unknown, n_known):
    if not VIDEOS.exists():
        print("videos.json이 없다 — 먼저 transcribe_hits.py --collect")
        return
    vids = json.loads(VIDEOS.read_text(encoding="utf-8"))
    vids.sort(key=lambda v: -v.get("views", 0))

    # ★판정 전에 한국어 원제목으로 갈아끼운다(yt-dlp 제목은 영어라 판정 불가).
    need = [v["video_id"] for v in vids if not v.get("title_ko")]
    if need:
        print("한국어 원제목 %d편 API로 받는다 (%d units)"
              % (len(need), (len(need) + 49) // 50))
        got = _api_titles(need)
        for v in vids:
            if v["video_id"] in got:
                v["title_ko"] = got[v["video_id"]]
        VIDEOS.write_text(json.dumps(vids, ensure_ascii=False, indent=1), encoding="utf-8")
        print("  받음 %d편" % len(got))

    unknown, known = [], collections.defaultdict(list)
    for v in vids:
        # ★판정은 한국어 원제목으로만(위 _api_titles 주석 참조)
        ax = axis_of(v.get("title_ko") or "")
        if ax:
            for a in ax:
                known[a].append(v)
        else:
            unknown.append(v)

    pick_u = unknown[:n_unknown]
    per = max(1, n_known // max(1, len(known)))
    pick_k = []
    for a, rows in known.items():
        for v in rows[:per]:
            if v not in pick_k:
                pick_k.append({**v, "known_axis": a})

    out = ([{**v, "group": "unknown"} for v in pick_u]
           + [{**v, "group": "known"} for v in pick_k])
    PICK.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("전체 %d편 → 안 걸림 %d · 걸림 %d"
          % (len(vids), len(unknown), sum(len(r) for r in known.values())))
    print("축별 걸린 편수: %s" % {a: len(r) for a, r in known.items()})
    print()
    print("★전사 대상 %d편 = unknown %d + known(대조군) %d"
          % (len(out), len(pick_u), len(pick_k)))
    print("  → out/sul_survey/pick.json")
    print()
    print("안 걸린 것 중 조회수 상위 12편 (여기에 새 축이 있다):")
    for v in pick_u[:12]:
        print("  %9d  %-14s %s"
              % (v["views"], v["channel"][:12],
                 (v.get("title_ko") or v.get("title") or "")[:50]))

    # ★자기검사 — 한국어 제목을 못 받았으면 판정이 통째로 무력하다.
    no_ko = sum(1 for v in vids if not v.get("title_ko"))
    if no_ko:
        print("\n⚠️한국어 원제목 없는 영상 %d편 — 이들은 판정이 불가해 unknown으로 샌다"
              % no_ko)
    if not known:
        print("⚠️★걸린 영상이 0건이다 — 판정기가 안 도는 것을 의심하라"
              "(영어 제목으로 판정하면 항상 이렇게 된다)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-unknown", type=int, default=400)
    ap.add_argument("--n-known", type=int, default=120)
    a = ap.parse_args()
    main(a.n_unknown, a.n_known)
