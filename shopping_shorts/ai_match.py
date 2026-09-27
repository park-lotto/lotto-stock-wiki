# -*- coding: utf-8 -*-
"""AI 장면 매칭 — 대본 줄 전체 + 컷 목록을 **한 번에** 주고 줄마다 컷을 고르게 한다 (2026-09-22 사장님 "매칭은 AI가 해봐").

★왜: 코드 매칭은 태그의 역할·순서만 보고 뜻을 안 읽는다. "먼지가 밀려나서 다시 닦아야 했던"에 '걸레를 물에 씻는' 컷이 붙었다
  (둘 다 역할=문제). 사람(AI)은 화면 설명을 읽고 고른다.
★코드가 하는 일은 셋뿐: ①실재하는 컷인가 ②한 컷을 두 줄에 안 쓰나 ③시간이 차나(모자라면 같은 영상 다음 컷으로 채움).
  호출 1회. 실패하면 [] → 호출부가 종전 코드 매칭으로 간다(조용한 폴백 아님 — note에 이유).
"""
import re

from shopping_shorts import script_generate as _sg

SCHEMA = {
    "type": "object",
    "properties": {"picks": {"type": "array", "items": {"type": "object", "properties": {
        "line": {"type": "integer"},
        "cuts": {"type": "array", "items": {"type": "string"}},
        "why": {"type": "string"},
    }, "required": ["line", "cuts"]}}},
    "required": ["picks"],
}

BRIEF = """너는 숏폼 편집자다. 대본 줄마다 **그 말과 같은 그림**인 컷을 고른다.

규칙
- 줄의 뜻을 읽어라. 불편을 말하는 줄엔 그 불편이 **보이는** 컷(기존 방식·before·문제), 해결·결과 줄엔 제품이 그 일을 **하는** 컷, 공개("이건 바로 X")엔 제품이 또렷이 보이는 컷.
- 한 컷은 한 줄에만. 앞 줄이 쓴 컷은 쓰지 마라.
- 줄마다 컷 길이 합이 대사 초 이상이 되게 1~4개. 짧은 줄(3초 이하)은 1개.
- 컷 목록에 없는 번호를 만들지 마라. 맞는 컷이 없으면 cuts를 비워라(코드가 채운다).
- 씨앗 영상(표시됨)의 컷은 쓰지 마라.
- ★줄의 **주인공**을 찍어라: "A가 아니라 B" · "A와 달리 B"에서 화면은 **B(제품이 하는 일)**다. 부정된 A(버리는 청소포, 기존 걸레)는
  그 줄이 불편 자체를 말할 때만 쓴다. 결과·반전·마무리 줄에 A를 넣지 마라(2026-09-22 사장님: "물티슈 버리는 게 아니라 제품을 계속 쓴다는 건데").
- why는 한 줄(10자 안팎)."""

MODEL = "gemini-3.5-flash"     # 매칭은 뜻을 읽는 일이라 한 단계 위 모델(호출 1회). 실패하면 _call_json이 기본 모델로 가지 않는다 — note에 남는다.


def _cut_block(seg_index, backbone_vid, order):
    rows = []
    for sid in order:
        v = seg_index.get(sid) or {}
        if v.get("vid") == backbone_vid or v.get("secs", 0) < 0.8:
            continue
        rows.append("  %s | %s | %.1f초 | [%s] %s" % (sid, v.get("vid"), v.get("secs", 0), v.get("role") or "", (v.get("desc") or "")[:70]))
    return "\n".join(rows)


def match(lines, seg_index, backbone_vid, note=None, model=None):
    """lines: [{role, text, sub}] → [{"role","seg","segs"}] (assign_cuts와 같은 모양). 실패면 []."""
    from shopping_shorts.backbone_assemble import _secs, MIN_CUT_SECS
    order = sorted(seg_index, key=lambda s: (seg_index[s].get("vid") or "", s))
    lb = "\n".join("  %d. [%s] (%.1f초) %s" % (i + 1, L.get("role") or "", _secs(L["text"]), L["text"]) for i, L in enumerate(lines))
    prompt = "%s\n\n[대본]\n%s\n\n[컷 목록] 번호 | 영상 | 길이 | [역할] 화면\n%s" % (BRIEF, lb, _cut_block(seg_index, backbone_vid, order))
    # ★Vertex 먼저(2026-09-25, 스위치 켠 계정만) — 실패하면 종전 키풀(_call_json) 그대로.
    from shopping_shorts import vertex_route

    def _vertex(cl, m):
        import json
        from google.genai import types
        resp = cl.models.generate_content(
            model=m, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json",
                                               response_schema=SCHEMA))
        return json.loads(resp.text)
    _ok, out = vertex_route.try_call("ai_match", _vertex, what="장면매칭")
    if _ok:
        if note is not None:
            note["matcher_auth"] = "vertex"
    else:
        out = _sg._call_json(prompt, SCHEMA, note=note, model=model or MODEL, vertex=False) or {}
    picks = {}
    for p in out.get("picks") or []:
        try:
            i = int(p.get("line")) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(lines):
            picks[i] = [str(c).strip() for c in (p.get("cuts") or [])]
    if not picks:
        if note is not None:
            note.setdefault("reason", "AI 매칭 응답 없음")
        return []
    used = set()
    by_video = {}
    for sid in order:
        by_video.setdefault(seg_index[sid].get("vid"), []).append(sid)
    out_bs = []
    for i, L in enumerate(lines):
        need = _secs(L["text"])
        chosen, have = [], 0.0
        descs = set()          # 태깅이 한 샷을 둘로 가른 것(설명이 같음)은 한 줄에 한 번만 — "중복 장면"의 뿌리(show8: s3 11.8/13.9, s7 19.0/21.1)
        for c in picks.get(i, []):
            if c in seg_index and c not in used and seg_index[c]["vid"] != backbone_vid and seg_index[c]["secs"] >= MIN_CUT_SECS                     and (seg_index[c].get("desc") or c) not in descs:
                chosen.append(c); used.add(c); have += seg_index[c]["secs"]; descs.add(seg_index[c].get("desc") or c)
        # ③ 모자라면 고른 컷과 같은 영상의 **다음 컷**으로 채운다(원본은 연속 촬영 — 결이 안 튄다)
        if chosen and have < need:
            vid = seg_index[chosen[-1]]["vid"]
            lst = by_video.get(vid) or []
            k = lst.index(chosen[-1]) + 1 if chosen[-1] in lst else len(lst)
            while have < need and k < len(lst):
                s = lst[k]; k += 1
                if s in used or seg_index[s]["secs"] < MIN_CUT_SECS or (seg_index[s].get("desc") or s) in descs:
                    continue
                chosen.append(s); used.add(s); have += seg_index[s]["secs"]; descs.add(seg_index[s].get("desc") or s)
        out_bs.append({"role": L.get("role") or "", "seg": chosen[0] if chosen else "", "segs": chosen,
                       "why": next((p.get("why") for p in (out.get("picks") or []) if p.get("line") == i + 1), "")})
    return out_bs
