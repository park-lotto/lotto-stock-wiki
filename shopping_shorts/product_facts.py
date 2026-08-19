# -*- coding: utf-8 -*-
"""쿠팡 상품 → **대본 재료**(product_facts) 수집·분석 (2026-08-16).

## 왜 필요한가 (사장님 지적 + 실측)

사장님: *"메종 대본은 특장점을 탄탄하게 뽑고 '심지어 + 장점2'까지 간다. 우리는 왜 단순하고
허접하게 나오나. 어떤 스타일이든 스토리+표현+구조가 탄탄한 게 전제이고 스타일은 그 뒤다."*

원인을 코드로 확인했다 — **재료가 얄팍했다.** 라이브 생성물(08-04) 실측을 보면 제품 얘기가
"기름때가 사라졌다" 한 줄뿐이었다. 반면 메종 히트작은 장점 3개에 원리·출처·수치가 붙는다.

그리고 메종의 그 문장들("0.02mm로 콘택트렌즈보다 얇아서")은 **영상 분석으로 나온 게 아니라
상세페이지·리뷰를 읽은 것**이다(사장님 관찰). 실제로 그 영상 나레이션에 0.02mm가 그대로
들어 있었다 — 즉 원본 채널도 상세페이지를 보고 대본을 썼다.

## 실측 검증 (2026-08-16, 필통 DTL9k_Xk3Nc / 쿠팡 8514193592)

    쿠팡 검색            20~30초   ✅ 사장님 PC(한국 IP)에서만 — 서버는 403
    상세 이미지 수집     60~90초   ✅ 2장 4.3MB
    베스트리뷰 수집      23초      ✅ 10건(도움순)
    제미니 분석 ×2       30~50초   ✅
    ─────────────────────────────
    합계                 약 2~3분  (상품당 1회, 이후 재사용)

★상세페이지는 **텍스트가 아니라 이미지**다(크롤로 글자 0개). 그래서 이미지를 그대로
  제미니에 넘긴다 — 그랬더니 "볼펜 65자루·20cm 자·220×120×70mm·특허 제40-2117352호"가
  나왔다. **원본 영상엔 이 수치가 하나도 없었다**(= 원본보다 탄탄한 대본이 가능하다).

★리뷰가 상세페이지보다 값어치 있다(사장님 지시로 추가). 상세의 pain은 판매자가 쓴 광고
  문구지만, 리뷰의 pain은 진짜다 — "아이가 필통을 2~4개씩 들고 다님". A/B 실측에서
  이 차이가 그대로 대본에 나타났다(A는 AI가 상상한 불편, B는 실제 사연).

## 어디서 도는가

- **수집(크롤)**: 사장님 PC. 서버는 한국 IP가 없어 403(coupang_relay.py 실측표).
- **분석(제미니)**: 서버·PC 어디서든. 키는 서버 `/etc/shopping-shorts.env`에 있다.
- 그래서 이 모듈은 **크롤과 분석을 분리**한다 — `collect_raw()`(PC) / `analyze()`(어디서든).
"""
import json
import os

# 상세 이미지 최대 장수 — 쿠팡 상세는 보통 1~3장의 긴 이미지다. 많으면 제미니 비용만 늘고
# 정보는 안 는다(실측: 필통은 2장으로 스펙 9개가 전부 나왔다).
MAX_DETAIL_IMAGES = 4
MIN_IMAGE_BYTES = 8000          # 아이콘·1px 추적픽셀 제외
REVIEW_PAGES = 2                # 베스트순 상위 2페이지면 도움순 상위가 다 들어온다

_DETAIL_IMG_JS = r"""
() => {
  const urls = [];
  const push = u => { if(!u) return; if(u.startsWith('//')) u='https:'+u;
                      if(/coupangcdn|coupang/.test(u)) urls.push(u); };
  const root = document.querySelector('.product-detail-content-inside')
            || document.querySelector('.vendor-item')
            || document.querySelector('.product-detail-content')
            || document;
  root.querySelectorAll('img').forEach(img=>{
    push(img.getAttribute('src')); push(img.getAttribute('data-src'));
    push(img.getAttribute('data-original')); push(img.getAttribute('data-lazy'));
  });
  return [...new Set(urls)];
}
"""

# ★셀렉터는 실측으로 확인한 것이다(probe, 2026-08-16):
#   리뷰 컨테이너 = div.sdp-review (개별 리뷰는 그 안의 article).
#   추측으로 쓴 첫 시도(.sdp-review__article__list)는 '도움됐어요' 카운트만 잡혔다.
_REVIEW_JS = r"""
() => {
  const clean = s => (s||'').replace(/\s+/g,' ').trim();
  const root = document.querySelector('div.sdp-review') || document.querySelector('.product-review');
  if(!root) return {ok:false, items:[]};
  const items=[];
  root.querySelectorAll('article, [class*=review__article]').forEach(a=>{
    const tx = clean(a.innerText);
    if(tx.length > 30) items.push(tx);
  });
  return {ok:true, items};
}
"""


def collect_raw(product_url, work_dir, *, profile_dir=None, headless=False, log=print):
    """쿠팡 상품페이지 → {detail_images:[경로], reviews:[본문], title}.

    ★사장님 PC에서만 된다(한국 IP). 서버에서 부르면 403으로 빈 결과가 온다 —
      예외를 던지지 않고 빈 값을 돌려준다(대본 생성은 재료 없이도 돌아야 한다).
    """
    import urllib.request
    from playwright.sync_api import sync_playwright

    os.makedirs(work_dir, exist_ok=True)
    out = {"title": "", "detail_images": [], "reviews": [], "url": product_url}
    profile_dir = profile_dir or os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), ".coupang_profile")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            profile_dir, headless=headless, channel="chrome",
            viewport={"width": 1280, "height": 950},
            locale="ko-KR", timezone_id="Asia/Seoul",
            args=["--disable-blink-features=AutomationControlled"])
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            out["title"] = (page.title() or "").strip()

            # ① 상세 이미지 — lazy-load라 끝까지 스크롤해야 src가 채워진다
            for sel in ["button:has-text('상품정보 더보기')", ".product-detail-seemore-icon-wpui"]:
                try:
                    el = page.query_selector(sel)
                    if el:
                        el.click(timeout=3000); page.wait_for_timeout(1500); break
                except Exception:
                    pass
            for _ in range(20):
                page.mouse.wheel(0, 1800); page.wait_for_timeout(450)
            page.wait_for_timeout(1500)
            urls = page.evaluate(_DETAIL_IMG_JS) or []

            # ② 리뷰 — 상품평 탭 + 베스트순(도움순) 정렬
            try:
                el = page.query_selector("a:has-text('상품평')")
                if el:
                    el.click(timeout=4000); page.wait_for_timeout(2500)
            except Exception:
                pass
            for _ in range(10):
                page.mouse.wheel(0, 1500); page.wait_for_timeout(450)
            for sel in ["button:has-text('베스트순')", "span:has-text('베스트순')"]:
                try:
                    e = page.query_selector(sel)
                    if e:
                        e.click(timeout=3000); page.wait_for_timeout(2500); break
                except Exception:
                    pass
            seen = []
            for _ in range(REVIEW_PAGES):
                d = page.evaluate(_REVIEW_JS) or {}
                for t in (d.get("items") or []):
                    if t not in seen:
                        seen.append(t)
                try:
                    nxt = page.query_selector(
                        "button.sdp-review__article__page__next:not([disabled])")
                    if not nxt:
                        break
                    nxt.click(timeout=3000); page.wait_for_timeout(2200)
                except Exception:
                    break
            out["reviews"] = seen
        finally:
            ctx.close()

    for i, u in enumerate(urls):
        if len(out["detail_images"]) >= MAX_DETAIL_IMAGES:
            break
        try:
            req = urllib.request.Request(u, headers={
                "User-Agent": "Mozilla/5.0", "Referer": "https://www.coupang.com/"})
            b = urllib.request.urlopen(req, timeout=25).read()
            if len(b) < MIN_IMAGE_BYTES:
                continue
            fp = os.path.join(work_dir, "detail_%02d.jpg" % i)
            with open(fp, "wb") as f:
                f.write(b)
            out["detail_images"].append(fp)
        except Exception:
            continue
    log("[product_facts] 상세이미지 %d장 · 리뷰 %d건"
        % (len(out["detail_images"]), len(out["reviews"])))
    return out


_SPEC_PROMPT = """이건 한국 쇼핑몰(쿠팡)의 **상품 상세페이지 이미지**다. 상품: {name}
이 이미지에서 **영상 대본에 쓸 수 있는 사실**만 뽑아라. 이미지에 안 적힌 건 절대 지어내지 마라.

JSON만 출력:
{{
 "specs":  ["수치·규격이 들어간 사실 (예: 포켓 7개, 가로 220mm, 볼펜 65자루)"],
 "why":    ["그 스펙이 왜 좋은지 — 이미지가 설명하는 이유"],
 "origin": ["브랜드·기술·인증·특허 등 권위 근거"],
 "peak":   "가장 강력한 셀링포인트 한 줄"
}}"""

_REVIEW_PROMPT = """아래는 쿠팡 **베스트리뷰**(도움순 상위)다. 상품: {name}
영상 대본에 녹일 재료를 뽑아라. **리뷰에 실제로 적힌 것만** 써라 — 지어내면 안 된다.

JSON만 출력:
{{
 "pain":      ["구매 전 어떤 불편/고민이 있었나 (실제 상황)"],
 "trigger":   ["왜 사게 됐나 — 결정적 계기"],
 "satisfy":   ["사고 나서 뭐가 좋았나 (구체적 장면)"],
 "voice":     ["대본에 그대로 써도 좋을 실사용자 말투 문장 (짧게)"],
 "complaint": ["아쉬운 점 — 대본에서 단정하면 반박당하는 부분"]
}}

리뷰:
{reviews}"""


def _gemini(parts_or_text, *, model="gemini-3-flash-preview", log=print):
    """키 로테이션으로 제미니 1회 호출 → dict. 실패하면 {}.

    ★키는 반드시 로테이션한다 — 무료키는 분당15·하루500 두 겹 한도가 있고,
      한 키만 때리면 조용히 죽는다(memory: 제미니키 두겹 한도)."""
    try:
        from shopping_shorts import comment_gen
        from google import genai
        from google.genai import types
    except Exception as e:
        log("[product_facts] genai 임포트 실패: %s" % e)
        return {}
    keys = list(comment_gen.SHORTS_GEMINI_KEYS or [])
    if not keys:
        log("[product_facts] 제미니 키 0개 — 건너뜀")
        return {}
    if isinstance(parts_or_text, str):
        contents = parts_or_text
    else:
        contents = [types.Content(role="user", parts=parts_or_text)]
    for k in keys[:8]:
        try:
            cl = genai.Client(api_key=k)
            r = cl.models.generate_content(
                model=model, contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.25))
            return json.loads(r.text or "{}")
        except Exception:
            continue
    log("[product_facts] 제미니 전부 실패")
    return {}


def analyze(raw, *, name="", log=print):
    """collect_raw 결과 → product_facts dict. 재료가 없으면 그 칸만 빈다(예외 없음)."""
    from google.genai import types

    facts = {"source_url": (raw or {}).get("url", ""),
             "title": (raw or {}).get("title", "")}
    name = name or facts["title"] or "이 상품"

    imgs = (raw or {}).get("detail_images") or []
    if imgs:
        parts = [types.Part.from_text(text=_SPEC_PROMPT.format(name=name))]
        for fp in imgs[:MAX_DETAIL_IMAGES]:
            try:
                with open(fp, "rb") as f:
                    parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))
            except Exception:
                continue
        d = _gemini(parts, log=log)
        for k in ("specs", "why", "origin", "peak"):
            if d.get(k):
                facts[k] = d[k]

    revs = (raw or {}).get("reviews") or []
    if revs:
        body = "\n\n---\n".join(r[:1200] for r in revs[:10])
        d = _gemini(_REVIEW_PROMPT.format(name=name, reviews=body), log=log)
        for k in ("pain", "trigger", "satisfy", "voice", "complaint"):
            if d.get(k):
                facts[k] = d[k]
    return facts


def collect_and_analyze(product_url, work_dir, *, name="", log=print):
    """수집+분석 한 번에. 크롤이 실패해도(서버 403 등) 빈 facts를 돌려준다."""
    try:
        raw = collect_raw(product_url, work_dir, log=log)
    except Exception as e:  # noqa: BLE001 — 재료 수집 실패가 대본 생성을 막으면 안 된다
        log("[product_facts] 수집 실패: %s %s" % (type(e).__name__, str(e)[:120]))
        return {}
    return analyze(raw, name=name, log=log)


def prompt_block(facts, max_items=6):
    """product_facts → 대본 프롬프트에 붙일 블록. 비면 ''(호출부는 빈 문자열이면 회귀0).

    ★A/B 실측(2026-08-16)에서 이 블록이 실제로 대본을 바꿨다:
      없을 때 → "툭하면 떨어져서 시끄럽고"(AI가 상상한 불편) / "펜이 수십 자루"
      있을 때 → "애가 필통을 네 개씩 들고 다니니"(리뷰의 실제 사연) / "볼펜 65자루랑 20cm 자"
    """
    if not facts:
        return ""
    def _lines(key, label):
        v = facts.get(key)
        if not v:
            return ""
        if isinstance(v, str):
            v = [v]
        v = [str(x).strip() for x in v if str(x).strip()][:max_items]
        return ("\n- %s: " % label) + " / ".join(v) if v else ""

    body = "".join([
        _lines("specs", "확인된 스펙(수치를 그대로 살려 써라)"),
        _lines("why", "그 스펙이 좋은 이유"),
        _lines("origin", "출처·권위(브랜드·특허·인증)"),
        _lines("peak", "가장 센 셀링포인트(고조 자리에 쓰기 좋다)"),
        _lines("pain", "실사용자가 겪던 불편(리뷰 실측 — 도입부에 쓰면 공감이 산다)"),
        _lines("trigger", "구매 계기"),
        _lines("satisfy", "사고 나서 좋아진 점(구체적 장면)"),
        _lines("voice", "실사용자 말투(이 결을 살려라)"),
    ])
    if not body:
        return ""
    warn = ""
    if facts.get("complaint"):
        c = facts["complaint"]
        if isinstance(c, str):
            c = [c]
        warn = ("\n- ⚠️단정하면 반박당하는 부분(과장 금지): "
                + " / ".join(str(x) for x in c[:3]))
    return ("\n★[이 제품에 대해 확인된 사실 — 쿠팡 상세페이지·베스트리뷰에서 뽑았다]"
            "\n  아래는 **실제로 확인된 것**이다. 수치·사연을 적극 쓰되, 여기 없는 사실은 "
            "절대 지어내지 마라." + body + warn)
