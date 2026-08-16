"""쿠팡 검색 도우미 — 사장님 PC에서 켜두면 서버 대신 쿠팡을 검색해 준다.

왜 PC에서 도는가: 쿠팡은 **한국 IP가 아니면 막는다**(서버 직결도, 독일 주거용 프록시도
403 — 실측). 사장님 PC는 한국 주거용 IP라 그냥 통과한다. 그래서 서버가 PC에게 물어본다.

    py scripts/coupang_relay_client.py

★서버로 **나가는** 연결만 쓴다 — 공유기 포트를 열 필요도, 공인 IP도 필요 없다.
★창을 닫으면 그냥 멈춘다(서버는 타임아웃 후 수동 안내로 돌아간다 — 아무것도 안 깨진다).

환경변수(없으면 아래 기본값):
    COUPANG_RELAY_SERVER  서버 주소   (기본 https://shoppingshorts.duckdns.org)
    COUPANG_RELAY_TOKEN   인증 토큰   (서버 /etc/shopping-shorts.env 와 같은 값)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shopping_shorts import coupang_search  # noqa: E402

SERVER = os.getenv("COUPANG_RELAY_SERVER", "https://shoppingshorts.duckdns.org").rstrip("/")
TOKEN = os.getenv("COUPANG_RELAY_TOKEN", "")
POLL_WAIT = 25          # 서버가 일감을 들고 기다려 주는 시간(초)


def _get(path, timeout):
    with urllib.request.urlopen(SERVER + path, timeout=timeout) as r:
        return json.load(r)


def _post(path, payload, timeout=20):
    req = urllib.request.Request(
        SERVER + path, method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def handle_detail(job):
    """상품 상세·리뷰 수집(2026-08-17) — 1단계에서 미리 걸어둔 일감.

    ★서버로 **결론만** 보낸다. 상세페이지는 글자가 아니라 이미지라 그대로 올리면
      용량이 크다 — 여기(PC)서 긁고 여기서 제미니 분석까지 끝내고 JSON만 보낸다.
    ★검색 → 1위 상품 → 상세·리뷰 순으로 간다. 상품을 못 찾으면 빈 결과를 보낸다
      (대본은 재료 없이도 나와야 하므로 실패를 예외로 만들지 않는다).
    """
    from shopping_shorts import product_facts

    p = job.get("payload") or {}
    product = (p.get("product") or job.get("q") or "").strip()
    print(f"  [상품재료] {product} — 검색 중…", flush=True)
    facts, picked = {}, {}
    try:
        found = coupang_search.search(product, limit=1)
        items = found.get("items") or []
        if items:
            picked = items[0]
            url = picked.get("url") or ""
            print(f"  [상품재료] {picked.get('name','')[:40]} — 상세·리뷰 수집(2~3분)…", flush=True)
            work = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                ".coupang_facts", (p.get("shortcode") or "tmp"))
            facts = product_facts.collect_and_analyze(url, work, name=picked.get("name") or "")
        else:
            print("  [상품재료] 상품을 못 찾음", flush=True)
    except Exception as exc:                       # 릴레이가 죽으면 안 된다
        print(f"  [상품재료] 실패: {type(exc).__name__} {str(exc)[:80]}", flush=True)
    n = sum(len(facts.get(k) or []) for k in ("specs", "pain", "satisfy", "voice")) if facts else 0
    print(f"  [상품재료] 완료 — 재료 {n}건", flush=True)
    _post("/api/coupang/relay/result", {
        "token": TOKEN, "id": job.get("id"), "ok": bool(facts),
        "facts": facts, "product": picked}, timeout=60)


def handle(job):
    """일감 하나 처리 — 로컬(한국 IP)에서 실제로 쿠팡을 긁는다."""
    if (job.get("kind") or "search") == "detail":
        handle_detail(job)
        return
    q = job.get("q") or ""
    print(f"  [검색] {q} …", flush=True)
    try:
        result = coupang_search.search(q, limit=job.get("limit") or None)
    except Exception as exc:                      # 릴레이가 죽으면 안 된다
        result = {"ok": False, "items": [], "search_url": "",
                  "notice": f"로컬 검색 실패: {type(exc).__name__}"}
    n = len(result.get("items") or [])
    print(f"  [결과] {n}건 {result.get('notice') or ''}".rstrip(), flush=True)
    _post("/api/coupang/relay/result", {
        "token": TOKEN, "id": job.get("id"), "ok": result.get("ok"),
        "items": result.get("items"), "search_url": result.get("search_url"),
        "notice": result.get("notice")})


def main():
    if not TOKEN:
        print("COUPANG_RELAY_TOKEN 이 없습니다 — 서버와 같은 토큰을 넣고 다시 실행하세요.")
        return 2
    # 크롤 자체가 꺼져 있으면 아무리 폴링해도 빈손이다. 여기서 미리 켠다.
    os.environ.setdefault("COUPANG_SEARCH_ENABLED", "1")
    from shopping_shorts import config
    config.COUPANG_SEARCH_ENABLED = True
    config.COUPANG_SEARCH_MODE = "local"          # ★릴레이 안에서는 반드시 직접 크롤

    print(f"쿠팡 검색 도우미 시작 — {SERVER}")
    print("이 창을 켜두면 숏템메이커에서 '쿠팡에서 상품 찾기'가 동작합니다. (Ctrl+C로 종료)")
    backoff = 1
    while True:
        try:
            d = _get(f"/api/coupang/relay/next?token={TOKEN}&wait={POLL_WAIT}",
                     timeout=POLL_WAIT + 15)
            backoff = 1
            job = d.get("job")
            if job:
                handle(job)
        except KeyboardInterrupt:
            print("\n종료합니다.")
            return 0
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("토큰이 서버와 다릅니다 — 확인 후 다시 실행하세요.")
                return 2
            print(f"  서버 오류 {e.code} — {backoff}초 후 재시도")
            time.sleep(backoff); backoff = min(backoff * 2, 30)
        except Exception as e:
            print(f"  연결 실패({type(e).__name__}) — {backoff}초 후 재시도")
            time.sleep(backoff); backoff = min(backoff * 2, 30)


if __name__ == "__main__":
    raise SystemExit(main())
