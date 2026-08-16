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

# ★윈도우 콘솔은 기본이 cp949라 '—'(em dash) 한 글자에 **시작하자마자 죽는다**
#   (2026-08-17 실측: UnicodeEncodeError로 릴레이가 첫 print에서 종료됐다).
#   안내문에서 특수문자를 빼는 건 답이 아니다 — 상품명·리뷰에 어떤 글자가 올지 모른다.
#   출력 스트림 자체를 UTF-8로 돌리고, 그래도 못 찍는 글자는 물음표로 흘린다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:      # noqa: BLE001 — 파이프로 넘길 땐 reconfigure가 없을 수 있다
        pass

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


_IMG_MAX_SIDE = 1400      # 제미니가 상세 글자를 읽는 데 이 정도면 충분(원본 6.3MB → 수백KB)
_IMG_QUALITY = 72
_RAW_MAX_BYTES = 12 * 1024 * 1024      # 전송 상한 — 넘으면 뒤쪽 이미지를 버린다


def _shrink_b64(path):
    """상세 이미지 1장 → 축소 JPEG base64. 실패하면 None(그 장만 버린다)."""
    import base64
    import io
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            if max(w, h) > _IMG_MAX_SIDE:
                r = _IMG_MAX_SIDE / float(max(w, h))
                im = im.resize((max(1, int(w * r)), max(1, int(h * r))))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=_IMG_QUALITY, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:      # noqa: BLE001 — 이미지 한 장 실패로 수집을 버리지 않는다
        return None


def handle_detail(job):
    """상품 상세·리뷰 수집(2026-08-17) — 1단계에서 미리 걸어둔 일감.

    ★역할을 가른다 — **PC는 긁기만, 분석은 서버가 한다**(2026-08-17 실측으로 결정).
      처음엔 PC가 제미니 분석까지 하게 짰는데 실행해 보니 `제미니 키 0개`로 멈췄다:
      분석 키(`SHORTS_GEMINI_KEY`)는 **서버 `/etc/shopping-shorts.env`에만** 있다.
      키를 PC로 복사하면 관리 지점이 둘이 된다(0순위-B: 같은 것을 두 곳에 두지 마라).
      그래서 PC는 쿠팡이 막는 부분(=긁기)만 하고, 이미지·리뷰를 서버로 올린다.
    ★이미지는 축소해서 보낸다 — 원본 4장이 6.3MB였다(실측). 상세 글자를 읽는 데는
      긴 변 1400px면 충분하다.
    ★검색 → 1위 상품 → 상세·리뷰 순으로 간다. 상품을 못 찾으면 빈 결과를 보낸다
      (대본은 재료 없이도 나와야 하므로 실패를 예외로 만들지 않는다).
    """
    from shopping_shorts import product_facts

    p = job.get("payload") or {}
    product = (p.get("product") or job.get("q") or "").strip()
    print(f"  [상품재료] {product} — 검색 중…", flush=True)
    picked, raw = {}, {}
    try:
        found = coupang_search.search(product, limit=1)
        items = found.get("items") or []
        if items:
            picked = items[0]
            url = picked.get("url") or ""
            print(f"  [상품재료] {picked.get('name','')[:40]} — 상세·리뷰 수집(2~3분)…", flush=True)
            work = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                ".coupang_facts", (p.get("shortcode") or "tmp"))
            raw = product_facts.collect_raw(url, work) or {}
        else:
            print("  [상품재료] 상품을 못 찾음", flush=True)
    except Exception as exc:                       # 릴레이가 죽으면 안 된다
        print(f"  [상품재료] 실패: {type(exc).__name__} {str(exc)[:80]}", flush=True)

    images, total = [], 0
    for path in (raw.get("detail_images") or []):
        b64 = _shrink_b64(path)
        if not b64:
            continue
        if total + len(b64) > _RAW_MAX_BYTES:
            print(f"  [상품재료] 전송 상한 도달 — 이미지 {len(images)}장까지만 보냅니다", flush=True)
            break
        images.append(b64)
        total += len(b64)
    reviews = [str(r) for r in (raw.get("reviews") or [])][:20]
    print(f"  [상품재료] 전송 — 이미지 {len(images)}장({total // 1024}KB) · 리뷰 {len(reviews)}건",
          flush=True)
    _post("/api/coupang/relay/result", {
        "token": TOKEN, "id": job.get("id"), "ok": bool(images or reviews),
        "raw": {"title": raw.get("title") or "", "url": raw.get("url") or "",
                "images_b64": images, "reviews": reviews},
        "product": picked}, timeout=180)


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
