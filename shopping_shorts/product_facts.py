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
    _last = None
    for k in keys[:8]:
        try:
            # ★2026-09-01: 유일하게 usage_meter 미배선이던 생성부(비용·429가 안 보였다).
            #   wrap으로 계측+관측 합류, 타임아웃은 comment_gen._client_for_key와 동일값.
            from shopping_shorts import usage_meter
            cl = usage_meter.wrap(
                genai.Client(api_key=k, http_options=types.HttpOptions(timeout=120_000)),
                pool="shorts", key=k)
            r = cl.models.generate_content(
                model=model, contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.25))
            return json.loads(r.text or "{}")
        except Exception as e:      # noqa: BLE001 — 한 키가 죽어도 다음 키로 넘어간다
            _last = e
            continue
    _why = ""
    if _last is not None:
        _m = str(_last)
        if "429" in _m or "RESOURCE_EXHAUSTED" in _m:
            _why = (" — 429 쿼터. 무료키는 분당15·하루500 두 겹이라 "
                    "연달아 돌리면 **분당** 쪽에 먼저 걸린다. 잠시 뒤 재시도해 보라")
        elif "401" in _m or "API_KEY_INVALID" in _m or "PERMISSION" in _m:
            _why = " — 키 인증 실패(401/권한). 키를 갈아야 한다"
        else:
            _why = " — %s: %s" % (type(_last).__name__, _m[:120])
    log("[product_facts] 제미니 전부 실패(키 %d개)%s" % (len(keys[:8]), _why))
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


# ── 제미니 지식으로 소구점 확장 (2026-09-08) ────────────────────────────────
#
# 왜 필요한가 — **재료가 0건이라 대본이 원본을 베낀다**(실측 2026-09-08):
#   최근 job 150건 전부 product.facts 없음(0%). 그래서 대본 생성이 보는 재료는
#   `_mix_source_block`이 만드는 원본 대본 800자 + 훅/전개/말투뿐이다.
#   원본을 요약하니 원본과 비슷해질 수밖에 없다.
#
# 왜 크롤이 아니라 제미니인가:
#   위 수집 경로(쿠팡)는 서버가 403이라 **사장님 PC 릴레이**가 필요하고 상품당 2~3분이
#   걸린다. 그래서 실제로 한 번도 안 채워졌다. 반면 제미니는 몇 초에 끝나고 릴레이가
#   필요 없다. 참고한 방법론(유튜브 '썰쇼핑쇼츠')도 크롤이 아니라 모델에게 한 마디
#   물어본다 — "이 아이템과 관련한 신기한 정보를 더 찾아줘".
#
# ★사장님 방향(2026-09-08): **대본이 최우선, 장면 배치는 후순위.**
#   그래서 여기서는 화면 근거로 재료를 거르지 않는다. 거르는 일이 필요하면
#   대본이 나온 **뒤에** 한다(insta_facts.gate_by_scene). 여기서 걸면 대본이
#   화면에 종속돼 다시 원본 베끼기로 돌아간다(feedback_대본자유_화면교차고정).
#
# ★출력 스키마는 prompt_block과 **같은 칸**을 쓴다(0순위-B). 새 통로를 만들지 않으므로
#   하류(대본 생성·슬롯 조립·스타일)는 코드 한 줄 안 바꾸고 그대로 돈다.

_EXPAND_KEYS = ("specs", "why", "origin", "peak", "pain", "trigger", "satisfy")

_EXPAND_PROMPT = """너는 쇼핑 숏폼 대본을 쓰기 위해 제품을 조사하는 사람이다.
대본을 쓰는 게 아니라 **재료를 캐는 것**이 네 일이다.

제품: {product}
분류: {category}
참고(원본 영상에서 관찰된 것): {hint}

★★가장 중요한 규칙 — **완성된 문장을 쓰지 마라. 사실 조각만 적어라.**

  나쁜 예(완성 문장):
    "스마트폰 필터로는 흉내 낼 수 없는 90년대 특유의 뽀샤시한 CCD 감성 색감"
    "USB 연결 시 별도 설정 없이 바로 고화질 웹캠으로 변신하여 라이브 방송 가능"
  좋은 예(사실 조각):
    "CCD 센서 / 색이 따뜻하고 노이즈가 낌 / 비교대상=폰카 필터"
    "USB 꽂으면 웹캠 됨 / 드라이버 설치 불필요"

  왜: 완성 문장을 주면 대본 쓰는 쪽이 **그대로 베낀다**. 그러면 열 편이 다 똑같아진다.
      사실만 주면 그쪽이 자기 말투로 새로 쓴다. 표현은 네 일이 아니다.

  · 수식어를 빼라(뽀샤시한·특유의·완벽하게·놀라운·환상적인).
  · 한 항목은 **짧게**. 낱말과 짧은 구로. 문장부호로 잇지 마라.
  · 서술어를 길게 늘이지 마라("~하여 ~가능함" 금지 → "~됨"으로 끊어라).

이 제품에 대해 **네가 아는 것**을 아래 칸에 채워라.
★원본 영상에 없던 내용이어도 좋다 — 오히려 그런 걸 원한다.
★단 지어내지 마라. 모르면 그 칸을 비워라. 빈 칸은 벌점이 아니다.

- specs   : 구조·소재·방식. (예: "CCD 센서", "3단 접이", "실리콘 밴드")
- why     : 그게 왜 좋은지. 원리만 짧게. (예: "빛을 덜 받아 색이 따뜻해짐")
- origin  : 유래·원래 용도. (예: "원래 등산용", "90년대 필름카메라 방식")
- peak    : ★**의외의 용도·쓰임**. 듣고 "어? 이런 게 된다고?" 소리가 나오는 것.
            ★목록이 아니라 **한 줄로 말이 되게** 적어라(쓰임+결과까지).
              X: "거울 셀카용 패션 소품"          ← 뭐 어쩌다는 건지 모른다
              O: "거울 셀카 찍을 때 소품으로 들면 분위기가 산다"
              X: "모니터 화면 촬영"
              O: "모니터 화면을 찍으면 글리치 효과가 그대로 남는다"
            ★단 수식어로 꾸미지는 말고(놀라운·완벽한·미친) 사실만 한 줄로.
            사양·기능 나열이 아니다. **원래 그 물건을 그렇게 쓸 줄 몰랐던 쓰임**이다.
              O: "샤워기 목에 감아 각도 고정" / "KTX 앞좌석 테이블에 꼬아 폰 거치"
                 "텐트 폴대에 감아 랜턴 걸이"
              X: "USB 웹캠 인식" / "SD카드 슬롯" / "날짜 각인 기능"
                 (이건 그냥 사양이다 — 듣고 놀랄 사람이 없다)
- pain    : 없을 때 겪던 불편. 상황만. (예: "폰카가 너무 선명해 잡티가 다 보임")
- trigger : 사게 되는 계기. (예: "여행 전 서브 카메라 필요할 때")
- satisfy : 쓰고 나서 좋아진 점. 장면으로. (예: "대충 찍어도 화보처럼 나옴")

★★peak가 이 조사의 핵심이다. 아래 시험을 통과하는 것만 적어라.
    "이 말을 들은 사람이 **어? 하고 멈추는가**"
    "그 물건을 이미 아는 사람도 **몰랐을 쓰임인가**"
  통과 못 하면 적지 마라. 사양·성능·스펙은 위 specs 칸에 이미 적었다 —
  peak에 또 적지 마라(그건 아무도 안 궁금해한다).
  이런 것을 노려라: 제조사가 의도 안 한 활용 / 다른 물건 대신 쓰는 법 /
  전혀 다른 상황에서 쓰는 법 / 원래 용도를 뒤집는 쓰임 /
  의외의 대상(아이·반려동물·차·여행) / 부작용처럼 보이는데 오히려 좋은 점.

  ★★**최소 4개**를 찾아라. 대본의 고조 칸이 2개라 골라 쓸 여유가 있어야 한다.
    2개밖에 못 찾으면 대본이 나머지를 '당연한 소리'로 메운다 — 그게 영상을 죽인다.

  ★★그 제품이면 **당연한 것은 절대 적지 마라**. 이게 밋밋함의 진짜 원인이다:
      X "방수라 물이 튀어도 괜찮다"      ← 세탁기·욕실용품이면 당연
      X "충전식이라 선 없이 쓴다"        ← 무선 제품이면 당연
      X "가벼워서 들고 다니기 좋다"      ← 휴대용이면 당연
      X "솔이 부드러워 긁히지 않는다"    ← 청소솔이면 당연
      X "작아서 수납이 편하다"           ← 미니 제품이면 당연
      O "안경이나 금속 시곗줄을 넣으면 초음파처럼 씻긴다"
      O "풍선 속에 넣으면 날아다니는 유령이 된다"
      O "모니터 화면을 찍으면 글리치가 그대로 남는다"
    → **판별법: 그 문장 앞에 "당연히"를 붙여도 말이 되면 버려라.**

  단 여기서도 **사실만** — 감탄사·수식어는 붙이지 마라. 4개를 못 채우겠으면
  억지로 채우지 말고 비워라(당연한 소리로 채우는 것보다 비는 게 낫다).

각 칸은 문자열 배열(**peak는 최대 8개**, 나머지는 최대 5개). 각 항목은 30자를 넘기지 마라. JSON만 출력."""


def expand_by_llm(product, category="", hint="", *, log=print):
    """제품명 → 소구점 재료 dict(prompt_block과 같은 스키마). 실패·무지식이면 {}.

    product 가 비면 아무것도 안 한다 — 제품을 모르는 채로 물으면 모델이 지어낸다.
    """
    product = (product or "").strip()
    if not product:
        log("[product_facts] 확장 건너뜀 — 제품명이 없다")
        return {}
    prompt = _EXPAND_PROMPT.format(
        product=product,
        category=(category or "").strip() or "(미상)",
        hint=(hint or "").strip()[:400] or "(없음)")
    got = _gemini(prompt, log=log) or {}
    # ★타입을 믿지 마라(2026-09-08 실측 사고). 모델이 칸 dict가 아니라 **배열**을
    #   돌려줄 때가 있다 — 그러면 got.get(k)가 AttributeError로 터진다.
    #   메모리 교훈 그대로: 받는 쪽부터 읽고 형태를 확인한 뒤 쓴다.
    if isinstance(got, list):
        merged = {}
        for it in got:
            if isinstance(it, dict):
                for k, v in it.items():
                    merged.setdefault(k, [])
                    merged[k] += v if isinstance(v, (list, tuple)) else [v]
        got = merged
    if not isinstance(got, dict):
        log("[product_facts] 확장 응답이 dict가 아니다(%s) — 건너뜀" % type(got).__name__)
        return {}
    out = {}
    for k in _EXPAND_KEYS:
        v = got.get(k)
        if not v:
            continue
        if isinstance(v, str):
            v = [v]
        vals = [str(x).strip() for x in v if str(x).strip()][:5]
        if vals:
            out[k] = vals
    if out:
        # ★출처 표식(2026-09-08) — 이게 없으면 prompt_block이 LLM 지식을
        #   "쿠팡에서 확인된 사실"이라고 말해 **가짜 스펙이 영상에 박힌다**.
        out["_source"] = "llm"
        log("[product_facts] 확장 성공 — %s (%s)"
            % (product, " ".join("%s%d" % (k, len(out[k]))
                                 for k in out if k != "_source")))
    else:
        log("[product_facts] 확장 결과 없음 — %s" % product)
    return out


def prompt_block(facts, max_items=6):
    """product_facts → 대본 프롬프트에 붙일 블록. 비면 ''(호출부는 빈 문자열이면 회귀0).

    ★A/B 실측(2026-08-16)에서 이 블록이 실제로 대본을 바꿨다:
      없을 때 → "툭하면 떨어져서 시끄럽고"(AI가 상상한 불편) / "펜이 수십 자루"
      있을 때 → "애가 필통을 네 개씩 들고 다니니"(리뷰의 실제 사연) / "볼펜 65자루랑 20cm 자"
    """
    if not facts:
        return ""
    def _lines(key, label):
        if key == "_source":          # 출처 표식은 재료가 아니다
            return ""
        v = facts.get(key)
        if not v:
            return ""
        if isinstance(v, str):
            v = [v]
        v = [str(x).strip() for x in v if str(x).strip()][:max_items]
        return ("\n- %s: " % label) + " / ".join(v) if v else ""

    # ★칸 라벨도 출처를 따라간다(2026-09-08 사장님 "스펙이라기보다 제품에 이런 특징이
    #   있다는 써도 된다"). LLM 재료에 "확인된 스펙 / 수치를 그대로 살려 써라"라는
    #   라벨을 붙이면 머리말로 아무리 말려도 모델이 수치를 그대로 쓴다 —
    #   지시와 라벨이 서로 다른 말을 하면 **가까운 라벨이 이긴다**.
    _llm = facts.get("_source") == "llm"
    body = "".join([
        _lines("specs", "제품의 특징(수치 단정 말고 '이런 게 있다'로)" if _llm
                        else "확인된 스펙(수치를 그대로 살려 써라)"),
        _lines("why", "그 특징이 좋은 이유" if _llm else "그 스펙이 좋은 이유"),
        _lines("origin", "알려진 유래·원래 용도(브랜드·특허·인증은 단정 금지)" if _llm
                         else "출처·권위(브랜드·특허·인증)"),
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
    # ★머리말은 재료의 **출처**에 따라 갈라야 한다(2026-09-08).
    #   실측으로 잡힌 위험: expand_by_llm(제미니 지식)이 만든 재료에도 종전 머리말이
    #   그대로 붙어 "쿠팡에서 확인된 사실 / 수치를 그대로 살려 써라"라고 말했다.
    #   베이스어스 이어폰 확장 결과에 '16.2mm 드라이버·IPX4·블루투스 5.3'이 나왔는데
    #   그게 실제 그 모델의 스펙인지는 **아무도 확인하지 않았다** — 그대로 쓰면
    #   가짜 스펙이 고객 영상에 박힌다(사장님 금지선: 가짜지표).
    if facts.get("_source") == "llm":
        head = ("\n★[이 제품에 대해 **일반적으로 알려진 것** — 검색·상세페이지가 아니라 "
                "AI 지식에서 왔다]"
                "\n  쓰임새·불편·활용은 적극 살려라. 다만 **확인된 값이 아니다**:"
                "\n  - 수치·모델명·인증은 **단정하지 마라**. 꼭 쓰려면 완곡하게"
                "\n    (\"16.2mm 드라이버\"(X) → \"드라이버가 큼\"(O),"
                " \"IPX4\"(X) → \"생활방수 되는\"(O))"
                "\n  - 브랜드·특허·수상은 **빼라**. 틀리면 영상 하나가 통째로 죽는다."
                "\n  - 반대로 **쓰임새·응용·불편·계기**는 마음껏 써라 — 여기가 이 재료의 값이다.")
    else:
        head = ("\n★[이 제품에 대해 확인된 사실 — 쿠팡 상세페이지·베스트리뷰에서 뽑았다]"
                "\n  아래는 **실제로 확인된 것**이다. 수치·사연을 적극 쓰되, 여기 없는 사실은 "
                "절대 지어내지 마라.")
    return head + body + warn
