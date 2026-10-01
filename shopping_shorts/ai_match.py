# -*- coding: utf-8 -*-
"""AI 장면 매칭 — 대본 줄 전체 + 컷 목록을 **한 번에** 주고 줄마다 컷을 고르게 한다 (2026-09-22 사장님 "매칭은 AI가 해봐").
★왜: 코드 매칭은 태그의 역할·순서만 보고 뜻을 안 읽는다. "먼지가 밀려나서 다시 닦아야 했던"에 '걸레를 물에 씻는' 컷이 붙었다
  (둘 다 역할=문제). 사람(AI)은 화면 설명을 읽고 고른다.

★2026-10-01 사장님(파스타 job 4a1d44721e8a 화면: 배수구 3회·감자·인사 컷):
  · AI 를 **대본·장면 배치 최고 전문가**로 세우고, [주제]와 [대본]을 먼저 읽게 한 뒤 한 단계씩 생각해 고르게 한다(steps).
  · 컷 목록에 1단계 태그를 다 준다(화면·쓰임·대본화 소구점·종류·훅·속도). 뒷컷은 목록에서 뺀다(_usable 한 곳).
  · 장면을 다양하게(같은 영상 세 줄 연속 금지), 시간을 맞추되(합×1.2 ≥ 대사) 딴 장면으로 채우지 않는다.
  · **고른 뒤 코드가 검사**(중복·목록 밖·길이·세 줄 연속)하고 걸린 줄만 AI 에게 **한 번 더** 묻는다 — 종전엔 1회 답을 코드가 덮어쓰고 아무도 다시 안 봤다.
  실측(tools/mix_ai_match_trial.py, tools/claim_trial_results/mixtrial_4a1d44721e8a): 11줄 중 10줄 말과 같은 그림, 반복 0, 호출 1회 29초.
★코드가 하는 일: ①실재하는 컷인가 ②한 컷을 두 줄에 안 쓰나 ③시간이 차나(모자라면 같은 영상·**같은 장면(label)** 다음 컷만) ④검사→재질의.
  실패하면 [] → 호출부가 종전 코드 매칭으로 간다(조용한 폴백 아님 — note에 이유).
"""
import re
from shopping_shorts import script_generate as _sg

SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {"type": "string"},
        "picks": {"type": "array", "items": {"type": "object", "properties": {
            "line": {"type": "integer"},
            "need_pic": {"type": "string"},
            "cuts": {"type": "array", "items": {"type": "string"}},
            "have": {"type": "number"},
            "need": {"type": "number"},
            "why": {"type": "string"},
        }, "required": ["line", "cuts"]}}},
    "required": ["picks"],
}

BRIEF = """너는 쇼핑 쇼츠에서 **대본과 장면을 딱 맞게 배치하는 최고 전문가**다. 수천 편을 편집했고, 말과 그림이 한 박자라도
어긋나면 시청자가 바로 이탈한다는 걸 안다. 네 기준은 하나다 — **그 줄이 읽히는 동안 화면에 그 말이 보이는가.**
서두르지 마라. 시간이 걸려도 **한 단계씩 생각하고** 그 생각을 steps 에 적은 뒤에 고른다.

1단계 — 읽기: [주제]와 [대본]을 처음부터 끝까지 읽고 이 영상이 무엇을 파는지, 줄마다 시청자에게 **무엇을 보여줘야 설득되는지** 정하라.
   줄마다 "필요한 그림"을 한 구절로 적는다(예: 미끼 줄 → 냄비 앞에서 고생하는 모습 / 배수 줄 → 용기 기울여 물 빠지는 순간).
2단계 — 재료 파악: [컷 목록]을 전부 훑어 어떤 그림이 있고 없는지, 어느 영상에 무엇이 있는지 정리하라. 컷마다 1단계 태깅이 있다:
   번호 | 영상 | 길이 | 화면에 보이는 것 | 쓰임 | 소구점(이 장면 위에 읽힐 말) | 종류 | 훅 | 속도.
3단계 — 배치: 줄마다 고른다.
   a. **말과 같은 그림**이 1순위. 소구점 문장이 줄의 뜻과 가까우면 그 컷.
   b. 줄 유형별
      - [훅] 첫 줄: 훅 표시(클로즈업/반전/비포애프터/충격)가 있는 제품 컷. 제품이 또렷해야 한다.
      - [미끼]·불편을 말하는 줄: 종류가 '문제'인 컷(제품 없이 불편·기존 방식). **없으면 cuts를 비우고 why에 "문제 장면 없음"**.
        제품 시연 컷으로 때우지 마라 — 틀린 그림은 빈 화면보다 나쁘다.
      - [공개] "이건 바로 X": 제품 전체가 또렷이 보이는 컷.
      - 기능·결과 줄: 그 기능을 **하고 있는 순간**(배수 줄엔 물 빠지는 장면, 전자레인지 줄엔 넣고 돌리는 장면, 계량 줄엔 계량하는 손).
      - [반전]·충격 포인트 줄: 훅 '충격'·'반전' 컷이 있으면 그것.
      - [마무리]·CTA: 완성품·제품 전체 컷. 인사·채널 화면은 안 된다.
      - ★줄의 **주인공**을 찍어라: "A가 아니라 B" · "A와 달리 B"에서 화면은 **B(제품이 하는 일)**다. 부정된 A(버리는 청소포, 기존 걸레)는
        그 줄이 불편 자체를 말할 때만 쓴다.
   c. **장면을 다양하게.** 같은 그림이 여러 영상에 있으면 **앞 줄과 다른 영상**의 컷을 골라 화면이 계속 바뀌게 하라.
      한 영상의 컷이 연달아 세 줄 이상 가지 않게. 같은 컷·같은 장면을 두 줄에 쓰지 마라.
   d. **시간을 맞춰라.** 줄마다 고른 컷 길이 합 × 1.2 ≥ 대사 초가 되게 하고, have(합)·need(대사 초)를 적어라.
      모자라면 같은 영상의 **같은 쓰임** 컷을 이어 붙이고, 그래도 모자라면 다른 영상의 같은 뜻 컷을 더한다.
      **딴 장면(다른 물건·다른 쓰임)으로 길이를 채우지 마라** — 길이보다 그림이 먼저다. 긴 줄(5초↑)은 2~3컷으로 나눠 리듬을 줘라.
   e. 씨앗 영상(표시됨)의 컷은 쓰지 마라. 목록에 없는 번호를 만들지 마라.
4단계 — 점검: 다 고른 뒤 전체를 다시 보며 ①중복 컷 ②길이 부족 ③세 줄 연속 같은 영상 을 스스로 잡아 고쳐라.

출력 JSON만:
{"steps": "1단계·2단계·4단계에서 생각한 것(각 2~3문장)",
 "picks": [{"line": 1, "need_pic": "이 줄에 필요한 그림", "cuts": ["번호", "번호"], "have": 초, "need": 초, "why": "화면에 무엇이 보여서(15자 안팎)"}]}
줄을 빠짐없이, 줄 순서대로."""

RETRY = """아래 줄들은 앞선 배정에 문제가 있었다. **그 줄만** 다시 골라라(다른 줄의 컷은 그대로 두니 그 컷들은 쓰지 마라).
문제와 쓸 수 없는 컷을 적어 두었다. 같은 규칙(말과 같은 그림, 한 컷 한 줄, 길이, 다양하게)으로. 맞는 컷이 정말 없으면 cuts를 비워라.
출력 JSON만: {"picks":[{"line":N,"cuts":[...],"why":"..."}]}

[다시 고를 줄]
%s

[쓸 수 없는 컷(다른 줄이 씀)]
%s
"""
MODEL = "gemini-3.5-flash"     # 매칭은 뜻을 읽는 일이라 한 단계 위 모델. 실패하면 _call_json이 기본 모델로 가지 않는다 — note에 남는다.
SLOW = 1.2                     # 늦춰 채우는 폭 — config.MAX_SLOWMO 와 같은 뜻(여기선 '길이가 모자란가' 판정에만 쓴다)


def _usable(seg_index, sid, backbone_vid):
    """AI 에게 보여 주고 AI 가 고를 수 있는 컷인가 — **한 곳**(목록·검증·채우기가 같은 판정을 쓴다, 0순위-B).
    뒷컷(seg_index['outro'] = 1단계 is_outro 이면서 제품 안 보임, backbone_assemble._seg_index 가 정함)은 여기서 빠진다
    (2026-10-01 실측 work 9bf4c5929d3d: AI 가 '엄지 치켜세우며 인사' 컷을 훅·마무리 줄에 붙였다 — assign_cuts 는 뺐는데 AI 는 몰랐다)."""
    from shopping_shorts.backbone_assemble import MIN_CUT_SECS      # match() 와 같은 지연 import(순환 방지)
    v = seg_index.get(sid) or {}
    return bool(v) and v.get("vid") != backbone_vid and v.get("secs", 0) >= MIN_CUT_SECS and not v.get("outro")


def _cut_block(seg_index, backbone_vid, order):
    rows = []
    for sid in order:
        if not _usable(seg_index, sid, backbone_vid):
            continue
        v = seg_index[sid]
        rows.append("  %s | %s | %.1f초 | %s | 쓰임:%s | 소구점:%s | 종류:%s | 훅:%s | 속도:%s" % (
            sid, v.get("vid"), v.get("secs", 0), (v.get("desc") or "")[:60], v.get("label") or "-", (v.get("use") or "")[:40] or "-",
            v.get("kind") or "-", v.get("hook") or "-", v.get("tempo") or "-"))
    return "\n".join(rows)


def _secs_of(text):
    from shopping_shorts.backbone_assemble import _secs
    return _secs(text)


def check(picks, lines, seg_index, backbone_vid):
    """코드 검사 — {줄번호(0부터): 이유}. 중복·목록 밖(뒷컷 포함)·길이 부족·같은 영상 세 줄 연속."""
    bad, used = {}, {}
    for i, L in enumerate(lines):
        cs = picks.get(i, [])
        need = _secs_of(L["text"])
        why = []
        for c in cs:
            if not _usable(seg_index, c, backbone_vid):
                why.append("목록 밖 %s" % c)
            elif c in used and used[c] != i:
                why.append("중복 %s(줄%d)" % (c, used[c] + 1))
            else:
                used[c] = i
        have = sum(seg_index[c]["secs"] for c in cs if c in seg_index)
        if cs and need and have * SLOW < need - 0.3:
            why.append("길이 %.1f×%.1f < %.1f" % (have, SLOW, need))
        if why:
            bad[i] = "; ".join(why)
    vids = [sorted({seg_index[c]["vid"] for c in picks.get(i, []) if c in seg_index}) for i in range(len(lines))]
    for i in range(2, len(lines)):
        if vids[i] and len(vids[i]) == 1 and vids[i] == vids[i - 1] == vids[i - 2] and i not in bad:
            bad[i] = "같은 영상 %s 세 줄 연속" % vids[i][0]
    return bad


def _ask(prompt, note, model):
    """버텍스 스위치가 켜졌으면 버텍스 1회, 아니면 키풀 — 종전 경로 그대로. 빈 응답은 {}."""
    import json
    from shopping_shorts import vertex_route

    def _vertex(cl, m):
        from google.genai import types
        resp = cl.models.generate_content(
            model=m, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=SCHEMA))
        return json.loads(resp.text)
    _ok, out = vertex_route.try_call("ai_match", _vertex, what="장면매칭")
    if _ok:
        if note is not None:
            note["matcher_auth"] = "vertex"
        return out or {}
    return _sg._call_json(prompt, SCHEMA, note=note, model=model or MODEL, vertex=False) or {}


def _parse(out, n_lines):
    picks = {}
    for p in (out or {}).get("picks") or []:
        try:
            i = int(p.get("line")) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < n_lines:
            picks[i] = [str(c).strip() for c in (p.get("cuts") or [])]
    return picks


def match(lines, seg_index, backbone_vid, note=None, model=None, product=""):
    """lines: [{role, text, sub}] → [{"role","seg","segs"}] (assign_cuts와 같은 모양). 실패면 []."""
    from shopping_shorts.backbone_assemble import _secs, MIN_CUT_SECS
    order = sorted(seg_index, key=lambda s: (seg_index[s].get("vid") or "", s))
    lb = "\n".join("  %d. [%s] (%.1f초) %s" % (i + 1, L.get("role") or "", _secs(L["text"]), L["text"]) for i, L in enumerate(lines))
    cut_txt = _cut_block(seg_index, backbone_vid, order)
    prompt = "%s\n\n[주제] 이 영상이 파는 것: %s\n\n[대본]\n%s\n\n[컷 목록] 번호 | 영상 | 길이 | 화면 | 쓰임 | 소구점 | 종류 | 훅 | 속도\n%s" % (
        BRIEF, product or "(제품명 미상 — 대본에서 읽어라)", lb, cut_txt)
    out = _ask(prompt, note, model)
    picks = _parse(out, len(lines))
    if not picks:
        if note is not None:
            note.setdefault("reason", "AI 매칭 응답 없음")
        return []
    if note is not None:
        note["matcher_steps"] = str((out or {}).get("steps") or "")[:400]
    # ④ 검사 → 걸린 줄만 한 번 더 묻는다(사장님 2026-10-01 "AI한테 다시 묻고 매칭해보라는 과정을 안 했나")
    bad = check(picks, lines, seg_index, backbone_vid)
    if bad:
        if note is not None:
            note["matcher_recheck"] = {str(i + 1): w for i, w in bad.items()}
        blocked = sorted({c for i, cs in picks.items() if i not in bad for c in cs})
        again = "\n".join("  %d. [%s] (%.1f초) %s — 문제: %s" % (i + 1, lines[i].get("role") or "", _secs(lines[i]["text"]), lines[i]["text"], w)
                          for i, w in bad.items())
        out2 = _ask(RETRY % (again, ", ".join(blocked) or "(없음)") + "\n\n[컷 목록]\n" + cut_txt, note, model)
        for i, cs in _parse(out2, len(lines)).items():
            if i in bad:
                picks[i] = cs
        left = check(picks, lines, seg_index, backbone_vid)
        if note is not None:
            note["matcher_left"] = {str(i + 1): w for i, w in left.items()}
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
            if _usable(seg_index, c, backbone_vid) and c not in used and (seg_index[c].get("desc") or c) not in descs:
                chosen.append(c); used.add(c); have += seg_index[c]["secs"]; descs.add(seg_index[c].get("desc") or c)
        # ③ 모자라면 고른 컷과 같은 영상의 **다음 컷**으로 채운다 — 단 같은 장면(label 같음)일 때만
        if chosen and have * SLOW < need:
            vid = seg_index[chosen[-1]]["vid"]
            lst = by_video.get(vid) or []
            k = lst.index(chosen[-1]) + 1 if chosen[-1] in lst else len(lst)
            _lab = (seg_index[chosen[-1]].get("label") or "").strip()
            while have * SLOW < need and k < len(lst):
                s = lst[k]; k += 1
                if s in used or not _usable(seg_index, s, backbone_vid) or (seg_index[s].get("desc") or s) in descs:
                    continue
                # ★다음 컷이 **같은 장면**(1단계 label 같음)일 때만 — 배수구 0.8초 다음이 '감자 결과 확인'이라 감자가 붙었다
                #   (2026-10-01 사장님 "감자가 무슨 태깅이길래", job 4a1d44721e8a). 같은 장면이 아니면 멈추고 코드 채우기에 맡긴다.
                if _lab and (seg_index[s].get("label") or "").strip() != _lab:
                    break
                chosen.append(s); used.add(s); have += seg_index[s]["secs"]; descs.add(seg_index[s].get("desc") or s)
        out_bs.append({"role": L.get("role") or "", "seg": chosen[0] if chosen else "", "segs": chosen,
                       "why": next((p.get("why") for p in (out.get("picks") or []) if p.get("line") == i + 1), "")})
    return out_bs
