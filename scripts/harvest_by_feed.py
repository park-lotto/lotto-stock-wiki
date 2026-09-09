# -*- coding: utf-8 -*-
"""유튜브 **추천 피드**를 타고 같은 결의 채널을 캔다 — 자가증식.

★왜 만들었나 (2026-09-09 사장님)
  "우리 썰채널들에서 피드타고 보는게 맞는거같은데"

  그때까지 쓰던 검색어 발굴(harvest_styles_forever)은 어휘 조합으로 채널을 찾는다.
  그 결과를 사장님이 직접 채점하니 **121개 중 O가 6개**였고, 구독 19만~195만짜리
  대형 채널 13개는 **전부 X**였다(셀프어쿠스틱=스톱모션 · 오빠두엑셀 · 인생2회차 등).
  어휘가 같아도 장르가 다르면 소용이 없다 — '숨겨진·비밀·정리'는 어느 판에서나 쓴다.

  유튜브 추천은 **같은 걸 보는 사람이 다음에 보는 것**이라 결이 훨씬 가깝다.
  실측(씨앗 15편): 새 채널 89개 중 쇼핑 결 21개(24%).
    감탄살림 "쓸수록 감탄나오는 다이소 역대급 추천템"
    살림 스튜디오 "다이소 자동정리 비밀, 다이소 직원도 털어놓"
    귀곰 "미친 성능의 신이 내린 대청소템 TOP3 l 내돈내산"
    노써치 "에어프라이어 유료 광고에 지친 당신을 위해 직접 사서 비교했습니다"

★비용: 추천 수집은 **페이지 긁기라 API 0 units**. 검증(업로드 25편 조회)만 채널당
  2 units 든다. 검색어 발굴이 검색 1회에 100 units 쓰던 것과 자릿수가 다르다.

★한 사이클
  ① 씨앗 = 이미 가진 좋은 채널의 영상들(랭킹에서 뽑는다)
  ② 그 영상 페이지의 추천에서 (채널, 제목)을 캔다
  ③ 검증 — 그 채널의 실제 업로드 25편을 판정기에 돌려 문턱을 넘어야 통과
     ⚠️추천에 딸려온 제목 1~2개로 판정하면 안 된다. 실측에서 JTBC·KBS News가
       제목 하나로 '쇼핑 100%'가 됐다 — 표본이 작으면 비율은 거짓말을 한다.
  ④ 통과 채널이 다음 사이클의 씨앗 → ①
"""
import collections
import json
import os
import random
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request

BASE = "/home/ubuntu/lotto-stock-wiki"
sys.path.insert(0, BASE)

from shopping_shorts import categorize as cz          # noqa: E402
from shopping_shorts import keyroute                  # noqa: E402
from shopping_shorts.config import DB_PATH            # noqa: E402
from shopping_shorts.store import Store               # noqa: E402

STATE = "/tmp/feed_state.json"
LOG = "/tmp/harvest_feed.log"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 쇼핑 결로 인정할 카테고리. 썰쇼핑(제품정체형·오용형)이 본진이고 홈템·장비템도 재료가 된다.
GOOD = ("제품정체형", "오용형", "홈템", "장비템", "차량템")
SUL = ("제품정체형", "오용형")

# ★검증 문턱 — 규모가 클수록 진하게 요구한다(2026-09-09 실측).
#   구독 100만 채널은 잡다한 영상이 많아 25편 중 5편쯤은 그냥 맞는다:
#   진영민(487만·먹방) 7편 · 오빠두엑셀(169만) 6편 · 인생2회차(105만·건강) 6편.
def need(subs):
    if subs >= 500000:
        return 15
    if subs >= 100000:
        return 10
    if subs >= 30000:
        return 7
    return 5


_HAN = re.compile(r"[가-힣]")


def log(msg):
    line = "[%s] %s" % (time.strftime("%m-%d %H:%M"), msg)
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ── 키 풀(검증용) — 회원 키까지 합류시킨다(0순위-B: keypool이 유일한 출처) ──────
def _keys():
    try:
        from shopping_shorts import keypool, config
        keypool.resync_pools(Store(DB_PATH), verbose=True)
        return list(config.YOUTUBE_API_KEYS)
    except Exception as e:      # noqa: BLE001
        log("키풀 합류 실패(환경변수만 사용): %r" % (e,))
        return [v for i in range(1, 31)
                if (v := os.environ.get("YOUTUBE_API_KEY" if i == 1
                                        else "YOUTUBE_API_KEY_%d" % i, ""))]


KEYS = _keys()
_ki = 0


def api(path, **p):
    """유튜브 API 1콜. 403/429면 다음 키로. 전부 마르면 None."""
    global _ki
    if not KEYS:
        return None
    for _ in range(len(KEYS)):
        p["key"] = KEYS[_ki % len(KEYS)]
        url = "https://www.googleapis.com/youtube/v3/%s?%s" % (
            path, urllib.parse.urlencode(p))
        try:
            return json.load(urllib.request.urlopen(url, timeout=20))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                _ki += 1
                continue
            return None
        except Exception:      # noqa: BLE001 — 네트워크 흔들림은 다음 키로
            _ki += 1
            continue
    return None


# ── 추천 캐기(페이지 긁기 · API 0) ────────────────────────────────────────
def recs_of(video_id):
    """영상 페이지 추천에서 [(채널id, 채널명, 영상제목)]. 실패하면 []."""
    req = urllib.request.Request(
        "https://www.youtube.com/watch?v=" + video_id,
        headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    try:
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
    except Exception:      # noqa: BLE001 — 한 편 실패가 루프를 죽이지 않는다
        return []
    m = re.search(r"ytInitialData\s*=\s*(\{.*?\});</script>", html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return []
    out = []

    def walk(o):
        if isinstance(o, dict):
            by = o.get("shortBylineText") or o.get("longBylineText")
            if by:
                t = o.get("title") or {}
                title = t.get("simpleText") or "".join(
                    x.get("text", "") for x in (t.get("runs") or []))
                for r in (by.get("runs") or []):
                    cid = (((r.get("navigationEndpoint") or {})
                            .get("browseEndpoint") or {}).get("browseId"))
                    if cid and str(cid).startswith("UC"):
                        out.append((cid, r.get("text") or "", title))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return out


# ── 검증(실제 업로드 25편) ────────────────────────────────────────────────
def judge(cid):
    """(통과여부, 채널명, 구독자, 쇼핑편수, 썰편수). 못 읽으면 (False, ...)."""
    ch = api("channels", part="contentDetails,snippet,statistics", id=cid)
    if not ch or not ch.get("items"):
        return False, "", 0, 0, 0
    it = ch["items"][0]
    name = it["snippet"]["title"]
    subs = int(it["statistics"].get("subscriberCount") or 0)
    up = it["contentDetails"]["relatedPlaylists"].get("uploads")
    if not up:
        return False, name, subs, 0, 0
    pl = api("playlistItems", part="snippet", playlistId=up, maxResults=25)
    titles = [x["snippet"]["title"] for x in (pl or {}).get("items", [])]
    if not titles:
        return False, name, subs, 0, 0
    # 한국어 채널만 — 이 서비스는 한국어 쇼핑 쇼츠를 만든다(영어권 DIY가 새던 자리).
    if sum(1 for t in titles if _HAN.search(t)) / len(titles) < 0.5:
        return False, name, subs, 0, 0
    cats = [cz.categorize(name, t) for t in titles]
    good = sum(1 for c in cats if c in GOOD)
    sul = sum(1 for c in cats if c in SUL)
    return good >= need(subs), name, subs, good, sul


# ── 상태 ─────────────────────────────────────────────────────────────────
def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            st = json.load(f)
    except Exception:      # noqa: BLE001 — 처음이거나 깨졌으면 새로 시작
        st = {}
    st.setdefault("pass", {})        # cid -> {name, subs, good, sul}
    st.setdefault("rejected", {})    # cid -> why
    st.setdefault("seen_videos", [])  # 이미 추천을 캔 영상
    st.setdefault("cycles", 0)
    return st


def save(st):
    st["seen_videos"] = st["seen_videos"][-4000:]
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(tmp, STATE)


def seed_videos(st, n=20):
    """씨앗 영상 — ①통과 채널의 영상 ②없으면 랭킹의 썰쇼핑 상위."""
    c = sqlite3.connect(os.path.join(BASE, "shopping_shorts/data/reference.db"))
    row = c.execute("SELECT value FROM settings WHERE key=?",
                    ("last_run::youtube",)).fetchone()
    items = json.loads(row[0]).get("items") or [] if row else []
    seen = set(st["seen_videos"])
    good_ch = set(st["pass"])
    pool = [i for i in items
            if i.get("shortcode") and i["shortcode"] not in seen
            and ((i.get("username") in good_ch)
                 or (i.get("category") or "") in SUL)]
    pool.sort(key=lambda x: -(x.get("views") or 0))
    return pool[:n]


def main():
    st = load()
    log("시작 — 키 %d개 · 통과 %d · 거절 %d"
        % (len(KEYS), len(st["pass"]), len(st["rejected"])))
    quiet = 0
    while True:
        st["cycles"] += 1
        seeds = seed_videos(st)
        if not seeds:
            log("씨앗 없음 — 10분 뒤 다시(수집이 새 영상을 넣어줘야 한다)")
            save(st)
            time.sleep(600)
            continue

        met = collections.defaultdict(lambda: {"name": "", "titles": []})
        for s in seeds:
            for cid, nm, title in recs_of(s["shortcode"]):
                m = met[cid]
                m["name"] = m["name"] or nm
                if title and title not in m["titles"]:
                    m["titles"].append(title)
            st["seen_videos"].append(s["shortcode"])
            time.sleep(0.6)      # 유튜브에 몰아치지 않는다

        fresh = [cid for cid in met
                 if cid not in st["pass"] and cid not in st["rejected"]]
        # 추천에 여러 번 나온 것부터 — 자주 붙어 나오면 결이 가깝다
        fresh.sort(key=lambda c: -len(met[c]["titles"]))
        added = 0
        for cid in fresh[:40]:
            ok, name, subs, good, sul = judge(cid)
            if not name:
                continue
            if ok:
                st["pass"][cid] = {"name": name, "subs": subs, "good": good, "sul": sul}
                added += 1
                log("  + %-20s 구독 %8s · 쇼핑 %2d/25 · 썰 %d"
                    % (name[:20], format(subs, ","), good, sul))
            else:
                st["rejected"][cid] = "쇼핑 %d/25 (구독 %d는 %d 필요)" % (good, subs, need(subs))
        save(st)
        log("C%d 씨앗 %d편 → 만난 채널 %d · 신규 %d · 통과 +%d (누적 %d)"
            % (st["cycles"], len(seeds), len(met), len(fresh), added, len(st["pass"])))
        quiet = quiet + 1 if added == 0 else 0
        if quiet >= 3:
            log("신규 0이 3회 — 10분 쉬고 계속(수집이 새 영상을 넣으면 다시 뻗는다)")
            time.sleep(600)
            quiet = 0
        else:
            time.sleep(30)


if __name__ == "__main__":
    main()
