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


# 직촬(본인이 찍어 출연) 신호 — 이 결의 채널은 **화면을 재료로 못 쓴다**(2026-09-08 사장님).
# ★씨앗을 고를 때만이 아니라 **발굴이 새로 찾는 채널에도** 걸어야 한다. 안 그러면
#   씨앗만 깨끗하고 자식 세대가 직촬로 오염된다 — 자가증식이라 한 번 새면 계속 번진다.
_VLOG_SIGN = ["브이로그", "vlog", "우리집", "저희집", "남편", "아내", "와이프",
              "먹방", "요리", "레시피", "만들기", "먹는 방법",
              "셀프도배", "셀프시공", "시공", "공사", "이사", "집들이",
              "년차", "구경하고", "루틴", "일상", "vs 딸", "엄마 vs",
              # ★2026-09-08 2차 보강 — 등록한 뒤 실제 업로드를 열어보고 추가했다.
              #   목록에 없어서 통과한 것들: ggyonghouse "월세집 화장실, 일반인이 두 달
              #   동안 셀프로 고친" · "변기 직접달다가" · "천장을 직접 설치하면".
              #   '셀프도배·셀프시공'만 막고 '셀프로 고친/직접 달다'는 안 막고 있었다.
              "셀프로", "직접 설치", "직접 달", "직접 고친", "직접 만든", "뜯다가",
              "고쳐봤", "해봤습니다", "도전", "후기", "리모델링", "인테리어 공사"]

# 이 서비스는 한국어 쇼핑 쇼츠를 만든다 — 제목이 한국어가 아니면 재료로 못 쓴다.
# ★2026-09-08 실측: 홈템 발굴에 Serena Neel(359만)·Lone Fox(178만) 같은 **영어 DIY
#   채널**이 들어왔다. 직촬 차단은 한국어 어휘 목록이라 영어 제목엔 한 글자도 안 걸린다.
#   "차단이 뚫렸다"가 아니라 **애초에 볼 수 없는 것**이었다 — 어휘로 막는 방식의 사각지대다.
_HANGUL_RE = re.compile(r"[가-힣]")


def _mostly_korean(titles, floor=0.5):
    """제목 절반 이상에 한글이 있나. 표본이 없으면 False(모르면 안 받는다)."""
    if not titles:
        return False
    return sum(1 for t in titles if _HANGUL_RE.search(t or "")) / len(titles) >= floor


def score_home(titles, name=""):
    """홈템 축(2026-09-08 사장님 "썰 다음 홈템 잘되는 체널들도 해야하고").

    판정은 `categorize` 한 곳에서만 빌린다(0순위-B) — 여기에 홈템 어휘를 다시 적으면
    채널은 걸러지는데 랭킹은 안 걸러지는 어긋남이 난다(2026-08-21 '만들기' 사고와 동형).
    ★썰쇼핑을 홈템으로 세지 않는다. `categorize`는 두 축을 이미 갈라 주므로
      제품정체형·오용형으로 판정된 편은 여기서 0점이다 — 축이 서로를 잡아먹지 않는다.
    ★직촬 채널은 **0점으로 떨어뜨린다**(2026-09-08 사장님 "살림도 직촬은 안되는데").
      홈템 판정은 통과하지만 화면을 재료로 못 쓰는 결이 있다 — 자기 집·자기 손으로
      찍어 출연하는 채널이다. 25편 중 4편(16%)만 그 결이어도 배제한다: 자가증식
      루프라 한 번 들어오면 그 채널의 어휘로 같은 결을 계속 불러온다.
    """
    if not titles:
        return 0
    if not _mostly_korean(titles):      # 영어권 DIY 채널 차단 — 어휘 목록으로는 못 잡는다
        return 0
    vlog = sum(1 for t in titles if _h(t, _VLOG_SIGN))
    if vlog / len(titles) > 0.16:
        return 0
    return sum(1 for t in titles if cz.categorize(name, t) == "홈템")


def harvest_home(titles):
    """홈템 채널 제목에서 다음 검색어를 만든다 — [홈템어] × [효과어] 조합.

    ★썰쇼핑(harvest_sul)은 [권위자]도 [부정어] [귀결어]라는 **문형**을 쓰지만,
      홈템은 문형이 아니라 **소재**가 축이다("주방 정리 이렇게 하세요"). 그래서
      제품어에 효과어를 붙여 실제로 쓰이는 검색어 모양을 만든다.
    어휘는 categorize.KEYWORDS['홈템']에서 빌린다(0순위-B).
    """
    out = collections.Counter()
    eff = ["정리", "수납", "청소", "꿀템", "추천", "인테리어", "살림템", "필수템"]
    kw = [w for w in cz.KEYWORDS.get("홈템", []) if len(w) >= 2]
    for t in titles:
        lt = t.lower()
        a = [x for x in kw if x in lt][:2]
        b = [x for x in eff if x in lt][:2]
        for c in itertools.product(a, b):
            if c[0] != c[1]:
                out["%s %s" % c] += 1
    return out


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
    # 2026-09-08 신설 — 사장님 "썰 다음 홈템 잘되는 체널들도 해야하고".
    # ★문턱을 신기템과 같은 급으로 둔다(min 5 · 구독 1,000+). 홈템은 신기템처럼
    #   **판정이 쉬운 축**이라 다른 축 눈높이(min 2~3)로 두면 우연히 걸린 잡채널이
    #   통째로 들어온다 — 신기템이 하룻밤 549채널로 오염됐던 그 함정이다.
    #   실측 근거: 라이브 8,917건에서 홈템 3편 이상인 채널이 이미 303개다.
    "홈템": {"score": score_home, "min": 5, "min_subs": 1000,
            "harvest": lambda ts: harvest_home(ts)},
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
    # ★썰쇼핑 씨앗(2026-09-08 신설). 위 주석은 "썰쇼핑도 살림킹왕짱을 심어 뒀다"고
    #   적혀 있었지만 **실제로는 이 표에 없었다** — 그래서 루프를 돌려도 썰쇼핑 축은
    #   영영 0이었다(실측: 27분 45채널 발굴분이 전부 '신기템'). 빈 풀은 스스로 못
    #   벗어난다는 바로 그 함정에 썰쇼핑이 걸려 있었다.
    # 씨앗은 **사장님이 직접 O로 찍은 채널**에서 골랐다(out/썰쇼핑_판정결과_전체.json,
    #   587편 채점). score = 그 채널에서 사장님이 O를 준 편수 — 추측이 아니라 사람 판정이다.
    "썰쇼핑": {
        "UCf_dI4hEIhyO_Ghbpg-0yXA": {"title": "공가미", "subs": 8070, "score": 7},
        "UCKppHYI5ul6uw-AXOMCFMiA": {"title": "뽀터언니", "subs": 1350, "score": 6},
        "UCXteg2LRkVxN8b7umCE7QOQ": {"title": "딸기라떼", "subs": 5130, "score": 6},
        "UCQRLTJOU9WTtstLwIeM2lmA": {"title": "왜 팔릴까", "subs": 1720, "score": 5},
        "UC8Wcwts4ChdpCe-nzqpM04A": {"title": "인생갓템", "subs": 30700, "score": 4},
        "UCo2z7vorOcD2wU8uxL8Wgew": {"title": "럭키박스", "subs": 2340, "score": 4},
        "UC7-zAnA-Q91i52Ma1ufhGHg": {"title": "달래샵", "subs": 6910, "score": 4},
        "UCkAv5c_XGwtEhpYk3i-zcFg": {"title": "오늘꿀템", "subs": 1380, "score": 4},
        # 원본 두 채널 — 이 장르를 정의한 곳이라 어휘 수확 대상으로 계속 둔다.
        "UCBFu04us6bv9OFcwrJDXdMg": {"title": "살림킹왕짱", "subs": 14600, "score": 4},
        "UCnD6bgF50o87a92-iK1dI8Q": {"title": "살림도사", "subs": 14500, "score": 4},
    },
    # 홈템 씨앗(2026-09-08) — 라이브 8,917건 실측.
    #
    # ★★처음엔 '홈템 편수 × 조회수'만 보고 뽑았다가 **전부 직촬 채널**이 걸렸다.
    #   사장님 지적: "살림도 직촬은 안되는데". 직촬은 본인이 자기 집·자기 손으로 찍어
    #   출연하는 결이라 **화면을 재료로 쓸 수 없다** — 이 서비스의 존재 이유가 남의
    #   제품 클립을 재편집하는 것인데, 그 채널들은 재료가 아니라 완성품이다.
    #   실제로 걸렸던 것:
    #     고수의살림  "유럽에서 아는 사람만 한다는 샐러드 먹는 방법"   ← 요리 직촬
    #     살림구조대  "코스트코 18년차 회원이 이번주 구경하고 온 제품" ← 매장 직촬
    #     소온풀      "다이소에 없는 주방꿀템으로 엄마 vs 딸 도시락"   ← 출연 상황극
    #     홈그래피    "도배 공사 절대 하지마세요 #셀프도배"           ← 시공 직촬
    #   편수·조회수는 "잘 되는 채널"은 말해주지만 **"재료로 쓸 수 있는 채널"은 말해주지
    #   않는다.** 지표를 늘리기 전에 그 지표가 무엇을 못 보는지 먼저 물어라.
    #
    # 그래서 사장님 확정 기준(2026-09-08)으로 다시 뽑았다 — **썰쇼핑처럼 제품 클립
    # 편집형만**. 직촬 어휘(브이로그·우리집·남편·시공·먹방·N년차·구경하고…)가 4편 중
    # 1편만 넘어도 배제하고, 물건 소개 어휘가 60% 이상인 채널만 남겼다.
    "홈템": {
        "UCwFNiYnTtrYuwO7YRWomatw": {"title": "살림토끼", "subs": 127000, "score": 9},
        "UCdvy8zJAV-z2w55b1yYGQYA": {"title": "인생 조언", "subs": 46200, "score": 6},
        "UCZseDHYlrD1LV8jwShLFsXw": {"title": "홈퀸살림", "subs": 37000, "score": 13},
        "UCP9At0_YeazqIriEbAoSU3A": {"title": "살림천재노다지", "subs": 29300, "score": 5},
        "UCXQRYw25xKBXGaMfb4FnnZQ": {"title": "홈템꿀팁", "subs": 28400, "score": 13},
        "UCOnSoSFUyeakdOOzAP0nnyw": {"title": "똑디템", "subs": 26900, "score": 17},
        "UCEDiNh6UkkFcjU9zxB-2Lrw": {"title": "쇼핑꿀템 연구소", "subs": 20900, "score": 14},
        "UCd2eMn4URep6NNO-H_MUTLg": {"title": "살림친구", "subs": 18600, "score": 11},
        "UCvh1AtO12W2A15ftNEGIRyg": {"title": "쇼핑스토리", "subs": 16000, "score": 10},
        "UCdgUlNruZABfk06xFW8DJlQ": {"title": "리빙테리어", "subs": 4250, "score": 23},
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
