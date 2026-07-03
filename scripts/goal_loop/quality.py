"""브리핑 콘텐츠(data dict) 품질 비평·개선. Gemini는 주입식(gemini_fn)."""
import json, re

CHECKLIST = [
    "수치 포함(막연한 서술 금지)",
    "명확한 판단(양면론·'관망' 금지)",
    "날짜검증 통과",
    "출처 인용",
    "차별화 인사이트(오실레이터·수급빈집 활용)",
]

def _extract_json(s: str):
    m = re.search(r"\{.*\}", s or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def critique(data: dict, gemini_fn) -> dict:
    prompt = (
        "너는 주식 브리핑 편집장이다. 아래 브리핑 콘텐츠(JSON)를 체크리스트로 채점하라.\n"
        f"[체크리스트]\n- " + "\n- ".join(CHECKLIST) + "\n\n"
        f"[콘텐츠]\n{json.dumps(data, ensure_ascii=False)}\n\n"
        '오직 JSON만 출력: {"pass": true/false, "issues": ["미달 항목 사유", ...]}\n'
        "하나라도 미달이면 pass=false."
    )
    parsed = _extract_json(gemini_fn(prompt))
    if not isinstance(parsed, dict) or "pass" not in parsed:
        return {"pass": False, "issues": ["비평 파싱 실패"]}
    return {"pass": bool(parsed.get("pass")), "issues": list(parsed.get("issues") or [])}

def revise(data: dict, issues: list, gemini_fn) -> dict:
    prompt = (
        "아래 브리핑 콘텐츠(JSON)를 지적사항만 반영해 개선하라. 구조·키는 유지.\n"
        f"[지적]\n- " + "\n- ".join(issues) + "\n\n"
        f"[콘텐츠]\n{json.dumps(data, ensure_ascii=False)}\n\n"
        "개선된 콘텐츠를 같은 스키마의 JSON으로만 출력."
    )
    parsed = _extract_json(gemini_fn(prompt))
    return parsed if isinstance(parsed, dict) and parsed else data
