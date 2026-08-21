# -*- coding: utf-8 -*-
"""3스타일 채널을 **계속** 발굴한다 — 쿼터가 마르면 자고, 리셋되면 다시 돈다.

사장님 지시(2026-08-19): "수집은 계속 돌려줘. 아주 많아야해."

한 사이클 =
  1) 스타일마다 수확: 통과 채널의 실제 제목에서 신호 조합을 뽑아 새 검색어 생성
  2) 검색 -> 만난 채널
  3) 검증: 최근 25편을 채점(썰쇼핑=판정기 / 연예인·레시피=결합 3편+)
  4) 통과분 누적 -> 다음 사이클의 수확 대상

쿼터(무료 10,000/일)가 마르면 죽지 않고 잔다. 아침 수집 몫 RESERVE는 남긴다.
결과는 /tmp/style_state.json 에 계속 쌓인다(등록은 사람이 register_styles.py로).
"""
# ★2026-08-19 리포 편입: 이 스크립트는 서버 `/tmp`에만 있었다 —
#   재부팅 한 번이면 발굴 루프가 통째로 사라진다(상태파일 /tmp/style_state.json도 같다).
#   앞으로는 이 파일이 정본이다. 서버에서 돌릴 때도 리포 경로에서 돌려라:
#     cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a #       && setsid python3 -u scripts/harvest_styles_forever.py >> /tmp/harvest_forever.out 2>&1 &
#   어휘축(권위자·부정어·귀결어)은 여기 적지 않는다 — `shopping_shorts/categorize.py`가
#   유일한 출처다(0순위-B). 발굴을 넓히려면 거기를 넓혀라.
import os
import sys
import json
import time
import re
import collections
import itertools
import datetime
import urllib.request
import urllib.parse
import urllib.error
import importlib.util
import types

BASE = "/home/ubuntu/lotto-stock-wiki/shopping_shorts"
STATE = "/tmp/style_state.json"
LOG = "/tmp/harvest_forever.log"
RESERVE = 3500          # 아침 채널수집(1,600채널x2)이 쓸 몫은 건드리지 않는다

# ★키는 config.py와 **같은 규칙**으로 읽는다(0순위-B: 같은 판단을 두 번 적지 마라).
#   YOUTUBE_API_KEY, YOUTUBE_API_KEY_2 ... _30 넘버링 스캔.
#   실측 사고(2026-08-19): 내 스크립트가 YOUTUBE_API_KEYS 한 변수만 읽어서
#   서버에 키가 10개 있는데 **1개만 쓰고** 쿼터를 1/10로 알고 돌았다.
_MAX = 30
KEYS = [v for i in range(1, _MAX + 1)
        if (v := os.environ.get("YOUTUBE_API_KEY" if i == 1 else "YOUTUBE_API_KEY_%d" % i, ""))]
if not KEYS:                                     # 예전 형식도 받아준다
    RAW = os.environ.get("YOUTUBE_API_KEYS", "")
    KEYS = [k for k in RAW.replace(",", " ").split() if k]
assert KEYS, "no keys"
DAILY = 10000 * len(KEYS)       # 키 1개당 하루 10,000 units

pkg = types.ModuleType("shopping_shorts")
pkg.__path__ = []
sys.modules.setdefault("shopping_shorts", pkg)


def _load(nm, *paths):
    for p in paths:
        if os.path.exists(p):
            sp = importlib.util.spec_from_file_location("shopping_shorts." + nm, p)
            m = importlib.util.module_from_spec(sp)
            sys.modules["shopping_shorts." + nm] = m
            sp.loader.exec_module(m)
            return m, p
    raise SystemExit("missing " + nm)


cz, czp = _load("categorize", BASE + "/categorize.py", "/tmp/categorize.py")
if "오용형" not in getattr(cz, "KEYWORDS", {}):
    cz, czp = _load("categorize", "/tmp/categorize.py")
ys, ysp = _load("yt_style", BASE + "/yt_style.py", "/tmp/yt_style.py")


def log(msg):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%m-%d %H:%M"), msg)
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


used = {"u": 0, "dry": False}


def _api(path, params):
    for k in KEYS:
        u = ("https://www.googleapis.com/youtube/v3/" + path + "?"
             + urllib.parse.urlencode(dict(params, key=k)))
        try:
            with urllib.request.urlopen(u, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                continue
            return None
        except Exception:
            return None
    used["dry"] = True
    return None


def search(q):
    # ★상한은 **전체 키 합계 - RESERVE**다. 키가 10개면 100,000이라 하루종일 돈다.
    #   진짜 소진 판정은 _api가 모든 키에서 403/429를 본 순간(used["dry"])이다 —
    #   내 카운터는 추정치일 뿐이고, 다른 기능도 같은 키를 쓰기 때문.
    if used["u"] + 100 > DAILY - RESERVE:
        used["dry"] = True
        return None
    used["u"] += 100
    return _api("search", {"part": "snippet", "q": q, "type": "video",
                           "maxResults": "50", "regionCode": "KR",
                           "relevanceLanguage": "ko", "order": "viewCount"})


def uploads(cid, n=25):
    if used["u"] + 2 > DAILY - RESERVE:
        used["dry"] = True
        return None, None
    used["u"] += 2
    ch = _api("channels", {"part": "contentDetails,statistics", "id": cid})
    if not ch or not ch.get("items"):
        return None, None
    it = ch["items"][0]
    pl = _api("playlistItems", {
        "part": "snippet",
        "playlistId": it["contentDetails"]["relatedPlaylists"]["uploads"],
        "maxResults": str(n)})
    if not pl:
        return None, None
    return [x["snippet"]["title"] for x in pl.get("items", [])], it["statistics"]


def _h(t, words):
    lt = t.lower()
    return sum(1 for w in words if w in lt)


def score_sul(titles, name=""):
    return sum(1 for t in titles if cz.categorize(name, t) in ("제품정체형", "오용형"))


def score_celeb(titles, name=""):
    return sum(1 for t in titles if _h(t, ys._CELEB) and _h(t, ys._PRODUCT))


def score_food(titles, name=""):
    # 음식 판정은 yt_style 한 곳에서만 한다(0순위-B) — '만들기' 오탐 처방이 두 벌이 되면
    # 채널은 걸러지는데 랭킹은 안 걸러지는 어긋남이 난다(2026-08-21).
    return sum(1 for t in titles if ys.is_food_title(t) and _h(t, ys._PRODUCT))


def harvest_sul(titles):
    out = collections.Counter()
    for t in titles:
        lt = t.lower()
        a = [x for x in cz._MISUSE_AUTH if x in lt][:2]
        n = [x for x in cz._MISUSE_NEG if x in lt][:2]
        e = [x for x in cz.KEYWORDS["오용형"] if x in lt][:2]
        for c in itertools.product(a, n, e):
            out["%s도 %s %s" % c] += 1
    return out


def harvest_pair(titles, left, right):
    out = collections.Counter()
    for t in titles:
        lt = t.lower()
        a = [x for x in left if x in lt][:2]
        b = [x for x in right if x in lt][:2]
        for c in itertools.product(a, b):
            out["%s %s" % c] += 1
    return out


STYLES = {
    "썰쇼핑": {"score": score_sul, "min": 2,
             "harvest": lambda ts: harvest_sul(ts)},
    "연예인결합": {"score": score_celeb, "min": 3,
                "harvest": lambda ts: harvest_pair(ts, ys._CELEB, ys._PRODUCT)},
    "레시피쇼핑": {"score": score_food, "min": 3,
                "harvest": lambda ts: harvest_pair(ts, ys._FOOD, ys._PRODUCT)},
    # 2026-08-20 신설 — 위 score_novel 주석 참고. min 3은 다른 축과 같은 눈높이.
    # 2026-08-20 신설 — 판정·검색어 생성은 yt_style에 있다(어휘축이 사는 곳, 0순위-B).
    # ★신기템만 문턱이 둘이다(2026-08-21 실측). 이 축은 판정이 쉬워 다른 축과 같은
    #   눈높이(min 3)로 두면 우연히 걸린 채널이 통째로 들어온다. 하룻밤 549채널을
    #   열어보니 두 종류로 오염돼 있었다:
    #     ① 잡채널 — 구독 중앙값 264(다른 축 1,410~8,030), 100명 미만이 38%
    #     ② 대형 오탐 — 25편 중 3편(12%)만 우연히 맞은 큰 채널
    #        (시스레터 1/12=이케아 브이로그 · 알쓸피식 2/12=피부과 · 서툴러도 1/12)
    #        진짜(오늘의건짐 3/12 ≈ 6/25)와 갈리는 선이 25편 중 5편이었다.
    #   연예인·오용형은 공식 자체가 어려워 그게 곧 필터였고, 이 축은 그게 없다.
    #   실측 잔존: 549 → 68채널(구독 중앙값 10,450) — 다른 축과 같은 급이 된다.
    "신기템": {"score": ys.score_novel, "min": 5, "min_subs": 1000,
             "harvest": lambda ts: ys.harvest_novel(ts)},
}
BLOCK = ["뉴스", "news", "kbs", "mbc", "sbs", "jtbc", "ytn", "연합", "정치", "국회",
         "설교", "복음", "사주", "asmr", "게임", "롤", "피파", "먹튀", "토토"]


def load():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    s = {"styles": {}, "tried": [], "seen": [], "rejected": {}, "cycles": 0}
    if os.path.exists("/tmp/harvest_state.json"):
        h = json.load(open("/tmp/harvest_state.json"))
        s["styles"]["썰쇼핑"] = {
            c: {"title": i["title"], "subs": i.get("subs", 0), "score": i.get("misuse", 0)}
            for c, i in (h.get("verified") or {}).items()}
        s["styles"]["썰쇼핑"]["UCBFu04us6bv9OFcwrJDXdMg"] = {
            "title": "살림킹왕짱", "subs": 14600, "score": 20}
        s["tried"] = h.get("tried_kw") or []
        s["seen"] = h.get("seen") or []
    if os.path.exists("/tmp/style_candidates.json"):
        for stl, rows in json.load(open("/tmp/style_candidates.json")).items():
            s["styles"].setdefault(stl, {})
            for r in rows:
                s["styles"][stl][r["cid"]] = {
                    "title": r["title"], "subs": r.get("subs", 0), "score": r.get("score", 0)}
    return s


st = load()
st.setdefault("styles", {})
st.setdefault("rejected", {})
st.setdefault("cycles", 0)
for k in STYLES:
    st["styles"].setdefault(k, {})

# 새 축은 **씨앗이 없으면 영영 못 큰다**(2026-08-20 신기템 신설에서 실측).
# 사이클은 `for cid in list(pool)[-10:]`로 **이미 가진 채널의 제목에서** 다음 검색어를
# 뽑는다 — 풀이 0이면 뽑을 제목이 없고, 검색어가 없으니 새 채널도 못 찾는다.
# 즉 빈 풀은 스스로 못 벗어난다(썰쇼핑도 같은 이유로 '살림킹왕짱'을 심어 뒀다).
# 씨앗은 라이브 실측으로 고른 채널이다 — score_novel 4점(12편 중), 전부 [기능
# 관형어]+[제품] 틀. rejected에 있으면 빼준다(거절 목록에 남으면 다시 안 본다).
_SEEDS = {
    "신기템": {
        "UC6FhOTXF3D0oDtOILYnkKow": {"title": "꿀템 보물찾기", "subs": 0, "score": 4},
        "UCXQRYw25xKBXGaMfb4FnnZQ": {"title": "홈템꿀팁 | 살림, 꿀템", "subs": 0, "score": 4},
    },
}
for _stl, _seed in _SEEDS.items():
    if _stl in STYLES and not st["styles"].get(_stl):
        st["styles"][_stl] = dict(_seed)
        for _cid in _seed:
            st["rejected"].pop(_cid, None)
        log("씨앗 심음 — %s %d채널" % (_stl, len(_seed)))
tried = set(st.get("tried") or [])
seen = set(st.get("seen") or [])
for k, v in st["styles"].items():
    seen |= set(v)

log("시작 — 판정기 %s / %s | 키 %d개 · 하루한도 %s units(예비 %d 제외)"
    % (os.path.basename(czp), os.path.basename(ysp), len(KEYS),
       format(DAILY, ","), RESERVE))
log("보유: " + " · ".join("%s %d" % (k, len(v)) for k, v in st["styles"].items()))


def save():
    st["tried"] = sorted(tried)
    st["seen"] = sorted(seen)
    json.dump(st, open(STATE, "w"), ensure_ascii=False)


def sleep_until_reset():
    now = datetime.datetime.utcnow()
    reset = now.replace(hour=7, minute=10, second=0, microsecond=0)   # PT 00:10 = UTC 07:10
    if reset <= now:
        reset += datetime.timedelta(days=1)
    secs = int((reset - now).total_seconds())
    log("쿼터 소진 — %d분 뒤 리셋까지 대기 (사용 %d units)" % (secs // 60, used["u"]))
    save()
    time.sleep(secs)
    used["u"] = 0
    used["dry"] = False
    log("쿼터 리셋 — 재개")


MAX_CYCLES = int(os.environ.get("MAX_CYCLES", "1000"))
while st["cycles"] < MAX_CYCLES:
    st["cycles"] += 1
    made_any = False
    for style, cfg in STYLES.items():
        if used["dry"]:
            break
        pool = st["styles"][style]
        combos = collections.Counter()
        for cid in list(pool)[-10:]:
            titles, _ = uploads(cid)
            if not titles:
                continue
            good = [t for t in titles if cfg["score"]([t], pool[cid]["title"])]
            combos += cfg["harvest"](good)
            if used["dry"]:
                break
        fresh = [k for k, _ in combos.most_common(60) if k not in tried]
        if not fresh:
            continue
        batch = fresh[:4]
        met = {}
        for kw in batch:
            d = search(kw)
            tried.add(kw)
            if d is None:
                break
            for it in d.get("items", []):
                sn = it["snippet"]
                met.setdefault(sn["channelId"], sn["channelTitle"])
        cand = [(c, t) for c, t in met.items() if c not in seen]
        new = 0
        for cid, title in cand:
            if used["dry"]:
                break
            lt = (title or "").lower()
            if any(b in lt for b in BLOCK):
                seen.add(cid)
                st["rejected"][cid] = title
                continue
            titles, stats = uploads(cid)
            seen.add(cid)
            if not titles:
                st["rejected"][cid] = title
                continue
            sc = cfg["score"](titles, title)
            subs = int((stats or {}).get("subscriberCount", 0))
            # ★구독자 하한(2026-08-20 신기템 실측). 판정이 쉬운 축은 신생·소형 채널이
            #   전부 통과해 풀이 잡채널로 찬다 — 하룻밤에 549채널이 들어왔는데 구독
            #   중앙값 264(다른 축 1,410~8,030), 100명 미만이 38%였다. 연예인·오용형
            #   공식은 어려워서 그 자체가 필터였던 것이고, 신기템은 그게 없다.
            #   레퍼런스로 쓸 수 없는 채널은 **안 담는 게 낫다** — 담아두면 다음 회차가
            #   그 채널 제목에서 검색어를 뽑아 같은 급을 계속 데려온다(오염이 번진다).
            if sc >= cfg["min"] and subs >= cfg.get("min_subs", 0):
                pool[cid] = {"title": title, "subs": subs, "score": sc}
                new += 1
                made_any = True
            else:
                st["rejected"][cid] = title
        if new:
            log("C%d [%s] +%d (누적 %d) 검색어 %s"
                % (st["cycles"], style, new, len(pool), batch[:2]))
    save()
    if used["dry"]:
        sleep_until_reset()
    elif not made_any:
        log("C%d 신규 0 — 60초 후 계속 (사용 %d)" % (st["cycles"], used["u"]))
        time.sleep(60)

log("종료 — " + " · ".join("%s %d" % (k, len(v)) for k, v in st["styles"].items()))
