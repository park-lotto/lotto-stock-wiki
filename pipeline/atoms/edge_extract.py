"""LLM 정밀 관계 엣지 추출 (Phase2 Increment 2).

atom content에서 기업/종목 간 '명시적' 관계(납품·협력·자회사·고객·경쟁)를 저가 Gemini로
추출해 atom_edges에 근거원자(source_atom_id)와 함께 저장한다. 섹터 동종(Inc1)보다
정밀한 연계 귀속을 가능케 한다. 추측 금지 — 텍스트에 명시된 관계만(환각 방지).

파서(parse_edges_response)와 조립(extract_edges_from_atom)은 generate_fn 주입으로
Gemini 없이 테스트 가능. run_extraction만 실제 key_vault 클라이언트를 쓴다(쿼터 가드).
"""
import json
import time

from pipeline.atoms import db as _db
from pipeline.atoms import edges as _edges

_GEMINI_MODEL = "gemini-3.1-flash-lite"
_GROUP = "ingest"
_VALID_TYPES = {"supply", "partner", "subsidiary", "customer", "competitor"}

_EDGE_PROMPT = """다음 텍스트에서 기업/종목 간 '명시적' 관계만 추출하라. 텍스트에 분명히 적힌 것만 — 추측·상식 보완 금지.
관계 유형: supply(납품/공급), partner(협력/제휴), subsidiary(자회사/지분), customer(고객사), competitor(경쟁).
JSON 배열만 출력: [{{"src":"A","dst":"B","type":"supply","confidence":0.0~1.0}}]. 관계 없으면 [].
텍스트: {text}"""


def parse_edges_response(text: str, source_atom_id: str) -> list:
    """Gemini 응답 텍스트 → 엣지 dict 리스트(순수). 잘못된 형식은 조용히 버린다."""
    if not text:
        return []
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t.strip("`")
        if t.startswith("json"):
            t = t[4:]
    try:
        data = json.loads(t)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for e in data:
        if not isinstance(e, dict):
            continue
        src, dst, typ = e.get("src"), e.get("dst"), e.get("type")
        if not src or not dst or typ not in _VALID_TYPES or src == dst:
            continue
        conf = e.get("confidence")
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = 0.5
        out.append({"src": src, "dst": dst, "relation_type": typ,
                    "source_atom_id": source_atom_id, "confidence": conf})
    return out


def extract_edges_from_atom(atom: dict, generate_fn=None) -> list:
    """한 atom에서 관계 엣지 추출. generate_fn(prompt)->text 주입 시 Gemini 미사용."""
    content = (atom or {}).get("content")
    if not content:
        return []
    prompt = _EDGE_PROMPT.format(text=content)
    if generate_fn is None:
        generate_fn = _gemini_generate
    text = generate_fn(prompt)
    return parse_edges_response(text, atom.get("id"))


def _gemini_generate(prompt: str) -> str:
    """실제 key_vault Gemini 호출(쿼터 시 키 로테이션/대기)."""
    from pipeline.atoms import key_vault
    from google.genai import types
    for _attempt in range(6):
        try:
            resp = key_vault.get_client(_GROUP).models.generate_content(
                model=_GEMINI_MODEL, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"))
            return resp.text
        except Exception as e:  # noqa: BLE001
            m = str(e)
            if any(c in m for c in ("429", "RESOURCE_EXHAUSTED")):
                if ("PerDay" in m or "limit: 500" in m) and key_vault.rotate(_GROUP):
                    continue
                time.sleep(62)
                continue
            raise
    return "[]"


def run_extraction(days: int = 3, limit: int = 20, generate_fn=None) -> int:
    """최근 atom에서 관계 엣지를 추출해 atom_edges에 저장. 반환=삽입한 엣지 수."""
    _edges.init_edges()
    atoms = _db.query_atoms(days=days, limit=limit, active_only=True)
    n = 0
    for atom in atoms:
        for e in extract_edges_from_atom(atom, generate_fn=generate_fn):
            _edges.insert_edge(e["src"], e["dst"], e["relation_type"], "llm",
                               source_atom_id=e["source_atom_id"], confidence=e["confidence"])
            n += 1
    return n
