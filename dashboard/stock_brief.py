"""종목 브리프 종합 — 발언 묶음을 **구조화 슬롯**으로만 뽑는다.

## 왜 슬롯인가 (2026-06-22 사고에서 배운 것)

앞선 종합엔진(`pipeline/atoms/synth_engine.py`)은 LLM에게 **페이지 전문을 다시 쓰게** 했다.
그 결과 에이전트가 stdout에 잡담을 섞거나 변경요약문만 반환해 **골드 페이지를 파괴**했고
(삼성전자 건), 그 경로는 폐기됐다. 수율 14%에서 멈춘 프로토타입의 진짜 원인이 이것이다.

그래서 여기서는 **LLM이 화면을 만들지 않는다.** 정해진 칸(일정/판단/쟁점/조건)에 들어갈
값만 JSON으로 받아오고, 화면은 코드가 그린다. 파싱이 실패하면 그 칸만 비고
나머지(원문 발언·수급 숫자)는 그대로 살아 있다 — 파괴가 원천적으로 불가능하다.

각 항목은 근거가 된 발언의 `id`를 들고 온다. 화면이 그 id로 원문을 되짚어 보여준다.
"""
from __future__ import annotations

import json
import re

# 프롬프트에 넣을 발언 수 상한. 너무 많으면 토큰만 먹고 정확도는 안 오른다.
MAX_ATOMS = 90
_CONTENT_CLIP = 200


def build_prompt(q: str, atoms: list[dict], flow: dict, vacuum: dict | None) -> str:
    """발언 묶음 + 수급 숫자 → 슬롯 추출 프롬프트."""
    lines = []
    for a in atoms[:MAX_ATOMS]:
        body = (a.get("content") or "").replace("\n", " ")[:_CONTENT_CLIP]
        meta = f"{a.get('date','')} {a.get('src','')}/{a.get('who','')}"
        extra = ""
        if a.get("tp"):
            extra += f" 목표가 {a['tp']}"
        if a.get("opinion"):
            extra += f" {a['opinion']}"
        lines.append(f"[{a.get('id')}] {meta}{extra} :: {body}")

    flow_txt = "수급 자료 없음"
    rows = (flow or {}).get("rows") or []
    if rows:
        parts = [f"{r['name']} 5일 {r['w5']:+,}억 / 20일 {r['w20']:+,}억" for r in rows]
        flow_txt = " · ".join(parts)
        if flow.get("close"):
            flow_txt = f"종가 {flow['close']:,}원({flow.get('change',0):+,}) · " + flow_txt

    vac_txt = "빈집 자료 없음"
    if vacuum:
        g = vacuum.get("grade") or "등급 미산출"
        vac_txt = f"수급빈집 {g} · 추세 {vacuum.get('trend') or '—'}"

    return f"""너는 증권 데이터 분석가다. 아래는 「{q}」에 대해 실제로 수집된 발언들과 수급 숫자다.
이걸 읽고 **정해진 칸에 들어갈 값만** JSON으로 뽑아라.

[규칙]
- 자료에 없는 사실을 만들어내지 마라. 근거가 없으면 그 칸을 비워라(빈 배열).
- 모든 항목에 근거가 된 발언 id를 `ids` 배열로 달아라.
  id는 아래 목록의 대괄호 안 값을 **글자 그대로** 옮겨 적는다(예: atom_tg_031c54a3eec9).
  목록에 없는 id를 만들어내지 마라.
- 문장은 한국어 평서문. 짧고 구체적으로. 양쪽을 다 맞다고 하는 얼버무림 금지.
- 수치는 자료에 적힌 그대로 쓴다. 반올림하거나 바꾸지 마라.

[수급]
{flow_txt}
{vac_txt}

[발언 {len(lines)}건]
{chr(10).join(lines)}

[뽑을 것 — 아래 JSON 형식 그대로, 설명 없이 JSON만 출력]
{{
  "verdict": "지금 상황 한 문장. 발언과 수급을 합쳐서. 40자 내외",
  "grounds": [
    {{"text": "판단 근거 한 줄", "sign": 1, "ids": ["atom_xxxx", "atom_yyyy"]}}
  ],
  "schedule": [
    {{"when": "8월 26일", "title": "행사·이벤트 이름", "detail": "무엇이 있나 한두 줄", "ids": ["atom_xxxx"]}}
  ],
  "debate": {{
    "topic": "지금 갈리는 쟁점 한 줄",
    "a_label": "한쪽 주장 이름", "a": [{{"text": "주장", "ids": ["atom_xxxx"]}}],
    "b_label": "반대쪽 주장 이름", "b": [{{"text": "주장", "ids": ["atom_yyyy"]}}],
    "pivot": "양쪽 차이의 핵심이 무엇인지 한두 줄"
  }},
  "risks": [
    {{"text": "이 판단이 틀리는 조건", "ids": ["atom_zzzz"]}}
  ]
}}

- grounds의 sign: 강세 근거면 1, 약세면 -1, 중립이면 0
- schedule: **앞으로 있을 일정**만. 이미 지난 일은 넣지 마라. 없으면 빈 배열
- debate: 실제로 반대 의견이 있을 때만. 없으면 topic을 빈 문자열로
"""


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def parse(text: str) -> dict:
    """LLM 응답 → 슬롯 dict. 실패하면 빈 슬롯(화면은 원문으로 살아남는다)."""
    empty = {"verdict": "", "grounds": [], "schedule": [],
             "debate": {}, "risks": [], "ok": False}
    if not text:
        return empty
    m = _JSON_BLOCK.search(text)
    if not m:
        return empty
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return empty
    if not isinstance(d, dict):
        return empty

    def _list(key):
        v = d.get(key)
        return v if isinstance(v, list) else []

    return {
        "verdict": str(d.get("verdict") or "")[:200],
        "grounds": _list("grounds")[:6],
        "schedule": _list("schedule")[:6],
        "debate": d.get("debate") if isinstance(d.get("debate"), dict) else {},
        "risks": _list("risks")[:6],
        "ok": True,
    }
