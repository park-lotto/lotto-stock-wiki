# -*- coding: utf-8 -*-
"""대본 쓰기 엔진 — 프리셋 규칙 + 역할 칸 + 소재·벤치·사실로 대본을 쓰고, 같은 자로 재고, 틀린 줄만 다시 쓴다 (관제 097, 2026-10-16).

    PYTHONUTF8=1 py tools/calcopy/engine/script_engine.py --preset channel/sseolpulda/preset/A_흰바탕창/창아래_검정 \
        --topic <out>/후보.json#c2 --bench <out>/벤치/c2.md --facts facts.json --mode captions --out <폴더>
    PYTHONUTF8=1 py tools/calcopy/engine/script_engine.py --preset yummyknow --topic 소재.json --bench 벤치.md --facts facts.json \
        --mode narration --out <폴더>

1) 규칙: 프리셋 뜯기(captions 줄·폭 / 받아쓰기 문장·cps / 존댓말 비율) + 갈래 rules.json(예문·말투) + **역할 칸**
   (--roles > manifest.roles > ROLES[slug] — 썰풀다 6칸·yummyknow 5칸·방구석 6박자). 쓴 역할 칸은 <out>/roles.json 에 남긴다.
2) 초안(LLM 1회, 무료 제미나이) — 줄마다 근거 번호(facts f* · 벤치 포인트 b*) 필수, 화면 묘사 금지, 지어낸 사실·숫자 금지, 과장 OK.
3) 검사 = style_writer.check_captions / check_narration(베낌·존댓말·숫자·말끝·묘사·톤 밖·길이) + 이 엔진의 역할 칸 채움·근거·말투 섞임·
   전체 길이(나레 초) → 틀린 줄만 다시 쓰기(최대 2회, 줄 단위).
4) 산출: 대본.json(remake.py --script 그대로: final.lines[fn,text,facts,sources] · facts{id:{text,url}} · gate.scores) ·
   대본_검사.md · 대본_계획.md(선검수: 소재 5기준·썰 각도·근거표).
판단 주인: 검사 판정 = check_script() 한 곳(아래 style_writer 검사를 부르고 합친다) · 다시 쓸 줄 고르기 = bad_lines().
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools.calcopy import style_writer as SW          # noqa: E402  검사·폭 추정·말끝·묘사 말끝은 style_writer 한 곳
from tools.calcopy.engine import topic_find as TF      # noqa: E402  프리셋 읽기·LLM 창구·5기준 이름 공용

# 채널별 역할 칸(뜯기·규칙 파일에 역할 칸이 없을 때 기본) — 근거:
#  sseolpulda = channel/sseolpulda/칼카피_ZdeZ/대본.json fns(원본 1위 6줄 역할·말끝, 10-16 통과편)
#  yummyknow  = 설계 지시(상황→반응→진짜 이유→반전→댓글 반응) · channel/yummyknow/칼카피_rGFX/대본.json final fn 5줄
#  banggu     = tools/calcopy/try_banggu_styles.py STYLES['숨은이유'] labels(제목 뺀 6칸)
ROLES = {
    "sseolpulda": ["발견 맥락(어디서 보고 알게 됐나) · 말끝 ~길래", "의심(처음엔 안 믿음) · 말끝 ~는데", "반전 시연(그냥 대기만 하면) · 말끝 ~면",
                   "결과 과장(평범한 물건이 뭐로 변함) · 말끝 ~함;;", "감탄 · 말끝 ~네", "인정·댓글유도 · 말끝 ~인정?"],
    "yummyknow": ["상황(훅 질문+무슨 일)", "반응(사람들 반응)", "진짜 이유(전언 ~다는데)", "반전", "댓글 반응(마무리)"],
    #  hottemreport = channel/hottemreport/칼카피_OE11/대본.json fns(10-16 통과편 7줄 그대로, 제품 고유 괄호만 일반화)
    "hottemreport": ["훅(의심→진짜)", "기능 1", "기능 2", "기능 3", "기능 4", "반전", "마무리"],
    "banggu": ["소개(남들이 좋아한다는 수식+제품, 명사로 끝)", "의문(사는 이유는 단순히 OO 때문이 아니라는데)", "살펴봄(특징 1~2개)",
               "꺾음(정작 꽂힌 포인트는 따로 있다는데)", "진짜 이유(그건 바로 ~)", "혼잣말(말투 바꾼 한 줄)"],
}
# 채널 기본도 없을 때의 최후 칸(경보와 함께) — 4채널 통과편 공통 뼈대(훅→전개→반전→마무리)
DEFAULT_ROLES = ["훅(질문·상황)", "전개", "반응", "반전", "마무리"]
MAX_REWRITES = 2


def pick_roles(P: dict, roles: list[str] | None = None) -> tuple[list[str], str]:
    """(판단 주인) 역할 칸 — 인자 > 프리셋 manifest.roles > ROLES[채널] > DEFAULT_ROLES. 뒤 둘은 '경보' 근거를 돌려준다.
    10-16 창고: 핫템리포트 프리셋에 roles 가 없어 script 단계가 SystemExit 로 죽었다(대본 통과 0/32의 원인 하나) → 멈추지 않고 폴백."""
    if roles:
        return list(roles), "인자"
    if P["manifest"].get("roles"):
        return list(P["manifest"]["roles"]), "프리셋 manifest.roles"
    if ROLES.get(P["slug"]):
        return list(ROLES[P["slug"]]), f"경보: 프리셋 manifest.roles 없음 → script_engine.ROLES[{P['slug']}] 채널 기본"
    return list(DEFAULT_ROLES), f"경보: 프리셋 manifest.roles·채널 기본 둘 다 없음({P['slug']}) → DEFAULT_ROLES"
# 소재 일치 검사용 브랜드·대표 제품명(10-16 실측 결함: 신라면 소재 대본이 벤치 영상 하나를 따라 '진라면 공장' 이야기가 됐는데 검사는 통과)
BRANDS = ("신라면", "진라면", "너구리", "안성탕면", "짜파게티", "불닭", "삼양라면", "열라면", "육개장", "오뚜기", "농심", "삼양", "팔도", "빙그레",
          "롯데", "해태", "오리온", "크라운", "비비고", "풀무원", "동원", "맥도날드", "버거킹", "롯데리아", "맘스터치", "스타벅스", "이디야",
          "메가커피", "컴포즈", "투썸", "다이소", "코스트코", "이케아", "이마트", "홈플러스", "트레이더스", "쿠팡", "올리브영", "무인양품",
          "세븐일레븐", "노브랜드", "교촌", "굽네", "피자헛", "도미노", "삼성", "애플", "샤오미", "아마존", "테무", "알리",
          "CU", "GS25", "KFC", "BBQ", "bhc", "CJ")
NARR_TOTAL_TOL = 0.15        # 나레 전체 글자 수 = 원본 받아쓰기 합 ±15%
BANMAL_END = r"(음|임|함|됨|짐|거|는데|다고|라고|던데|네|냐|지|야|다)[.!?~;]*$"
POLITE_END = r"(습니다|니다|어요|아요|해요|세요|에요|예요|죠|네요)[.!?~;]*$"


# ── 입력 읽기 ─────────────────────────────────────────────────────────────
def load_topic(arg: str, pick: str | None = None) -> dict:
    """'후보.json#c2' · 후보.json(--pick 또는 recommend[0]) · 소재.json({topic,…}) · 그냥 글."""
    path, _, cid = arg.partition("#")
    p = Path(path)
    if p.suffix == ".json" and p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and "candidates" in d:
            cid = cid or pick or (d.get("recommend") or [None])[0]
            c = next((c for c in d["candidates"] if c["id"] == cid), None)
            if not c:
                raise SystemExit(f"후보 {cid!r} 없음 — {[c['id'] for c in d['candidates']]}")
            return c
        if isinstance(d, dict) and d.get("topic"):
            return d
        raise SystemExit(f"소재 파일 꼴 모름: {arg}")
    return {"topic": arg}


def load_facts(path: str | None) -> dict:
    """facts.json → {id: {text, url}}. 받는 꼴: {id:{text,url}} · {id:"글"} · [{id?,text,source|url}] · {"facts":[…]}(seedflow)."""
    if not path:
        return {}
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(d, dict) and isinstance(d.get("facts"), (list, dict)):
        d = d["facts"]
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out[k] = {"text": v, "url": ""} if isinstance(v, str) else {"text": v.get("text", ""), "url": v.get("url") or v.get("source") or "",
                                                                         "date": v.get("date") or ""}
    else:
        for i, v in enumerate(d, 1):
            out[v.get("id") or f"f{i}"] = {"text": v.get("text", ""), "url": v.get("url") or v.get("source") or "", "date": v.get("date") or ""}
    return {k: v for k, v in out.items() if (v["text"] or "").strip()}


# ── 기사 대조 관문(조율자 10-16 묶음3) ─────────────────────────────────────
# 제품비하인드·식품 소재는 기사 ≥1(URL·날짜·발췌)이 facts 에 있어야 대본으로 넘어간다. 없으면 상태 facts_insufficient(이유) — LLM 을 부르지 않는다.
# 기사 통로: 네이버 뉴스 검색 API 키는 .env 에 없다(10-16 확인, 키 이름에 NAVER·NEWS 0개) → 사람이 찾은 기사를 facts 에 넣거나 topic_find.news_search(제목·URL만).
NOT_ARTICLE = ("youtube.com", "youtu.be", "instagram.com", "tiktok.com", "facebook.com", "x.com", "twitter.com", "threads.net", "rednote.com")
FOOD_WORDS = ("라면", "과자", "빵", "치킨", "버거", "음료", "커피", "아이스크림", "스프레드", "초콜릿", "우유", "피자", "떡볶이", "도시락", "식품",
              "소스", "젤리", "맥주", "소주", "김치", "햄버거", "디저트", "케이크", "쿠키")
_DATE = re.compile(r"(19|20)\d{2}[-./년 ]\s*\d{1,2}")
ARTICLE_MIN_CHARS = 20


def article_facts(facts: dict) -> list[str]:
    """기사 근거 번호 — URL 이 영상·SNS 가 아닌 http 주소 + 날짜(date 칸 또는 글 안 'YYYY-MM') + 발췌(글 ARTICLE_MIN_CHARS 자 이상)."""
    out = []
    for k, v in facts.items():
        url = (v.get("url") or "").lower()
        if not url.startswith("http") or any(d in url for d in NOT_ARTICLE):
            continue
        if not (v.get("date") or _DATE.search(v.get("text") or "")):
            continue
        if len((v.get("text") or "").replace(" ", "")) < ARTICLE_MIN_CHARS:
            continue
        out.append(k)
    return out


def article_gate(topic: dict, facts: dict, kind: str | None) -> tuple[bool, str]:
    """(판단 주인) 이 소재가 기사 대조를 요구하나 + 충족했나 → (통과, 이유)."""
    t = topic.get("topic") or ""
    food = [w for w in FOOD_WORDS if w in t]
    if kind != "제품비하인드" and not food:
        return True, f"기사 대조 대상 아님(출처 유형 {kind}, 식품 낱말 없음)"
    arts = article_facts(facts)
    why_need = f"출처 유형 {kind}" if kind == "제품비하인드" else f"식품 소재({food})"
    if arts:
        return True, f"{why_need} — 기사 근거 {arts}"
    return False, f"{why_need} — 기사 근거(영상·SNS 아닌 URL + 날짜 + 발췌 {ARTICLE_MIN_CHARS}자↑) 0개. facts 에 기사를 넣어야 대본으로 넘어간다"


ARTICLE_NEED = 2   # 자동 기사 찾기 목표 개수(조율자 10-16: 기사 2건 이상)
NOT_ARTICLE_PAGE = ("news.google.com", "search.daum.net", "search.naver.com", "bing.com/news")   # 검색·중계 페이지(기사 아님)


def find_articles(topic: dict, net: dict | None = None, need: int = ARTICLE_NEED, per_query: int = 8, log=print) -> tuple[dict, list[str]]:
    """(판단 주인) 기사 근거 자동 찾기 — 네이버 뉴스 → 다음 뉴스 → 빙 뉴스 RSS 순으로 검색(검색어 = 소재 제품명 낱말, 없으면 소재 머리),
    기사 페이지의 발췌(og:description)·날짜를 읽어 article_facts 꼴을 통과한 것만 {a1: {text, url, date}} 로 need 개까지.
    돌려주는 값 (facts, 기록). 키 없는 무료 통로만 — 실패는 기록에 남기고 빈 dict(조용한 통과 없음: 부르는 쪽이 관문을 다시 잰다)."""
    net = net or TF.NET
    head = re.split(r"\s+—\s+|\(|\s+vs\s+|\s+-\s+", topic.get("product") or topic.get("topic") or "")[0]
    q = " ".join(product_terms(topic)[:3]) or head.strip()
    found, notes, seen = {}, [], set()
    for chan in ("news_search", "daum_news_search", "bing_news_search"):   # 구글 뉴스 RSS 는 주소가 중계 페이지라 발췌가 'Google 뉴스…'로 와서 뺐다(10-16 실측)
        if len(found) >= need or chan not in net:
            continue
        try:
            rows = net[chan](q, per_query)
        except Exception as e:  # noqa: BLE001 — 통로 하나가 죽어도 다음 통로로(이유는 남긴다)
            notes.append(f"{chan}({q!r}) 실패: {type(e).__name__}: {str(e)[:80]}")
            continue
        notes.append(f"{chan}({q!r}) {len(rows)}건")
        for r in rows:
            if len(found) >= need:
                break
            url = r.get("url") or ""
            if not url.startswith("http") or url in seen or any(d in url.lower() for d in NOT_ARTICLE):
                continue
            seen.add(url)
            try:
                pg = net["article_page"](url)
            except Exception as e:  # noqa: BLE001
                notes.append(f"  읽기 실패 {url[:60]}: {type(e).__name__}")
                continue
            exc = (pg.get("excerpt") or "").strip()
            fact = {"text": f"{(pg.get('title') or r.get('title') or '').strip()} — {exc}", "url": pg.get("url") or url,
                    "date": pg.get("date") or r.get("date") or ""}
            if pg.get("url") and any(d in pg["url"].lower() for d in NOT_ARTICLE + NOT_ARTICLE_PAGE):
                continue
            if len(exc.replace(" ", "")) < ARTICLE_MIN_CHARS or not article_facts({"x": fact}):
                notes.append(f"  거름 {url[:60]}: 발췌 {len(exc)}자·날짜 {fact['date'][:10] or '없음'}")
                continue
            # 그 소재 기사인가 — 판단 주인 topic_find.relevance(벤치 영상과 같은 자). 10-16 실측: '빅맥송' 검색에 KBS 라디오 전쟁 인터뷰가 걸렸다
            rel, rwhy = TF.relevance({"title": pg.get("title") or r.get("title") or "", "description": exc}, q, topic.get("topic") or q)
            if not rel:
                notes.append(f"  관련 없음 {url[:60]}: {rwhy}")
                continue
            found[f"a{len(found) + 1}"] = fact
    notes.append(f"기사 근거 {len(found)}건(목표 {need})")
    for n_ in notes:
        log(f"[기사 찾기] {n_}")
    return found, notes


def load_bench(path: str | None) -> dict:
    """벤치 md(topic_find 가 쓴 '- [b1] (kind) 글 — from') 또는 같은 이름 .json → {b1: {text,url,kind}} + 베낌 검사용 원문."""
    if not path:
        return {"points": {}, "texts": []}
    p = Path(path)
    j = p.with_suffix(".json")
    if j.exists():
        d = json.loads(j.read_text(encoding="utf-8"))
        vids = {v["id"]: v for v in d.get("videos") or []}
        pts = {}
        for x in d.get("points") or []:
            vid = re.sub(r"^v_", "", str(x.get("from") or ""))
            pts[x["id"]] = {"text": f"({x.get('kind')}) {x['text']}", "url": (vids.get(vid) or {}).get("url", ""), "kind": x.get("kind")}
        texts = [v.get("title") or "" for v in vids.values()] + [c["text"] for v in vids.values() for c in v.get("comments", [])[:20]]
        return {"points": pts, "texts": texts}
    pts = {}
    for m in re.finditer(r"^- \[(b\d+)\]\s*(.+)$", p.read_text(encoding="utf-8"), re.M):
        pts[m.group(1)] = {"text": m.group(2).strip(), "url": "", "kind": None}
    return {"points": pts, "texts": []}


CH_LEN_TOL = 0.20   # 채널 길이 = 벤치(채널 편들) 받아쓰기 글자 수 중앙값 ±20%(조율자 10-16: 311자=35초 초과 실례)


def channel_length(P: dict, R: dict, one: int) -> tuple[tuple[int, int], str]:
    """나레 전체 글자 범위(판단 주인). ① 채널 뜯기 편들(channel/<slug>/뜯기/*/뜯기.json) 받아쓰기 합의 중앙값 ±20% (3편 이상)
    ② 갈래 rules.json length_chars 중앙값 ±20% ③ 프리셋 원본 1편 ±15%."""
    totals = []
    for f in sorted((P["chdir"] / "뜯기").glob("*/뜯기.json")):
        try:
            tr = (json.loads(f.read_text(encoding="utf-8")).get("audio") or {}).get("transcript") or []
        except (OSError, ValueError):
            continue
        tr = tr.get("segments") or [] if isinstance(tr, dict) else tr
        n = sum(len((t.get("text") or "").replace(" ", "")) for t in tr if isinstance(t, dict) and t.get("lang", "ko") == "ko")
        if n:
            totals.append(n)
    if len(totals) >= 3:
        m = st.median(totals)
        return (int(m * (1 - CH_LEN_TOL)), int(m * (1 + CH_LEN_TOL)) + 1), f"채널 뜯기 {len(totals)}편 받아쓰기 중앙 {m}자 ±20%"
    med = (R.get("length_chars") or {}).get("median")
    if med:
        return (int(med * (1 - CH_LEN_TOL)), int(med * (1 + CH_LEN_TOL)) + 1), f"rules.json length_chars 중앙 {med}자 ±20%"
    return (int(one * (1 - NARR_TOTAL_TOL)), int(one * (1 + NARR_TOTAL_TOL)) + 1), f"프리셋 원본 1편 {one}자 ±15%"


def skeleton(P: dict, mode: str | None, roles: list[str] | None) -> dict:
    """프리셋 → 칸 목록과 길이 규칙. 판단 주인: 줄 길이 범위는 style_writer.line_ranges/_cap_range, 나레 전체는 원본 받아쓰기 합 ±15%."""
    J = json.loads(Path(P["tteutgi"]).read_text(encoding="utf-8")) if P.get("tteutgi") else {}
    R = json.loads(Path(P["rules"]).read_text(encoding="utf-8")) if P.get("rules") else {}
    vr = J.get("voice_rules") or {}
    mode = mode or ("captions" if vr.get("narration") == "none" else "narration")
    roles, roles_basis = pick_roles(P, roles)
    n = len(roles)
    polite_ratio = (J.get("script_tone") or {}).get("polite_ratio")
    honor = "존댓말" if (polite_ratio or 0) > 0.5 else "반말"
    sk = {"mode": mode, "roles": roles, "ends": SW.ends_of(roles), "honorific": honor, "rules": R, "tteutgi": P.get("tteutgi"),
          "width": None, "total": None, "cps": vr.get("cps") or (SW.CPS if mode == "narration" else None), "roles_basis": roles_basis}
    if mode == "captions":
        items = {i["i"]: i for i in (J.get("captions") or {}).get("items") or []}
        orig = [" ".join(items[k].get("text") or []) for k in sorted(items)]
        if len(orig) == n:
            widths = [(items[k].get("widths") or [None])[0] for k in sorted(items)]
            sk["ranges"] = SW.line_ranges(orig)
            if P.get("frame") and all(widths):
                try:
                    est = SW.width_estimator(P["frame"])
                    sk["width"] = {"est": est, "orig": widths}
                    # 판정이 폭(px)이면 쓰라고 주는 글자 수도 폭에서 — 원본 글자 수로 주면 '바이럴인 줄 알았는데...'(점 3개 = 좁음) 칸에
                    # 12자를 쓰고 폭 686 vs 546px 로 반려됐다(10-16 창고 sseolpulda 13~16 넷 다 2번 줄). 한 글자 폭 = 공백 섞인 한글 표본.
                    sample = "가나다 라마바 사아자 차카타"
                    ppc = est(sample) / len(sample.replace(" ", ""))
                    sk["ranges"] = SW.line_ranges(orig, widths, ppc)
                    sk["px_per_char"] = round(ppc, 1)
                except Exception as e:  # noqa: BLE001 — 폭 추정 못 하면 글자 수 기준으로(이유는 남긴다)
                    sk["width_failed"] = f"{type(e).__name__}: {str(e)[:100]}"
        else:   # 원본 줄 수와 역할 칸 수가 다르면 원본 줄 길이 중앙 ±30%
            m = st.median([len(t.replace(" ", "")) for t in orig]) if orig else 12
            sk["ranges"] = [(max(4, int(m * 0.7)), int(m * 1.3) + 1)] * n
        sk["orig"] = orig
    else:
        tr = (J.get("audio") or {}).get("transcript") or []
        tr = tr.get("segments") or [] if isinstance(tr, dict) else tr
        orig = [t["text"].strip() for t in tr if isinstance(t, dict) and t.get("lang", "ko") == "ko"]
        T = sum(len(t.replace(" ", "")) for t in orig) or (R.get("length_chars") or {}).get("median") or 200
        sk["total"], sk["total_basis"] = channel_length(P, R, T)
        per = T / n
        sk["ranges"] = [(max(6, int(per * 0.4)), int(per * 2.0) + 1)] * n   # 줄은 느슨하게 — 판정은 전체 길이
        sk["orig"] = orig
    return sk


# ── 프롬프트 ──────────────────────────────────────────────────────────────
# 규칙 문장의 주인 = style_writer(0순위-B, 10-16 커밋 71bd08ac2) — 여기선 가져다 쓰기만(test_calcopy_prompt_owner 가 동일성을 지킨다).
# 소재 이탈 금지 문장은 아직 SW 에 없다(요청) — 지금은 check_script 의 topic_match 가 잡고 FIX 단계에서 '빼야 할 이름'을 준다.
DRAFT_PROMPT = SW.DRAFT_PROMPT
FIX_PROMPT = SW.FIX_PROMPT


def _grounds(facts: dict, bench: dict) -> str:
    rows = [f"[{k}] (사실) {v['text']}" + (f" — {v['url']}" if v.get("url") else "") for k, v in facts.items()]
    rows += [f"[{k}] (벤치 포인트) {v['text']}" for k, v in bench["points"].items()]
    return "\n".join(rows) or "(없음)"


def _slots(sk: dict) -> str:
    out = []
    for k, r in enumerate(sk["roles"]):
        lo, hi = sk["ranges"][k]
        out.append(f"{k + 1}. 역할={r} · {lo}~{hi}자" + (f" · 화면 폭 약 {sk['width']['orig'][k]}px" if sk.get("width") else ""))
    if sk.get("total"):
        out.append(f"(전체 {sk['total'][0]}~{sk['total'][1]}자 ≈ {round(sum(sk['total']) / 2 / (sk['cps'] or SW.CPS), 1)}초)")
    return "\n".join(out)


# ── 검사(판단 주인) ────────────────────────────────────────────────────────
def _role_name(r: str) -> str:
    return re.split(r"[(·]", r)[0].strip()


def _brands_in(text: str) -> set:
    t = text or ""
    return {b for b in BRANDS if (re.search(rf"(?<![A-Za-z]){re.escape(b)}(?![A-Za-z])", t, re.I) if b.isascii() else b in t)}


def product_terms(topic: dict) -> list[str]:
    """소재 제품명 낱말 — topic.product 가 있으면 그것, 없으면 소재 글 머리(' — '·'('·' vs ' 앞)의 핵심 낱말."""
    head = topic.get("product") or re.split(r"\s+—\s+|\(|\s+vs\s+|\s+-\s+", topic.get("topic") or "")[0]
    return TF.core_terms(head)


def topic_match(texts: list[str], topic: dict, facts: dict, mode: str) -> dict:
    """소재 일치(판단 주인): ① 소재·사실(f*)에 없는 브랜드명이 줄에 나오면 그 줄 실패 ② 나레 꼴(또는 topic.product 지정)이면
    소재 제품명 낱말이 대본 어딘가에 1회 이상. 자막 꼴은 화면이 제품을 보여 줘 이름을 안 부르는 게 채널 꼴(ZdeZ·LED 수도꼭지) — ②는 경고만."""
    allowed = _brands_in(topic.get("topic") or "") | _brands_in(topic.get("product") or "") | _brands_in(" ".join(v["text"] for v in facts.values()))
    other = {k: sorted(_brands_in(t) - allowed) for k, t in enumerate(texts)}
    other = {k: v for k, v in other.items() if v}
    terms = product_terms(topic)
    flat = re.sub(r"\s+", "", " ".join(texts)).lower()
    named = [w for w in terms if w in flat]
    required = mode == "narration" or bool(topic.get("product"))
    return {"other_brand": other, "product_terms": terms, "product_named": named,
            "product_missing": bool(terms) and not named and required, "product_warn": bool(terms) and not named and not required}


_RANGE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:~|∼|〜|–|-|에서)\s*(\d+(?:[.,]\d+)?)")
HEARSAY = ("댓글", "반응", "라는", "다는", "라며", "이라며", "냐는", "얘기", "후기", "평이")   # "팬들 사이에서 …취급"은 전언이 아니라 단정(리센느 실례) — 넣지 않는다
# 근거 없으면 못 쓰는 단정형 과장(10-16 리센느 '전설의 포켓몬 취급'·'극락 간다는'). 감탄(미쳤네·소름)은 채널 말투라 빼지 않는다.
OPINION_ROLES = ("감탄", "인정", "댓글유도", "혼잣말", "의심")   # 화자 자신의 감상 칸 — 사실 주장이 아니라 전언 표식 대상 아님(최상급·단정 검사는 그대로)


def number_ranges(lines_text: list[str], facts: dict) -> dict:
    """(4) 근거 글의 범위(a~b)를 대본이 한쪽 값으로만 쓰면 그 줄 실패 — '6~8배'를 '8배'로(10-16 바나나 편)."""
    ft = " ".join(v["text"] for v in facts.values())
    ends = {}
    for a, b in _RANGE.findall(ft):
        ends.setdefault(a, f"{a}~{b}")
        ends.setdefault(b, f"{a}~{b}")
    alone = _RANGE.sub(" ", ft)
    out = {}
    for k, t in enumerate(lines_text):
        if _RANGE.search(t):
            continue
        hit = [ends[x] for x in re.findall(r"\d+(?:[.,]\d+)?", t)
               if x in ends and not re.search(r"(?<![\d.,])" + re.escape(x) + r"(?![\d.,])", alone)]
        if hit:
            out[k] = hit
    return out


def comment_facts(facts: dict, bench: dict) -> set:
    """댓글·반응 근거 번호 — c* 번호, 글에 '댓글'이 든 사실, 벤치 반응 포인트."""
    ids = {k for k, v in facts.items() if k.startswith("c") or "댓글" in (v.get("text") or "")[:20]}   # 글 머리가 댓글인 근거만(관찰 뒤에 댓글을 덧붙인 근거는 사실)
    return ids | {k for k, v in bench["points"].items() if v.get("kind") == "reaction" or "댓글" in (v.get("text") or "")}


def comment_as_fact(lines: list[dict], facts: dict, bench: dict, roles: list[str] | None = None) -> dict:
    """(5) 댓글을 사실로 승격 금지: 근거가 전부 댓글·반응이면 그 줄에 전언 표식('댓글에선·~라는 반응')이 있어야 한다.
    (근거 없는 과장·최상급은 claim_off 한 곳 — 여기서 다시 재지 않는다)"""
    cids = comment_facts(facts, bench)
    out = {}
    for k, l in enumerate(lines):
        t, ids = l.get("text") or "", set(l.get("facts") or [])
        opinion = any(o in ((roles or [""] * len(lines))[k] if k < len(roles or []) else "") for o in OPINION_ROLES)
        if ids and ids <= cids and not opinion and not any(h in t for h in HEARSAY):
            out[k] = ["댓글을 사실처럼(전언 표식 없음)"]
    return out


SPACE_MIN_CHARS = 8       # 한글이 이보다 적은 줄은 재지 않는다('두 가지' 등)
SPACE_RUN_MAX = 9         # 띄어쓰기 없이 이어진 한글이 이보다 길면 지운 것(4채널 원본 줄 최장 어절 4~6자, 10-16 실측)
SPACE_MEAN_MULT = 1.6     # 줄의 한글 어절 평균 길이 > 원문 평균 × 이것(최소 SPACE_MEAN_MIN)이면 지운 것
SPACE_MEAN_MIN = 4.5      #   실측(10-16): 원문 2.7~3.5 · 통과 손 대본 2.5~3.5 · 지운 줄 6.5('숨어있던호스 샤워기로변신함')~10
_HANGUL_RUN = re.compile(r"[가-힣]+")
# ★1판(공백 비율)은 숫자·영문이 든 줄을 잘못 잡았다(10-16 창고 sseolpulda/14 '8,262,695회나 조회됐길래' 0.06) → 한글 어절 길이로만 잰다


def _mean_run(t: str) -> float | None:
    r = [len(x) for x in _HANGUL_RUN.findall(t or "")]
    return sum(r) / len(r) if r else None


def spacing_base(facts: dict, orig: list[str] | None = None) -> tuple[float, str]:
    """띄어쓰기 기준 = 한글 어절 평균 길이 — ① 원문(채널 원본 줄, 8자↑ 3줄 이상) 평균 ② 한글 위주 근거 글 평균 ③ 3.0."""
    o = [m for m in (_mean_run(t) for t in (orig or []) if len(t.strip()) >= SPACE_MIN_CHARS) if m]
    if len(o) >= 3:
        return sum(o) / len(o), f"원문 {len(o)}줄"
    ko = [m for m in (_mean_run(v["text"]) for v in facts.values()
                      if len("".join(_HANGUL_RUN.findall(v["text"]))) >= max(10, len(v["text"]) * 0.5)) if m]
    if ko:
        return sum(ko) / len(ko), f"한글 근거 {len(ko)}개"
    return 3.0, "기본값"


def spacing_off(texts: list[str], facts: dict, orig: list[str] | None = None) -> dict:
    """(묶음4·판단 주인) 띄어쓰기 지움 — ① 띄어쓰기 없는 한글 덩어리 > SPACE_RUN_MAX 자 ② 한글 어절 평균 길이 > 기준(spacing_base) × SPACE_MEAN_MULT."""
    base, basis = spacing_base(facts, orig)
    lim = max(SPACE_MEAN_MIN, base * SPACE_MEAN_MULT)
    out = {}
    for k, t in enumerate(texts):
        core = (t or "").strip()
        if len("".join(_HANGUL_RUN.findall(core))) < SPACE_MIN_CHARS:
            continue
        run = max((len(m) for m in _HANGUL_RUN.findall(core)), default=0)
        mean = _mean_run(core) or 0
        if run > SPACE_RUN_MAX:
            out[k] = f"띄어쓰기 없는 {run}자 덩어리(>{SPACE_RUN_MAX})"
        elif mean > lim:
            out[k] = f"한글 어절 평균 {mean:.1f}자 > {basis} 평균 {base:.1f}×{SPACE_MEAN_MULT}"
    return out


# 최상급·단정 무리(판단 주인 claim_off 한 곳) — 같은 무리 낱말이 그 줄의 근거 글에 있어야 쓸 수 있다. 영어 근거는 무리별 영어 표현으로.
# 감탄(미쳤네·소름)·'난리'(반응 묘사, LED 손 대본 '…라고 난리길래')는 채널 말투라 넣지 않는다.
CLAIM_GROUPS = {
    "가장": (("가장", "제일", "최고"), r"\b(\w+est|most|best)\b"),
    "최초": (("최초", "처음으로"), r"\bfirst\b"),
    "유일": (("유일",), r"\bonly\b"),
    "세계": (("세계에서", "세상에서", "전세계", "전 세계"), r"\bworld'?s?\b"),
    "절대": (("절대",), r"\b(never|absolutely)\b"),
    "역대": (("역대급", "역대"), r"\b(ever|all-time|record)\b"),
    "1위": (("1위", "1등", "일등"), r"(#1|\bnumber one\b|\bno\.? ?1\b)"),
    "전설": (("전설",), r"\blegend"),
    "국민": (("국민",), r"\bnational\b"),
    "대란": (("대란", "품절"), r"\bsold[ -]?out\b"),
    "극락": (("극락",), None),
    "끝판왕": (("끝판왕",), None),
    "신드롬": (("신드롬",), r"\bsyndrome\b"),
}


def claim_off(lines: list[dict], facts: dict, bench: dict) -> dict:
    """(묶음4·판단 주인) 최상급·단정(가장·최초·유일·세계에서·절대·역대급·1위·전설·극락…) — 그 줄이 기댄 근거 글(f*·b*)에
    같은 무리의 주장(한글 낱말 또는 무리별 영어 표현)이 없으면 실패. 돌려주는 값 {줄: [걸린 낱말]}."""
    allf = {**facts, **bench["points"]}
    out = {}
    for k, l in enumerate(lines):
        t = l.get("text") or ""
        src = " ".join((allf.get(i) or {}).get("text", "") for i in (l.get("facts") or []))
        miss = []
        for words, en in CLAIM_GROUPS.values():
            hit = next((w for w in words if w in t), None)
            if hit and not (any(w in src for w in words) or (en and re.search(en, src, re.I))):
                miss.append(hit)
        if miss:
            out[k] = miss
    return out


SUPPORT_PROMPT = """아래 대본 줄마다, 그 줄이 기댄 **근거 글**이 그 문장의 사실 내용을 뒷받침하는지 판정해라.
- 근거에 없는 행동·경고·인용·이유·숫자를 지어 붙였으면 아니오(예: 근거는 '228만 원 썼다는 댓글'인데 줄은 '절대 먹지 말라고 경고'면 아니오).
- 꾸밈 말투·감탄(미쳤다·대박)은 사실이 아니니 따지지 마라. 주장된 사실만 본다.
- [감상 칸] 표시 줄은 화자 자신의 느낌·첫인상(의심했는데·싶었는데·인정?)이다 — 그 느낌은 따지지 말고 그 안에 든 사실 주장만 본다.
- 근거의 주장(회사·댓글 주장)을 단정 사실처럼 바꿨으면 아니오.
출력 JSON만: {{"items":[{{"i":번호,"ok":"예|아니오","why":"한 줄"}}]}}

{rows}"""


def support_check(lines: list[dict], facts: dict, bench: dict, llm, roles: list[str] | None = None) -> tuple[dict | None, str | None]:
    """(묶음4) 줄↔근거 일치 — 제미나이 1회 묶음. 돌려주는 값 {줄: 이유}(아니오인 줄). 판정 실패면 (None, 이유) — 부르는 쪽이 통과시키지 않는다.
    감상 칸(OPINION_ROLES)은 [감상 칸] 표시 — 10-16 창고 sseolpulda/13 '과장 광고 아닐까 의심했는데'(의심 칸)를 '근거에 의심 없음'으로 반려한 오탐."""
    allf = {**facts, **bench["points"]}
    rows = []
    for k, l in enumerate(lines):
        src = " / ".join(f"[{i}] {(allf.get(i) or {}).get('text', '(없는 번호)')}" for i in (l.get("facts") or [])) or "(근거 없음)"
        role = (roles or [])[k] if k < len(roles or []) else ""
        tag = " [감상 칸]" if any(o in role for o in OPINION_ROLES) else ""
        rows.append(f"{k + 1}. 줄{tag}: {l.get('text')}\n   근거: {src}")
    d, err = llm(SUPPORT_PROMPT.format(rows="\n".join(rows)), "support")
    if not d:
        return None, f"줄↔근거 판정 LLM 실패: {err}"
    out, seen = {}, set()
    for it in d.get("items") or []:
        try:
            k = int(it.get("i")) - 1
        except (TypeError, ValueError):
            continue
        seen.add(k)
        if not str(it.get("ok", "")).strip().startswith("예"):
            out[k] = (it.get("why") or "근거가 뒷받침 안 함").strip()
    for k in range(len(lines)):
        if k not in seen:
            out[k] = "판정 답 없음"
    return out, None


def _banggu_lint(lines: list[dict], sk: dict, facts: dict, title):
    """방구석 채널 린터(주인 = shopping_shorts/channel_presets/banggu/rules.lint)를 부른다 — 판정을 여기 다시 적지 않는다."""
    from shopping_shorts.channel_presets.banggu import rules as BR
    last_is_comment = bool(sk["roles"]) and "혼잣말" in sk["roles"][-1]
    body_lines = lines[:-1] if last_is_comment and lines else lines
    script = {"kind": "hidden", "title": title or "", "lines": [{"role": _role_name(r), "text": l.get("text") or ""} for r, l in zip(sk["roles"], body_lines)],
              "comment": (lines[-1].get("text") or "") if last_is_comment and lines else ""}
    issues = BR.rejects(BR.lint(script, {"source_text": " ".join(v["text"] for v in facts.values())}))
    return issues, (len(lines) - 1 if last_is_comment and lines else None)


CHANNEL_LINTERS = {"banggu": _banggu_lint}   # 채널 rules.lint 가 있는 곳만 — 새 채널은 여기 이름만 잇는다


def channel_lint(slug, lines: list[dict], sk: dict, facts: dict, title) -> dict:
    """(6) 채널 린터 결과를 줄 번호로: 'lines[-1]' → 마지막 본문 줄, 'comment' → 혼잣말 줄, found 글이 든 줄, 나머지(제목·길이·문장 수) → 전체."""
    fn = CHANNEL_LINTERS.get(slug)
    if not fn:
        return {"linter": None, "by_line": {}, "global": []}
    issues, comment_i = fn(lines, sk, facts, title)
    by, glob = {}, []
    body_n = comment_i if comment_i is not None else len(lines)
    for i in issues:
        msg = f"채널 규칙 {i.rule}: {i.why}"
        k = None
        if i.where == "lines[-1]":
            k = body_n - 1
        elif i.where == "comment" and comment_i is not None:
            k = comment_i
        elif i.found and i.rule not in ("bg_length", "bg_lines"):
            k = next((j for j, l in enumerate(lines) if i.found in (l.get("text") or "")), None)
        if k is None:
            glob.append(msg)
        else:
            by.setdefault(k, []).append(msg)
    return {"linter": f"{slug}.rules.lint", "by_line": by, "global": glob}


def check_script(lines: list[dict], sk: dict, facts: dict, bench: dict, free_roles: tuple = (), topic: dict | None = None,
                 slug: str | None = None, title: str | None = None, support: dict | None = None) -> dict:
    """한 곳에서 판정 — style_writer 검사 + 역할 칸·근거·말투 섞임·전체 길이·소재 일치. 줄 번호는 0부터."""
    n = len(sk["roles"])
    R = sk["rules"] or {"examples": []}
    R.setdefault("examples", [])
    ids = set(facts) | set(bench["points"])
    facts_text = " ".join(v["text"] for v in facts.values())
    texts = [l.get("text") or "" for l in lines]
    # 역할 칸: 줄 수 + 줄마다 그 칸 역할 이름으로 시작하는 fn
    role_missing = [k for k in range(n) if k >= len(lines) or _role_name(sk["roles"][k]) not in (lines[k].get("fn") or "")]
    extra_lines = list(range(n, len(lines)))
    base_lines = (lines + [{"fn": "", "text": ""}] * n)[:n]
    if sk["mode"] == "captions":
        base = SW.check_captions(base_lines, sk["orig"] if len(sk["orig"]) == n else [""] * n, R, sk["ranges"], sk.get("width"), sk["ends"])
        len_off = base["len_off_lines"]
        copied = base["copied_lines"] if len(sk["orig"]) == n else []
        describe, ending_off = base["describe_lines"], base["ending_off"]
    else:
        fstr = " ".join(f"[{k}] {v['text']}" for k, v in {**facts, **bench["points"]}.items())
        base = SW.check_narration(base_lines, sk["orig"] if len(sk["orig"]) == n else [""] * n, sk["ranges"], fstr)
        len_off, copied = base["len_off_lines"], base["copied_lines"]
        describe = [k for k, t in enumerate(texts[:n]) if t.rstrip("?!.;~ ").endswith(SW.DESCRIBE_ENDS)]
        ending_off = [k for k, (t, e) in enumerate(zip(texts[:n], sk["ends"])) if e and not SW._core(t).endswith(SW._core(e))]
        if len(sk["orig"]) != n:   # 원본 문장 수가 칸 수와 다르면 베낌은 원본 전체와 8글자 겹침으로
            copied = sorted(SW.copied_from(texts[:n], sk["orig"]))
    # 벤치 영상 제목·댓글과 8글자 겹침(포인트는 가져오되 문장은 베끼지 않는다)
    copied_bench = sorted(SW.copied_from(texts[:n], bench.get("texts") or []))   # 베낌 판정 주인 = style_writer.copied_from
    # 근거: 줄마다 알려진 번호 1개 이상(free_roles 칸만 예외)
    no_ground = [k for k, l in enumerate(lines[:n]) if not (set(l.get("facts") or []) & ids)
                 and not any(fr and fr in (sk["roles"][k] if k < n else "") for fr in free_roles)]
    unknown_ids = sorted({i for l in lines for i in (l.get("facts") or []) if i not in ids})
    # 숫자: [f…] 사실 글에 있는 숫자만(벤치 포인트 숫자는 남의 영상 주장 — 사실 조사 전엔 못 쓴다)
    num_lines = [k for k, t in enumerate(texts[:n]) if any(x not in facts_text for x in re.findall(r"\d[\d,.]*", t))]
    # 말투: 채널이 반말이면 존댓말 줄, 존댓말이면 반말 줄
    if sk["honorific"] == "반말":
        tone_off = [k for k, t in enumerate(texts[:n]) if re.search(POLITE_END, t.strip()) or re.search(r"(습니다|어요|아요|해요|세요)\s", t)]
    else:
        tone_off = [k for k, t in enumerate(texts[:n]) if re.search(BANMAL_END, t.strip()) and not re.search(POLITE_END, t.strip())]
    off_tone_words = [k for k, t in enumerate(texts[:n]) if any(w in t for w in SW.OFF_TONE)]
    total_off = None
    chars = [len(t.replace(" ", "")) for t in texts[:n]]
    if sk.get("total"):
        tot = sum(chars)
        if not (sk["total"][0] <= tot <= sk["total"][1]):
            total_off = {"chars": tot, "range": list(sk["total"]), "fix_line": (max if tot > sk["total"][1] else min)(range(len(chars)), key=lambda k: chars[k]) if chars else None}
    tm = topic_match(texts[:n], topic or {}, facts, sk["mode"]) if topic else {"other_brand": {}, "product_missing": False}
    rng = number_ranges(texts[:n], facts)
    spc = spacing_off(texts[:n], facts, sk.get("orig"))
    sup = claim_off(lines[:n], facts, bench)
    unsup = support or {}
    cmt = comment_as_fact(lines[:n], facts, bench, sk["roles"])
    cl = channel_lint(slug, lines[:n], sk, facts, title) if slug else {"linter": None, "by_line": {}, "global": []}
    per_line = {"spacing_off": sorted(spc), "superlative": sorted(sup), "unsupported": sorted(unsup), "range_as_single": sorted(rng), "comment_as_fact": sorted(cmt), "channel_lint": sorted(cl["by_line"]),
                "off_topic_brand": sorted(tm["other_brand"]), "product_missing": [0] if tm["product_missing"] else [], "role_missing": role_missing, "no_ground": no_ground, "len_off": len_off, "copied_orig": copied, "copied_bench": copied_bench,
                "describe": describe, "ending_off": ending_off, "numbers_unsourced": num_lines, "tone_off": tone_off, "off_tone_words": off_tone_words}
    chk = {**per_line, "n_lines": len(lines), "n_roles": n, "extra_lines": extra_lines, "unknown_ids": unknown_ids, "total_off": total_off,
           "chars": chars, "ranges": [list(r) for r in sk["ranges"]], "sec_est": round(sum(chars) / sk["cps"], 1) if sk.get("cps") else None,
           "est_px": base.get("est_px"), "orig_px": base.get("orig_px"), "width_median_pct": base.get("width_median_pct"),
           "copied_8grams_vs_examples": base.get("copied_8grams_vs_examples"), "topic_match": tm,
           "spacing_hit": spc, "superlative_hit": sup, "support_hit": unsup, "support_checked": support is not None,
           "ranges_hit": rng, "comment_hit": cmt, "channel_lint_detail": cl, "total_basis": sk.get("total_basis")}
    chk["bad"] = bad_lines(chk)
    chk["ok"] = not chk["bad"] and not extra_lines and not unknown_ids and not total_off and len(lines) == n and not cl["global"]
    return chk


def bad_lines(chk: dict) -> dict:
    """다시 쓸 줄 → 이유 목록(판단 주인). 전체 길이 어긋남은 가장 긴/짧은 줄에 붙인다."""
    why = {}
    names = {"spacing_off": "띄어쓰기 지움", "superlative": "근거 없는 최상급·단정", "unsupported": "근거가 문장을 뒷받침 안 함",
             "range_as_single": "근거의 범위를 한쪽 값으로 단정", "comment_as_fact": "댓글 승격", "channel_lint": "채널 규칙 반려",
             "off_topic_brand": "소재 밖 브랜드명(소재 이탈)", "product_missing": "소재 제품명이 대본에 없음", "role_missing": "칸 역할 빠짐/어긋남", "no_ground": "근거 번호 없음", "len_off": "글자 수·폭 범위 밖", "copied_orig": "원본과 겹침",
             "copied_bench": "벤치 영상 문장과 겹침", "describe": "화면 묘사", "ending_off": "정해진 말끝으로 안 끝남",
             "numbers_unsourced": "사실에 없는 숫자", "tone_off": "말투 섞임(채널 말투 밖)", "off_tone_words": "톤 밖 낱말",
             "ungrounded": "근거 필수 줄(제품 속성·효과·반응·가격)에 근거 번호 없음", "copied_examples": "예문과 7자 이상 겹침"}
    detail = {"spacing_off": chk.get("spacing_hit") or {}, "superlative": chk.get("superlative_hit") or {}, "unsupported": chk.get("support_hit") or {},
              "range_as_single": chk.get("ranges_hit") or {}, "comment_as_fact": chk.get("comment_hit") or {},
              "channel_lint": (chk.get("channel_lint_detail") or {}).get("by_line") or {},
              "copied_examples": chk.get("copy7_hit") or {}, "ungrounded": chk.get("ungrounded_hit") or {}}
    for key, label in names.items():
        for k in chk.get(key) or []:
            d = detail.get(key, {}).get(k)
            why.setdefault(k, []).append(label + (f" {d}" if d else ""))
    t = chk.get("total_off")
    if t and t.get("fix_line") is not None:
        why.setdefault(t["fix_line"], []).append(f"전체 {t['chars']}자 → {t['range'][0]}~{t['range'][1]}자")
    return dict(sorted(why.items()))


# ── 쓰기 ─────────────────────────────────────────────────────────────────
def _merge(lines: list[dict], fixed: list[dict], n: int) -> list[dict]:
    out = [dict(l) for l in (lines + [{"fn": "", "text": "", "facts": []}] * n)[:n]]
    for f in fixed:
        try:
            i = int(f.get("i")) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < n and (f.get("text") or "").strip():
            out[i] = {"fn": f.get("fn") or out[i].get("fn"), "text": f["text"].strip(), "facts": f.get("facts") or []}
    return out


def write(P: dict, topic: dict, facts: dict, bench: dict, sk: dict, llm, free_roles: tuple = (), log=print) -> dict:
    honor_rule = ("존댓말(습니다·어요·해요·세요) 0 — 반말 음슴체·전언체(~임/~함/~는데/~다고 함)." if sk["honorific"] == "반말"
                  else "반말 섞지 마라 — 끝까지 존댓말.")
    prompt = DRAFT_PROMPT.format(slug=P["slug"], kind="자막" if sk["mode"] == "captions" else "나레이션", topic=topic.get("topic"),
                                 angle=topic.get("angle") or "-", grounds=_grounds(facts, bench), n=len(sk["roles"]), slots=_slots(sk),
                                 honor=sk["honorific"], honor_rule=honor_rule, orig="\n".join(f"- {t}" for t in sk["orig"][:12]) or "(없음)")
    tries = []
    d, err = llm(prompt, "draft")
    if not d:
        return {"error": f"초안 LLM 실패: {err}", "tries": [{"error": err}], "prompt": prompt}
    lines = [l for l in d.get("lines") or d.get("items") or [] if isinstance(l, dict)]
    meta = {k: d.get(k) for k in ("angle", "twist", "title")}

    def judge(ls):
        """줄↔근거 판정(LLM 1회)을 결정 검사와 같은 판에 매번 — 다른 검사에 걸린 줄도 근거 어긋남을 같이 고쳐 쓰게(10-16 다이소 c3:
        '절대 먹지 말라고 경고' 줄이 댓글 승격에 먼저 걸려 근거 판정을 못 받았다). 판정 실패는 통과로 치지 않는다(조용한 통과 금지)."""
        sup, serr = support_check(ls[:len(sk["roles"])], facts, bench, llm, sk["roles"])
        c = check_script(ls, sk, facts, bench, free_roles, topic, P["slug"], meta.get("title"), support=sup)
        if sup is None:
            c["ok"], c["support_error"] = False, serr
        return c
    chk = judge(lines)
    tries.append({"lines": lines, "check": chk, "model": d.get("_model")})
    log(f"[초안] {len(lines)}줄 · 다시 쓸 줄 {list(chk['bad'])}")
    for r in range(MAX_REWRITES):
        if chk["ok"] or chk.get("support_error"):
            break
        bad = chk["bad"] or {k: ["칸 수 맞추기"] for k in range(len(sk["roles"])) if k >= len(lines)}
        fixes = []
        for k, why in bad.items():
            lo, hi = sk["ranges"][k] if k < len(sk["ranges"]) else (0, 0)
            ob = (chk.get("topic_match") or {}).get("other_brand", {}).get(k)
            fixes.append(f"{k + 1}번 칸(역할 {sk['roles'][k] if k < len(sk['roles']) else '-'}) — {', '.join(why)}" + (f"(빼야 할 이름: {ob})" if ob else "")
                         + (f"(소재 제품명 {chk['topic_match']['product_terms']} 를 넣어라)" if "소재 제품명이 대본에 없음" in why else "") + f" · 목표 {lo}~{hi}자")
        if chk["unknown_ids"]:
            fixes.append(f"없는 근거 번호 {chk['unknown_ids']} → 위 목록 번호만")
        fixes += [f"전체 — {m}" for m in (chk.get("channel_lint_detail") or {}).get("global") or []]
        cur = _merge(lines, [], len(sk["roles"]))
        d2, err = llm(prompt + "\n\n" + FIX_PROMPT.format(lines=json.dumps([{"i": i + 1, **l} for i, l in enumerate(cur)], ensure_ascii=False),
                                                         fixes="\n".join(fixes), honor=sk["honorific"]), f"rewrite{r + 1}")
        if not d2:
            tries.append({"error": err, "round": r + 1})
            log(f"[다시 쓰기 {r + 1}] LLM 실패 {err} — 멈춤")
            break
        lines = _merge(cur, d2.get("lines") or d2.get("items") or [], len(sk["roles"]))
        chk = judge(lines)
        tries.append({"lines": lines, "check": chk, "model": d2.get("_model"), "round": r + 1, "asked": list(bad)})
        log(f"[다시 쓰기 {r + 1}] 남은 줄 {list(chk['bad'])}")
    return {"lines": lines, "check": chk, "tries": tries, "meta": meta}


# ── 대본 설명서 경로(3판, 관제 097 10-16 밤) — 설명서 있는 채널은 brief() 로 쓰고, 없으면 ROLES 폴백(경보) ──────────
# 판단 주인: 생성 = draft · 검사 = check_frame(기존 결정 검사 + 판별기·창작 허용선·예문 베낌을 한 판에) · 줄→장면 종류 = shot_kinds_for
def find_frame(slug: str | None) -> dict | None:
    """channel/<slug>/대본설명서/script_frame.json — 없으면 None(부르는 쪽이 폴백 경보)."""
    if not slug:
        return None
    p = ROOT / "channel" / slug / "대본설명서" / "script_frame.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _facts_rows(facts: dict) -> str:
    return "\n".join(f"[{k}] {v['text']}" for k, v in facts.items()) or "(없음)"


# 서사 노드 → 설명서 5칸(줄↔장면 계약)의 역할 칸
NODE_ROLE = {"계기": "계기", "극단행동": "훅", "자기위치": "계기", "불편공감": "문제·불편", "원리스펙": "원리·속성", "체감비유": "장점·결과",
             "체감사실": "장점·결과", "결과과장": "장점·결과", "사회반응": "사회적증거", "가격": "원리·속성", "감상": "감상", "권유": "행동유도"}


def shot_kinds_for(lines: list[dict], frame: dict | None) -> list[str]:
    """(판단 주인) 줄마다 장면 종류 — 첫 줄=훅 칸, 나머지는 줄 노드의 역할 칸. 그 칸의 계약(5칸 by_role) 1위 종류, 바로 앞 줄과 같으면 2위."""
    by = ((frame or {}).get("5_shot_contract") or {}).get("by_role") or {}
    out, prev = [], None
    for k, l in enumerate(lines):
        role = "훅" if k == 0 else NODE_ROLE.get(l.get("node") or "", "원리·속성")
        kinds = list((by.get(role) or {}).get("shot_kinds") or {}) or ["제품전체", "사용동작"]
        pick = next((x for x in kinds if x != prev), kinds[0])
        out.append(pick)
        prev = pick
    return out


def draft(product: dict, frame: dict | None, facts: dict, llm, slug: str | None = None, exclude: tuple = (), log=print) -> dict:
    """(판단 주인) 상품 → 대본 초안. 설명서가 있으면 script_frame.brief(공식·훅·S1 선택·서사 노드·창작 허용선·원리 상한·어미·예문 3·장면 계약)
    로 쓰고, 없으면 ROLES[slug]/DEFAULT_ROLES 역할 칸 폴백(경보 로그). 문장은 모델이 통째로 쓴다(빈칸 끼우기 금지)."""
    from tools.calcopy.engine import script_frame as SF
    name = product.get("name") or product.get("topic") or ""
    if frame:
        b = SF.brief(product, frame, [v["text"] for v in facts.values()], exclude=exclude)
        ids = list(facts)
        f1 = frame["1_skeleton"]["formulas"][0]
        prompt = SW.FRAME_DRAFT_PROMPT.format(
            slug=slug or frame.get("channel"), product=name, nodes=", ".join(f"{k} {v:.0%}" for k, v in b["narr_nodes"].items()),
            slots=" > ".join(f1["slots"]), hooks="·".join(b["hook_types"]),
            cap=max(1, sum(1 for x in b["facts_picked"] if x["kind"] == "원리스펙")),
            picked="; ".join(f"{ids[x['i']]} {x['text']}" for x in b["facts_picked"]), grounds=_facts_rows(facts),
            endings="·".join(b["endings"]), foreign="·".join(b.get("foreign_endings") or []) or "없음", conn="·".join(b.get("connectives") or []),
            cps=b.get("connect_per_sent", 1), chars=int(b["length"]["chars_median"]), nsent=int(b["length"]["n_sent_median"]),
            examples="\n\n".join(f"({i + 1}) {e['text']}" for i, e in enumerate(b["examples"])))
        path, roles = "frame", None
    else:
        roles = ROLES.get(slug or "") or DEFAULT_ROLES
        log(f"[경보] 대본 설명서 없음({slug}) → 역할 칸 폴백 {'ROLES[' + str(slug) + ']' if slug in ROLES else 'DEFAULT_ROLES'}")
        prompt = SW.FRAME_FALLBACK_PROMPT.format(slug=slug or "-", product=name, slots=" > ".join(roles), grounds=_facts_rows(facts))
        path, b = "fallback", None
    d, err = llm(prompt, "draft")
    lines = [l for l in ((d or {}).get("lines") or (d or {}).get("items") or []) if isinstance(l, dict) and (l.get("text") or "").strip()]
    for l in lines:
        l["text"] = l["text"].strip()
        l["facts"] = [i for i in (l.get("facts") or []) if isinstance(i, str)]
        l.setdefault("fn", l.get("node") or "")
    for l, kind in zip(lines, shot_kinds_for(lines, frame)):
        l["shot_kind"] = kind
    return {"path": path, "lines": lines, "title": (d or {}).get("title"), "brief": b, "roles": roles, "prompt": prompt, "error": None if d else err,
            "model": (d or {}).get("_model")}


def check_frame(lines: list[dict], frame: dict | None, facts: dict, examples: list[str] = (), support: dict | None = None,
                tags=None, product: dict | None = None) -> dict:
    """(판단 주인) 설명서 경로 검사 — 한 판에: 기존 결정 검사(최상급·띄어쓰기·범위 숫자·사실에 없는 숫자·없는 번호·소재 밖 브랜드·줄↔근거 판정 결과)
    + 창작 허용선(grounding_audit: 근거 필수 줄에 번호) + 예문 7자 베낌(copy_spans) + 판별기(judge_like, tags 주면 서사 관문)."""
    from tools.calcopy.engine import script_frame as SF
    bench0 = {"points": {}, "texts": []}
    texts = [l.get("text") or "" for l in lines]
    ids = set(facts)
    ftext = " ".join(v["text"] for v in facts.values())
    sup = claim_off(lines, facts, bench0)
    spc = spacing_off(texts, facts, None)
    rng = number_ranges(texts, facts)
    nums = [k for k, t in enumerate(texts) if any(x not in ftext for x in re.findall(r"\d[\d,.]*", t))]
    unknown = sorted({i for l in lines for i in (l.get("facts") or []) if i not in ids})
    allowed = _brands_in((product or {}).get("name") or "") | _brands_in(ftext)
    brand = {k: sorted(_brands_in(t) - allowed) for k, t in enumerate(texts)}
    brand = {k: v for k, v in brand.items() if v}
    ga = SF.grounding_audit(texts)
    ungrounded = {k: a["tags"] for k, (a, l) in enumerate(zip(ga, lines)) if a["needs_ground"] and not (set(l.get("facts") or []) & ids)}
    copy7 = {k: SF.copy_spans(t, list(examples), 7) for k, t in enumerate(texts)}
    copy7 = {k: v for k, v in copy7.items() if v}
    judge = SF.judge_like(" ".join(texts), frame, tags=tags) if frame else None
    chk = {"superlative": sorted(sup), "superlative_hit": sup, "spacing_off": sorted(spc), "spacing_hit": spc,
           "range_as_single": sorted(rng), "ranges_hit": rng, "numbers_unsourced": nums, "off_topic_brand": sorted(brand),
           "unsupported": sorted(support or {}), "support_hit": support or {}, "support_checked": support is not None,
           "ungrounded": sorted(ungrounded), "ungrounded_hit": ungrounded, "copied_examples": sorted(copy7), "copy7_hit": copy7,
           "unknown_ids": unknown, "judge": judge, "n_lines": len(lines), "chars": [len(t.replace(" ", "")) for t in texts]}
    chk["bad"] = bad_lines(chk)
    glob = []
    if unknown:
        glob.append(f"없는 근거 번호 {unknown}")
    if judge and not judge["pass"]:
        glob.append(f"판별기 반려 점수 {judge['score']} < {judge['threshold']}" + (f" · 필수 실패 {judge['hard_fail']}" if judge["hard_fail"] else ""))
    chk["global"] = glob
    chk["ok"] = not chk["bad"] and not glob and bool(lines)
    return chk


def materials_plan(lines: list[dict]) -> dict:
    """줄↔장면 계약 → 재료.json 꼴(narr_video 가 읽는 shots[i] 키: i·kind·src·ss·ours·why). src·ss 는 재료 담당이 채운다."""
    return {"_note": "script_engine.run_frame 이 쓴 재료 계획 — kind = 대본 설명서 5칸 계약(shot_kinds_for). src/ss/src_crop 은 재료 담당이 채운다.",
            "shots": [{"i": k, "line": k, "kind": l.get("shot_kind"), "src": None, "ss": None, "ours": "", "text": l.get("text"),
                       "why": f"줄 {k + 1} 노드 {l.get('node') or l.get('fn') or '-'}"} for k, l in enumerate(lines)]}


def run_frame(slug: str, product: dict, facts: dict, out: Path, llm=None, frame: dict | None = None, exclude: tuple = (),
              tagger=None, with_support: bool = True, log=print) -> dict:
    """설명서 경로 한 편 — draft → (줄↔근거 판정 1회) → check_frame → 대본.json·재료_계획.json·대본_검사.md. 다시 쓰기는 하지 않는다(판정 결과만)."""
    llm = llm or TF.LLM(budget=4)
    frame = frame if frame is not None else find_frame(slug)
    out.mkdir(parents=True, exist_ok=True)
    dr = draft(product, frame, facts, llm, slug, exclude, log)
    lines = dr["lines"]
    support = None
    if with_support and lines:
        need = [k for k, l in enumerate(lines) if l.get("facts")]
        sub = [lines[k] for k in need]
        sup, serr = support_check(sub, facts, {"points": {}}, llm) if sub else ({}, None)
        support = {need[i]: why for i, why in (sup or {}).items()} if sup is not None else None
        if sup is None:
            log(f"[줄↔근거] 판정 실패 {serr} — 통과로 치지 않는다")
    tags = tagger(lines) if (tagger and frame) else None
    ex = [e["text"] for e in ((dr.get("brief") or {}).get("examples") or [])]
    chk = check_frame(lines, frame, facts, ex, support, tags, product)
    if with_support and support is None:
        chk["ok"] = False
        chk["global"].append("줄↔근거 판정 실패")
    S = {"engine": "script_engine v1 · 대본 설명서 경로", "path": dr["path"], "slug": slug, "product": product, "title": dr.get("title"),
         "facts": facts, "final": {"lines": [{**l, "sources": [facts[i].get("url", "") for i in l.get("facts") or [] if i in facts and facts[i].get("url")]}
                                             for l in lines], "check": chk},
         "brief_examples": [e["id"] for e in ((dr.get("brief") or {}).get("examples") or [])], "llm_calls": llm.calls, "error": dr.get("error"),
         "status": "ok" if chk["ok"] else "failed_checks"}
    (out / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "재료_계획.json").write_text(json.dumps(materials_plan(lines), ensure_ascii=False, indent=1), encoding="utf-8")
    md = [f"# 대본 검사(설명서 경로) — {product.get('name')}", "", f"- 경로 {dr['path']} · 판정 **{'통과' if chk['ok'] else '반려'}**"]
    md += [f"- ⚠ {g}" for g in chk["global"]]
    md += ["", "| # | 노드 | 장면 | 줄 | 근거 | 문제 |", "|---|---|---|---|---|---|"]
    md += [f"| {k + 1} | {l.get('node') or l.get('fn')} | {l.get('shot_kind')} | {l['text'].replace('|', '¦')} | {', '.join(l.get('facts') or []) or '-'} | "
           f"{', '.join(chk['bad'].get(k, [])) or 'OK'} |" for k, l in enumerate(lines)]
    (out / "대본_검사.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log(f"[끝] {dr['path']} · 판정 {'통과' if chk['ok'] else '반려'} → {out / '대본.json'}")
    return S


# ── 산출 ─────────────────────────────────────────────────────────────────
def build_outputs(out: Path, P: dict, topic: dict, facts: dict, bench: dict, sk: dict, res: dict, bench_path: str | None, llm_calls: list) -> dict:
    allf = {**facts, **{k: {"text": v["text"], "url": v.get("url", "")} for k, v in bench["points"].items()}}
    lines = [{"fn": l.get("fn"), "text": l.get("text"), "facts": l.get("facts") or [],
              "sources": sorted({allf[i]["url"] for i in (l.get("facts") or []) if i in allf and allf[i].get("url")})} for l in res.get("lines") or []]
    sc = topic.get("scores") or {}
    gate = {"scores": {"엔진(LLM)": {name: (sc.get(k) or {}).get("score", "-") for k, name in TF.CRITERIA}} if sc else {},
            "score_note": "topic_find 점수(근거 문장 필수) — 사람/오푸스 판정 전" if sc else "",
            "angle": (res.get("meta") or {}).get("angle") or topic.get("angle"), "twist": (res.get("meta") or {}).get("twist")}
    S = {"engine": "script_engine v1", "topic": topic.get("topic"), "mode": sk["mode"], "preset": str(P.get("preset_dir") or P["slug"]),
         "tteutgi": sk.get("tteutgi"), "roles": sk["roles"], "ranges": [list(r) for r in sk["ranges"]], "orig": sk["orig"], "facts": allf,
         "title": (res.get("meta") or {}).get("title"), "bench": bench_path, "gate": gate,
         "final": {"lines": lines, "check": res.get("check")}, "tries": res.get("tries"), "llm_calls": llm_calls}
    if res.get("error"):
        S["error"] = res["error"]
    S["status"] = (res.get("check") or {}).get("status") or ("ok" if (res.get("check") or {}).get("ok") else "failed_checks")
    S["article_gate"] = (res.get("check") or {}).get("article_gate") or (res.get("check") or {}).get("why")
    (out / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "roles.json").write_text(json.dumps({"slug": P["slug"], "roles": sk["roles"], "mode": sk["mode"],
                                                "note": "프리셋 manifest.roles 로 옮길 값(manifest 주인 preset_save 가 저장)"}, ensure_ascii=False, indent=1), encoding="utf-8")
    c = res.get("check") or {}
    md = [f"# 대본 검사 — {topic.get('topic')}", "", f"- 꼴 {sk['mode']} · 말투 {sk['honorific']} · 칸 {len(sk['roles'])} · 판정 **{'통과' if c.get('ok') else '미통과'}**"
          + (f" · 다시 쓰기 {len([t for t in res.get('tries') or [] if t.get('round')])}회" if res.get("tries") else ""), ""]
    if res.get("error"):
        md += [f"- ⚠ {res['error']}", ""]
    if c.get("total_off"):
        md.append(f"- ⚠ 전체 길이 {c['total_off']['chars']}자 → {c['total_off']['range']}")
    for m in (c.get("channel_lint_detail") or {}).get("global") or []:
        md.append(f"- ⚠ {m}")
    if c.get("total_basis"):
        md.append(f"- 길이 기준: {c['total_basis']}")
    if c.get("sec_est"):
        md.append(f"- 예상 길이 {c['sec_est']}초(cps {sk['cps']})")
    if c.get("unknown_ids"):
        md.append(f"- ⚠ 없는 근거 번호 {c['unknown_ids']}")
    md += ["", "| # | 칸 | 줄 | 근거 | 글자(범위) | 문제 |", "|---|---|---|---|---|---|"]
    for k, l in enumerate(lines):
        rg = sk["ranges"][k] if k < len(sk["ranges"]) else ["-", "-"]
        md.append(f"| {k + 1} | {l['fn']} | {(l['text'] or '').replace('|', '¦')} | {', '.join(l['facts']) or '-'} | {len((l['text'] or '').replace(' ', ''))}({rg[0]}~{rg[1]}) | "
                  f"{', '.join((c.get('bad') or {}).get(k, [])) or 'OK'} |")
    (out / "대본_검사.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    pm = [f"# 대본 계획(선검수) — {topic.get('topic')}", "", "## 소재 5기준", ""]
    if sc:
        pm += ["| 기준 | 점수 | 근거 |", "|---|---|---|"] + [f"| {name} | {(sc.get(k) or {}).get('score', '-')} | {(sc.get(k) or {}).get('why', '')} |" for k, name in TF.CRITERIA]
        ov = topic.get("overlap") or {}
        pm.append(f"\n- 이미 만든 소재 겹침 {ov.get('score')} ({ov.get('with') or '-'}) · 합계 {topic.get('total')}")
    else:
        pm.append("- (소재 점수 없음 — topic_find 후보가 아닌 소재)")
    pm += ["", "## 썰 각도", "", f"- 각도: {gate['angle'] or '-'}", f"- 반전 자리: {gate['twist'] or '-'}", f"- 제목: {S['title'] or '-'}",
           "", "## 대본", ""] + [f"{k + 1}. ({l['fn']}) {l['text']} — 근거 {', '.join(l['facts']) or '없음'}" for k, l in enumerate(lines)]
    used = sorted({i for l in lines for i in l["facts"]})
    pm += ["", "## 근거표", "", "| 번호 | 내용 | 출처 |", "|---|---|---|"] + [f"| {i} | {allf[i]['text'] if i in allf else '(없는 번호)'} | {allf.get(i, {}).get('url', '')} |" for i in used]
    pm += ["", f"- 벤치: {bench_path or '-'}", "- 판정 자리: 이 계획을 사람/조율자가 보고 OK 면 remake.py --script 대본.json --plan-only 로 재료 계획을 잇는다"]
    (out / "대본_계획.md").write_text("\n".join(pm) + "\n", encoding="utf-8")
    return S


def run(preset: str, topic_arg: str, out: Path, bench_path: str | None = None, facts_path: str | None = None, mode: str | None = None,
        roles: list[str] | None = None, tteutgi: str | None = None, pick: str | None = None, free_roles: tuple = (), llm=None, log=print,
        source_kind: str | None = None, auto_articles: bool = True, net: dict | None = None) -> dict:
    llm = llm or TF.LLM()
    P = TF.load_preset(preset, tteutgi)
    topic = load_topic(topic_arg, pick)
    facts = load_facts(facts_path)
    bench = load_bench(bench_path)
    sk = skeleton(P, mode, roles)
    out.mkdir(parents=True, exist_ok=True)
    log(f"[규칙] {P['slug']} · {sk['mode']} · 칸 {len(sk['roles'])} · 말투 {sk['honorific']} · 사실 {len(facts)} · 벤치 포인트 {len(bench['points'])}")
    if sk["roles_basis"].startswith("경보"):
        log(f"[경보] 역할 칸 {sk['roles_basis']} — {sk['roles']}")
    kind = source_kind or (topic.get("source") or {}).get("kind") or P["manifest"].get("source_kind")
    ok, why = article_gate(topic, facts, kind)
    if not ok and auto_articles:   # 10-16 창고: 제품비하인드 5건 전부 facts_insufficient — 워커가 기사를 넣는 단계가 없었다
        got, notes = find_articles(topic, net, log=log)
        if got:
            facts = {**facts, **got}
            (out / "facts_기사.json").write_text(json.dumps({"facts": got, "notes": notes}, ensure_ascii=False, indent=1), encoding="utf-8")
            ok, why = article_gate(topic, facts, kind)
            why += f" (자동 기사 찾기 {len(got)}건 → facts_기사.json)"
    log(f"[기사 대조] {'통과' if ok else '멈춤'} — {why}")
    if not ok:
        res = {"lines": [], "check": {"ok": False, "status": "facts_insufficient", "why": why, "bad": {}}, "tries": [],
               "error": f"facts_insufficient: {why}", "meta": {}}
        S = build_outputs(out, P, topic, facts, bench, sk, res, bench_path, llm.calls)
        return S
    res = write(P, topic, facts, bench, sk, llm, free_roles, log)
    res.setdefault("check", {})["article_gate"] = why
    S = build_outputs(out, P, topic, facts, bench, sk, res, bench_path, llm.calls)
    log(f"[끝] 판정 {'통과' if (res.get('check') or {}).get('ok') else '미통과'} → {out / '대본.json'}")
    return S


def main(argv=None):
    ap = argparse.ArgumentParser(description="대본 쓰기 엔진")
    ap.add_argument("--preset", required=True)
    ap.add_argument("--topic", required=True, help="후보.json#c2 · 후보.json · 소재.json · 그냥 글")
    ap.add_argument("--pick", help="후보.json 에서 고를 id(없으면 recommend[0])")
    ap.add_argument("--bench")
    ap.add_argument("--facts")
    ap.add_argument("--mode", choices=["captions", "narration"])
    ap.add_argument("--roles", default="", help="쉼표 구분 역할 칸(없으면 manifest.roles → 채널 기본)")
    ap.add_argument("--free-roles", default="", help="근거 번호 없이 둘 수 있는 칸 이름(쉼표)")
    ap.add_argument("--tteutgi")
    ap.add_argument("--source-kind", help="기사 대조 관문용 출처 유형(없으면 소재 source.kind → manifest.source_kind)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-llm", type=int, default=7, help="무료 제미나이 호출 상한(초안 1 + 다시 쓰기 2 + 줄↔근거 판정 ≤3 + 여유)")
    a = ap.parse_args(argv)
    S = run(a.preset, a.topic, Path(a.out), a.bench, a.facts, a.mode, [r for r in a.roles.split(",") if r.strip()] or None, a.tteutgi, a.pick,
            tuple(x for x in a.free_roles.split(",") if x), TF.LLM(budget=a.max_llm), source_kind=a.source_kind)
    for l in S["final"]["lines"]:
        print(f"  ({l['fn']}) {l['text']}  {l['facts']}")
    return 0 if (S["final"].get("check") or {}).get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
