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


# ── 주장 추출 (스토리라인 → 이 대본이 사실로 내세울 핵심 주장 + 검증 계획) ──
def extract_claims(storyline_text: str) -> dict:
    """서사 설계도 → 대본이 주장할 핵심 클레임 + 각 주장의 검증 질문·검색어·관련 종목.
    실패/방법론이면 needs_research=False."""
    prompt = f"""아래는 유튜브 영상의 서사 설계도다. 이 대본이 시청자에게 '사실'로 내세울
핵심 주장(claim)들을 뽑아라. 그리고 각 주장이 진짜인지 검증할 계획을 세워라.

=== 서사 설계도 ===
{storyline_text}

규칙:
- 검증이 필요한 '사실 주장'만 뽑아라(예: "메타 투자 축소로 반도체가 폭락했다"). 감상·의견·방법론은 제외.
- 각 주장마다: 그것을 검증할 질문 + 뉴스/데이터에서 찾을 짧은 검색어 2개.
- 특정 종목이 걸려 있으면 entities에 종목명.
- 순수 방법론 영상(매매기법·도구사용법 등 시점 무관)이면 needs_research=false, claims 빈 배열.

JSON만 출력:
{{"claims": [{{"claim": "대본이 사실로 주장하는 것", "question": "이게 사실인지 검증할 질문", "keywords": ["검색어1", "검색어2"]}}], "entities": ["관련 상장 종목명"], "needs_research": true, "reason": "판정 근거 한 문장"}}"""
    try:
        d = G.call_json(prompt)
        claims = []
        for c in (d.get("claims") or []):
            claim = str(c.get("claim", "")).strip()
            if not claim:
                continue
            claims.append({
                "claim": claim,
                "question": str(c.get("question", "")).strip(),
                "keywords": [str(k).strip() for k in (c.get("keywords") or []) if str(k).strip()][:2],
            })
        return {
            "claims": claims[:5],
            "entities": [str(e).strip() for e in (d.get("entities") or []) if str(e).strip()][:5],
            "needs_research": bool(d.get("needs_research", False)) and bool(claims),
            "reason": str(d.get("reason", "")).strip(),
        }
    except Exception:
        return {"claims": [], "entities": [], "needs_research": False,
                "reason": "주장 추출 실패 — 리서치 생략"}


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
            # description = 네이버 제공 기사 요약(첫 1~2문장). 제목만으론 대본이 추측하므로 함께.
            desc = NF._clean(it.get("description", ""))
            out.append({"title": title, "desc": desc,
                        "date": NF._fmt_rss(it.get("pubDate", "")),
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
    """원자 DB(검증된 크롤) 최근 맥락. 뉴스보다 넓게(2주) — 흐름·히스토리용.
    run_query는 CLI용 print를 대량 뱉으므로 stdout을 억제해 서버 로그 오염을 막는다."""
    import io
    import contextlib
    try:
        run_query = _from_pipeline("pipeline.atoms.query", "run_query")
    except Exception:
        return []
    seen, out = set(), []
    for kw in keywords:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                atoms = run_query(kw, n=4, days=days, mode="hybrid")
            for a in atoms:
                c = (a.get("content") or "").strip()
                key = c[:40]
                if c and key not in seen:
                    seen.add(key)
                    out.append({"content": c[:200], "date": a.get("date", ""),
                                "source": a.get("source_type", "")})
        except Exception:
            continue
    return out[:8]


# ── 주장별 근거 검증 ─────────────────────────────────────────
def _verify_claim(c: dict, days: int) -> dict:
    """주장 1개 → 그 검증 검색어로 최근기사·원자 수집 → 근거 강도 판정.
    verdict: 충분(뉴스+원자 합 3+) / 약함(1~2) / 없음(0)."""
    kws = c.get("keywords") or [c.get("claim", "")]
    news = _recent_news(kws, days)
    atoms = _our_atoms(kws)
    total = len(news) + len(atoms)
    verdict = "충분" if total >= 3 else ("약함" if total >= 1 else "없음")
    return {"claim": c["claim"], "question": c.get("question", ""),
            "news": news[:4], "atoms": atoms[:4], "verdict": verdict}


_VMARK = {"충분": "✅", "약함": "△", "없음": "⚠️"}


# ── 팩트팩 조립 (주장별 근거 + 정합성 경고) ──────────────────
def build_factpack(ex: dict, days: int) -> dict:
    """주장 추출 결과 → 주장별 타겟 리서치 → 근거 매핑 팩트팩.
    반환 {text, warnings, has_data, prices, claim_evidence, weak_claims}."""
    prices = _prices(ex["entities"])
    claim_ev = [_verify_claim(c, days) for c in ex["claims"]]

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

    lines.append(f"[주장별 근거 검증 — 최근 {days}일 기사 + 우리 원자DB]")
    weak = []
    for ce in claim_ev:
        mark = _VMARK.get(ce["verdict"], "")
        lines.append(f"◆ 주장: {ce['claim']}")
        lines.append(f"  검증: {ce['verdict']} {mark}")
        if ce["news"]:
            for n in ce["news"]:
                d = f"({n['date']}) {n['title']}"
                lines.append(f"  - {d}")
                if n.get("desc"):
                    lines.append(f"      → {n['desc']}")
        for a in ce["atoms"]:
            lines.append(f"  - [원자 {a.get('date','')}] {a['content']}")
        if ce["verdict"] == "없음":
            weak.append(ce["claim"])
            lines.append("  ※ 근거 못 찾음 — 대본에서 단정 금지. 약화하거나 질문형으로.")
        lines.append("")

    if weak:
        warnings.append(f"근거 부족 주장 {len(weak)}개 — 단정하지 말 것: " + " / ".join(weak))

    text = "\n".join(lines).strip()
    return {"text": text, "warnings": warnings, "has_data": bool(claim_ev),
            "prices": prices, "claim_evidence": claim_ev, "weak_claims": weak}


# ── 오케스트레이터 ───────────────────────────────────────────
def research(storyline_text: str, days: int = 3, force: "bool | None" = None) -> dict:
    """스토리라인 설계도 → 주장 추출 → 주장별 타겟 리서치 → 근거 팩트팩.
    force: None=자동판정 / True=강제ON / False=강제OFF. 반환 {skipped, plan, factpack}."""
    ex = extract_claims(storyline_text)
    run_it = ex["needs_research"] if force is None else (force and bool(ex["claims"]))
    if not run_it:
        return {"skipped": True, "plan": ex, "factpack": None}
    fp = build_factpack(ex, days)
    return {"skipped": False, "plan": ex, "factpack": fp}
