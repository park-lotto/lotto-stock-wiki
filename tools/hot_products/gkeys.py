"""조사 도구의 키·환경값을 주는 **유일한 곳** — 스크립트마다 .env 를 따로 읽지 않는다.

- env(): PC 에선 저장소 .env, 서버에선 os.environ(/etc/shopping-shorts.env 를 set -a 로 올린 것)
- gemini_keys(): HOT_SERVER_POOL=1 이면 서버 제미나이 공용풀(사장님+회원, 2026-10-20 사장님 "공용풀로 써"),
  아니면 PC .env 의 무료 키(GEMINI_API/INGEST/BRIEFING_KEY*).
  ★공용풀 키는 서버 밖으로 꺼내지 않는다 — 서버에서 돌릴 때만 메모리로 받는다(파일·출력 금지)."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(HERE, "..", "..", ".env")


def env():
    out = dict(os.environ)
    if os.path.exists(_ENV_PATH):
        for line in open(_ENV_PATH, encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1); out[k.strip()] = v.strip().strip('"')
    return out


def naver_keys():
    """네이버 오픈API 앱 (Client ID, Secret) 목록 — NAVER_CLIENT_ID, NAVER_CLIENT_ID_2, _3 …
    데이터랩 검색어트렌드는 앱마다 하루 1,000회라 앱을 늘리면 한도가 는다(10-20 사장님이 앱 추가 가입)."""
    e = env(); out = []
    for suf in [""] + [f"_{i}" for i in range(2, 21)]:
        i, s = e.get("NAVER_CLIENT_ID" + suf), e.get("NAVER_CLIENT_SECRET" + suf)
        if i and s: out.append((i, s))
    return out


_nk = {"i": 0}
def datalab(body, timeout=40):
    """데이터랩 검색어트렌드 호출의 유일한 곳 — 한도(429)·오류면 다음 앱 키로 넘긴다. 실패하면 예외."""
    import json, urllib.request, urllib.error, time
    keys = naver_keys(); last = None
    for _ in range(len(keys) * 2):
        cid, sec = keys[_nk["i"] % len(keys)]
        req = urllib.request.Request("https://openapi.naver.com/v1/datalab/search", json.dumps(body).encode(),
                                     {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec, "Content-Type": "application/json"})
        try:
            return json.load(urllib.request.urlopen(req, timeout=timeout))["results"]
        except urllib.error.HTTPError as ex:
            last = f"{ex.code} {ex.read()[:120]!r}"
            _nk["i"] += 1                                  # 429(한도)·401 → 다음 앱
            if ex.code not in (429, 401, 403): time.sleep(2)
        except Exception as ex:
            last = str(ex)[:120]; time.sleep(2)
    raise RuntimeError(f"데이터랩 실패(앱 {len(keys)}개 모두): {last}")


def gemini_keys():
    if os.environ.get("HOT_SERVER_POOL") == "1":
        from shopping_shorts import config, keyroute
        from shopping_shorts.store import Store
        config.refresh_member_gemini_keys(Store(config.DB_PATH).get_pooled_keys(keyroute.SVC_GEMINI))
        keys = list(config.SHORTS_GEMINI_KEYS)
        print(f"[gkeys] 서버 공용풀 {len(keys)}개", flush=True)
        return keys
    e = env()
    return [v for k, v in e.items() if re.match(r"^GEMINI_(API|INGEST|BRIEFING)_KEY(_\d+)?$", k) and v]
