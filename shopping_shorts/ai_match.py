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
      **딴 장면(다른 물건·다른 쓰임)으로 길이를 채우지 마라** — 길이보다 그림이 먼저다.
      ★한 장면만 길게 틀지 마라: **2.5초가 넘는 줄은 서로 다른 장면(다른 컷 번호) 2개 이상**, 5초가 넘으면 3개. 같은 뜻의 다른 컷·다른 영상의
      같은 쓰임 컷으로 리듬을 줘라(2026-10-02 실측: 2.5초↑ 칸 34%가 한 장면만 이어져 같은 화면이 계속 나왔다).
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


LONG_LINE_SECS = 2.5     # 이 길이 이상인 줄은 서로 다른 장면 2개 이상(2026-10-02)


def _spare_cuts(seg_index, used, backbone_vid):
    """아직 어느 줄도 안 쓴, 쓸 수 있는 컷이 남았나(재료가 모자라면 '한 장면 더'를 요구하지 않는다)."""
    return any(_usable(seg_index, c, backbone_vid) for c in seg_index if c not in used)


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
        # ★긴 줄 한 장면(2026-10-02 사장님 "같은 장면 계속 / 화면 모자라 멈춤"): 2.5초↑ 줄에 다른 컷이 1개뿐이면 다시 묻는다.
        #   실측 24시간 687칸 중 2.5초↑인데 한 장면만 이어진 칸 237(34%). 남은 쓸 컷이 없으면(재료 부족) 묻지 않는다.
        if need >= LONG_LINE_SECS and len({c for c in cs if c in seg_index}) == 1 and _spare_cuts(seg_index, used, backbone_vid):
            why.append("%.1f초 줄에 장면 1개 — 다른 장면 1개 이상 더" % need)
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


ONLY = """★이번엔 **%s번 줄만** 골라라. 다른 줄은 이미 장면이 정해져 있고(컷 목록에서 이미 뺐다) 그 줄들은 출력하지 마라.
대본 전체는 흐름을 읽으라고 보여주는 것이다 — 앞뒤 줄과 같은 그림이 되지 않게 고른다."""


def match(lines, seg_index, backbone_vid, note=None, model=None, product="", only=None):
    """lines: [{role, text, sub}] → [{"role","seg","segs"}] (assign_cuts와 같은 모양). 실패면 [].
    only=[줄번호(0부터)]: 그 줄만 고른다(3단계 「채우기」, 2026-10-01 사장님 "채우기를 같은 함수로") — 나머지 줄은 빈 segs."""
    from shopping_shorts.backbone_assemble import _secs, MIN_CUT_SECS
    order = sorted(seg_index, key=lambda s: (seg_index[s].get("vid") or "", s))
    lb = "\n".join("  %d. [%s] (%.1f초) %s" % (i + 1, L.get("role") or "", _secs(L["text"]), L["text"]) for i, L in enumerate(lines))
    cut_txt = _cut_block(seg_index, backbone_vid, order)
    only = sorted({int(i) for i in (only or []) if 0 <= int(i) < len(lines)}) or None
    prompt = "%s\n%s\n[주제] 이 영상이 파는 것: %s\n\n[대본]\n%s\n\n[컷 목록] 번호 | 영상 | 길이 | 화면 | 쓰임 | 소구점 | 종류 | 훅 | 속도\n%s" % (
        BRIEF, ("\n" + ONLY % ", ".join(str(i + 1) for i in only) + "\n") if only else "",
        product or "(제품명 미상 — 대본에서 읽어라)", lb, cut_txt)
    out = _ask(prompt, note, model)
    picks = _parse(out, len(lines))
    if only:
        picks = {i: cs for i, cs in picks.items() if i in only}
    if not picks:
        if note is not None:
            note.setdefault("reason", "AI 매칭 응답 없음")
        return []
    if note is not None:
        note["matcher_steps"] = str((out or {}).get("steps") or "")[:400]
    # ④ 검사 → 걸린 줄만 한 번 더 묻는다(사장님 2026-10-01 "AI한테 다시 묻고 매칭해보라는 과정을 안 했나")
    bad = check(picks, lines, seg_index, backbone_vid)
    if only:
        bad = {i: w for i, w in bad.items() if i in only}
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


def apply(lines, code_bs, seg_index, backbone_vid, note=None, product=""):
    """3단계 매칭 전문가를 부르고 코드 매칭(code_bs)과 합친다 — **두 경로(백본·이야기작가)가 이 함수 하나를 부른다**(2026-10-02 사장님
    "각 단계별로 전문가가 들어가는 것": 1단계 이야기 작가 · 2단계 대본 작가 · 3단계 매칭 전문가).
    AI가 고른 줄은 AI 컷, AI가 비운 줄은 코드 매칭 컷 중 안 겹치는 것만, AI가 아예 실패하면 코드 매칭 그대로(note["matcher"]에 이유)."""
    note = note if note is not None else {}
    an = {}
    ai_bs = match(lines, seg_index, backbone_vid, note=an, product=product)
    for k in ("matcher_recheck", "matcher_left", "matcher_auth"):
        if an.get(k):
            note[k] = an[k]
    bs = [dict(b) for b in (code_bs or [])]
    if not ai_bs:
        note["matcher"] = "code(%s)" % (an.get("reason") or "")
        return bs
    used = {c for b in ai_bs for c in (b.get("segs") or [])}
    for i, b in enumerate(ai_bs):
        if i >= len(bs):
            break
        if b.get("segs"):
            bs[i] = b
        else:
            keep = [c for c in (bs[i].get("segs") or []) if c not in used]
            bs[i] = {"role": bs[i].get("role"), "seg": keep[0] if keep else "", "segs": keep}
            used.update(keep)
    note["matcher"] = "ai"
    return bs


def _order_key(sid):
    """seg_id → (영상 접두, 순번) — 1단계가 영상마다 0부터 매긴 순번(_assign_seg_ids)으로 원본 순서를 안다."""
    head, _, tail = str(sid).rpartition("-")
    try:
        return head, int(tail)
    except ValueError:
        return str(sid), 0


def ensure_cover(bs, lines, seg_index, backbone_vid, note=None):
    """★2단계 장면 보장(관제 084, 2026-10-02 사장님 "화면 모자라 멈춤 — 땜빵 말고 구조적으로"):
    줄마다 **장면 길이 합 × SLOW ≥ 대사 초**가 되게 장면을 더한다. 3단계(planClips)는 받은 장면에 시간만 나눈다.
    더하는 순서(사장님 규칙): ① 같은 의미 장면 — 그 줄 첫 장면과 같은 쓰임(label)의 안 쓴 컷(다른 영상 우선)
                            ② 원본에서 이어지는 장면 — 뒤쪽 가장 가까운 안 쓴 컷, 없으면 앞쪽
                            ③ 다른 영상의 같은 종류(기능·효과…) 컷.
    뒷컷·목록 밖·다른 줄이 쓴 컷은 안 쓴다. 끝내 모자란 줄은 note["cover_short"]에 남긴다(대사 줄이기 대상).
    bs 를 제자리에서 고치고 더한 컷 수를 돌려준다. 실측(24시간 706칸): 멈춤 126칸 중 102칸이 여기(2단계)서부터 짧았다."""
    from shopping_shorts.backbone_assemble import _secs
    used = {c for b in (bs or []) if b for c in (b.get("segs") or [])}
    by_vid = {}
    for sid in seg_index:
        by_vid.setdefault(_order_key(sid)[0], []).append(sid)
    for v in by_vid.values():
        v.sort(key=lambda x: _order_key(x)[1])
    added, short = 0, []
    for i, L in enumerate(lines or []):
        b = bs[i] if bs and i < len(bs) else None
        if not b or not (b.get("segs") or []):
            continue
        segs = [c for c in b["segs"] if c in seg_index]
        need = _secs(L.get("text") or "")
        have = lambda: sum(seg_index[c]["secs"] for c in segs)
        guard = 0
        while segs and have() * SLOW < need - 0.3 and guard < 8:
            guard += 1
            pick = None
            lab = (seg_index[segs[0]].get("label") or "")[:6]
            if lab:
                same = [c for c in seg_index if c not in used and c not in segs and _usable(seg_index, c, backbone_vid)
                        and (seg_index[c].get("label") or "")[:6] == lab]
                same.sort(key=lambda c: (seg_index[c]["vid"] == seg_index[segs[0]]["vid"], -seg_index[c]["secs"]))
                pick = same[0] if same else None
            if not pick:   # ② 원본에서 이어지는 장면 — 뒤쪽으로 가장 가까운 안 쓴 컷, 없으면 앞쪽으로 가장 가까운 컷
                head, k = _order_key(segs[-1])
                seq = by_vid.get(head) or []
                ok = lambda c: c not in used and c not in segs and _usable(seg_index, c, backbone_vid)
                pick = next((c for c in seq if _order_key(c)[1] > k and ok(c)), None)                     or next((c for c in reversed(seq) if _order_key(c)[1] < _order_key(segs[0])[1] and ok(c)), None)
            if not pick:   # ③ 다른 영상의 같은 종류(기능·효과…) 컷
                kind = seg_index[segs[0]].get("kind") or ""
                pick = next((c for c in seg_index if kind and seg_index[c].get("kind") == kind and c not in used
                             and c not in segs and _usable(seg_index, c, backbone_vid)), None)
            if not pick:
                break
            segs.append(pick); used.add(pick); added += 1
        b["segs"] = segs
        b["seg"] = segs[0] if segs else b.get("seg", "")
        if segs and have() * SLOW < need - 0.3:
            short.append(i)
    if note is not None:
        note["cover_added"] = added
        note["cover_short"] = short
    return added
