"""스파인 클러스터링(A1) — 승인 소스를 상황유형 아크로 묶는다.
enum 힌트(기존 스파인명 + __NEW__)로 신규 남발을 억제(통제어휘, structure_analyze 방식).
승격 게이트(source_count>=3 AND 사람승인)는 여기가 아니라 daily_batch가 판정."""
from shopping_shorts import pattern_bank

NEW_SENTINEL = "__NEW__"
_MAX_SOURCES = 60   # 프롬프트 폭주 방지


def _schema(existing_names):
    enum = list(dict.fromkeys(existing_names + [NEW_SENTINEL]))
    return {
        "type": "object",
        "properties": {
            "assignments": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "integer"},
                    "spine_name": {"type": "string", "enum": enum},
                    "situation_type": {"type": "string"},
                },
                "required": ["source_id", "spine_name"],
            }},
        },
        "required": ["assignments"],
    }


def _prompt(sources, existing):
    lines = [f"[{s['id']}] ({s.get('product_category', '?')}) {(s.get('full_text') or '')[:400]}"
             for s in sources[:_MAX_SOURCES]]
    known = "\n".join(f"- {e.get('name')}: {e.get('situation_type', '')}" for e in existing) or "(없음)"
    return ("아래 대본들을 서사 상황유형(스파인)으로 묶어라. 기존 스파인에 맞으면 그 이름을 쓰고, "
            "정말 새로우면 spine_name=\"__NEW__\"로 두고 situation_type에 한 줄 이름을 제안하라. "
            f"기존 스파인:\n{known}\n\n대본:\n" + "\n".join(lines))


def cluster_sources(sources, existing_spines, call=None):
    """→ [{source_id, spine_name, situation_type}]. call None/빈응답이면 [](비치명적)."""
    if call is None:
        call = pattern_bank._default_call
    if not sources:
        return []
    existing_names = [e.get("name") for e in existing_spines if e.get("name")]
    schema = _schema(existing_names)
    res = call(_prompt(sources, existing_spines), schema)
    if not res or not isinstance(res, dict):
        return []
    out = []
    for a in res.get("assignments", []):
        if a.get("source_id") is None or not a.get("spine_name"):
            continue
        out.append({"source_id": a["source_id"], "spine_name": a["spine_name"],
                    "situation_type": a.get("situation_type", "")})
    return out
