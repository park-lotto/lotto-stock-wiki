# -*- coding: utf-8 -*-
"""썰채널 전수조사 — **로컬에서 도는** 자가증식 발굴 루프 (2026-09-05).

## 왜 새로 쓰나

`scripts/harvest_styles_forever.py`가 정본이지만 경로가 **서버 전용**으로 박혀 있다
(`/home/ubuntu/...`, `/tmp/style_state.json`). 지금 이 PC는 SSH가 막혀 서버에서 못 돌린다.
그래서 **판정 로직은 그대로 빌려 쓰고**(`categorize._is_misuse` 등) 경로·상태만 로컬로 돌린다.
★어휘축(권위자·부정어·귀결어)은 여기 적지 않는다 — `categorize.py`가 유일한 출처다(0순위-B).

## 한 사이클

    ① 수확  통과 채널의 **실제 제목**에서 신호 조합을 뽑아 새 검색어를 만든다
    ② 검색  안 써본 조합으로 search.list (100 units/회)
    ③ ★검증 신규 채널마다 최근 N편을 **판정기에 돌려** 기준 통과만 남긴다 (2 units)
    ④ 통과 채널이 다음 사이클의 수확 대상 → ①

★검증 단계가 일의 대부분을 한다. 오용형발굴 실측에서 이 단계가 **180개를 배제**했다
  (검색 히트 1위가 게임 채널 '킬폭'이었다). 검색 히트수만 믿으면 안 된다.

## 토큰

결과는 **전부 파일에 쌓는다**(state.json). 화면에는 진행 한 줄씩만 찍는다 —
수천 편을 대화창에 띄우면 컨텍스트가 터진다.

실행:
    py scripts/harvest_sul_local.py --rounds 12
    py scripts/harvest_sul_local.py --status      # 쌓인 것만 본다
"""
import argparse
import collections
import datetime
import io
import itertools
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OUT = BASE / "out" / "sul_survey"
OUT.mkdir(parents=True, exist_ok=True)
STATE = OUT / "state.json"
LOG = OUT / "harvest.log"

from shopping_shorts import categorize as cz          # noqa: E402

# ── 키: config와 같은 규칙(YOUTUBE_API_KEY, _2 ... _30) ──────────────────
def _load_keys():
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
    return keys


KEYS = _load_keys()
DAILY = 10000 * max(1, len(KEYS))
RESERVE = 500                     # 다른 기능 몫은 남긴다
used = {"u": 0, "dry": False}


def log(msg):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%m-%d %H:%M"), msg)
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _api(path, params):
    for k in KEYS:
        u = ("https://www.googleapis.com/youtube/v3/" + path + "?"
             + urllib.parse.urlencode(dict(params, key=k)))
        try:
            with urllib.request.urlopen(u, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                continue          # 이 키는 말랐다 — 다음 키
            return None
        except Exception:
            return None
    used["dry"] = True
    return None


def search(q, n=50):
    if used["u"] + 100 > DAILY - RESERVE:
        used["dry"] = True
        return []
    used["u"] += 100
    d = _api("search", {"part": "snippet", "q": q, "type": "video",
                        "maxResults": n, "order": "viewCount",
                        "relevanceLanguage": "ko"})
    return (d or {}).get("items", []) or []


def uploads_titles(cid, n=25):
    """채널 최근 업로드 제목 — 검증용. 2 units."""
    if used["u"] + 2 > DAILY - RESERVE:
        used["dry"] = True
        return []
    used["u"] += 2
    d = _api("channels", {"part": "contentDetails", "id": cid})
    items = (d or {}).get("items") or []
    if not items:
        return []
    pl = items[0]["contentDetails"]["relatedPlaylists"].get("uploads")
    if not pl:
        return []
    d = _api("playlistItems", {"part": "snippet", "playlistId": pl, "maxResults": n})
    return [(it["snippet"].get("title") or "")
            for it in ((d or {}).get("items") or [])]


# ── 검증 — ★판정은 categorize 한 벌만 쓴다(0순위-B) ────────────────────
def judge(titles):
    """제목 목록 → {축: 편수}. categorize의 판정기를 그대로 부른다.

    ★인자 순서가 `(name_t, cap_t)`다 — **영상 제목은 두 번째(cap_t)**에 넣는다.
      첫 자리는 채널명이다. 여기에 제목을 넣으면 판정이 통째로 어긋난다
      (handoff/오용형발굴.md 실사고: 차단어 검사를 채널명까지 묶었더니 '살림치트키'가
       채널명의 '치트키' 두 글자 때문에 전 영상이 죽었다 → 차단은 cap_t로만).
      실측으로 확인함: 제목을 name_t에 넣으면 오용형 제목도 False가 나온다.
    """
    got = collections.Counter()
    for t in titles:
        for axis, fn in (("오용형", cz._is_misuse), ("제품정체형", cz._is_hook_product),
                         ("장비템", cz._is_gear), ("차량템", cz._is_car)):
            try:
                if fn("", t):          # name_t="" · cap_t=제목
                    got[axis] += 1
            except Exception:
                pass
    return got


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"passed": {}, "rejected": {}, "queries_done": [], "units": 0}


def save_state(st):
    st["units"] = used["u"]
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 수확: 통과 채널 제목에서 새 검색어를 만든다 ──────────────────────────
_WORD = re.compile(r"[가-힣]{2,}")

def harvest_queries(st, want=6):
    """통과 채널들의 제목에서 자주 나온 말 조합 → 새 검색어."""
    words = collections.Counter()
    for ch in st["passed"].values():
        for t in ch.get("sample_titles", []):
            for w in _WORD.findall(t):
                if len(w) >= 2:
                    words[w] += 1
    common = [w for w, c in words.most_common(40) if c >= 2]
    done = set(st["queries_done"])
    out = []
    for a, b in itertools.combinations(common[:18], 2):
        q = "%s %s" % (a, b)
        if q not in done:
            out.append(q)
        if len(out) >= want:
            break
    return out


SEED_QUERIES = [
    "제조사도 모르는 사용법", "개발자도 놀란 활용법", "이걸 이렇게 쓴다고",
    "원래 용도는 따로", "숨은 기능 발견", "잘못 쓰고 있던 물건",
]


def run(rounds, per_ch=25, min_hits=2):
    if not KEYS:
        log("★유튜브 API 키가 없다 — .env 확인")
        return
    st = load_state()
    log("시작 — 키 %d개 · 상한 %d units · 이미 통과 %d채널"
        % (len(KEYS), DAILY - RESERVE, len(st["passed"])))

    for rd in range(1, rounds + 1):
        if used["dry"]:
            log("쿼터 소진 — 중단")
            break
        qs = harvest_queries(st) or []
        if not qs:
            qs = [q for q in SEED_QUERIES if q not in set(st["queries_done"])][:3]
        if not qs:
            log("새 검색어 없음 — 수렴")
            break

        new_ch = 0
        for q in qs:
            if used["dry"]:
                break
            items = search(q)
            st["queries_done"].append(q)
            met = {}
            for it in items:
                sn = it.get("snippet") or {}
                cid = sn.get("channelId")
                if cid:
                    met.setdefault(cid, sn.get("channelTitle") or "")
            for cid, name in met.items():
                if used["dry"]:
                    break
                if cid in st["passed"] or cid in st["rejected"]:
                    continue
                titles = uploads_titles(cid, per_ch)
                if not titles:
                    continue
                got = judge(titles)
                total = sum(got.values())
                rec = {"name": name, "hits": dict(got), "total": total,
                       "checked": len(titles), "sample_titles": titles[:8],
                       "found_by": q}
                if total >= min_hits:
                    st["passed"][cid] = rec
                    new_ch += 1
                else:
                    st["rejected"][cid] = {"name": name, "total": total}
            save_state(st)
        log("R%02d  검색어%d  신규통과%d  누적통과%d  배제%d  units%d"
            % (rd, len(qs), new_ch, len(st["passed"]), len(st["rejected"]), used["u"]))
        if new_ch == 0 and rd > 2:
            log("신규 0 — 수렴으로 본다")
            break

    save_state(st)
    log("끝 — 통과 %d / 배제 %d / units %d"
        % (len(st["passed"]), len(st["rejected"]), used["u"]))


def status():
    st = load_state()
    print("통과 %d채널 / 배제 %d / 검색어 %d개 / units %d"
          % (len(st["passed"]), len(st["rejected"]),
             len(st["queries_done"]), st.get("units", 0)))
    rows = sorted(st["passed"].items(), key=lambda kv: -kv[1]["total"])
    print("\n%-24s %5s  %s" % ("채널", "적중", "축별"))
    for cid, r in rows[:40]:
        print("%-24s %5d  %s" % (r["name"][:22], r["total"], r["hits"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--per-ch", type=int, default=25)
    ap.add_argument("--min-hits", type=int, default=2)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        status()
    else:
        run(a.rounds, a.per_ch, a.min_hits)
