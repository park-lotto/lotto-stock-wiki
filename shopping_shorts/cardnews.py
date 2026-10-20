# -*- coding: utf-8 -*-
"""카드뉴스 제작소(관제 223, 2026-10-17 사장님 "숏템에서 / 최고의 디자인 UI로").

★판단은 여기 한 곳(0순위-B·C). 화면(cardnews.html)·자동 규칙 루프·API는 이 함수들을 **부르기만** 한다.
  · 장 구성·문구 규칙      → plan_outline / build_carousel
  · 결과물 글 검사         → check_carousel   (글자 넘침은 브라우저 렌더에서 잰다 — cardnews-render.js measure)
  · 배경 그림              → gen_background   (허용 판정은 vertex_route.veo_allowed 를 빌린다)
  · 자동 규칙 다음 실행 시각 → next_run_at
  · 카드 그리기(디자인)는 static/cardnews-render.js 한 곳 — 편집 미리보기·썸네일·다운로드가 같은 함수를 쓴다.

AI 호출은 script_generate._call_json 깔때기(vertex_op="cardnews"). 버텍스 등록 회원·관리자는 자기/사장님 Vertex,
그 외는 무료 키풀 — 판정은 vertex_route.plan 한 곳.
"""
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

RULE_VERSION = "cardnews-2026-10-17"
VERTEX_OP = "cardnews"
ROLES = ("cover", "number", "compare", "steps", "list", "quote", "cta")
ROLE_NAMES = {"cover": "표지", "number": "숫자", "compare": "비교", "steps": "단계", "list": "목록",
              "quote": "한마디", "cta": "마무리"}
PACKS = ("editorial", "magazine", "photo", "pastel")
MIN_SLIDES, MAX_SLIDES, AUTO_SLIDES = 3, 10, 6
COVER_MAX = 22          # 첫 장 제목 글자 수 상한({} 제외). aiCarousels 점검표 '첫 장 12단어 이하'를 한글 글자로
TITLE_MAX = 30
BODY_MAX = 90
ITEM_MAX = 22
IMAGE_MODEL_DEFAULT = "gemini-3.1-flash-lite-image"   # ★Imagen 4는 사장님 프로젝트에서 404(2026-10-17 라이브 실측, 모델 목록에 없음).
#   제미니 그림 모델은 location=global 에서만 된다(us-central1 404). lite 4.9초·142KB, 지시대로 글자 없는 사진이 나왔다
#   (3.1-flash-image 는 9.2초·병에 영어 라벨을 그려 넣음). 설정 cardnews_image_model 로 바꿀 수 있다(imagen-* 도 받는다).
FALLBACK_MODEL = "gemini-3.5-flash"   # 무료 키풀 기본 모델이 503 과부하일 때 마지막 한 번(버텍스 경로는 vertex_route.model 그대로)
KST = timezone(timedelta(hours=9))

PURPOSES = {"info": "정보 전달", "promo": "상품 홍보", "save": "저장 유도", "follow": "팔로우 유도"}
TONES = ("친근한 존댓말", "전문가 존댓말", "짧고 강한 반말")

DEFAULT_BRAND = {"name": "", "color": "#37e0bd", "tone": "친근한 존댓말", "ban": "", "cta": "",
                 "handle": "", "logo": ""}


# ── 공용 정리 ─────────────────────────────────────────────────────────────
def plain(s):
    """{강조} 표시를 뺀 글자."""
    return re.sub(r"[{}]", "", s or "")


def clamp_count(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return AUTO_SLIDES
    return max(MIN_SLIDES, min(MAX_SLIDES, n))


def brand_of(store, cid):
    b = dict(DEFAULT_BRAND)
    try:
        got = store.cardnews_brand_get(cid) or {}
    except Exception as e:      # noqa: BLE001
        log.warning("cardnews: 브랜드 조회 실패 %r — 기본값", e)
        got = {}
    b.update({k: v for k, v in got.items() if k in DEFAULT_BRAND})
    return b


def clean_brand(d):
    out = dict(DEFAULT_BRAND)
    for k in DEFAULT_BRAND:
        v = (d or {}).get(k, out[k])
        out[k] = str(v)[:300] if v is not None else ""
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", out["color"] or ""):
        out["color"] = DEFAULT_BRAND["color"]
    if out["tone"] not in TONES:
        out["tone"] = DEFAULT_BRAND["tone"]
    if out["logo"] and not out["logo"].startswith("/api/cardnews/asset/"):
        out["logo"] = ""
    return out


def normalize_slide(s):
    """AI·화면이 보낸 장 하나를 정해진 모양으로. 모르는 칸은 버린다."""
    s = s if isinstance(s, dict) else {}
    role = s.get("role") if s.get("role") in ROLES else "list"

    def t(k, m):
        return str(s.get(k) or "").strip()[:m]

    out = {"role": role, "kicker": t("kicker", 24), "title": t("title", 80), "body": t("body", 220),
           "num": t("num", 12), "items": [str(x).strip()[:60] for x in (s.get("items") or []) if str(x).strip()][:6],
           "layout": int(s.get("layout") or 0) % 4,
           "image_prompt": t("image_prompt", 400)}
    for side in ("a", "b"):
        o = s.get(side) if isinstance(s.get(side), dict) else {}
        out[side] = {"name": str(o.get("name") or "").strip()[:20],
                     "points": [str(x).strip()[:40] for x in (o.get("points") or []) if str(x).strip()][:4]}
    bg = s.get("bg") if isinstance(s.get("bg"), dict) else {}
    url = str(bg.get("url") or "")
    if url and not (url.startswith("/api/cardnews/asset/") or url.startswith("https://")):
        url = ""
    out["bg"] = {"kind": bg.get("kind") if bg.get("kind") in ("none", "link", "ai") else "none", "url": url}
    return out


def normalize_carousel(car):
    car = car if isinstance(car, dict) else {}
    slides = [normalize_slide(x) for x in (car.get("slides") or [])][:MAX_SLIDES]
    opts = car.get("opts") if isinstance(car.get("opts"), dict) else {}
    return {
        "topic": str(car.get("topic") or "")[:200],
        "source": car.get("source") if isinstance(car.get("source"), dict) else {},
        "opts": {"purpose": opts.get("purpose") if opts.get("purpose") in PURPOSES else "info",
                 "pack": opts.get("pack") if opts.get("pack") in PACKS else "editorial",
                 "font": str(opts.get("font") or "Pretendard")[:40],
                 "cover_font": str(opts.get("cover_font") or "")[:40],
                 "size": opts.get("size") if opts.get("size") in ("S", "M", "L") else "M",
                 "ratio": opts.get("ratio") if opts.get("ratio") in ("4:5", "1:1", "9:16") else "4:5",
                 "img": opts.get("img") if opts.get("img") in ("none", "link", "ai") else "none"},
        "slides": slides,
        "caption": str(car.get("caption") or "")[:2000],
        "hashtags": [str(h).strip().lstrip("#")[:30] for h in (car.get("hashtags") or []) if str(h).strip()][:15],
        "checks": car.get("checks") if isinstance(car.get("checks"), list) else [],
        "rule_version": car.get("rule_version") or RULE_VERSION,
    }


# ── 링크 읽기 ─────────────────────────────────────────────────────────────
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/124.0 Safari/537.36")


def _meta(html, *names):
    for n in names:
        m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]+content=["\']([^"\']+)' % re.escape(n), html, re.I) \
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']%s["\']' % re.escape(n), html, re.I)
        if m:
            import html as _h
            return _h.unescape(m.group(1)).strip()
    return ""


def read_link(url):
    """링크에서 제목·설명·대표 사진을 읽는다. 실패해도 예외 없이 {ok:False, why}."""
    import requests
    url = (url or "").strip()
    if not re.match(r"^https?://", url):
        return {"ok": False, "why": "http로 시작하는 링크를 넣어 주세요"}
    try:
        if re.search(r"(youtube\.com|youtu\.be)/", url):
            r = requests.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"},
                             timeout=8, headers={"User-Agent": _UA})
            if r.ok:
                d = r.json()
                return {"ok": True, "kind": "youtube", "url": url, "title": d.get("title", ""),
                        "desc": "", "image": d.get("thumbnail_url", "")}
        r = requests.get(url, timeout=8, headers={"User-Agent": _UA, "Accept-Language": "ko-KR,ko;q=0.9"})
        html = r.text[:400_000]
        title = _meta(html, "og:title", "twitter:title")
        if not title:
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        desc = _meta(html, "og:description", "description", "twitter:description")
        image = _meta(html, "og:image", "twitter:image")
        if not (title or desc):
            return {"ok": False, "why": "이 링크는 내용을 읽을 수 없어요(사이트가 막음). 주제나 글로 넣어 주세요"}
        return {"ok": True, "kind": "web", "url": url, "title": title[:200], "desc": desc[:600],
                "image": image if image.startswith("https://") else ""}
    except Exception as e:      # noqa: BLE001
        log.warning("cardnews.read_link 실패 %s: %r", url, e)
        return {"ok": False, "why": "링크를 여는 중 문제가 생겼어요. 주제나 글로 넣어 주세요"}


def source_text(src):
    """AI에 줄 원문 — 검사(지어낸 숫자·날짜)의 기준이기도 하다."""
    src = src or {}
    parts = [src.get("topic") or "", src.get("title") or "", src.get("desc") or "", src.get("text") or "",
             src.get("product") or ""]
    return "\n".join(p for p in parts if p).strip()[:6000]


# ── AI 호출 ───────────────────────────────────────────────────────────────
def _busy(note):
    d = str((note or {}).get("detail") or "")
    return (note or {}).get("reason") == "api_error" and ("503" in d or "UNAVAILABLE" in d or "overloaded" in d.lower())


def _ai_json(prompt, schema, note=None):
    """AI JSON 1회. 구글 쪽 일시 과부하(503 UNAVAILABLE)면 2초·5초 뒤 두 번 더 — 실측 2026-10-17 로컬 키풀
    'This model is currently experiencing high demand'로 개요가 연달아 빈 결과였다. 세 번째는 다른 모델로.
    다른 실패(키 소진·스키마 등)는 바로 돌려준다."""
    from shopping_shorts import script_generate as _sg
    note = note if note is not None else {}
    for wait, model in ((0, None), (2, None), (3, FALLBACK_MODEL)):
        if wait:
            time.sleep(wait)
        note.clear()
        got = _sg._call_json(prompt, schema, note=note, model=model, vertex_op=VERTEX_OP) or {}
        if got or not _busy(note):
            return got
        log.warning("cardnews: AI 과부하(503) — 다시 시도%s", " (다른 모델 %s)" % FALLBACK_MODEL if model is None and wait == 2 else "")
    return {}


def _brand_lines(brand):
    lines = []
    if brand.get("name"):
        lines.append("- 계정 이름: %s" % brand["name"])
    lines.append("- 말투: %s" % (brand.get("tone") or DEFAULT_BRAND["tone"]))
    if brand.get("ban"):
        lines.append("- 쓰면 안 되는 말: %s" % brand["ban"])
    if brand.get("cta"):
        lines.append("- 마지막 장 문구 방향: %s" % brand["cta"])
    return "\n".join(lines)


_OUTLINE_SCHEMA = {"type": "object", "properties": {
    "title": {"type": "string"},
    "slides": {"type": "array", "items": {"type": "object", "properties": {
        "role": {"type": "string", "enum": list(ROLES)}, "line": {"type": "string"}},
        "required": ["role", "line"]}}},
    "required": ["title", "slides"]}


def plan_outline(src, opts, brand, note=None):
    """개요(장별 종류 + 한 줄). 크레딧이 드는 '만들기' 전의 무료 단계."""
    count = opts.get("count")
    n_rule = ("%d장" % clamp_count(count)) if str(count).isdigit() else "주제에 맞게 %d~%d장" % (5, 8)
    prompt = f"""너는 인스타그램 카드뉴스(캐러셀) 기획자다. 아래 소재로 카드뉴스 개요를 만든다.

[소재]
{source_text(src)}

[목적] {PURPOSES.get(opts.get('purpose'), '정보 전달')}
[계정]
{_brand_lines(brand)}

[규칙]
- 장수: {n_rule}. 첫 장은 반드시 cover(표지), 마지막 장은 반드시 cta(저장·팔로우를 부르는 마무리).
- 가운데 장은 내용에 맞게 고른다: number(숫자 하나가 핵심) · compare(둘을 견줌) · steps(순서) · list(항목 나열) · quote(한마디 인용).
  같은 종류가 3장 넘게 이어지지 않게 섞는다.
- line은 그 장에 들어갈 핵심을 한국어 한 줄(30자 이내)로.
- 소재에 없는 날짜·통계·가격·고유명사를 지어내지 않는다.
- title은 이 카드뉴스 전체 제목(20자 이내)."""
    out = _ai_json(prompt, _OUTLINE_SCHEMA, note=note)
    slides = []
    for s in (out.get("slides") or [])[:MAX_SLIDES]:
        if isinstance(s, dict) and s.get("role") in ROLES:
            slides.append({"role": s["role"], "line": str(s.get("line") or "").strip()[:60]})
    if len(slides) < MIN_SLIDES:
        return {"ok": False, "why": "개요를 만들지 못했어요. 잠시 뒤 다시 눌러 주세요", "note": note}
    slides[0]["role"] = "cover"
    slides[-1]["role"] = "cta"
    return {"ok": True, "title": str(out.get("title") or "").strip()[:40], "slides": slides}


_SLIDE_SCHEMA = {"type": "object", "properties": {
    "role": {"type": "string", "enum": list(ROLES)},
    "kicker": {"type": "string"}, "title": {"type": "string"}, "body": {"type": "string"},
    "num": {"type": "string"}, "items": {"type": "array", "items": {"type": "string"}},
    "a": {"type": "object", "properties": {"name": {"type": "string"},
                                           "points": {"type": "array", "items": {"type": "string"}}}},
    "b": {"type": "object", "properties": {"name": {"type": "string"},
                                           "points": {"type": "array", "items": {"type": "string"}}}},
    "image_prompt": {"type": "string"}},
    "required": ["role", "kicker", "title", "body"]}
_BUILD_SCHEMA = {"type": "object", "properties": {
    "slides": {"type": "array", "items": _SLIDE_SCHEMA},
    "caption": {"type": "string"}, "hashtags": {"type": "array", "items": {"type": "string"}}},
    "required": ["slides", "caption", "hashtags"]}

_WRITE_RULES = f"""[문구 규칙]
- 한국어. 말투는 계정 말투를 끝까지 지킨다(존댓말·반말 섞지 않기).
- 장마다 title에서 가장 중요한 말 하나를 {{중괄호}}로 감싼다(강조색이 들어간다). 한 장에 한 번만.
- cover: kicker(작은 머리말 8자 이내), title({COVER_MAX}자 이내, 넘기게 만드는 질문·약속), body(부제 25자 이내).
- number: num(숫자+단위, 예 '10분', '3배'. 소재에 있는 숫자만), title(26자 이내), body(설명 60자 이내).
- compare: title, a.name/b.name(각 8자 이내), a.points/b.points(각 2~3개, 14자 이내, 장점은 '+', 단점은 '-'로 시작).
- steps·list: title, items 3~5개(각 {ITEM_MAX}자 이내), body는 비워도 된다.
- quote: title(인용문 40자 이내), body(누가 한 말인지, 없으면 비움).
- cta: title(저장·팔로우를 부르는 한 줄 26자 이내), body(다음 편 예고나 한마디 30자 이내).
- body는 {BODY_MAX}자 이내. 모든 title은 {TITLE_MAX}자 이내.
- 소재에 없는 날짜·통계·가격·고유명사를 지어내지 않는다. 확실하지 않으면 숫자를 빼고 말로 쓴다.
- image_prompt: 그 장 배경 사진을 만들 영어 설명(사람 얼굴 클로즈업·글자·로고 금지, 사진 같은 장면, 1문장).
- caption: 인스타 본문 3~5줄(줄바꿈 포함). 첫 줄은 궁금하게. 마지막 줄에 저장을 권한다.
- hashtags: 5~8개, # 없이."""


def _build_prompt(src, outline, opts, brand, fix=None):
    ol = "\n".join("%d. [%s] %s" % (i + 1, ROLE_NAMES.get(s["role"], s["role"]), s.get("line", ""))
                   for i, s in enumerate(outline))
    fix_block = ""
    if fix:
        fix_block = "\n[고칠 점 — 앞서 만든 결과에서 걸린 것. 반드시 고친다]\n" + "\n".join("- " + f for f in fix)
    return f"""너는 인스타그램 카드뉴스 카피라이터다. 아래 개요의 장 수와 순서·종류를 그대로 지켜 장별 문구를 쓴다.

[소재]
{source_text(src)}

[목적] {PURPOSES.get(opts.get('purpose'), '정보 전달')}
[계정]
{_brand_lines(brand)}

[개요 — 이 순서·종류 그대로]
{ol}

{_WRITE_RULES}{fix_block}"""


def build_carousel(src, outline, opts, brand, note=None):
    """★문구의 주인. 개요 → 장별 문구 → 검사 → 걸리면 한 번 다시 쓰기. 돌려주는 값은 normalize_carousel 모양."""
    outline = [o for o in (outline or []) if isinstance(o, dict) and o.get("role") in ROLES][:MAX_SLIDES]
    if len(outline) < MIN_SLIDES:
        return {"ok": False, "why": "개요가 %d장보다 적어요" % MIN_SLIDES}
    outline[0]["role"], outline[-1]["role"] = "cover", "cta"
    raw = _ai_json(_build_prompt(src, outline, opts, brand), _BUILD_SCHEMA, note=note)
    car = _assemble(src, outline, opts, raw)
    if not car["slides"]:
        return {"ok": False, "why": "문구를 만들지 못했어요. 잠시 뒤 다시 눌러 주세요", "note": note}
    issues = check_carousel(car, brand)
    hard = [i for i in issues if i["level"] == "fix"]
    fixed_codes = []
    if hard:
        raw2 = _ai_json(_build_prompt(src, outline, opts, brand, fix=[i["msg"] for i in hard]), _BUILD_SCHEMA)
        car2 = _assemble(src, outline, opts, raw2)
        if car2["slides"]:
            issues2 = check_carousel(car2, brand)
            if len([i for i in issues2 if i["level"] == "fix"]) < len(hard):
                fixed_codes = sorted({i["code"] for i in hard} - {i["code"] for i in issues2 if i["level"] == "fix"})
                car, issues = car2, issues2
    car["checks"] = _check_report(issues, fixed_codes)
    return {"ok": True, "carousel": car}


def _assemble(src, outline, opts, raw):
    got = raw.get("slides") if isinstance(raw, dict) else None
    slides = []
    for i, o in enumerate(outline):
        s = got[i] if isinstance(got, list) and i < len(got) and isinstance(got[i], dict) else None
        if not s:
            continue
        s = dict(s)
        s["role"] = o["role"]          # ★개요의 종류가 주인 — AI가 바꿔도 되돌린다
        slides.append(s)
    car = normalize_carousel({"topic": src.get("topic") or src.get("title") or "", "source": _src_meta(src),
                              "opts": opts, "slides": slides,
                              "caption": (raw or {}).get("caption", ""), "hashtags": (raw or {}).get("hashtags", [])})
    img = opts.get("img")
    if img == "link" and src.get("image"):
        for s in car["slides"]:
            s["bg"] = {"kind": "link", "url": src["image"]}
    return car


def _src_meta(src):
    return {k: (src or {}).get(k, "") for k in ("kind", "url", "title", "image")}


# ── 검사(글) ──────────────────────────────────────────────────────────────
CHECK_LIST = [
    ("invented", "주제에 없는 날짜·숫자를 지어냈나"),
    ("empty", "내용이 빈 장이 있나"),
    ("dup_title", "제목이 다른 장과 겹치나"),
    ("cover_long", "첫 장 제목 %d자 이하" % COVER_MAX),
    ("too_long", "제목·본문·항목 길이"),
    ("banned", "쓰면 안 되는 말"),
    ("tone", "존댓말·반말 섞임"),
    ("repeat", "같은 문장 반복"),
    ("cta", "마지막 장이 저장·팔로우를 부르나"),
    ("highlight", "장마다 강조 한 곳"),
    ("count", "장수 %d~%d장" % (MIN_SLIDES, MAX_SLIDES)),
    ("overflow", "글자가 칸을 넘치나(그리기 단계에서 잼)"),
]
_DATE_RE = re.compile(r"(\d{4}\s*년|\d{1,2}\s*월\s*\d{1,2}\s*일|\d{4}[./-]\d{1,2}([./-]\d{1,2})?)")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|퍼센트|배|만원|원|억|만|개월|년|명|건|위)")
_BANMAL_END = re.compile(r"(해|야|지|어|거든|잖아|자|함|임|음)[.!?]?$")
_JONDAE_END = re.compile(r"(요|니다|세요|까요|죠)[.!?]?$")


def _texts(s):
    out = [s.get("kicker", ""), plain(s.get("title", "")), s.get("body", "")]
    out += s.get("items") or []
    for side in ("a", "b"):
        out.append((s.get(side) or {}).get("name", ""))
        out += (s.get(side) or {}).get("points") or []
    return [x for x in out if x]


def check_carousel(car, brand, source=None):
    """★글 검사의 주인. [{slide(0부터, -1=전체), code, level('fix'|'warn'), msg}]."""
    slides = car.get("slides") or []
    src = source if source is not None else source_text(car.get("source") or {}) + "\n" + (car.get("topic") or "")
    issues = []

    def add(i, code, level, msg):
        issues.append({"slide": i, "code": code, "level": level, "msg": msg})

    if not (MIN_SLIDES <= len(slides) <= MAX_SLIDES):
        add(-1, "count", "fix", "장수가 %d장이에요(%d~%d장)" % (len(slides), MIN_SLIDES, MAX_SLIDES))
    titles = {}
    seen_sent = {}
    bans = [b.strip() for b in re.split(r"[,\n]", (brand or {}).get("ban") or "") if b.strip()]
    ends = {"j": 0, "b": 0}
    for i, s in enumerate(slides):
        n = i + 1
        role = s.get("role")
        t = plain(s.get("title"))
        if not t:
            add(i, "empty", "fix", "%d장 제목이 비었어요" % n)
        if role in ("steps", "list") and len(s.get("items") or []) < 2:
            add(i, "empty", "fix", "%d장 항목이 2개보다 적어요" % n)
        if role == "compare" and not ((s.get("a") or {}).get("points") and (s.get("b") or {}).get("points")):
            add(i, "empty", "fix", "%d장 비교 양쪽 내용이 비었어요" % n)
        if role == "number" and not s.get("num"):
            add(i, "empty", "warn", "%d장 숫자 카드에 숫자가 없어요" % n)
        if t:
            key = re.sub(r"\s+", "", t)
            if key in titles:
                add(i, "dup_title", "fix", "%d장 제목이 %d장과 같아요" % (n, titles[key] + 1))
            titles.setdefault(key, i)
        if i == 0 and len(t) > COVER_MAX:
            add(i, "cover_long", "fix", "첫 장 제목이 %d자예요(%d자 이하로)" % (len(t), COVER_MAX))
        if i > 0 and len(t) > TITLE_MAX:
            add(i, "too_long", "fix", "%d장 제목이 %d자예요(%d자 이하로)" % (n, len(t), TITLE_MAX))
        if len(s.get("body") or "") > BODY_MAX:
            add(i, "too_long", "fix", "%d장 본문이 길어요(%d자 이하로)" % (n, BODY_MAX))
        if any(len(x) > ITEM_MAX for x in (s.get("items") or [])):
            add(i, "too_long", "fix", "%d장 항목이 길어요(%d자 이하로)" % (n, ITEM_MAX))
        if s.get("title") and "{" not in s.get("title"):
            add(i, "highlight", "warn", "%d장에 강조할 말이 없어요" % n)
        for txt in _texts(s):
            for m in _DATE_RE.finditer(txt):
                if re.sub(r"\s", "", m.group(0)) not in re.sub(r"\s", "", src):
                    add(i, "invented", "fix", "%d장 '%s' — 소재에 없는 날짜예요. 빼거나 확인해 주세요" % (n, m.group(0)))
            for m in _NUM_RE.finditer(txt):
                if re.sub(r"\s", "", m.group(0)) not in re.sub(r"\s", "", src) and role != "steps":
                    add(i, "invented", "warn", "%d장 '%s' — 소재에 없는 숫자예요. 사실인지 확인해 주세요" % (n, m.group(0)))
            for b in bans:
                if b and b in txt:
                    add(i, "banned", "fix", "%d장에 쓰면 안 되는 말 '%s' 포함" % (n, b))
            for sent in re.split(r"(?<=[.!?])\s+", txt):
                sk = re.sub(r"\W", "", sent)
                if len(sk) >= 8:
                    if sk in seen_sent and seen_sent[sk] != i:
                        add(i, "repeat", "warn", "%d장 문장이 %d장과 같아요" % (n, seen_sent[sk] + 1))
                    seen_sent.setdefault(sk, i)
        for txt in [s.get("body") or ""] + ([plain(s.get("title"))] if role in ("cta", "quote") else []):
            txt = txt.strip()
            if _JONDAE_END.search(txt):
                ends["j"] += 1
            elif _BANMAL_END.search(txt):
                ends["b"] += 1
    if ends["j"] and ends["b"]:
        add(-1, "tone", "warn", "존댓말과 반말이 섞였어요(존댓말 %d · 반말 %d)" % (ends["j"], ends["b"]))
    if slides and slides[-1].get("role") != "cta":
        add(len(slides) - 1, "cta", "fix", "마지막 장이 마무리(저장·팔로우) 장이 아니에요")
    return issues


def _check_report(issues, fixed_codes):
    """화면에 보일 12가지 검사 결과."""
    by = {}
    for i in issues:
        by.setdefault(i["code"], []).append(i)
    out = []
    for code, label in CHECK_LIST:
        got = by.get(code) or []
        if code == "overflow":
            state = "render"
        elif any(x["level"] == "fix" for x in got):
            state = "fail"
        elif got:
            state = "warn"
        elif code in fixed_codes:
            state = "fixed"
        else:
            state = "ok"
        msgs = list(dict.fromkeys(x["msg"] for x in got))[:5]
        out.append({"code": code, "label": label, "state": state, "msgs": msgs})
    return out


# ── 글 하나 다시 쓰기 ───────────────────────────────────────────────────────
REWRITE_MODES = {"re": "같은 뜻을 다른 표현으로 새로", "short": "더 짧고 굵게(절반 길이)",
                 "long": "조금 더 구체적으로(1.5배 이내)", "easy": "초등학생도 아는 쉬운 말로"}


def rewrite_text(text, field, mode, car, brand, note=None):
    if mode not in REWRITE_MODES:
        return {"ok": False, "why": "모르는 수정 방식이에요"}
    lim = COVER_MAX if field == "cover_title" else TITLE_MAX if field == "title" else BODY_MAX
    prompt = f"""카드뉴스 한 칸의 글을 고친다. 방식: {REWRITE_MODES[mode]}.
- 원래 글: {text}
- 카드뉴스 주제: {car.get('topic') or ''}
{_brand_lines(brand)}
- {lim}자 이내. 제목이면 핵심 한 곳을 {{중괄호}}로 감싼다. 소재에 없는 숫자·날짜를 새로 넣지 않는다.
- 결과는 text 하나."""
    out = _ai_json(prompt, {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                   note=note)
    t = str(out.get("text") or "").strip()
    if not t:
        return {"ok": False, "why": "다시 쓰지 못했어요. 잠시 뒤 다시 눌러 주세요"}
    return {"ok": True, "text": t[:220]}


def restyle_all(car, instruction, brand, note=None):
    """'AI로 전체 수정' — 같은 장 구성·종류로 문구만 지시대로 다시."""
    outline = [{"role": s["role"], "line": plain(s.get("title"))} for s in car.get("slides") or []]
    src = dict(car.get("source") or {})
    src["topic"] = car.get("topic") or ""
    src["text"] = "\n".join(" / ".join(_texts(s)) for s in car.get("slides") or [])
    opts = dict(car.get("opts") or {})
    raw = _ai_json(_build_prompt(src, outline, opts, brand, fix=["사용자 지시: " + instruction[:200]]),
                   _BUILD_SCHEMA, note=note)
    new = _assemble(src, outline, opts, raw)
    if not new["slides"]:
        return {"ok": False, "why": "전체 수정을 하지 못했어요. 잠시 뒤 다시 눌러 주세요"}
    for a, b in zip(new["slides"], car.get("slides") or []):
        a["bg"], a["layout"] = b.get("bg") or a["bg"], b.get("layout", 0)
    new["opts"], new["source"], new["topic"] = car.get("opts"), car.get("source"), car.get("topic")
    new["checks"] = _check_report(check_carousel(new, brand), [])
    return {"ok": True, "carousel": new}


# ── 배경 그림(버텍스) ───────────────────────────────────────────────────────
def asset_dir(data_dir, cid):
    d = os.path.join(data_dir, "cardnews_assets", str(int(cid)))
    os.makedirs(d, exist_ok=True)
    return d


def image_allowed(cid):
    """(허용, 막을 때 문구) — AI 장면생성(Veo)과 같은 원칙: 회원 자기 버텍스 또는 관리자(사장님 프로젝트)."""
    from shopping_shorts import vertex_route
    ok, why = vertex_route.veo_allowed(cid)
    if not ok:
        why = "배경 그림 생성은 구글 버텍스 API를 등록해야 쓸 수 있어요 — 마이페이지 › 내 키 등록"
    return ok, why


def gen_background(cid, prompt, data_dir, model=None):
    """버텍스 그림 모델(기본 제미니 lite 그림, imagen-* 도 받음)로 3:4 배경 1장 → 파일명. 실패하면 (None, 이유)."""
    from shopping_shorts import vertex_route
    ok, why = image_allowed(cid)
    if not ok:
        return None, why
    imagen = (model or IMAGE_MODEL_DEFAULT).startswith("imagen")
    # 허용은 위 image_allowed(회원 자기 버텍스 또는 관리자)가 정했다 — 클라이언트 고르기는 vertex_route 한 곳
    cl = vertex_route.veo_client(cid) if imagen else vertex_route.client(cid)
    if cl is None:
        return None, "버텍스 연결을 찾지 못했어요"
    from google.genai import types
    p = (prompt or "").strip() or "minimal clean background, soft natural light, empty space for text"
    p = p[:600] + ". Photorealistic, no text, no letters, no logos, no watermark, editorial magazine photo."
    t0 = time.monotonic()
    data, ext = None, "png"
    try:
        if imagen:
            resp = cl.models.generate_images(
                model=model or IMAGE_MODEL_DEFAULT, prompt=p,
                config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="3:4"))
            imgs = getattr(resp, "generated_images", None) or []
            data = imgs[0].image.image_bytes if imgs else None
        else:
            resp = cl.models.generate_content(
                model=model or IMAGE_MODEL_DEFAULT, contents=p,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                                   image_config=types.ImageConfig(aspect_ratio="3:4")))
            for cand in (getattr(resp, "candidates", None) or [])[:1]:
                for part in (getattr(cand.content, "parts", None) or []):
                    inl = getattr(part, "inline_data", None)
                    if inl is not None and inl.data:
                        data = inl.data
                        ext = "jpg" if "jpeg" in (inl.mime_type or "") else "png"
                        break
    except Exception as e:      # noqa: BLE001
        log.warning("cardnews.gen_background 실패(%.1fs): %r", time.monotonic() - t0, e)
        msg = str(e)
        if "PERMISSION" in msg.upper() or "403" in msg:
            return None, "버텍스 프로젝트에 이미지 생성 권한이 없어요(Vertex AI API 사용 설정 확인)"
        return None, "그림을 만들지 못했어요. 잠시 뒤 다시 눌러 주세요"
    if not data:
        return None, "그림이 비어서 왔어요(안전 필터에 걸렸을 수 있어요). 설명을 바꿔 다시 눌러 주세요"
    name = "bg_%d_%s.%s" % (int(time.time() * 1000), os.urandom(3).hex(), ext)
    with open(os.path.join(asset_dir(data_dir, cid), name), "wb") as fh:
        fh.write(data)
    log.info("cardnews.gen_background OK %.1fs %dKB", time.monotonic() - t0, len(data) // 1024)
    return name, ""


def save_upload(cid, raw, data_dir, ext):
    ext = ext.lower().lstrip(".")
    if ext not in ("png", "jpg", "jpeg", "webp"):
        return None, "PNG·JPG·WEBP만 올릴 수 있어요"
    if len(raw) > 6 * 1024 * 1024:
        return None, "6MB 이하로 올려 주세요"
    name = "up_%d_%s.%s" % (int(time.time() * 1000), os.urandom(3).hex(), "jpg" if ext == "jpeg" else ext)
    with open(os.path.join(asset_dir(data_dir, cid), name), "wb") as fh:
        fh.write(raw)
    return name, ""


def fetch_remote_image(cid, url, data_dir):
    """링크 대표 사진을 회원 폴더로 받아 둔다 — 브라우저가 카드를 이미지로 바꿀 때 남의 사이트 사진은 막히므로
    (교차 출처) 같은 주소(/api/cardnews/asset/…)로 바꿔 쓴다. 실패하면 (None, 이유)."""
    import requests
    if not re.match(r"^https://", url or ""):
        return None, "사진 주소가 올바르지 않아요"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": _UA}, stream=True)
        ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(ctype)
        if not r.ok or not ext:
            return None, "사진을 받지 못했어요"
        raw = r.raw.read(6 * 1024 * 1024 + 1, decode_content=True)
    except Exception as e:      # noqa: BLE001
        log.warning("cardnews.fetch_remote_image 실패 %s: %r", url, e)
        return None, "사진을 받지 못했어요"
    return save_upload(cid, raw, data_dir, ext)


def asset_path(data_dir, cid, name):
    """회원 자기 폴더 안의 파일만. 경로 탈출 차단."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]{4,80}", name or "") or ".." in name:
        return None
    p = os.path.join(data_dir, "cardnews_assets", str(int(cid)), name)
    return p if os.path.isfile(p) else None


# ── 자동 규칙 ─────────────────────────────────────────────────────────────
def clean_rule(d):
    d = d or {}
    days = sorted({int(x) for x in (d.get("days") or []) if str(x).isdigit() and 0 <= int(x) <= 6}) or [0, 1, 2, 3, 4]
    try:
        hour = max(0, min(23, int(d.get("hour", 9))))
    except (TypeError, ValueError):
        hour = 9
    topics = [str(t).strip()[:120] for t in (d.get("topics") or []) if str(t).strip()][:60]
    return {"name": str(d.get("name") or "자동 카드뉴스")[:40], "days": days, "hour": hour,
            "topics": topics, "purpose": d.get("purpose") if d.get("purpose") in PURPOSES else "info",
            "pack": d.get("pack") if d.get("pack") in PACKS else "editorial",
            "count": clamp_count(d.get("count") or AUTO_SLIDES), "img": "ai" if d.get("img") == "ai" else "none",
            "cursor": int(d.get("cursor") or 0)}


def next_run_at(rule, now_epoch=None):
    """다음 실행 시각(epoch). 규칙의 요일(0=월)·시(한국 시간) 중 지금 이후 가장 가까운 때."""
    now = datetime.fromtimestamp(now_epoch or time.time(), KST)
    for add in range(0, 8):
        d = (now + timedelta(days=add)).replace(hour=rule["hour"], minute=0, second=0, microsecond=0)
        if d.weekday() in rule["days"] and d > now:
            return int(d.timestamp())
    return 0


def run_rule_once(store, rule_row, data_dir):
    """자동 규칙 1회 — 다음 주제로 개요·문구를 만들어 승인 대기(pending)로 저장. 배경 그림은 승인 뒤 편집에서."""
    from shopping_shorts import keyctx
    cid, rule = rule_row["customer_id"], clean_rule(rule_row["rule"])
    if not rule["topics"]:
        return None
    topic = rule["topics"][rule["cursor"] % len(rule["topics"])]
    brand = brand_of(store, cid)
    opts = {"purpose": rule["purpose"], "pack": rule["pack"], "count": rule["count"], "img": "none"}
    src = {"kind": "topic", "topic": topic}
    with keyctx.owner(cid):
        ol = plan_outline(src, opts, brand)
        if not ol.get("ok"):
            return None
        got = build_carousel(src, ol["slides"], opts, brand)
    if not got.get("ok"):
        return None
    car = got["carousel"]
    wid = store.cardnews_save(None, cid, car, status="pending", title=topic[:60], rule_id=rule_row["rule_id"])
    rule["cursor"] += 1
    store.cardnews_rule_save(cid, rule, next_run_at(rule), rule_id=rule_row["rule_id"])
    return wid


def run_due_rules(store, data_dir, now_epoch=None):
    """시간이 된 규칙을 돈다. 여러 프로세스가 동시에 불러도 규칙 하나는 한 번만(cardnews_rule_claim)."""
    now = int(now_epoch or time.time())
    done = 0
    for r in store.cardnews_rules_due(now):
        rule = clean_rule(r["rule"])
        if not store.cardnews_rule_claim(r["rule_id"], r["next_run"], next_run_at(rule, now), now):
            continue
        try:
            if run_rule_once(store, r, data_dir):
                done += 1
        except Exception as e:      # noqa: BLE001 — 한 규칙 실패가 다른 회원 규칙을 막지 않게, 사실은 남긴다
            log.warning("cardnews 자동 규칙 %s 실패: %r", r["rule_id"], e)
    return done
