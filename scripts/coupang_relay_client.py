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


# 틱톡 로그인 세션(쿠키). 서버의 /home/ubuntu/tiktok_session.json 과 같은 파일이다.
# ★저장소에 올리지 않는다(.gitignore) — 사장님 계정 쿠키다.
_TIKTOK_SESSION = os.getenv("TIKTOK_SESSION_PATH") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tiktok_session.json")


def _tiktok_session_health():
    """세션 쿠키가 얼마나 남았나 — (남은 일수, 사람이 읽는 말). 없으면 (None, 사유).

    ★왜 (2026-09-08 사장님 "세션이 끊기면 어쩌나 주기적으로")
      세션이 죽으면 검색이 **조용히 0건**이 된다. 오늘 하루가 정확히 그거였다 —
      코드도 프록시도 멀쩡한데 결과만 없어서 원인을 찾는 데 한참 걸렸다.
      그래서 만료를 미리·크게 알린다. 갱신은 tools/tiktok_session_from_firefox.py.
    """
    import json as _json
    if not os.path.exists(_TIKTOK_SESSION):
        return None, "세션 파일이 없습니다"
    try:
        with open(_TIKTOK_SESSION, encoding="utf-8") as f:
            cookies = (_json.load(f) or {}).get("cookies") or []
    except Exception as e:      # noqa: BLE001
        return None, f"세션 파일을 못 읽습니다({type(e).__name__})"
    now = time.time()
    # 로그인 자체를 지탱하는 쿠키. 이게 죽으면 무슨 짓을 해도 0건이다.
    key = [c for c in cookies if c.get("name") in ("sessionid", "sid_tt")]
    if not key:
        return None, "로그인 쿠키(sessionid)가 없습니다 — 로그인 안 된 세션입니다"
    exps = [c.get("expires") for c in key if (c.get("expires") or 0) > 0]
    if not exps:
        return None, "로그인 쿠키에 만료일이 없습니다"
    days = (min(exps) - now) / 86400.0
    if days <= 0:
        return 0, "로그인 쿠키가 **만료됐습니다**"
    return days, f"로그인 쿠키 {days:.0f}일 남음"


def _warn_session(note):
    """세션 문제를 창에 크게 적는다 — 작은 글씨로 흘리면 아무도 안 본다."""
    print("", flush=True)
    print("  " + "!" * 58, flush=True)
    print(f"  !! 틱톡 {note}", flush=True)
    print("  !! 갱신: py tools/tiktok_session_from_firefox.py", flush=True)
    print("  !!       (파이어폭스로 틱톡에 로그인한 뒤, 파이어폭스를 완전히 닫고 실행)", flush=True)
    print("  " + "!" * 58, flush=True)
    print("", flush=True)


def handle_tiktok(job):
    """틱톡 검색 — 이 PC의 **진짜 크롬 창**으로 긁는다 (2026-09-08).

    ★왜 PC인가 (실측으로 갈랐다):
        내 PC + 창 띄움  → 영상 24개    내 PC + 헤드리스 → 0개
        서버 + 창(xvfb)  → 0개          서버 + 창 + 직결 → 0개
      세션·프록시·IP는 전부 멀쩡했고, 틱톡이 헤드리스와 서버 환경을 걸러낸다.
      쿠팡이 한국 IP 때문에 PC를 쓰는 것과 이유만 다르고 구조는 같다.

    ★headless=False가 필수다 — 창이 잠깐 떴다 사라진다. 그게 정상이다.
    """
    payload = job.get("payload") or {}
    kw = (payload.get("keyword") or job.get("q") or "").strip()
    limit = int(payload.get("limit") or job.get("limit") or 10)
    print(f"  [틱톡] {kw} …", flush=True)
    items, note = [], ""
    days, health = _tiktok_session_health()
    if days is None or days <= 0:
        # 세션이 죽었으면 브라우저를 띄우지도 않는다 — 어차피 0건이고 시간만 버린다.
        _warn_session(health)
        note = f"틱톡 세션 문제 — {health}"
        _post("/api/coupang/relay/result", {
            "token": TOKEN, "id": job.get("id"), "ok": False,
            "items": [], "search_url": "", "notice": note})
        return
    if days < 7:
        _warn_session(f"{health} — 곧 끊깁니다. 미리 갱신하세요")
    if not os.path.exists(_TIKTOK_SESSION):
        note = "틱톡 세션 파일이 없습니다(tiktok_session.json)"
    else:
        try:
            from urllib.parse import quote
            from playwright.sync_api import sync_playwright
            url = "https://www.tiktok.com/search?q=" + quote(kw)
            with sync_playwright() as p:
                # ★창을 화면 **밖**에 띄운다 (2026-09-08 사장님 "왜 자꾸 꺼지나").
                #   헤드리스로는 틱톡이 막으므로 진짜 창이 필요한데, 검색할 때마다
                #   화면에 떴다 사라지면 일하는 데 거슬린다. 위치만 옮기면
                #   틱톡이 보기엔 여전히 보통 크롬이고 사장님 눈에는 안 띈다.
                b = p.chromium.launch(
                    headless=False, channel="chrome",
                    args=["--disable-blink-features=AutomationControlled",
                          "--window-position=-32000,-32000"])
                ctx = b.new_context(storage_state=_TIKTOK_SESSION, locale="ko-KR",
                                    viewport={"width": 1360, "height": 950})
                pg = ctx.new_page()
                pg.goto(url, timeout=60000, wait_until="domcontentloaded")
                pg.wait_for_timeout(9000)
                # ★사장님 실측: 첫 시도에 "문제가 발생했습니다"가 뜨는 일이 있고
                #   다시 시도를 누르면 풀린다. 그래서 비어 있으면 두 번 더 눌러 본다.
                for _ in range(2):
                    if pg.evaluate(
                            "document.querySelectorAll('a[href*=\"/video/\"]').length"):
                        break
                    try:
                        pg.get_by_text("다시 시도", exact=True).first.click(timeout=4000)
                    except Exception:
                        break
                    pg.wait_for_timeout(6000)
                # ★검색 결과 카드에는 **조회수와 링크뿐**이다(2026-09-08 DOM 실측).
                #   `search_top-item` 안의 표식은 video-views 하나이고, 제목·계정은
                #   이 화면에 아예 없다(카드를 열어야 나온다 — 그건 비용이 크다).
                #   그래서 계정은 **주소에서** 뽑는다(@아이디/video/…). 채널을 모으는 게
                #   목적이라 계정·조회수·주소면 충분하다.
                items = pg.evaluate("""
                  (() => {
                    const acc = u => (String(u||'').match(/tiktok\\.com\\/@([\\w.\\-]+)/)||[])[1]||'';
                    const cards=[...document.querySelectorAll('[data-e2e="search_top-item"]')];
                    const pick=(c,k)=>{const e=c.querySelector('[data-e2e="'+k+'"]');
                                       return e?String(e.innerText||'').trim():'';};
                    const rows=cards.map(c=>{
                      const a=c.querySelector('a[href*="/video/"]');
                      if(!a) return null;
                      const who=acc(a.href);
                      return {url:a.href,
                              account:who,
                              views:pick(c,'video-views'),
                              // 제목 자리가 비면 화면에 빈 카드가 뜬다 → 계정을 넣는다
                              title:(who?'@'+who:'') ,
                              thumb:(c.querySelector('img')||{}).src||''};
                    }).filter(Boolean);
                    // 카드가 안 잡히면(레이아웃이 바뀌면) 링크만이라도 건진다
                    if(rows.length) return rows;
                    return [...document.querySelectorAll('a[href*="/video/"]')]
                      .map(a=>({url:a.href, account:acc(a.href), views:'',
                                title:(acc(a.href)?'@'+acc(a.href):''),
                                thumb:(a.querySelector('img')||{}).src||''}));
                  })()""") or []
                ctx.close()
                b.close()
        except Exception as exc:      # noqa: BLE001 — 릴레이가 죽으면 안 된다
            note = f"틱톡 검색 실패: {type(exc).__name__}"
    # 같은 영상이 여러 번 잡힌다(썸네일·제목이 따로 링크) → 주소로 중복 제거
    seen, out = set(), []
    for it in items:
        u = (it or {}).get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    print(f"  [결과] {len(out)}건 {note}".rstrip(), flush=True)
    _post("/api/coupang/relay/result", {
        "token": TOKEN, "id": job.get("id"), "ok": bool(out),
        "items": out[:limit], "search_url": "", "notice": note})


def handle(job):
    """일감 하나 처리 — 로컬(한국 IP·진짜 크롬)에서 실제로 긁는다."""
    kind = job.get("kind") or "search"
    if kind == "detail":
        handle_detail(job)
        return
    if kind == "tiktok":
        handle_tiktok(job)
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

    print(f"검색 도우미 시작 — {SERVER}")
    print("이 창을 켜두면 '쿠팡에서 상품 찾기'와 '틱톡 검색'이 동작합니다. (Ctrl+C로 종료)")
    # ★켤 때 한 번 알린다 — 검색해 보고 나서 아는 것보다 낫다.
    _days, _health = _tiktok_session_health()
    if _days is None or _days <= 0:
        _warn_session(_health)
    elif _days < 7:
        _warn_session(f"{_health} — 곧 끊깁니다. 미리 갱신하세요")
    else:
        print(f"  틱톡 세션: {_health}")
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
