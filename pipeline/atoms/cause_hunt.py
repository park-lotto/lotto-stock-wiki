"""원인추적 캐스케이드 (Phase3). 직접+그래프로도 미귀속인 강세 종목의 원인을,
소스 신뢰등급 순으로 계단식 수색해 라벨과 함께 반환한다.

계단(높은 신뢰 우선): 공시🟢 → 뉴스🟢 → 텔레그램🟡 → 종토방🟠 → LLM추론🔵.
- Stage 1(atom): atoms.db의 해당 종목 원자를 최고 신뢰등급으로 채택(종토방·텔레도
  원자로 인제스트돼 있으면 여기서 잡힘).
- Stage 2(inference): 원자가 없으면 최근 시장 맥락으로 LLM 가설 생성(🔵, 저신뢰).
- Stage 3(silent): 그래도 없으면 '전 소스 침묵 — 최우선 추적'.

절대 사실처럼 흘리지 않는다 — 모든 결과에 신뢰등급과 출처(또는 '추론')를 단다.
query_fn/generate_fn 주입으로 Gemini·DB 없이 테스트 가능.
"""
from pipeline.atoms import db as _db
from pipeline.atoms.strength_net import trust_tier

# 신뢰등급 우선순위(높을수록 먼저 채택)
_TIER_RANK = {"🟢": 4, "🟡": 3, "🟠": 2, "🔵": 1}
_SILENT_FLAG = "⚠️ 전 소스 침묵 — 최우선 추적"

_INFER_PROMPT = """오늘 국내 증시에서 '{name}'가 강세다. 아래 최근 시장 맥락을 참고해,
왜 오르는지 '가장 그럴듯한 가설 한 줄'만 제시하라. 확정 아닌 추론임을 전제로,
근거가 약하면 약하다고 밝혀라. 맥락에 단서가 전혀 없으면 '단서 없음'이라고만 답하라.
맥락:
{context}"""


def _tier_rank(atom: dict) -> int:
    return _TIER_RANK.get(trust_tier(atom), 0)


def hunt_cause(name: str, days: int = 3, query_fn=None,
               generate_fn=None, context_fn=None) -> dict:
    """한 미귀속 종목의 원인을 계단식으로 추적. 항상 신뢰등급/출처 라벨을 단다."""
    if query_fn is None:
        query_fn = _db.query_atoms
    base = {"name": name}

    # Stage 1 — 원자(공시/뉴스/텔레/종토방)
    atoms = query_fn(asset=name, days=days, active_only=True) or []
    if atoms:
        best = sorted(atoms, key=lambda a: (_tier_rank(a), a.get("strength_score", 1)),
                      reverse=True)[0]
        return {**base, "found": True, "stage": "atom", "tier": trust_tier(best),
                "source": best.get("source_name"), "cause": best.get("content"),
                "atom_id": best.get("id"), "flag": None}

    # Stage 2 — LLM 추론
    if generate_fn is not None:
        context = context_fn(name) if context_fn else ""
        text = (generate_fn(_INFER_PROMPT.format(name=name, context=context)) or "").strip()
        if text and "단서 없음" not in text:
            return {**base, "found": True, "stage": "inference", "tier": "🔵",
                    "source": "LLM추론", "cause": text, "atom_id": None, "flag": None}

    # Stage 3 — 전 소스 침묵
    return {**base, "found": False, "stage": "silent", "tier": None,
            "source": None, "cause": None, "atom_id": None, "flag": _SILENT_FLAG}


def _default_context(name: str) -> str:
    """최근 시장/해당 종목 원자 몇 개를 맥락 문자열로."""
    rows = _db.query_atoms(days=3, limit=8, active_only=True) or []
    return "\n".join(f"- {r.get('asset')}: {r.get('content')}" for r in rows)


def hunt_with_llm(name: str, days: int = 3) -> dict:
    """실 Gemini + 실 맥락으로 원인추적(impure 엔트리)."""
    from pipeline.atoms.edge_extract import _gemini_generate
    return hunt_cause(name, days=days, generate_fn=_gemini_generate, context_fn=_default_context)
