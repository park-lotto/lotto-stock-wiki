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

칸 6~10개를 네가 정해라. ★흐름 틀(이 순서를 지켜라, 필요 없는 칸은 빼도 되고 같은 칸을 두 번 써도 된다):
  hook(3초 안에 스크롤을 멈출 훅) → bait(궁금증) → pain(쓰기 전 불편, 선택) → reveal(정체 공개: 이건 OO) → feature(이건 이런 특징·쓰는 법)
  → escalation(고조: 앞 효능보다 한 단계 더 센 것) → twist(반전: 예상 밖 쓰임·충격, 선택) → benefit(이점·반응·증거) → closing(마무리)
  각 칸은 **제 역할을 하는 문장**이어야 한다 — twist 칸에 고조 문장, feature 칸에 마무리 문장을 쓰지 마라.
칸마다:
- slot: 위 영어 칸 이름 그대로(두 번째면 feature_2 처럼), need: 그 칸이 하는 일
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


def _roles_from_chain(chain):
    """[옛 스타일 1~4번(2026-07 레시피)] 칸 이름·첫 줄 틀 없이 흐름 글(beat_chain)만 있다 → 흐름 글로 칸 이름을 붙인다(첫 칸은 훅, CTA는 마무리)."""
    out = []
    for i, c in enumerate(chain):
        t = str(c)
        r = ("hook" if i == 0 else "cta" if "CTA" in t.upper() else "react" if "반응" in t else "problem" if ("이유" in t or "문제" in t or "틀렸" in t)
             else "method" if any(w in t for w in ("비법", "방법", "시도")) else "result" if "결과" in t else "solve")
        while r in out:
            r += "_2"
        out.append(r)
    return out


# 옛 레시피 스타일 1~4번(2026-07, 근거 1~3편, 흐름 글 4단계뿐) → 7~8칸 틀(2026-10-04 사장님 "인물 드라마형 틀이 너무 짧다").
# 원래 흐름 글의 뜻은 그대로 두고, 빠진 단계(왜 곤란했나·정체 공개·결과·고조)를 같은 계열 최신 스타일(가족갈등 반전형 10칸) 결로 채운다.
# ★시안 도구 안에서만 — 라이브 스타일 표(reference.db spine)는 고치면 고객에게 바로 가므로 사장님 확인 뒤에.
OLD_EXPAND = {
    "인물 드라마형": [("hook", "[인물]이 [상황]이라 급하게 — 이야기로 연다"), ("situation", "왜 급했나·뭐가 곤란했나(불편을 생생하게)"),
                  ("reveal", "그래서 꺼낸 게 이거 — 정체 공개"), ("method", "시도: 이렇게만 했을 뿐"), ("result", "결과가 눈에 보이는 순간"),
                  ("react", "주변 놀란 반응"), ("escalation", "심지어 — 한 단계 더(덤·의외의 장점)"), ("cta", "CTA")],
    "역발상 경고형": [("hook", "충격 경고: [소재] 절대 [흔한방법] 마세요"), ("mistake", "다들 그렇게 하는데"), ("problem", "왜 틀렸나 이유"),
                  ("reveal", "올바른 비법·도구 공개"), ("method", "이렇게 하면 된다(킥 하나 감춤)"), ("result", "결과 차이"),
                  ("escalation", "심지어 — 한 단계 더"), ("cta", "CTA 댓글")],
    "비밀 궁금증형": [("hook", "[소재] [흔한방법] 하는 분들 이거 꼭 보세요"), ("problem", "문제 제기"), ("bait", "다들 놓치는 결정적 한 끗"),
                  ("reveal", "핵심 비법 살짝만 공개"), ("method", "하는 법"), ("result", "결과"), ("escalation", "심지어 — 한 단계 더"), ("cta", "CTA")],
    "충격 결과형": [("hook", "결과 먼저: [행동]했을 뿐인데 [놀라운결과]"), ("result", "결과를 한 번 더 보여 줌"), ("bait", "비결이 궁금하게"),
                  ("reveal", "알고 보니 간단한 방법·도구"), ("method", "하는 법"), ("escalation", "심지어 — 한 단계 더"), ("twist", "비법 킥 감춤"), ("cta", "CTA")],
}


def _families(db):
    rows = db.execute("select id, name, situation_type, fit_categories_json, beat_roles_json, beat_chain_json, emotion_arc, "
                      "templates_json, voice_json from spine where status='approved' order by id").fetchall()
    fam, order = {}, []
    for sid, name, sit, fit, roles, chain, arc, tpl, voice in rows:
        roles_l = json.loads(roles or "[]")
        chain_l = json.loads(chain or "[]")
        tpl_d = json.loads(tpl or "{}") or {}
        if not roles_l and name in OLD_EXPAND:      # 옛 스타일 1~4번: 7~8칸 틀로
            roles_l = [r for r, _ in OLD_EXPAND[name]]
            chain_l = [c for _, c in OLD_EXPAND[name]]
            chain = json.dumps(chain_l, ensure_ascii=False)
            tpl_d = {"hook": [str(chain_l[0]).split(" — ")[0].replace("충격 경고: ", "").replace("결과 먼저: ", "").replace("[", "{").replace("]", "}")]}
            tpl = json.dumps(tpl_d, ensure_ascii=False)
        elif not roles_l and chain_l:      # 옛 스타일: 흐름 글로 칸을 만들고, 첫 흐름 글을 첫 줄 틀로 쓴다([소재] → {소재})
            roles_l = _roles_from_chain(chain_l)
            tpl_d = {roles_l[0]: [re.sub(r"^[^:]*:\s*", "", str(chain_l[0])).replace("[", "{").replace("]", "}")]} if not tpl_d else tpl_d
            tpl = json.dumps(tpl_d, ensure_ascii=False)
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


EXTRA_DESC = {"escalation": "고조 — 효능을 한 단계 더 세게(더 놀라운 장면으로)", "twist": "반전 — 예상 밖·딴 용도·충격 포인트",
              "proof": "반응·증거 — 사람 반응·감탄·입소문", "pain": "불편 — 쓰기 전 겪던 답답함", "how": "사용법 — 어떻게 쓰는지 과정",
              "reveal": "정체 공개 — 제품이 처음 제대로 등장", "bait": "미끼 — 궁금증을 거는 한 줄", "result": "결과 — 완성·효과가 보이는 장면"}

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


def _board(fam, pan, r1, groups_txt, star, segs, texts, creative=None, roles_pick="", extra=None, prev=None):
    roles = list(fam["roles"] or ["hook", "problem", "method", "result", "land"])
    chain = list(fam["chain"] or [])
    # 이미 있는 칸은 뺀다 — 스타일은 그 스타일 칸과, AI 자동은 직전 스토리보드 칸과 비교(AI 자동은 스타일 칸이 참고일 뿐이라 roles 와 비교하면 고조가 조용히 버려진다)
    _have = set(roles) if creative is None else {str(x).split("_")[0].lower() for x in (prev or []) if x}
    extra = [e for e in (extra or []) if e in EXTRA_DESC and e not in _have]
    if extra and creative is None:      # ★손님이 고른 칸을 마무리 앞에 넣는다(칸 구조는 그 스타일 그대로 + 추가 칸)
        at = max(1, len(roles) - 1)
        roles[at:at] = extra
        chain[at:at] = [EXTRA_DESC[e] + " (손님이 추가한 칸)" for e in extra]
    fam = dict(fam, roles=roles, chain=chain)
    slot_txt = "\n".join("  %d. %s — %s\n     문장 틀: %s" % (i + 1, r, (fam["chain"][i] if i < len(fam["chain"]) else ""),
                                                    " / ".join((fam["tpl"].get(r) or [])[:4]) or "(없음)") for i, r in enumerate(roles))
    v = fam["voice"] or {}
    voice = "어조: %s · 어미: %s · 강조어: %s · 의성어: %s" % (v.get("tone_note", ""), ", ".join(v.get("endings", [])),
                                                       ", ".join(v.get("intensifier", [])), ", ".join(v.get("onomatopoeia", [])))
    n3, n4 = {}, {}
    # ★말맛(2026-10-04 사장님 "투박하고 어색 — S급·우리 자료를 참고 안 한 듯"): 라이브 대본 작가 지침서 + 플랫폼 말투 지침 + 히트 대본 + 승인 부품을 앞에 붙인다
    head = _writer_head(fam, r1.get("kind") or "")
    if creative is not None:      # 1번 AI 자동 — 스타일은 참고, 말맛은 부품·히트 대본
        add = ""
        if extra:      # ★AI 자동은 칸을 코드로 못 끼운다 → 직전 흐름을 주고, 끼운 칸 이름을 정해 주고, 결과를 코드로 검사한다(2026-10-04 사장님 "고조 눌렀는데 8칸→7칸, 고조 없음")
            pv = [x for x in (prev or []) if x]
            add = ("\n★다시 쓰기 — 직전 스토리보드 칸 흐름: %s (%d칸)\n그 흐름은 그대로 두고, 아래 칸을 알맞은 자리에 끼워 %d칸 이상으로 써라. 칸 수를 줄이지 마라.\n"
                   "끼우는 칸(slot 이름을 정확히 이 영어 이름으로): %s\n") % (" → ".join(pv) or "(없음)", len(pv), len(pv) + len(extra),
                                                                       " / ".join("%s = %s" % (e, EXTRA_DESC[e]) for e in extra))
        r3 = sg._call_json(head + P3C % (r1.get("kind") or "", groups_txt, " / ".join(r1.get("missing") or []), ", ".join(star) or "(없음)", roles_pick or "(없음)",
                                         ", ".join(fam["names"]), " → ".join(roles), creative) + add, S3, note=n3, vertex=True) or {}
    else:
        r3 = sg._call_json(head + P3 % (r1.get("kind") or "", pan or "", groups_txt, " / ".join(r1.get("missing") or []), ", ".join(star) or "(없음)", roles_pick or "(없음)",
                                        ", ".join(fam["names"]), voice, len(roles), slot_txt), S3, note=n3, vertex=True) or {}
    slots = r3.get("slots") or []
    if creative is None:      # 스타일 대본: 칸 이름은 그 스타일 칸 그대로(3.6이 "1"·"2" 같은 번호로 돌려줄 때가 있다 — 2026-10-04 인물 드라마형 실측)
        for i, sl in enumerate(slots):
            if i < len(roles) and str(sl.get("slot") or "") not in roles:
                sl["slot"] = roles[i]
    if creative is not None and extra:
        def _miss(sl):
            names = {str(x.get("slot") or "").split("_")[0].lower() for x in sl}
            m = [e for e in extra if e not in names]
            if len(sl) < len([x for x in (prev or []) if x]) + len(extra):
                m.append("칸 수 줄어듦(%d칸)" % len(sl))
            return m
        if _miss(slots):      # 한 번만 다시 시킨다 — 그래도 빠지면 빠졌다고 결과에 남긴다(조용히 넘기지 않음)
            r3 = sg._call_json(head + P3C % (r1.get("kind") or "", groups_txt, " / ".join(r1.get("missing") or []), ", ".join(star) or "(없음)", roles_pick or "(없음)",
                                             ", ".join(fam["names"]), " → ".join(roles), creative) + add + "★직전 답에서 끼울 칸이 빠졌거나 칸이 줄었다. 반드시 넣어라.", S3, note=n3, vertex=True) or r3
            slots = r3.get("slots") or []
        r3["extra_missing"] = _miss(slots)
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
            "star_missing": star_missing, "role_fixed": role_fixed, "extra": extra, "extra_missing": r3.get("extra_missing") or [], "auth": [n3.get("auth"), n4.get("auth")]}


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


def gen(jid, keys, star_s="", role_s="", extra_s="", prev_s=""):
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
            out["auto"] = _board(top, "", r1, groups_txt, star, segs, texts, creative=creative, roles_pick=roles_txt, extra=extra_s.split(","), prev=prev_s.split(","))
            out["auto"]["names"] = ["AI 자동"]
        else:
            fam = next((f for n, f, _ in fams if str(n) == str(k)), None)
            if fam:
                out[str(k)] = _board(fam, pan_of.get(str(k)) or "", r1, groups_txt, star, segs, texts, roles_pick=roles_txt, extra=extra_s.split(","))
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


# ── 칸 끼워 넣기(2026-10-04 사장님 "지금 나온 대본에 고조 한 칸을 더 — '이게 미친 포인트가'·'이게 말도 안 되는게' 같은 우리 접속어로,
#    전체 문장이 어색하지 않게, 고조 장면도 잘 골라야 살아난다"): 대본을 처음부터 다시 쓰지 않는다. 있는 칸은 그대로 두고 고른 칸만 끼운다.
#    접속어·문장 틀은 승인 스타일의 그 역할 칸 문장에서 실제로 뽑아 준다. 장면은 아직 안 쓴 조각을 쓰임·설명과 함께 주고 고르게 한다. 3.6 1번.
EXTRA_KIN = {"escalation": ("escalation", "escalate", "more", "extra", "bonus"), "twist": ("twist", "cases"),
             "proof": ("proof", "react", "witness", "fame", "spread"), "pain": ("pain", "problem", "limit", "mistake"),
             "how": ("how", "howto", "method", "steps", "usage", "solve"), "reveal": ("reveal", "what", "origin"),
             "bait": ("bait", "notice", "situation"), "result": ("result",)}
EXTRA_TAG = {"escalation": ("애프터", "반전", "반응"), "twist": ("반전",), "proof": ("반응",), "pain": ("비포",), "result": ("애프터",),
             "reveal": ("훅감", "애프터"), "how": (), "bait": ("훅감",)}
EXTRA_HOW = {"escalation": "바로 앞 칸보다 **한 단계 더 센** 효능·장면. 앞 칸을 받아 '심지어 / 게다가 / 근데 진짜 미친 포인트는 / 이게 말도 안 되는게' 같은 접속어로 올라탄다",
             "twist": "예상 밖 쓰임이나 충격 포인트. '근데 진짜 충격적인 포인트는 / 하지만 진짜 소름 돋는 반전은' 처럼 꺾는다",
             "proof": "사람 반응·입소문·주변 반응으로 증명한다", "pain": "쓰기 전 겪던 답답함을 생생하게",
             "how": "쓰는 과정이 쉽다는 걸 한 줄로", "reveal": "제품이 무엇인지 처음 제대로 밝힌다", "bait": "다음이 궁금해지게 한 줄 건다",
             "result": "완성·효과가 눈에 보이는 순간"}
S_INS = {"type": "object", "properties": {
    "inserts": {"type": "array", "items": {"type": "object", "properties": {
        "after": {"type": "integer"}, "slot": {"type": "string"}, "need": {"type": "string"}, "line": {"type": "string"},
        "ids": {"type": "array", "items": {"type": "string"}}, "why_scene": {"type": "string"}}, "required": ["after", "slot", "line", "ids"]}},
    "touch": {"type": "array", "items": {"type": "object", "properties": {
        "i": {"type": "integer"}, "line": {"type": "string"}, "why": {"type": "string"}}, "required": ["i", "line"]}}},
    "required": ["inserts"]}
P_INS = """너는 쇼핑 쇼츠 대본 작가다. 아래는 **이미 완성된 스토리보드**다. 다시 쓰지 마라 — 고른 칸만 끼워 넣는다.

[완성된 스토리보드] (칸 번호 | 칸 | 문장 | 쓰는 장면)
%s

[끼워 넣을 칸]
%s

[쓰는 법]
- 끼울 자리는 흐름 틀(훅→미끼→불편→정체 공개→특징→고조→반전→이점·반응→마무리)대로 정해진다 — after 에 그 자리(그 칸 **뒤**) 번호를 적고, 문장은 그 바로 앞 칸을 받아 이어 써라.
- 문장은 **앞 칸에서 이어지는 접속어로 시작**해 한 단계 끌어올린다. 아래 우리 히트 스타일 문장 틀의 결을 따라라(그대로 베끼지 말고 이 제품에 맞게).
- 말투·어미·길이는 **앞뒤 칸과 똑같은 결**로(앞 칸이 '~다는 거'면 그 결, '~거 있죠'면 그 결). 한 칸 = 한 문장.
- 강조어는 우리 것만: %s
- 제품 사실(기능·숫자·가격)은 아래 장면 설명과 지금 대본에 있는 것만. 지어내지 마라.
- 앞뒤 칸 문장은 **원문 그대로** 둔다. 끼운 문장 때문에 이어짐이 어색할 때만 바로 앞이나 뒤 **한 칸**을 최소로 고쳐 touch 에 적어라(칸 번호는 위 원래 번호, 고친 이유 한 줄).

[장면 고르기 — 이게 대본만큼 중요하다]
- 아래 **아직 안 쓴 장면**에서만 고른다. 끼운 문장이 말하는 걸 **화면이 그대로 보여 주는** 장면, 그중 시각적으로 가장 센 것.
- 문장 길이(약 %s초)를 채울 만큼 1~3개. 이미 쓴 장면과 거의 같은 그림은 피한다. why_scene 에 고른 이유 한 줄.
후보 (조각 번호 | 길이 | AI가 본 쓰임 | 화면 설명):
%s
"""


def _tpl_for(db, extra):
    got = []
    names = EXTRA_KIN.get(extra, (extra,))
    for (t,) in db.execute("select templates_json from spine where status='approved'"):
        try:
            d = json.loads(t or "{}") or {}
        except ValueError:
            continue
        for r, v in d.items():
            if str(r).split("_")[0].lower() in names:
                for x in (v if isinstance(v, list) else [v]):
                    if x and x not in got:
                        got.append(x)
    return got


# ── 흐름 틀(2026-10-04 사장님 "정체 공개 후에 이건 이런 특징이 있는데 → 고조1 → 반전 → 이점… 자연스러워야"): 칸 이름 → 흐름 순위
ARC_RANK = [(("hook", "title"), 0), (("bait", "notice", "situation", "ask", "context"), 1), (("pain", "problem", "limit", "mistake", "regret", "before"), 2),
            (("reveal", "what", "origin", "identity", "intro"), 3),
            (("feature", "how", "method", "steps", "usage", "solve", "easy", "ease", "action", "use", "power", "spec", "effect", "benefit_", "texture", "mechanism", "contrast", "more", "extra", "good"), 4),
            (("escalation", "escalate", "bonus"), 5), (("twist", "cases", "shock"), 6),
            (("benefit", "proof", "react", "witness", "fame", "spread", "scale", "authority", "result", "land_"), 7),
            (("price", "deal", "cta", "closing", "land", "outro", "end"), 8)]
ARC_KO = {"hook": "훅", "bait": "미끼(궁금증)", "pain": "불편", "reveal": "정체 공개", "feature": "특징·쓰는 법", "escalation": "고조", "twist": "반전",
          "benefit": "이점·반응", "proof": "반응·증거", "how": "사용법", "result": "결과", "closing": "마무리"}


def arc_rank(slot):
    t = str(slot or "").lower()
    b = t.split("_")[0]
    for keys, r in ARC_RANK:          # 칸 이름 앞부분이 정확히 맞으면 그 순위
        if b in keys:
            return r
    for keys, r in ARC_RANK:          # 아니면 들어 있는 낱말로(effect_water → effect → 특징)
        if any(k.rstrip("_") in t for k in keys):
            return r
    return 4


def arc_place(slots, extra):
    """끼울 자리(그 칸 뒤 번호). 스타일마다 순서가 다르다(arc_audit.py 실측 18묶음 중 14개가 공통 틀과 다름 — 결과 → '심지어' 고조로 끝을 미는 틀,
    가격·딜·반응이 첫 칸인 틀). 그래서 ① 첫 칸은 훅, 끝 칸은 마무리로 고정(그 사이에만 끼운다) ② 같은 종류 칸이 이미 있으면 그 바로 뒤(고조2)
    ③ 없으면 흐름 순위가 extra 이하인 마지막 칸 뒤."""
    n = len(slots)
    if n < 2:
        return n
    kin = EXTRA_KIN.get(extra, (extra,))
    same = [i for i, x in enumerate(slots[1:n - 1], 1) if str(x.get("slot") or "").split("_")[0].lower() in kin]
    if same:
        return same[-1] + 1
    r = arc_rank(extra)
    at = 1
    for i, x in enumerate(slots[1:n - 1], 1):
        if arc_rank(x.get("slot")) <= r:
            at = i + 1
    return at


S_FLOW = {"type": "object", "properties": {"fix": {"type": "array", "items": {"type": "object", "properties": {
    "n": {"type": "integer"}, "why": {"type": "string"}, "line": {"type": "string"}}, "required": ["n", "line"]}}}, "required": ["fix"]}
P_FLOW = """너는 쇼핑 쇼츠 대본 **편집장**이다. 아래 스토리보드를 처음부터 끝까지 소리 내 읽는다고 생각하고 검수하라.
흐름 틀: 훅 → 미끼 → (불편) → 정체 공개 → 특징·쓰는 법 → 고조(앞 효능보다 한 단계 더 센 것) → 반전(예상 밖·충격으로 꺾음) → 이점·반응 → 마무리

(칸 번호 | 칸 역할 | 문장 | 화면)
%s

고칠 칸만 골라라:
1) **역할을 못 하는 칸** — 반전 칸인데 꺾임이 없다 / 고조 칸인데 앞 칸보다 약하거나 같은 얘기 / 특징 칸인데 마무리 말투 등.
2) **이어짐이 끊기는 칸** — 앞 문장을 받아 주는 접속어가 없어 뚝 끊기거나, 같은 접속어('심지어')가 연달아 반복.
3) 같은 효능을 두 칸이 되풀이.
고칠 때: 그 칸 **화면에 보이는 것**으로, 앞뒤와 같은 말투·어미, 한 문장(12~45자). 제품 사실(기능·숫자·가격)은 지금 대본과 화면 설명에 있는 것만.
우리 접속어 결: %s
강조어는 우리 것만: %s
멀쩡한 칸은 건드리지 마라(최대 3칸). 출력 JSON만: {"fix":[{"n":칸번호,"why":"무엇이 어색했나 한 줄","line":"고친 문장"}]}
"""


def flow_review(slots, texts, voice):
    """끼운 뒤 전체 흐름 검수(3.6 1번) — 역할 못 하는 칸·끊기는 이음만 고친다. 고친 칸은 line_before·fixed_why 로 남긴다."""
    body = "\n".join("%d | %s | %s | %s" % (i + 1, ARC_KO.get(str(x.get("slot") or "").split("_")[0].lower(), x.get("need") or x.get("slot")), x.get("line"),
                                             " / ".join(texts.get(c, "?")[:50] for c in x.get("ids") or []))
                     for i, x in enumerate(slots))
    conj = "심지어 / 게다가 / 근데 진짜 미친 포인트는 / 이게 말도 안 되는게 / 근데 진짜 충격적인 포인트는 / 알고 보니 / 그래서 / 덕분에 / 이 정도면"
    n = {}
    r = sg._call_json(P_FLOW % (body, conj, ", ".join(sorted(voice))), S_FLOW, note=n, vertex=True) or {}
    done = []
    for f in (r.get("fix") or [])[:3]:
        i = f.get("n")
        if isinstance(i, int) and 1 <= i <= len(slots) and (f.get("line") or "").strip() and f["line"].strip() != slots[i - 1].get("line"):
            x = slots[i - 1]
            x["line_before"], x["line"], x["fixed_why"] = x.get("line"), f["line"].strip(), "흐름 검수: " + (f.get("why") or "")
            done.append(i)
    return done, n.get("auth")


def insert(jid, payload):
    """[모드 insert] stdin = {"board": 지금 스토리보드, "extra": [칸...]} → 그 스토리보드에 고른 칸만 끼운 결과(3.6 1번)."""
    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    R = json.load(open("/tmp/sbtrial_%s.json" % jid))
    tag_of = R["inventory"].get("tag_of") or {}
    ex = json.loads(db.execute("select extract_json from mix_jobs where job_id=?", (jid,)).fetchone()[0])
    segs, texts = {}, {}
    for vid, e in ex.items():
        for s_ in (e or {}).get("segments") or []:
            a, b = float(s_.get("start") or 0), float(s_.get("end") or 0)
            if b - a < 0.6 or (s_.get("is_outro") and not s_.get("product_benefits")):
                continue
            segs[s_["seg_id"]] = round(b - a, 1)
            texts[s_["seg_id"]] = "%s %s" % (s_.get("scene_desc") or "", s_.get("use_point") or "")
    bd = payload["board"]
    slots = [dict(x) for x in bd["slots"]]
    have = {str(x.get("slot") or "").split("_")[0].lower() for x in slots}
    extra = [e for e in payload.get("extra") or [] if e in EXTRA_DESC and e not in have]
    used = {c for x in slots for c in (x.get("ids") or [])}
    board_txt = "\n".join("%d | %s | %s | %s" % (i + 1, x.get("slot"), x.get("line"),
                                                 " / ".join("%s(%s)" % (c, texts.get(c, "?")[:40]) for c in x.get("ids") or []))
                          for i, x in enumerate(slots))
    want_tags = set(t for e in extra for t in EXTRA_TAG.get(e, ()))
    cand = [c for c in segs if c not in used]
    cand.sort(key=lambda c: (0 if want_tags & set(tag_of.get(c) or []) else 1, -segs[c]))
    cand_txt = "\n".join("%s | %.1f초 | %s | %s" % (c, segs[c], "/".join(tag_of.get(c) or []) or "-", texts.get(c, "")[:90]) for c in cand[:30])
    ex_txt = "\n".join("- %s (%s): %s\n  우리 히트 스타일 문장 틀 예: %s" % (e, EXTRA_DESC[e], EXTRA_HOW[e], " / ".join(_tpl_for(db, e)[:10]) or "(없음)")
                       for e in extra)
    voice = set()
    for (v,) in db.execute("select voice_json from spine where status='approved'"):
        try:
            voice.update((json.loads(v or "{}") or {}).get("intensifier") or [])
        except ValueError:
            pass
    avg = sum(narr_secs(x.get("line") or "") for x in slots) / max(1, len(slots))
    prompt = P_INS % (board_txt, ex_txt, ", ".join(sorted(voice)), "%.1f" % avg, cand_txt)
    n = {}
    r = (sg._call_json(prompt, S_INS, note=n, vertex=True) or {}) if extra else {}
    ok_ids = set(cand)
    ins = []
    for it in r.get("inserts") or []:
        sl = str(it.get("slot") or "").split("_")[0].lower()
        if sl not in extra or any(x["slot"] == sl for x in ins):
            continue
        ids = [c for c in it.get("ids") or [] if c in ok_ids][:3]
        ins.append({"after": arc_place(slots, sl), "slot": sl,
                    "need": it.get("need") or EXTRA_DESC[sl].split(" — ")[0],
                    "line": (it.get("line") or "").strip(), "ids": ids, "why_scene": it.get("why_scene") or "", "added": True})
    touched = []
    for t in (r.get("touch") or [])[:len(ins)]:
        i = t.get("i")
        if isinstance(i, int) and 1 <= i <= len(slots) and (t.get("line") or "").strip():
            x = slots[i - 1]
            x["line_before"], x["line"], x["fixed_why"] = x.get("line"), t["line"].strip(), t.get("why") or "이어짐"
            touched.append(i)
    for it in sorted(ins, key=lambda x: arc_rank(x["slot"])):      # 흐름 순위 순서로 하나씩 — 고조·반전을 같이 넣어도 고조 → 반전
        it["after"] = arc_place(slots, it["slot"])
        slots.insert(it["after"], it)
    flow_fixed, auth2 = flow_review(slots, texts, voice) if ins else ([], None)
    check, seen = [], set()
    for x in slots:
        ids = x.get("ids") or []
        check.append({"bad_ids": [c for c in ids if c not in segs], "dup_ids": [c for c in ids if c in seen],
                      "have": round(sum(segs.get(c, 0) for c in ids), 1), "need": round(narr_secs(x.get("line") or ""), 1)})
        check[-1]["short"] = check[-1]["have"] * 1.2 < check[-1]["need"] - 0.2
        seen.update(ids)
    out = dict(bd, slots=slots, check=check, extra=sorted(set((bd.get("extra") or []) + [x["slot"] for x in ins])),
               extra_missing=[e for e in extra if e not in [x["slot"] for x in ins]], touched=touched, flow_fixed=flow_fixed, auth=[n.get("auth"), auth2], mode="insert",
               prompt_chars=len(prompt))
    print("RESULT " + json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    if sys.argv[1:2] == ["gen"]:
        gen(sys.argv[2], sys.argv[3].split(","), *(sys.argv[4:8]))
    elif sys.argv[1:2] == ["insert"]:
        insert(sys.argv[2], json.load(sys.stdin))
    elif sys.argv[1:2] == ["families"]:
        families_json()
    else:
        main(sys.argv[1:])
