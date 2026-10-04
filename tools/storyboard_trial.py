# -*- coding: utf-8 -*-
"""[서버용·읽기 전용] 장면 먼저 → 스토리보드 시험 (2026-10-04 사장님 "분석부터 매칭까지 이 화면 전체", 3.6).

  ① 장면 목록(1단계): 모든 조각을 "무엇을 보여 주나"로 묶는다(빠지는 조각 0 — 모델이 빠뜨리면 코드가 '기타'로) +
     조각별 쓰임 표시(훅감·비포·애프터·반전·반응) + 재료 종류 + 없는 장면
  ② 스타일 추천(2단계): 승인 스타일을 칸 구조가 같은 것끼리 묶어, 재료 종류에 맞는 판 + 칸마다 맞는 쓰임 장면이 있나로 4개
  ③ 스토리보드(2단계): 추천 1·2위 각각 — 칸 목록·칸별 첫 줄/문장 틀(templates)·말투(voice)를 그대로 주고, ⭐꼭 쓰기 장면은 반드시 넣게
  ③-2 검수: **제품 사실을 지어냈나만** 본다(화면에 없는 가격·숫자·기능). 스타일이 요구하는 화면 밖 이야기(가족 반응·전문가 출처·댓글 유도)는 허용
  ④ 코드 검사: 없는 컷 번호·칸끼리 겹침·길이(컷 합×1.2 < 문장)·화면에 없는 숫자·빈칸 틀
  모델 호출: ①1 + ②1 + (③1 + ③-2 1) × 스타일 2개 = 6번. script_generate._call_json(vertex=True) = gemini-3.6-flash. DB 무변경.

    set -a && . /etc/shopping-shorts.env && set +a && cd /home/ubuntu/lotto-stock-wiki
    python3 tools/storyboard_trial.py f3d86941c30b:49ef-6,1e75-3 9fed785a6af4:32b1-2,dccd-3      # 작업:⭐꼭 쓰기 조각(끝자리)
"""
import json
import os
import re
import sqlite3
import sys
import time

sys.path.insert(0, os.getcwd())
from shopping_shorts import script_generate as sg            # noqa: E402
from shopping_shorts.edit_plan import narr_secs                # noqa: E402

DB = "shopping_shorts/data/reference.db"
TAGS = ("훅감", "비포", "애프터", "반전", "반응")

S1 = {"type": "object", "properties": {
    "kind": {"type": "string"},
    "groups": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"}, "desc": {"type": "string"}, "ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["name", "ids"]}},
    "tags": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}}, "required": ["id", "tags"]}},
    "missing": {"type": "array", "items": {"type": "string"}}},
    "required": ["kind", "groups", "tags", "missing"]}

S2 = {"type": "object", "properties": {"styles": {"type": "array", "items": {"type": "object", "properties": {
    "family": {"type": "integer"}, "pan": {"type": "string"}, "filled": {"type": "integer"}, "total": {"type": "integer"},
    "note": {"type": "string"}}, "required": ["family", "filled", "total"]}}}, "required": ["styles"]}

S3 = {"type": "object", "properties": {
    "first_line_style": {"type": "string"},
    "slots": {"type": "array", "items": {"type": "object", "properties": {
        "slot": {"type": "string"}, "need": {"type": "string"}, "ids": {"type": "array", "items": {"type": "string"}},
        "line": {"type": "string"}, "weak": {"type": "string"}}, "required": ["slot", "ids", "line"]}}},
    "required": ["slots"]}

S4 = {"type": "object", "properties": {"fix": {"type": "array", "items": {"type": "object", "properties": {
    "i": {"type": "integer"}, "why": {"type": "string"}, "line": {"type": "string"}}, "required": ["i", "line"]}}}, "required": ["fix"]}

P1 = """너는 쇼핑 쇼츠 **영상 추출·분석 전문가**다. 아래는 담은 영상들의 조각 태그다(조각 번호 | 길이 | 화면 설명 | 쓰임 | 소구점).
대본을 쓰기 **전에**, 이 재료에 어떤 장면이 있는지 한눈에 보이게 정리하라.
1) kind: 재료 종류 하나 — 레시피 / 홈템 / 뷰티 / 가전 / 생활용품 / 장비템 / 기타
2) groups: "무엇을 보여 주나"가 같은 조각끼리 5~10묶음. name 은 이모지 하나 + 짧은 이름, desc 는 한 구절.
   ★목록의 조각 **전부**를 어느 한 묶음에 넣어라(빠뜨리지 마라, 한 조각은 한 묶음에만). 묶음 안 순서는 대표 조각부터.
3) tags: 대본 흐름에서 쓰일 수 있는 조각에 쓰임 표시 — 훅감(첫 장면으로 잡아 끌 그림) / 비포(불편·기존 방식·문제) /
   애프터(결과·완성) / 반전(예상 밖·딴 용도·충격 포인트) / 반응(사람의 반응·시식·놀람). 해당 없는 조각은 넣지 마라.
4) missing: 쇼츠 대본에 흔히 쓰는데 이 재료에는 없는 장면 2~4개.
출력 JSON만.

[조각 목록]
%s
"""

P2 = """너는 수천 편을 쓴 쇼핑 쇼츠 **영상 대본 작가 겸 편집자**다. 아래가 이 재료에 있는 장면 전부다.
[재료 종류] %s
[장면 목록 — 묶음: 조각 수 · 쓰임 표시]
%s
[없는 장면] %s

[스타일 묶음] — 번호 | 이름들 | 맞는 재료 종류 | 칸 구조(칸 이름: 그 칸이 하는 일)
%s

styles: 이 재료로 쓸 수 있는 묶음 4개, 점수 높은 순. 재료 종류가 그 묶음의 기본 종류와 다르면 칸 뜻을 이 재료에 맞게 읽어라(pan 에 판 이름).
칸마다 그 칸을 보여 줄 장면이 있는지 세어 filled/total. ★칸이 요구하는 장면이 [없는 장면]에 있으면 채운 칸으로 세지 마라.
단, 그 칸이 **화면 밖 이야기**(가족 반응·전문가 출처·댓글 유도·가격 말하기)라면 장면 대신 화면에 보이는 결과 장면을 깔면 되므로 채운 칸으로 센다 — 단 가격 칸은 [없는 장면]에 가격이 있으면 세지 마라.
note: 무엇이 모자란지 한 구절.
출력 JSON만.
"""

P3 = """너는 수천 편을 쓴 쇼핑 쇼츠 **영상 대본 작가 겸 편집자**다. 장면이 먼저고, 문장은 장면에서 나온다.
[재료 종류] %s (판: %s)
[장면 목록 — 조각 번호(길이)·쓰임]
%s
[없는 장면] %s
[⭐ 손님이 꼭 쓰라고 고른 조각 — 반드시 어느 칸엔가 넣어라] %s
[🎯 손님이 역할을 정한 조각 — 그 역할 칸의 **맨 앞**에 놓아라(그 칸 시간이 남으면 다른 조각을 뒤에 더 붙여도 된다). ★그 조각만 그 역할에 쓰라는 뜻이 아니고, 같은 묶음의 다른 조각은 다른 칸에도 자유롭게 써라] %s

[스타일] %s
[말투] %s
[칸 — 아래 %d칸을 이 순서대로 **전부** 채워라. 칸마다: 그 칸이 하는 일 / 그 스타일이 실제로 쓴 문장 틀]
%s

칸마다:
- ids: 그 칸 조각 번호 1~3개(목록에 있는 것만, 한 조각은 한 칸에만). 조각 길이 합 × 1.2 ≥ 그 칸 문장 읽는 시간(글자 수 ÷ 7초).
- line: 그 칸의 일을 하는 한 문장(12~45자). ★위 문장 틀의 말투·어미·리듬을 그대로 타라({ } 빈칸은 이 재료의 말로 채움).
  화면에 보이는 장면을 살려 말맛 있게(구어·리듬·감탄·과장 허용). 장면 설명문 금지.
  그 칸이 화면 밖 이야기(가족 반응·전문가 출처·댓글 유도)를 하는 칸이면 그 이야기를 하되, 깔리는 조각은 그 이야기에 어울리는 결과 장면으로.
  ★화면에 없는 가격·숫자·제품 기능은 지어내지 마라.
- need: 그 칸이 하는 일.
- weak: 딱 맞는 장면이 없어 가까운 장면으로 대신했으면 그 이유와 보충 방법 한 줄, 맞으면 빈 문자열.
first_line_style: 고른 첫 줄 틀(빈칸 채운 것).
출력 JSON만.
"""

P3C = """너는 수천 편을 쓴 쇼핑 쇼츠 **영상 대본 작가 겸 편집자**다. 장면이 먼저고, 문장은 장면에서 나온다.
이번엔 정해진 스타일에 갇히지 말고 **이 재료로 가장 재밌는 이야기**를 짜라. 아래 [참고 스타일]은 흐름 참고만, [말맛 재료]의 결·어미·리듬을 살려라.
[재료 종류] %s
[장면 목록 — 조각 번호(길이)·쓰임]
%s
[없는 장면] %s
[⭐ 손님이 꼭 쓰라고 고른 조각 — 반드시 어느 칸엔가 넣어라] %s
[🎯 손님이 역할을 정한 조각 — 그 역할 칸의 **맨 앞**에 놓아라(그 칸 시간이 남으면 다른 조각을 뒤에 더 붙여도 된다). ★그 조각만 그 역할에 쓰라는 뜻이 아니고, 같은 묶음의 다른 조각은 다른 칸에도 자유롭게 써라] %s
[참고 스타일] %s — 칸 흐름: %s
[말맛 재료 — 우리가 모은 승인 부품·히트 대본]
%s

칸 6~10개를 네가 정해라(첫 칸은 3초 안에 스크롤을 멈출 훅, 끝 칸은 마무리). 칸마다:
- slot: 칸 이름(짧게), need: 그 칸이 하는 일
- ids: 그 칸 조각 번호 1~3개(목록에 있는 것만, 한 조각은 한 칸에만). 조각 길이 합 × 1.2 ≥ 문장 읽는 시간(글자 수 ÷ 7초).
- line: 한 문장(12~45자). 화면에 보이는 장면을 구체 동작·질감으로, 과장·감탄·반전 허용. 화면 밖 이야기(가족 반응·전문가 출처·댓글 유도)도 허용.
  ★화면에 없는 가격·숫자·제품 기능은 지어내지 마라.
- weak: 딱 맞는 장면이 없어 대신했으면 이유와 보충 방법 한 줄, 맞으면 빈 문자열.
first_line_style: 이 대본의 성격 한 구절.
출력 JSON만.
"""

P4 = """너는 쇼핑 쇼츠 **제품 사실 검수자**다. 아래는 스토리보드 칸마다 [칸이 하는 일]·[문장]·[깔린 조각의 화면 설명]이다.
★문장이 화면 설명에 없는 **제품 사실**(가격·숫자·용량·제품 기능)을 지어낸 칸만 찾아, 같은 말투로 그 사실을 빼고 다시 써라.
가족 반응·전문가 출처·댓글 유도·과장·감탄은 스타일이니 **고치지 마라**. 칸이 하는 일도 바꾸지 마라.
코드가 이미 걸러 낸 칸: %s
출력 JSON만: {"fix":[{"i":칸번호(0부터),"why":"...","line":"..."}]}

%s
"""


def _families(db):
    rows = db.execute("select id, name, situation_type, fit_categories_json, beat_roles_json, beat_chain_json, emotion_arc, "
                      "templates_json, voice_json from spine where status='approved' order by id").fetchall()
    fam, order = {}, []
    for sid, name, sit, fit, roles, chain, arc, tpl, voice in rows:
        roles_l = json.loads(roles or "[]")
        key = tuple(roles_l) if roles_l else ("solo", sid)
        if key not in fam:
            fam[key] = {"ids": [], "names": [], "fit": set(), "roles": roles_l, "chain": json.loads(chain or "[]"), "arc": arc or "",
                        "sit": sit or "", "tpl": {}, "voice": {}}
            order.append(key)
        f = fam[key]
        f["ids"].append(sid); f["names"].append(name); f["fit"].update(json.loads(fit or "[]"))
        try:
            for k, v in (json.loads(tpl or "{}") or {}).items():
                f["tpl"].setdefault(k, [])
                f["tpl"][k] += [x for x in (v if isinstance(v, list) else [v]) if x not in f["tpl"][k]]
        except (ValueError, AttributeError):
            pass
        if not f["voice"]:
            try:
                f["voice"] = json.loads(voice or "{}") or {}
            except ValueError:
                pass
    out = []
    for n, k in enumerate(order, 1):
        f = fam[k]
        slots = " / ".join("%s: %s" % (r, (f["chain"][i] if i < len(f["chain"]) else ""))[:80] for i, r in enumerate(f["roles"])) \
            or ("(칸 구조 없음 — %s)" % f["sit"])
        out.append((n, f, "%d | %s | %s | %s" % (n, ", ".join(f["names"]), ", ".join(sorted(f["fit"])), slots)))
    return out


def _code_flags(slots, text_of):
    out = {}
    for i, sl in enumerate(slots):
        line = sl.get("line") or ""
        seen = " ".join(text_of(c) for c in sl.get("ids") or [])
        why = ["화면에 없는 숫자 %s" % n for n in re.findall(r"\d+", line) if n not in seen]
        if "{" in line or "}" in line:
            why.append("빈칸 틀")
        if why:
            out[i] = why
    return out


_HEAD_CACHE = {}


def _writer_head(fam, kind):
    """라이브 대본 작가가 쓰는 지침(WRITER_BRIEF) + 플랫폼 말투(YT/IG) + 그 종류 히트 대본(없으면 가까운 종류) + 승인 부품."""
    yt = any(str(n).startswith("유튜브") for n in fam["names"]) or (fam["roles"][:1] == ["title"])
    ck = (yt, kind)
    if ck in _HEAD_CACHE:
        return _HEAD_CACHE[ck]
    from shopping_shorts import backbone_assemble as _ba, story_writer as _sw, bank_assemble as _bk
    from shopping_shorts.store import Store
    st = Store(DB)
    win = ""
    for k in [kind, "홈템", "생활용품", "레시피", "기타"]:
        try:
            win = _bk.winners_block(st, k, k=2) or ""
        except Exception as e:      # noqa: BLE001 — 시험 도구: 이유만 남긴다
            print("   히트 대본 읽기 실패(%s): %r" % (k, e), flush=True)
        if win:
            break
    try:
        parts = _bk.parts_block(st)
    except Exception as e:      # noqa: BLE001
        print("   부품 읽기 실패: %r" % e, flush=True)
        parts = ""
    head = "%s\n%s\n%s\n%s\n\n" % (_ba.WRITER_BRIEF, _sw.YT_BRIEF if yt else _sw.IG_BRIEF, win, parts)
    head += ("★이번 일은 스토리보드다 — 칸마다 장면을 먼저 꽂고 그 위에 읽힐 대본 문장을 쓴다. 문장은 장면 설명문이 아니라 "
             "위 지침·히트 대본처럼 **말맛 있는 대본**이어야 한다(\"~해 줍니다\" 같은 설명·요리법 낭독 금지).\n\n")
    _HEAD_CACHE[ck] = head
    return head


# 역할 상자 → 스타일 칸 이름(우리 승인 스타일 칸에서 뽑음, 화면 page1.js ROLES 와 같은 표)
BOX_SLOTS = {"훅": ("title", "hook"), "미끼·궁금증": ("bait", "notice", "situation", "ask", "context"),
             "문제·불편": ("limit", "pain", "problem", "mistake", "regret"), "정체 공개": ("reveal", "origin", "what"),
             "사용법": ("solve", "method", "steps", "how", "howto", "usage", "easy", "ease"),
             "효과·소구점": ("escalation", "escalate", "more", "benefit", "power", "texture", "spec", "mechanism", "good", "extra", "bonus"),
             "반전·의외": ("twist", "cases"), "반응·증거": ("fame", "proof", "witness", "react", "authority", "spread", "scale"),
             "결과": ("result", "land"), "CTA·가격": ("cta", "price", "deal")}


def _apply_role_picks(slots, roles_pick):
    """★손님이 상자에 담은 조각을 그 역할 칸 **맨 앞**으로(모델이 안 지켜도 코드가 보장). 다른 칸에 들어가 있었으면 거기선 뺀다.
    그 칸의 나머지 조각(AI 고른 것)은 뒤로 — 3단계에서 시간이 넘치면 흑백으로 보이고 손님이 순서를 바꾼다."""
    moved = []
    for part in (roles_pick or "").split(" / "):
        box, _, ids_s = part.partition(": ")
        keys = BOX_SLOTS.get(box.strip())
        ids = [x.strip() for x in ids_s.split(",") if x.strip()]
        if not keys or not ids:
            continue
        tgt = next((i for i, sl in enumerate(slots) if str(sl.get("slot") or "").lower().split("_")[0] in keys), None)
        if tgt is None:
            continue
        for sid in reversed(ids):
            for j, sl in enumerate(slots):
                if j != tgt and sid in (sl.get("ids") or []):
                    sl["ids"] = [c for c in sl["ids"] if c != sid]
            cur = [c for c in (slots[tgt].get("ids") or []) if c != sid]
            slots[tgt]["ids"] = [sid] + cur
            slots[tgt].setdefault("picked", [])
            if sid not in slots[tgt]["picked"]:
                slots[tgt]["picked"].insert(0, sid)
            moved.append((box.strip(), sid, tgt))
    return moved


def _board(fam, pan, r1, groups_txt, star, segs, texts, creative=None, roles_pick=""):
    roles = fam["roles"] or ["hook", "problem", "method", "result", "land"]
    slot_txt = "\n".join("  %d. %s — %s\n     문장 틀: %s" % (i + 1, r, (fam["chain"][i] if i < len(fam["chain"]) else ""),
                                                    " / ".join((fam["tpl"].get(r) or [])[:4]) or "(없음)") for i, r in enumerate(roles))
    v = fam["voice"] or {}
    voice = "어조: %s · 어미: %s · 강조어: %s · 의성어: %s" % (v.get("tone_note", ""), ", ".join(v.get("endings", [])),
                                                       ", ".join(v.get("intensifier", [])), ", ".join(v.get("onomatopoeia", [])))
    n3, n4 = {}, {}
    # ★말맛(2026-10-04 사장님 "투박하고 어색 — S급·우리 자료를 참고 안 한 듯"): 라이브 대본 작가 지침서 + 플랫폼 말투 지침 + 히트 대본 + 승인 부품을 앞에 붙인다
    head = _writer_head(fam, r1.get("kind") or "")
    if creative is not None:      # 1번 AI 자동 — 스타일은 참고, 말맛은 부품·히트 대본
        r3 = sg._call_json(head + P3C % (r1.get("kind") or "", groups_txt, " / ".join(r1.get("missing") or []), ", ".join(star) or "(없음)", roles_pick or "(없음)",
                                         ", ".join(fam["names"]), " → ".join(roles), creative), S3, note=n3, vertex=True) or {}
    else:
        r3 = sg._call_json(head + P3 % (r1.get("kind") or "", pan or "", groups_txt, " / ".join(r1.get("missing") or []), ", ".join(star) or "(없음)", roles_pick or "(없음)",
                                        ", ".join(fam["names"]), voice, len(roles), slot_txt), S3, note=n3, vertex=True) or {}
    slots = r3.get("slots") or []
    flags = _code_flags(slots, lambda c: texts.get(c, ""))
    block = "\n".join("칸 %d [%s — %s] 문장: %s\n   화면: %s" % (i, sl.get("slot"), sl.get("need") or "", sl.get("line"),
                                                       " / ".join(texts.get(c, "?") for c in sl.get("ids") or [])) for i, sl in enumerate(slots))
    r4 = sg._call_json(P4 % (json.dumps({str(k): v for k, v in flags.items()}, ensure_ascii=False), block), S4, note=n4, vertex=True) or {}
    fixed = []
    for fx in r4.get("fix") or []:
        i = fx.get("i")
        if isinstance(i, int) and 0 <= i < len(slots) and (fx.get("line") or "").strip():
            slots[i]["line_before"], slots[i]["line"], slots[i]["fixed_why"] = slots[i].get("line"), fx["line"].strip(), fx.get("why") or ""
            fixed.append(i)
    used, check = {}, []
    for i, sl in enumerate(slots):
        ids = sl.get("ids") or []
        check.append({"bad_ids": [c for c in ids if c not in segs], "dup_ids": [c for c in ids if c in used],
                      "have": round(sum(segs.get(c, 0) for c in ids), 1), "need": round(narr_secs(sl.get("line") or ""), 1)})
        check[-1]["short"] = check[-1]["have"] * 1.2 < check[-1]["need"] - 0.2
        for c in ids:
            used.setdefault(c, i)
    star_missing = [c for c in star if c not in used]
    role_fixed = _apply_role_picks(slots, roles_pick)
    return {"names": fam["names"], "pan": pan, "first_line_style": r3.get("first_line_style") or "", "slots": slots, "check": check,
            "fixed": fixed, "left_flags": {str(k): v for k, v in _code_flags(slots, lambda c: texts.get(c, "")).items()},
            "star_missing": star_missing, "role_fixed": role_fixed, "auth": [n3.get("auth"), n4.get("auth")]}


def main(args):
    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    fams = _families(db)
    for arg in args:
        jid, _, rest = arg.partition(":")
        star_s, _, role_s = rest.partition(":")
        t0 = time.time()
        ex = json.loads(db.execute("select extract_json from mix_jobs where job_id=?", (jid,)).fetchone()[0])
        segs, rows, texts, order = {}, [], {}, []
        for vid, e in ex.items():
            for s in (e or {}).get("segments") or []:
                a, b = float(s.get("start") or 0), float(s.get("end") or 0)
                if b - a < 0.6 or (s.get("is_outro") and not s.get("product_benefits")):
                    continue
                sid = s["seg_id"]; segs[sid] = round(b - a, 1); order.append(sid)
                texts[sid] = "%s %s" % (s.get("scene_desc") or "", s.get("use_point") or "")
                rows.append("  %s | %.1f초 | %s | 쓰임:%s | 소구점:%s" % (sid, b - a, (s.get("scene_desc") or "")[:70],
                                                                 s.get("label") or "-", (s.get("use_point") or "")[:40] or "-"))
        star = [next((sid for sid in order if sid.endswith(x.strip())), x.strip()) for x in star_s.split(",") if x.strip()]
        role_pick = {}
        for part in role_s.split("|"):
            r, _, ids = part.partition("=")
            if r.strip() and ids.strip():
                role_pick[r.strip()] = [next((sid for sid in order if sid.endswith(x.strip())), x.strip()) for x in ids.split(",") if x.strip()]
        roles_txt = " / ".join("%s: %s" % (r, ", ".join(v)) for r, v in role_pick.items())
        n1, n2 = {}, {}
        r1 = {}
        for _try in range(2):      # 1차 시험: CPL 에서 묶음이 비어 전부 '기타'로 떨어짐 — 그러면 한 번 더 묻는다
            r1 = sg._call_json(P1 % "\n".join(rows), S1, note=n1, vertex=True) or {}
            got = {c for g in r1.get("groups") or [] for c in (g.get("ids") or []) if c in segs}
            if len(r1.get("groups") or []) >= 3 and len(got) >= 0.7 * len(segs):
                break
            print("   장면 목록 다시 묻기: 묶음 %d · 들어간 조각 %d/%d" % (len(r1.get("groups") or []), len(got), len(segs)), flush=True)
        # ★빠지는 조각 0: 모델이 빠뜨리거나 두 번 넣은 조각을 코드가 정리
        seen, groups = set(), []
        for g in r1.get("groups") or []:
            ids = [c for c in (g.get("ids") or []) if c in segs and c not in seen]
            seen.update(ids)
            if ids:
                groups.append(dict(g, ids=ids))
        left = [c for c in order if c not in seen]
        if left:
            groups.append({"name": "📦 기타 장면", "desc": "분류가 애매한 조각", "ids": left})
        r1["groups"] = groups
        tag_of = {}
        for t in r1.get("tags") or []:
            if t.get("id") in segs:
                tag_of[t["id"]] = [x for x in (t.get("tags") or []) if x in TAGS]
        r1["tag_of"] = tag_of
        inv = "\n".join("  %s (%s): 조각 %d · %s" % (g["name"], g.get("desc") or "", len(g["ids"]),
                                                 ", ".join("%s %d" % (t, sum(1 for c in g["ids"] if t in tag_of.get(c, []))) for t in TAGS
                                                           if any(t in tag_of.get(c, []) for c in g["ids"])) or "-") for g in groups)
        r2 = sg._call_json(P2 % (r1.get("kind") or "", inv, " / ".join(r1.get("missing") or []), "\n".join(f[2] for f in fams)),
                           S2, note=n2, vertex=True) or {}
        groups_txt = "\n".join("  %s: %s" % (g["name"], ", ".join("%s(%.1f초%s)" % (c, segs[c], ("·" + "/".join(tag_of[c])) if tag_of.get(c) else "")
                                                                  for c in g["ids"])) for g in groups)
        boards = {}
        styles = r2.get("styles") or []
        top = next((f for n, f, _ in fams if styles and n == styles[0].get("family")), fams[0][1])
        # 1번 AI 자동: 1위 스타일은 흐름 참고만, 말맛은 승인 부품·같은 종류 히트 대본
        from shopping_shorts.store import Store
        from shopping_shorts import bank_assemble as _bk
        _st = Store(DB)
        try:
            creative = _bk.parts_block(_st) + "\n" + (_bk.winners_block(_st, r1.get("kind") or "", k=2) or "")
        except Exception as e:      # noqa: BLE001 — 시험 도구: 부품을 못 읽으면 이유를 남기고 빈 재료로
            print("   부품 읽기 실패: %r" % e, flush=True)
            creative = ""
        boards["auto"] = _board(top, styles[0].get("pan") if styles else "", r1, groups_txt, star, segs, texts, creative=creative, roles_pick=roles_txt)
        boards["auto"]["names"] = ["AI 자동(참고: %s)" % ", ".join(top["names"])]
        # 2번: 1위 스타일 그대로(나머지 3·4번은 화면에서 누르면 만든다 — +2번 호출)
        if styles:
            fam = next((f for n, f, _ in fams if n == styles[0].get("family")), None)
            if fam:
                boards[str(styles[0]["family"])] = _board(fam, styles[0].get("pan"), r1, groups_txt, star, segs, texts, roles_pick=roles_txt)
        fam_names = {str(n): f["names"] for n, f, _ in fams}
        fam_first = {str(n): (f["tpl"].get((f["roles"] or ["hook"])[0]) or [""])[0] for n, f, _ in fams}
        out = {"job": jid, "secs": round(time.time() - t0, 1), "star": star, "role_pick": role_pick, "inventory": r1, "styles": r2.get("styles") or [],
               "boards": boards, "family_names": fam_names, "family_first": fam_first, "auth": [n1.get("auth"), n2.get("auth")]}
        json.dump(out, open("/tmp/sbtrial_%s.json" % jid, "w"), ensure_ascii=False, indent=1)
        calls = 2 + 2 * len(boards)
        print(jid, "%.0f초" % out["secs"], "호출", calls, "· 조각", len(order), "· 묶음", len(groups), "· 기타로 넣은 조각", len(left),
              "· 쓰임 표시", len(tag_of), flush=True)
        for fid, bd in boards.items():
            ck = bd["check"]
            print("   스타일 %s %s · 칸 %d · 없는 번호 %d · 겹침 %d · 길이 모자람 %d · 검수 고친 칸 %d · 남은 걸림 %d · ⭐빠짐 %s" % (
                fid, bd["names"][0][:18], len(bd["slots"]), sum(len(c["bad_ids"]) for c in ck), sum(len(c["dup_ids"]) for c in ck),
                sum(1 for c in ck if c["short"]), len(bd["fixed"]), len(bd["left_flags"]), bd["star_missing"]), flush=True)


def gen(jid, keys, star_s="", role_s=""):
    """[화면 버튼용] 저장된 장면 목록(/tmp/sbtrial_<job>.json)으로 고른 스타일들의 스토리보드만 만든다(스타일당 호출 2번).
    keys: 'auto' 또는 스타일 묶음 번호들. 결과 JSON을 표준출력 마지막 줄에 'RESULT ' + JSON 으로."""
    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    fams = _families(db)
    R = json.load(open("/tmp/sbtrial_%s.json" % jid))
    r1 = R["inventory"]
    ex = json.loads(db.execute("select extract_json from mix_jobs where job_id=?", (jid,)).fetchone()[0])
    segs, texts, order = {}, {}, []
    for vid, e in ex.items():
        for s in (e or {}).get("segments") or []:
            a, b = float(s.get("start") or 0), float(s.get("end") or 0)
            if b - a < 0.6 or (s.get("is_outro") and not s.get("product_benefits")):
                continue
            segs[s["seg_id"]] = round(b - a, 1); order.append(s["seg_id"])
            texts[s["seg_id"]] = "%s %s" % (s.get("scene_desc") or "", s.get("use_point") or "")
    tag_of = r1.get("tag_of") or {}
    groups_txt = "\n".join("  %s: %s" % (g["name"], ", ".join("%s(%.1f초%s)" % (c, segs.get(c, 0), ("·" + "/".join(tag_of[c])) if tag_of.get(c) else "")
                                                              for c in g["ids"])) for g in r1["groups"])
    star = [x for x in star_s.split(",") if x]
    roles_txt = " / ".join("%s: %s" % (p.split("=")[0], p.split("=")[1]) for p in role_s.split("|") if "=" in p)
    pan_of = {str(s.get("family")): s.get("pan") for s in R.get("styles") or []}
    out = {}
    for k in keys:
        if k == "auto":
            top = next((f for n, f, _ in fams if R.get("styles") and n == R["styles"][0].get("family")), fams[0][1])
            from shopping_shorts.store import Store
            from shopping_shorts import bank_assemble as _bk
            creative = _bk.parts_block(Store(DB))
            out["auto"] = _board(top, "", r1, groups_txt, star, segs, texts, creative=creative, roles_pick=roles_txt)
            out["auto"]["names"] = ["AI 자동"]
        else:
            fam = next((f for n, f, _ in fams if str(n) == str(k)), None)
            if fam:
                out[str(k)] = _board(fam, pan_of.get(str(k)) or "", r1, groups_txt, star, segs, texts, roles_pick=roles_txt)
    print("RESULT " + json.dumps(out, ensure_ascii=False))


def families_json():
    """[화면용] 스타일 카드 — 칸 구조가 같은 스타일을 한 카드로. 플랫폼·맞는 종류·첫 줄 틀들·칸 구조."""
    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    out = []
    for n, f, _ in _families(db):
        first = f["tpl"].get((f["roles"] or ["hook"])[0]) or []
        out.append({"id": n, "names": f["names"], "yt": any(str(x).startswith("유튜브") for x in f["names"]) or f["roles"][:1] == ["title"],
                    "fit": sorted(f["fit"]), "first": first[:6], "roles": f["roles"], "chain": f["chain"], "arc": f["arc"], "sit": f["sit"]})
    print("RESULT " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1:2] == ["gen"]:
        gen(sys.argv[2], sys.argv[3].split(","), *(sys.argv[4:6]))
    elif sys.argv[1:2] == ["families"]:
        families_json()
    else:
        main(sys.argv[1:])
