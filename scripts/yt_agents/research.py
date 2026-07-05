"""리서치·검증 동반 — 대본이 '오늘 시점' 사실과 어긋나지 않게 팩트팩을 만든다.
오염 방지 3원칙:
  ① 우리 자료 우선(원자 DB — 검증된 크롤)  ② 최근 기사만(오늘 기준 N일 이내)
  ③ 현재 주가 정합성(반등중인데 하락 서술 등 모순을 경고로 차단)
소재가 '방법론·툴'이면 리서치는 무의미 → 자동 스킵(수동 토글로 강제 가능).
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

_HERE = Path(__file__).parent
_ROOT = _HERE.parent.parent
for p in (str(_HERE), str(_ROOT), str(_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import gemini_client as G


def _from_pipeline(dotted: str, attr: str = None):
    """pipeline 패키지 import — yt_agents/pipeline.py(동명 모듈)가 _ROOT/pipeline 패키지를
    가리는 것을 회피. basename이 yt_agents인 경로(절대·상대)를 모두 잠시 빼고,
    yt_agents/pipeline.py로 잘못 캐시된 모듈도 지운 뒤 import한다."""
    import importlib
    import os
    saved = sys.path[:]
    sys.path[:] = [p for p in sys.path
                   if os.path.basename(os.path.normpath(p or ".")) != "yt_agents"]
    for k in list(sys.modules):
        if (k == "pipeline" or k.startswith("pipeline.")):
            f = getattr(sys.modules[k], "__file__", "") or ""
            if "yt_agents" in f:
                del sys.modules[k]
    try:
        mod = importlib.import_module(dotted)
        return getattr(mod, attr) if attr else mod
    finally:
        sys.path[:] = saved


# ── 소재 판정 ────────────────────────────────────────────────
def detect_topic(draft: dict) -> dict:
    """믹스 초안 → 소재 키워드·종목·리서치 필요 여부. 실패 시 보수적(리서치 OFF)."""
    titles = " / ".join(draft.get("제목후보", []) or [])
    gu = " · ".join(draft.get("구성") or [])
    prompt = f"""아래는 새 유튜브 영상의 대본 초안이다. 이 영상이 다루는 '소재'를 분석하라.

제목후보: {titles}
구성: {gu}
핵심포인트: {' · '.join(draft.get('핵심대본_포인트') or [])}

판정:
- 특정 종목·섹터·시장 상황(시황)을 다루면 needs_research=true (최신 사실·주가 확인이 필요).
- 순수 방법론(매매기법·AI 활용법·도구 사용법 등 시점 무관 콘텐츠)이면 needs_research=false.

JSON만 출력:
{{"keywords": ["뉴스·원자 검색용 키워드 2~3개"], "entities": ["구체적 상장 종목명(있으면, 없으면 빈 배열)"], "needs_research": true, "reason": "판정 근거 한 문장"}}"""
    try:
        d = G.call_json(prompt)
        return {
            "keywords": [str(k).strip() for k in (d.get("keywords") or []) if str(k).strip()][:3],
            "entities": [str(e).strip() for e in (d.get("entities") or []) if str(e).strip()][:5],
            "needs_research": bool(d.get("needs_research", False)),
            "reason": str(d.get("reason", "")).strip(),
        }
    except Exception:
        return {"keywords": [], "entities": [], "needs_research": False,
                "reason": "소재 판정 실패 — 리서치 생략"}


# ── 수집 ─────────────────────────────────────────────────────
def _recent_news(keywords: list, days: int) -> list:
    """네이버 뉴스 최신순 → 오늘 기준 days 이내만. 각 {title,date,url,age}."""
    try:
        import news_feed as NF
    except Exception:
        return []
    now = datetime.now(timezone.utc)
    seen, out = set(), []
    for kw in keywords:
        for it in NF._search(kw, display=15, sort="date"):
            url = it.get("originallink") or it.get("link") or ""
            title = NF._clean(it.get("title", ""))
            if not title or url in seen:
                continue
            age = NF._age_days(it.get("pubDate", ""), now)
            if age > days:        # ② 오래된 기사 배제(오염 방지)
                continue
            seen.add(url)
            out.append({"title": title, "date": NF._fmt_rss(it.get("pubDate", "")),
                        "url": url, "age": round(age, 1)})
    out.sort(key=lambda x: x["age"])
    return out[:8]


def _prices(entities: list) -> list:
    """종목명 → 코드 → 현재가·등락. {name,price,change_rate,dir}.
    KIS가 주말·장마감에 신뢰 불가한 값(name 공백/등락률 비현실)을 주므로, 이상하면 naver
    일봉으로 폴백한다(주말엔 금요일 종가 기준). 둘 다 실패하면 그 종목은 뺀다(오염 방지)."""
    try:
        codemap = _from_pipeline("pipeline.atoms.codemap")
        import kis_api
        import naver_api
    except Exception:
        return []
    out = []
    for name in entities:
        try:
            code = codemap.code_for(name)
            if not code:
                continue
            price = cr = None
            disp = name
            # 1) KIS 실시간 — name이 채워지고 등락률이 현실 범위(±30%)일 때만 신뢰
            try:
                p = kis_api.get_price(code)
                if p.get("name") and p.get("price", 0) > 0 and abs(p.get("change_rate", 0)) < 30:
                    price, cr, disp = p["price"], p["change_rate"], p["name"]
            except Exception:
                pass
            # 2) 폴백 — naver 일봉(최근 종가 vs 전일)
            if price is None:
                cs = naver_api.daily_candles(code, count=3)
                if len(cs) >= 2:
                    last, prev = cs[-1], cs[-2]
                    price = int(last["close"])
                    cr = round((last["close"] - prev["close"]) / prev["close"] * 100, 2) if prev["close"] else 0
            if price is None:
                continue
            direction = "상승" if cr >= 1 else ("하락" if cr <= -1 else "보합")
            out.append({"name": disp, "price": price, "change_rate": cr, "dir": direction})
        except Exception:
            continue
    return out


def _our_atoms(keywords: list, days: int = 14) -> list:
    """원자 DB(검증된 크롤) 최근 맥락. 뉴스보다 넓게(2주) — 흐름·히스토리용."""
    try:
        run_query = _from_pipeline("pipeline.atoms.query", "run_query")
    except Exception:
        return []
    seen, out = set(), []
    for kw in keywords:
        try:
            for a in run_query(kw, n=4, days=days, mode="hybrid"):
                c = (a.get("content") or "").strip()
                key = c[:40]
                if c and key not in seen:
                    seen.add(key)
                    out.append({"content": c[:200], "date": a.get("date", ""),
                                "source": a.get("source_type", "")})
        except Exception:
            continue
    return out[:8]


# ── 팩트팩 조립 + 정합성 경고 ────────────────────────────────
def build_factpack(topic: dict, days: int) -> dict:
    """수집 → 오염검증 팩트팩. 반환 {text, warnings, has_data, prices, news_n, atoms_n}."""
    news = _recent_news(topic["keywords"], days)
    prices = _prices(topic["entities"])
    atoms = _our_atoms(topic["keywords"])

    lines, warnings = [], []

    if prices:
        lines.append("[현재 주가 — 이 방향과 모순되는 서술 금지]")
        for p in prices:
            lines.append(f"- {p['name']}: {p['price']:,}원 ({p['change_rate']:+.1f}%, {p['dir']}중)")
            if p["dir"] == "상승":
                warnings.append(f"{p['name']} 현재 {p['change_rate']:+.1f}% 상승중 — 하락·약세 서술 금지")
            elif p["dir"] == "하락":
                warnings.append(f"{p['name']} 현재 {p['change_rate']:+.1f}% 하락중 — 급등·강세 서술 금지")
        lines.append("")

    if news:
        lines.append(f"[최근 {days}일 기사 — 시점 검증됨]")
        for n in news:
            lines.append(f"- ({n['date']}) {n['title']}")
        lines.append("")

    if atoms:
        lines.append("[우리 자료 — 원자 DB(검증된 크롤, 최근 2주)]")
        for a in atoms:
            src = f" [{a['source']}]" if a.get("source") else ""
            lines.append(f"- ({a.get('date','')}){src} {a['content']}")
        lines.append("")

    text = "\n".join(lines).strip()
    return {"text": text, "warnings": warnings, "has_data": bool(text),
            "prices": prices, "news_n": len(news), "atoms_n": len(atoms)}


# ── 오케스트레이터 ───────────────────────────────────────────
def research(draft: dict, days: int = 3, force: "bool | None" = None) -> dict:
    """force: None=자동판정 / True=강제ON / False=강제OFF.
    반환 {skipped, topic, factpack}. skipped면 factpack None."""
    topic = detect_topic(draft)
    run_it = topic["needs_research"] if force is None else force
    if not run_it:
        return {"skipped": True, "topic": topic, "factpack": None}
    fp = build_factpack(topic, days)
    return {"skipped": False, "topic": topic, "factpack": fp}
