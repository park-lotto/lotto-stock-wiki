"""순환매 감지기 (Sector Rotation Detector).

트리거 뉴스(강한 원자)가 터진 섹터와, 오늘 실제로 급등한 '다른 섹터' 종목이
둘 다 있을 때만 — 그 사이 인과관계가 말이 되는지 LLM에게 물어 카드를 만든다.
화살표맵(관계그래프) 없이 섹터 버킷 + LLM 지식만으로 온더플라이 매칭.

설계 원칙(strength_net의 '침묵 금지'와 반대):
  - 트리거+급등 둘 다 있어야 후보 (하나라도 없으면 LLM 호출 자체를 안 함 → 비용 0)
  - 억지 연결이면 LLM이 빈 결과를 내도 정상 (카드 개수를 억지로 안 채운다)
설계 문서: docs/superpowers/specs/2026-07-07-순환매감지기-design.md
"""
import json
from pipeline.atoms import db as _db

# strength_net과 동일한 호재 신호 집합 재사용(중복 정의 방지)
_BULLISH_SIGNALS = {"bullish", "positive", "상승", "호재"}

_TIER_BY_SOURCE = {
    "공시": "🟢", "dart": "🟢", "disclosure": "🟢",
    "news": "🟢", "뉴스": "🟢",
    "telegram": "🟡", "텔레그램": "🟡",
    "종토방": "🟠", "naver_board": "🟠",
}


def _trust_tier(source_type: str) -> str:
    st = (source_type or "").strip().lower()
    for key, tier in _TIER_BY_SOURCE.items():
        if key.lower() == st:
            return tier
    return "🔵"


def _is_bullish(atom: dict) -> bool:
    s = (atom.get("signal") or "").strip()
    return s.lower() in _BULLISH_SIGNALS or s in _BULLISH_SIGNALS


def trigger_candidates(days: int = 3, min_strength: int = 3,
                       limit: int = 40, query_fn=None) -> list:
    """atoms.db에서 최근 N일 '강한 호재' 원자를 트리거 후보로. 섹터 없으면 제외(순환매는 섹터 단위).

    반환: [{atom_id, content, sector, source_name, trust, strength_score}]
    """
    if query_fn is None:
        query_fn = _db.query_atoms
    rows = query_fn(days=days, limit=limit, active_only=True) or []
    out = []
    for a in rows:
        if not _is_bullish(a):
            continue
        if (a.get("strength_score") or 1) < min_strength:
            continue
        sector = (a.get("sector") or "").strip()
        if not sector:
            continue
        out.append({
            "atom_id": a.get("id"),
            "content": a.get("content"),
            "sector": sector,
            "source_name": a.get("source_name"),
            "trust": _trust_tier(a.get("source_type")),
            "strength_score": a.get("strength_score"),
        })
    return out


def mover_candidates(heatmap: dict, exclude_sectors: set = None,
                     min_rate: float = 5.0) -> list:
    """히트맵에서 min_rate 이상 급등 종목 중 '트리거 섹터가 아닌' 종목만 급등 후보로(순수).

    형태: {"sectors":[{"name","stocks":[{"name","code","change_rate","price"}]}]}
    - price==0(데이터 없음) 제외, 한 종목 여러 타일이면 최고 등락률 1건.
    """
    exclude_sectors = exclude_sectors or set()
    best = {}  # code -> mover(최고 rate)
    for sector in heatmap.get("sectors") or []:
        sec_name = sector.get("name")
        if sec_name in exclude_sectors:
            continue
        for st in sector.get("stocks") or []:
            code = st.get("code")
            rate = st.get("change_rate")
            if not code or rate is None or rate < min_rate:
                continue
            if (st.get("price") or 0) == 0:
                continue
            prev = best.get(code)
            if prev is None or rate > prev["rate"]:
                best[code] = {"name": st.get("name"), "code": code,
                              "sector": sec_name, "rate": rate}
    return sorted(best.values(), key=lambda m: m["rate"], reverse=True)


def build_prompt(triggers: list, movers: list) -> str:
    """트리거 리스트 + 급등 리스트를 주고 '말이 되는 인과관계 조합만' 뽑게 하는 프롬프트."""
    trig_lines = "\n".join(
        f"- [{t.get('sector')}] {t.get('content')} (출처 {t.get('source_name')})"
        for t in triggers)
    mv_lines = "\n".join(
        f"- {m.get('name')}({m.get('code')}) · {m.get('sector')} · +{m.get('rate')}%"
        for m in movers)
    return f"""너는 한국 주식시장 순환매(sector rotation) 분석가다.

[트리거 — 오늘 나온 강한 호재]
{trig_lines}

[급등 — 오늘 실제로 오른 다른 섹터 종목]
{mv_lines}

위 트리거 중 하나가 원인이 되어 급등 종목이 '순환매 2차 수혜'로 올랐다고
합리적으로 설명되는 조합만 골라라. 억지로 엮지 마라 — 인과관계가 불명확하면
그 종목은 빼라. 하나도 말이 안 되면 빈 배열을 반환하라.

JSON만 출력(설명 금지):
{{"matches":[{{"trigger_sector":"...","mover_sector":"...","mover_stock":"...",
"mover_code":"...","pct":0.0,"trigger_summary":"<트리거 한줄>",
"reasoning":"<왜 이 종목이 수혜인지 한줄>"}}]}}"""


def parse_matches(llm_text: str) -> list:
    """LLM 응답(JSON, 코드펜스 허용)에서 matches 배열을 파싱. 실패하면 []."""
    if not llm_text:
        return []
    txt = llm_text.strip()
    if txt.startswith("```"):
        # ```json ... ``` 코드펜스 제거
        txt = txt.split("```", 2)
        txt = txt[1] if len(txt) >= 2 else llm_text
        if txt.lstrip().lower().startswith("json"):
            txt = txt.lstrip()[4:]
        txt = txt.strip().rstrip("`").strip()
    try:
        data = json.loads(txt)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, dict):
        return data.get("matches") or []
    if isinstance(data, list):
        return data
    return []


def _make_label(m: dict) -> str:
    """카드 라벨: '반도체 클러스터 확정 → 성신양회 +16% → 건자재 2차수혜'.
    (앞 이모지는 UI(mkCard)가 🔄로 붙이므로 여기선 넣지 않는다)."""
    trg = m.get("trigger_summary") or m.get("trigger_sector") or ""
    stock = m.get("mover_stock") or ""
    pct = m.get("pct")
    reason = m.get("reasoning") or ""
    pct_s = f" +{pct}%" if isinstance(pct, (int, float)) else ""
    return f"{trg} → {stock}{pct_s} → {reason}".strip()


def detect(triggers: list, movers: list, llm_fn, ts: str = None) -> list:
    """게이트 → LLM 매칭 → 카드. triggers/movers 둘 중 하나라도 비면 LLM 호출 없이 [].

    llm_fn(prompt) -> {"ok":True,"analysis":str} | {"error":str}
      (Gemini든 Sonnet(claude -p)든 이 시그니처만 맞추면 교체 가능)
    ts: 카드에 붙일 시각 "HH:MM" (호출측에서 주입 — 순수성 유지, 테스트 결정성).
    """
    if not triggers or not movers:
        return []
    prompt = build_prompt(triggers, movers)
    res = llm_fn(prompt) or {}
    if not res.get("ok"):
        return []
    cards = []
    for m in parse_matches(res.get("analysis", "")):
        if not m.get("mover_stock"):
            continue
        card = {
            "type": "circulation",
            "trigger_sector": m.get("trigger_sector"),
            "mover_sector": m.get("mover_sector"),
            "mover_stock": m.get("mover_stock"),
            "mover_code": str(m.get("mover_code") or ""),
            "pct": m.get("pct"),
            "trigger_summary": m.get("trigger_summary"),
            "reasoning": m.get("reasoning"),
            "label": _make_label(m),
        }
        if ts:
            card["ts"] = ts
        cards.append(card)
    return cards
