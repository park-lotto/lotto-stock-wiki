# -*- coding: utf-8 -*-
"""2단계 스토리보드 — 장면 먼저 → 스타일별 대본(관제 120, 2026-10-04~05 사장님 "장면 먼저 → 스토리보드로 대본").

★스토리보드 판단(장면 묶기·스타일 추천·칸 틀·상자 담기 자리·칸 끼워 넣기)의 주인은 이 모듈 하나다.
  라이브 화면(app /api/produce/storyboard/*)과 시험 도구(tools/storyboard_trial.py)가 모두 여기를 부른다.
  ① inventory: 조각을 "무엇을 보여 주나"로 묶고(빠지는 조각 0) 쓰임 표시 + 재료 종류 + 없는 장면, 스타일 추천
  ② make_boards: 스타일 칸 목록·문장 틀·말투를 주고 칸마다 장면을 먼저 꽂고 문장을 쓴다 + 제품 사실 검수
  ③ insert: 지금 스토리보드에 고른 칸만 끼워 넣는다
  모델: script_generate._call_json(vertex=True) = gemini-3.6-flash. DB 는 읽기만.
  확정 뒤 3단계로 넘기는 것은 story_writer.storyboard_to_beat_sources(줄별 장면 고정)가 맡는다.
"""
import hashlib
import json
import os
import re
import sqlite3
import time

from shopping_shorts import script_generate as sg
from shopping_shorts.edit_plan import narr_secs

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
[🎯 손님이 역할을 짐작해 담은 조각 — 역할 이름은 **손님 짐작**이다(문제인지 효과인지 헷갈렸을 수 있다). 조각 내용을 보고 이 스타일 칸 중 가장 맞는 칸의 맨 앞에 넣어라. 훅으로 담은 조각은 반드시 첫 칸. CTA로 담은 조각은 CTA 칸이 있을 때만 그 칸에, 없으면 넣지 마라(칸을 새로 만들지 마라). 맞는 칸이 정말 없으면 넣지 않아도 된다 — 손님 화면에 따로 보여 준다. 같은 묶음의 다른 조각은 다른 칸에도 자유롭게 써라] %s

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
[🎯 손님이 역할을 짐작해 담은 조각 — 역할 이름은 **손님 짐작**이다(문제인지 효과인지 헷갈렸을 수 있다). 조각 내용을 보고 이 스타일 칸 중 가장 맞는 칸의 맨 앞에 넣어라. 훅으로 담은 조각은 반드시 첫 칸. CTA로 담은 조각은 CTA 칸이 있을 때만 그 칸에, 없으면 넣지 마라(칸을 새로 만들지 마라). 맞는 칸이 정말 없으면 넣지 않아도 된다 — 손님 화면에 따로 보여 준다. 같은 묶음의 다른 조각은 다른 칸에도 자유롭게 써라] %s
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



def is_seed_source(e):
    """이 재료 영상이 씨앗(자동 배치 제외)인가 — 표식(auto_exclude)만 읽는다. 판정은 edit_plan._auto_blocked,
    표식을 다는 건 mix_pipeline.mark_seed_sources 한 곳(새 판정을 만들지 않는다)."""
    from shopping_shorts import edit_plan as _ep
    return _ep._auto_blocked(e)


def _keep_ids(*parts):
    """사람이 상자에 담은 조각 번호(star 'id,id' · roles '훅=id,id|CTA=id') — 씨앗이어도 재료에 남긴다."""
    out = set()
    for p in parts:
        for chunk in str(p or "").split("|"):
            out.update(x.strip() for x in chunk.partition("=")[2 if "=" in chunk else 0].split(",") if x.strip())
    return out


def mat_sig(ex):
    """재료 지문 — 장면 목록을 만든 재료(담은 영상 전부의 조각, 씨앗 포함)가 지금과 같은가를 가르는 한 곳(관제 147).
    ★씨앗 여부는 안 넣는다: 장면 목록은 씨앗과 무관하게 재료 전체로 묶고, 씨앗은 보드를 만들 때 뺀다."""
    ids = sorted(str(s.get("seg_id")) for e in (ex or {}).values() for s in ((e or {}).get("segments") or []) if s.get("seg_id"))
    return "%d:%s" % (len(ids), hashlib.sha1("|".join(ids).encode("utf-8")).hexdigest()[:12])


def seed_sig(ex):
    """씨앗 지문 — 어떤 영상이 씨앗(auto_exclude)인가. AI 자동 보드가 이 값과 다르면 낡은 것이다(관제 147)."""
    return ",".join(sorted(str(k) for k, e in (ex or {}).items() if is_seed_source(e)))


def inventory_fresh(R, ex):
    """저장된 장면 목록이 지금 재료로 만든 것인가. ★2026-10-06 사고: 미리 만들기가 외국 영상 5편 재료가 들어오기 1분 전에 돌아
    장면 목록이 씨앗 조각뿐으로 굳었고, 뒤에 만든 보드는 쓸 조각이 0이라 칸마다 '장면 0초'가 됐다(work ef07493ca035).
    지문이 없는 옛 목록도 낡은 것으로 본다 — 한 번 다시 묶으면 그 뒤로는 지문으로 가른다."""
    return bool(R and R.get("inventory") and R.get("mat_sig") == mat_sig(ex))


def _materials(db, jid, ex=None, keep=(), with_seed=False):
    """작업 재료(1단계 조각) — 조각별 길이·설명. 0.6초 미만·끝 화면(효능 없음)은 뺀다. 목록·생성·끼워 넣기 공용(한 곳).
    ex = 재료(job.extract 모양 {영상: {segments}}) — 라이브는 app 이 넘긴다(매칭 작업이 없으면 작업파일의 담은 영상 분석,
    2단계 대본 생성과 같은 규칙). 없으면(시험 도구) mix_jobs 에서 읽는다. ★짝은 seg_id 로만 — 바깥 키(s0·shortcode)는 다를 수 있다."""
    if ex is None:
        row = db.execute("select extract_json from mix_jobs where job_id=?", (jid,)).fetchone()
        ex = json.loads((row[0] if row else None) or "{}")
    # ★씨앗 영상(auto_exclude)은 AI 후보(장면 목록·보드 배치·끼워 넣기)에서 뺀다(관제 120 장면배분, 사장님 10-06
    #   "썰 채널 씨앗은 자막틀이 박혀 못 쓴다"). 3단계 소스 필름엔 그대로 있다(scene_lab 은 extract 전체를 본다).
    #   ★단 사람이 1단계 '꼭 쓰고 싶은 장면' 상자에 직접 담은 씨앗 조각(keep)은 사람이 고른 것이니 존중해 남긴다.
    #   재료가 씨앗뿐이면 표식 자체가 안 달려(mark_seed_sources) 여기서도 안 빠진다.
    #   ★with_seed=True 는 장면 목록(inventory) 전용 — 목록은 씨앗과 무관하게 재료 전체로 묶는다(관제 147). 씨앗이 나중에
    #   정해지거나 바뀌어도 목록을 다시 묶지 않고, 보드를 만들 때(이 함수 기본값) 씨앗 조각을 뺀다.
    keep = set(keep or ())
    segs, texts, order, rows = {}, {}, [], []
    for vid, e in ex.items():
        seed = is_seed_source(e) and not with_seed
        for s in (e or {}).get("segments") or []:
            a, b = float(s.get("start") or 0), float(s.get("end") or 0)
            if b - a < 0.6 or (s.get("is_outro") and not s.get("product_benefits")):
                continue
            if seed and s.get("seg_id") not in keep:
                continue
            sid = s["seg_id"]
            segs[sid] = round(b - a, 1)
            order.append(sid)
            texts[sid] = "%s %s" % (s.get("scene_desc") or "", s.get("use_point") or "")
            rows.append("  %s | %.1f초 | %s | 쓰임:%s | 소구점:%s" % (sid, b - a, (s.get("scene_desc") or "")[:70],
                                                             s.get("label") or "-", (s.get("use_point") or "")[:40] or "-"))
    return segs, texts, order, rows


def _ro(db_path):
    return sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)


def _state_path(jid):
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "storyboard")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.json" % re.sub(r"[^0-9A-Za-z_-]", "", str(jid)))


def load_state(jid):
    """inventory 결과(장면 목록·스타일 추천) — 없으면 None."""
    try:
        return json.load(open(_state_path(jid), encoding="utf-8"))
    except (OSError, ValueError):
        return None

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


def _core_txt(fam):
    """[스타일 핵심] 상황·감정 흐름·왜 먹히나 — 칸·문장 틀만 주면 '가족갈등'이 친구 이야기로, '단정 명령'이 공감·전문가 없이 나온다(2026-10-04 전수 검사 40편)."""
    c = (fam.get("core") or [{}])[0]
    if not c.get("sit"):
        return ""
    return ("\n[스타일 핵심 — 대본에 반드시 살아야 한다] 상황: %s / 감정 흐름: %s / 왜 먹히나: %s"
            "\n  ★이 상황·등장인물·감정 흐름을 칸 흐름 위에 그대로 얹어라. 재료가 다른 종류면 그 상황을 이 제품에 맞게 옮겨라(예: 요리 상황 → 이 제품을 급하게 쓴 상황)."
            % (c["sit"], c.get("arc") or "", c.get("appeal") or ""))


def _families(db):
    rows = db.execute("select id, name, situation_type, fit_categories_json, beat_roles_json, beat_chain_json, emotion_arc, "
                      "templates_json, voice_json, appeal from spine where status='approved' order by id").fetchall()
    fam, order = {}, []
    for sid, name, sit, fit, roles, chain, arc, tpl, voice, appeal in rows:
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
                        "sit": sit or "", "tpl": {}, "voice": {}, "core": []}
            order.append(key)
        f = fam[key]
        f["core"].append({"name": name, "sit": sit or "", "arc": arc or "", "appeal": appeal or ""})      # 스타일의 상황·감정·소구(2026-10-04 전수 검사: 이게 빠져 가족갈등이 친구 이야기로 나왔다)
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
    for k in order:
        f = fam[k]
        n = int(f["ids"][0])      # 묶음 번호 = 첫 스타일 고유번호(spine id). 순번이면 묶음이 바뀔 때 화면·서버 번호가 엇갈린다(2026-10-04 '가족갈등' 탭에 비밀 궁금증형이 나온 사고)
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


def _is_yt(fam):
    """유튜브(썰) 스타일인가 — 말투 지침·신호어 풀이 이걸로 갈린다."""
    return any(str(n).startswith("유튜브") for n in fam["names"]) or (fam["roles"][:1] == ["title"])


def _writer_head(fam, kind):
    """라이브 대본 작가가 쓰는 지침(WRITER_BRIEF) + 플랫폼 말투(YT/IG) + 그 종류 히트 대본(없으면 가까운 종류) + 승인 부품."""
    yt = _is_yt(fam)
    ck = (yt, kind)
    if ck in _HEAD_CACHE:
        return _HEAD_CACHE[ck]
    from shopping_shorts import backbone_assemble as _ba, story_writer as _sw, bank_assemble as _bk
    from shopping_shorts.store import Store
    from shopping_shorts.config import DB_PATH as _DBP   # 시안 도구에서 옮길 때 남은 DB(전역) — 라이브엔 없다(10-05 라이브 첫 생성에서 NameError)
    st = Store(_DBP)
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


# ── 신호어(2026-10-05 사장님 "신호어를 조사 많이 하고 변형해서 세트로"): 낱말·자리·박기는 story_writer 가 주인이다
#    (pick_signals·storyboard_signals·attach_signal). 여기는 **어느 칸이 고조·반전 계열인가**(칸 이름 = 이 파일의 말)만 정한다.
_SIG_ESC = set(BOX_SLOTS["효과·소구점"])
_SIG_TWIST = set(BOX_SLOTS["반전·의외"]) | {"shock"}


def signal_kinds(slots):
    """칸마다 "esc"(고조 계열) / "twist"(반전 계열) / "". 첫 칸(훅)·끝 칸(마무리)은 빼고, 정체 공개 칸이 있으면 그 뒤만."""
    base = [str(x.get("slot") or "").split("_")[0].lower() for x in slots]
    rev = max([i for i, b in enumerate(base) if b in BOX_SLOTS["정체 공개"]] or [0])
    out = []
    for i, b in enumerate(base):
        if i == 0 or i == len(base) - 1 or i <= rev:
            out.append("")
        else:
            out.append("twist" if b in _SIG_TWIST else "esc" if b in _SIG_ESC else "")
    return out


def apply_signals(slots, key, nth=0, yt=True):
    """고조·반전 칸 첫머리에 신호어를 박는다(생성 뒤 코드 확인·보정). 다른 신호어로 열었으면 떼고 붙이고,
    신호어가 안 배정된 칸이 배정된 낱말로 또 시작하면 뗀다(한 편 안 반복 금지). 박은 낱말은 칸의 signal 에 남긴다."""
    from shopping_shorts import story_writer as _sw
    ranks = []
    words = _sw.storyboard_signals(signal_kinds(slots), key, nth, "yt" if yt else "ig", ranks)
    for sl, r in zip(slots, ranks):
        if r:
            sl["sig_rank"] = r            # 짤은 [1]·[3] 자리에만(사장님 10-05) — 자리 번호는 신호어 배정한 곳이 정한다
    used = [w for w in words if w]
    for sl, w in zip(slots, words):
        line = sl.get("line") or ""
        if w:
            new = _sw.attach_signal(line, w)
        elif any(line.startswith(u + " ") for u in used):
            new = _sw.attach_signal(line, "")
        else:
            continue
        if new != line:
            sl.setdefault("line_signal_before", line)
            sl["line"] = new
        if w:
            # ★실제로 붙은 낱말을 남긴다 — attach_signal 이 본문과 같은 말이면 같은 자리 다른 신호어로 바꾸기 때문(관제 139:
            #   짤 길이는 TTS 에서 이 낱말을 찾아 재므로 원래 낱말이 남으면 '신호어 시각 못 찾음'으로 짤이 빠졌다)
            sl["signal"] = next((x for x in sorted(_sw._ALL_SIGNAL_WORDS, key=len, reverse=True)
                                 if (sl.get("line") or "").startswith(x + " ")), w)
    # 짤 들어갈 줄의 감정(관제 143) — 2단계 화면이 '여기 짤 들어감(감정)'을 보이려고 읽는다. 감정 판정은 meme_emotion 한 곳
    for sl in slots:
        emo = meme_emotion(int(sl.get("sig_rank") or 0), sl.get("signal") or "") if str(sl.get("sig_rank") or "").isdigit() else None
        if emo:
            sl["meme_emotion"] = emo
        else:
            sl.pop("meme_emotion", None)
    return words


# ── 감정짤 자리(관제 139, 2026-10-06 사장님 확정) ─────────────────────────────────────────────────────
#   ★"어느 줄 맨 앞에 짤을 몇 초 넣나"의 주인은 meme_slots 하나다. 3단계 화면(scene_play.js scenesV2Alloc)·렌더·캡컷·ZIP 은
#     이 함수가 남긴 beat["cutaway"](match_type "meme", head_sec)를 **읽기만** 한다 — 짤 컷을 첫 컷으로 두고 남은 시간에 장면을 나눈다.
#   규칙: 신호어 자리 [1]·[3] 줄만 · 길이 = 그 줄 음성에서 신호어 마지막 낱말이 끝나는 초를 1.0~2.0초로 자름 · 시작은 줄 시작 ·
#         짤 뒤 남은 시간이 장면 하나 하한(1.0초)보다 짧으면 그 줄은 짤 없음.
#   감정: [1] 이면서 "말도 안/말이 돼" 류 → 의심_황당 · 그 밖 [1] → 놀람 · [3] → 충격_입막.
MEME_MIN_SEC = 1.0          # 짤 최소 길이
MEME_MAX_SEC = 2.0          # 짤 최대 길이
MEME_SCENE_MIN = 1.0        # 짤 뒤 장면 하나의 최소 길이 — cutaway["scene_min"] 으로 실어 화면 배분(scenesV2Alloc)이 같은 값을 읽는다
MEME_RANKS = (1, 3)
_MEME_DOUBT = re.compile(r"말도\s*안|말이\s*돼|말이\s*되")
_MEME_EMOTION = {1: "놀람", 3: "충격_입막"}


def meme_emotion(rank, signal):
    """신호어 자리·낱말 → 짤 감정. [1]·[3] 밖이면 None."""
    if rank == 1 and _MEME_DOUBT.search(signal or ""):
        return "의심_황당"
    return _MEME_EMOTION.get(rank)


def _compact(t):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t or "")


def signal_end_sec(narration, signal, words):
    """줄 음성 낱말 시각 words=[{word,start,end}] 에서 신호어(줄 첫머리)를 다 말한 초. 못 찾으면 None."""
    sig = _compact(signal)
    if not sig or not _compact(narration).startswith(sig) or not words:
        return None
    acc = ""
    for w in words:
        acc += _compact((w or {}).get("word"))
        if len(acc) >= len(sig):
            if not acc.startswith(sig):
                return None          # 음성 낱말이 신호어와 어긋난다(받아쓰기 오인식 등) — 짐작하지 않는다
            try:
                return float(w.get("end"))
            except (TypeError, ValueError):
                return None
    return None


MEME_DEFAULT_SEC = 1.25   # 사람이 [＋짤]로 넣은 줄에 신호어 시각이 없을 때 짤 길이(시안 MEME_SEC 와 같은 값)
MEME_PREF_KEY = "meme_prefs"   # 회원별 '감정별 우선 짤' — store.customer_prefs 의 키. 값 [{asset_id, emotion, rank}]


def meme_prefs_by_emotion(prefs):
    """[{asset_id, emotion, rank}] → {감정: [asset_id…(rank 순)]}. 모양이 어긋난 항목은 버린다."""
    out = {}
    for p in sorted([x for x in (prefs or []) if isinstance(x, dict)], key=lambda x: (int(x.get("rank") or 0))):
        try:
            aid = int(p.get("asset_id"))
        except (TypeError, ValueError):
            continue
        emo = str(p.get("emotion") or "").strip()
        if emo and aid not in out.setdefault(emo, []):
            out[emo].append(aid)
    return out


def meme_head(beat, words, dur, manual=False):
    """짤 길이(초)를 정한다 — 자동 배치와 사람이 [＋짤]로 넣을 때가 **같은 함수**를 쓴다(판단 한 곳).
    신호어를 다 말한 초(signal_end_sec)를 1.0~2.0초로 자른다. 못 찾으면 자동은 짤 없음, 사람(manual)은 1.25초.
    짤 뒤 남은 시간이 장면 하나 하한(1.0초)보다 짧으면 짤 없음. 돌려주는 것 = (초, None) | (None, 이유)."""
    end = signal_end_sec((beat or {}).get("narration") or "", str((beat or {}).get("signal") or ""), words)
    if end is None:
        if not manual:
            return None, "신호어 시각 못 찾음(%s)" % (str((beat or {}).get("signal") or "") or "신호어 없음")
        head = MEME_DEFAULT_SEC
    else:
        head = end - float((beat or {}).get("head_trim") or 0.0)
    head = round(min(MEME_MAX_SEC, max(MEME_MIN_SEC, head)), 2)
    try:
        dur = float(dur or 0)
    except (TypeError, ValueError):
        dur = 0.0
    if dur - head < MEME_SCENE_MIN - 1e-6:
        return None, "짤 뒤 남은 시간 %.2f초 < %.1f초" % (dur - head, MEME_SCENE_MIN)
    return head, None


def meme_cut(asset, head, emotion, manual=False):
    """beat["cutaway"] 짤 모양 — 화면·렌더·캡컷이 읽는 열쇠는 여기 한 곳에서 만든다."""
    cw = {"asset_id": int(asset["asset_id"]), "match_type": "meme", "head_sec": head,
          "vid": "meme_%d" % int(asset["asset_id"]),      # 짤 컷의 video_id — 화면·렌더·캡컷이 이 이름 하나로 짤 파일을 찾는다
          "emotion": emotion, "scene_min": MEME_SCENE_MIN, "owner": int(asset.get("owner") or 0)}
    if manual:
        cw["manual"] = 1          # 사람이 고른 짤 — meme_slots 가 다시 정할 때 건드리지 않는다
    return cw


def meme_slots(plan, words_of, pool, log=None, key="", prefs=None):
    """편성표의 칸마다 짤 자리를 정해 beat["cutaway"] 에 남긴다(관제 139). 판단은 여기 한 곳.

    words_of(beat) → (낱말 시각 [{word,start,end}] | None, 칸 길이 초(head_trim·tail_trim 뺀 실제 칸 길이) | None)
    pool = {감정: [{"asset_id", "duration"}...]} — 고를 수 있는 짤(서버 짤 팩). 비면 짤 없음 + 이유.
    prefs = {감정: [asset_id…]} — 회원이 고른 '감정별 우선 짤'(관제 143). 고르기는 meme_choose 한 곳(⭐ 중 작업 key 해시 랜덤, ⭐ 없으면 팩).
    칸의 beat["meme_pick"](2단계 스토리보드에서 미리 고른 짤 번호)이 있으면 그 짤을 먼저 쓴다.
    돌려주는 것 = [{"beat_idx","meme"(bool),"why"|"head_sec","emotion","asset_id"}] — 칸마다 왜 넣었나/안 넣었나.
    ★다른 끼움 장면(AI 장면·사람이 붙인 컷어웨이)이 이미 있는 칸과 사람이 고른 짤(manual)·뺀 칸(meme_off)은 건드리지 않는다. 옛 자동 짤은 다시 정한다."""
    out = []
    used = {}
    taken = set()
    by_id = {int(a["asset_id"]): (emo, a) for emo, lst in (pool or {}).items() for a in (lst or [])}
    for b in (plan or {}).get("beats") or []:
        cw = b.get("cutaway") if isinstance(b, dict) else None
        if isinstance(cw, dict) and cw.get("match_type") == "meme" and cw.get("manual"):
            taken.add(int(cw.get("asset_id") or 0))
    for b in (plan or {}).get("beats") or []:
        if not isinstance(b, dict):
            continue
        bi = b.get("beat_idx")
        cw = b.get("cutaway")
        if cw and (cw or {}).get("match_type") != "meme":
            out.append({"beat_idx": bi, "meme": False, "why": "다른 끼움 장면 있음"})
            continue
        if cw and cw.get("manual"):
            out.append({"beat_idx": bi, "meme": True, "head_sec": cw.get("head_sec"), "emotion": cw.get("emotion"),
                        "asset_id": cw.get("asset_id"), "why": "사람이 고른 짤"})
            continue
        b.pop("cutaway", None)        # 옛 짤은 지금 음성·대본으로 다시 정한다(못 정하면 빠진다)
        if b.get("meme_off"):         # 사람이 [빼기]로 뺀 칸 — 다시 넣지 않는다(관제 143)
            out.append({"beat_idx": bi, "meme": False, "why": "사람이 뺌"})
            continue

        def _no(why):
            out.append({"beat_idx": bi, "meme": False, "why": why})
        try:
            rank = int(b.get("sig_rank") or 0)
        except (TypeError, ValueError):
            rank = 0
        if rank not in MEME_RANKS:
            if rank:
                _no("신호어 자리 [%d]" % rank)
            continue
        signal = str(b.get("signal") or "")
        emo = meme_emotion(rank, signal)
        try:
            words, dur = words_of(b)
        except Exception as e:      # noqa: BLE001 — 음성 시각을 못 읽은 칸은 짤 없음(이유를 남긴다)
            _no("음성 시각 실패 %s" % type(e).__name__)
            continue
        head, why = meme_head(b, words, dur)
        if head is None:
            _no(why)
            continue
        fits = lambda a: float(a.get("duration") or 0) >= head - 1e-3
        a = None
        try:
            mp = int(b.get("meme_pick") or 0)
        except (TypeError, ValueError):
            mp = 0
        if mp and mp in by_id and fits(by_id[mp][1]):      # 2단계에서 미리 고른 짤 — 그 짤의 감정으로
            emo, a = by_id[mp]
        if a is None:
            cands = [x for x in (pool or {}).get(emo) or [] if fits(x)]
            if not cands:
                _no("짤 없음(감정 %s, %.2f초 이상)" % (emo, head))
                continue
            k = used.get(emo, 0)
            used[emo] = k + 1
            a = meme_choose(emo, cands, prefs, key, k, taken)
        taken.add(int(a["asset_id"]))
        b["cutaway"] = meme_cut(a, head, emo)
        out.append({"beat_idx": bi, "meme": True, "head_sec": head, "emotion": emo, "asset_id": int(a["asset_id"])})
    if log is not None:
        for r in out:
            log(r)
    return out


def _hash_pick(cands, key, salt, k=0):
    """작업 key 해시로 고른다 — 작업마다 다르고, 같은 작업은 다시 열어도 같다. 같은 salt 가 한 편에 여러 번이면 k 로 다음 것."""
    import zlib
    return cands[(zlib.crc32(("%s|%s" % (key, salt)).encode("utf-8")) + int(k or 0)) % len(cands)]


def meme_choose(emo, cands, prefs, key, k=0, taken=()):
    """감정짤 고르기의 주인(관제 143, 10-06 사장님 "내 ⭐ 중 랜덤"). 2단계 미리보기(meme_preview)·3단계 자동 배치(meme_slots)가 같이 쓴다.
    cands = 그 감정의 쓸 수 있는 짤 [{asset_id,…}] · prefs = {감정: [asset_id…]}.
    ★그 감정 ⭐가 있으면 ⭐ 중 key 해시 랜덤(한 편에 같은 짤 두 번 안 씀), 없으면 팩 전체에서 key 해시(종전 공식 그대로)."""
    ids = {int(x["asset_id"]): x for x in cands}
    tk = set(taken or ())
    pref = [ids[i] for i in (prefs or {}).get(emo) or [] if i in ids and i not in tk]
    if pref:
        return _hash_pick(pref, key, "fav|" + str(emo), k)
    # ★작업마다 다른 짤(key=작업 번호): 종전엔 늘 목록 맨 앞이라 모든 영상에 같은 짤이 들어갔다(10-06 팩 1,283개 올린 뒤 확인).
    return _hash_pick(cands, key, emo, k)


def meme_preview(slots, pool, prefs=None, key="", log=None):
    """2단계 스토리보드 줄에 '실제로 들어갈 짤'을 미리 싣는다(sl["meme_pick"], 자동이면 meme_auto=1).
    고르기는 meme_choose — 확정 때 meme_pick 이 beat 로 넘어가 meme_slots 가 그대로 쓰므로 2단계에서 보인 짤 = 3단계 짤.
    사람이 고른 짤(meme_auto 없음)·뺀 줄(meme_off)은 그대로. 길이를 아직 모르니 2초(MEME_MAX_SEC) 이상 짤을 먼저(3단계에서 길이로 탈락하지 않게)."""
    used, taken = {}, set()
    for sl in slots or []:
        if isinstance(sl, dict) and sl.get("meme_pick") and not sl.get("meme_auto"):
            taken.add(int(sl["meme_pick"]))
    for i, sl in enumerate(slots or []):
        if not isinstance(sl, dict):
            continue
        emo = sl.get("meme_emotion")
        if sl.get("meme_off") or not emo:
            if sl.get("meme_auto"):
                sl.pop("meme_pick", None)
                sl.pop("meme_auto", None)
            continue
        if sl.get("meme_pick") and not sl.get("meme_auto"):
            continue
        allc = list((pool or {}).get(emo) or [])
        cands = [x for x in allc if float(x.get("duration") or 0) >= MEME_MAX_SEC - 1e-3] or allc
        if not cands:
            sl.pop("meme_pick", None)
            sl.pop("meme_auto", None)
            if log:
                log("줄 %d 짤 없음(감정 %s)" % (i + 1, emo))
            continue
        k = used.get(emo, 0)
        used[emo] = k + 1
        a = meme_choose(emo, cands, prefs, key, k, taken)
        taken.add(int(a["asset_id"]))
        sl["meme_pick"], sl["meme_auto"] = int(a["asset_id"]), 1
    return slots


# ── 효과음 자리(관제 143 확장, 2026-10-06 사장님 "줄마다 효과음 자리 — 짤엔 리액션 탄성, 센 마무리엔 박수") ─────────────
#   ★"이 줄에 어떤 분류의 효과음을 넣나"의 주인은 sfx_category 하나, "어느 파일을"은 sfx_choose 하나다.
#     2단계 미리보기(sfx_preview)·3단계 배치(sfx_slots)가 둘 다 이 둘을 부른다. 렌더·미리보기·청소본·캡컷은
#     beat["sfx"](match_type "line")를 기존 비트 효과음 길(_resolve_sfx_paths → sfx_events_for)로 받는다.
#   효과음 파일 = 서버 사장님(0) 장면 자산 asset_type "sfx" · category 가 아래 분류 이름 중 하나.
#   그 밖 줄은 썰 효과음팩(sfx_pack) 몫 — 여기서 정한 줄은 팩이 그 줄 첫 발만 비운다(같은 순간 두 발 금지).
SFX_CATS = ("리액션 탄성", "박수/환호", "웃음", "놀람", "휙/전환", "팝/띵", "실패", "긴장")
# 짤 감정 → 효과음 분류(10-06 사장님이 고른 13개 기준). 표에 없는 감정은 리액션 탄성.
#   같은 분류 안에서는 자산 tone(그 소리가 맞는 감정들, 쉼표)에 그 감정이 든 소리를 먼저 쓴다(sfx_choose).
MEME_SFX = {"놀람": "리액션 탄성", "감탄_박수": "리액션 탄성", "의심_황당": "리액션 탄성", "당황_멘붕": "리액션 탄성",
            "충격_입막": "긴장", "공포_움찔": "긴장", "기쁨_환호": "박수/환호", "웃음": "웃음",
            "거절_절레": "실패", "분노_짜증": "실패", "슬픔": "실패", "끄덕_엄지": "팝/띵"}
_STRONG_END = re.compile(r"품절\s*대란|대박이지|난리\s*(?:났|나|난)|완판|역대급|미쳤")
CARRY_KEYS = ("meme_pick", "meme_auto", "meme_off", "sfx_pick", "sfx_auto", "sfx_off")   # 2단계 줄 → 3단계 beat 로 함께 넘기는 칸(숫자)
#   + "pack_edit"(기본 효과음팩 빼기·바꾸기, dict) — carry_picks 가 따로 싣는다


def carry_picks(src):
    """2단계 줄(또는 화면 행)의 짤·효과음 고름 → beat 로 넘길 dict. 확정 길(story_writer·edit_plan)이 이 함수 하나로 싣는다."""
    out = {}
    # 팩 소리 빼기·바꾸기(dict) — 모양 정리는 주인 sfx_pack.clean_pack_edit 한 곳(여기선 싣기만)
    from shopping_shorts.sfx_pack import clean_pack_edit
    pe = clean_pack_edit((src or {}).get("pack_edit"))
    if pe:
        out["pack_edit"] = pe
    for k in CARRY_KEYS:
        v = (src or {}).get(k)
        if str(v if v is not None else "").isdigit() and int(v):
            out[k] = int(v)
    return out


def sfx_category(text, is_last, meme_emotion=None):
    """줄 → 효과음 분류(없으면 None = 썰 효과음팩 몫). 짤 줄 → 감정의 리액션 탄성 · 마지막 줄이 센 마무리 → 박수/환호."""
    if meme_emotion:
        return MEME_SFX.get(meme_emotion, "리액션 탄성")
    if is_last and _STRONG_END.search(text or ""):
        return "박수/환호"
    return None


def sfx_choose(cat, bank, key, k=0, cur=None, emotion=None):
    """분류 → 효과음 자산 하나(작업 key 해시). cur 이 그 분류에 아직 있으면 그대로(2단계에서 보인 소리 = 3단계 소리). 없으면 None.
    emotion(짤 감정)을 주면 그 감정이 tone 에 든 소리를 먼저 — 슬픈 짤에 '와우'가 붙지 않게."""
    cands = list((bank or {}).get(cat) or [])
    if not cands:
        return None
    if cur:
        hit = next((x for x in cands if int(x["asset_id"]) == int(cur)), None)
        if hit:
            return hit
    if emotion:
        fit = [x for x in cands if emotion in [t.strip() for t in str(x.get("tone") or "").split(",")]]
        if fit:
            cands = fit
    return _hash_pick(cands, key, "sfx|" + cat + "|" + str(emotion or ""), k)


def sfx_preview(slots, bank, key="", log=None):
    """2단계 줄마다 효과음 자리 — sl["sfx_pick"](자동이면 sfx_auto=1, 분류 sfx_cat). 사람이 고른 것·뺀 줄(sfx_off)은 그대로.
    자산이 없으면 조용히가 아니라 log 로 '효과음 없음(분류)'를 남기고 비운다(sl["sfx_cat"] 은 남겨 화면이 '준비 중'을 보인다)."""
    n = len(slots or [])
    for i, sl in enumerate(slots or []):
        if not isinstance(sl, dict) or sl.get("sfx_off"):
            continue
        if sl.get("sfx_pick") and not sl.get("sfx_auto"):
            continue
        emo = None if sl.get("meme_off") else sl.get("meme_emotion")
        cat = sfx_category(sl.get("line") or "", i == n - 1, emo)
        if not cat:
            for x in ("sfx_pick", "sfx_auto", "sfx_cat"):
                sl.pop(x, None)
            continue
        sl["sfx_cat"] = cat
        a = sfx_choose(cat, bank, key, i, sl.get("sfx_pick"), emo)
        if a is None:
            sl.pop("sfx_pick", None)
            sl.pop("sfx_auto", None)
            if log:
                log("줄 %d 효과음 없음(%s)" % (i + 1, cat))
            continue
        sl["sfx_pick"], sl["sfx_auto"] = int(a["asset_id"]), 1
    return slots


def sfx_line(asset_id, cat=None, manual=False):
    """beat["sfx"] 줄 효과음 모양 — 줄 시작 1발(position first), 파일은 사장님(0) 효과음 자산."""
    d = {"asset_id": int(asset_id), "match_type": "line", "position": "first", "owner": 0}
    if cat:
        d["cat"] = cat
    if manual:
        d["manual"] = 1
    return d


def sfx_slots(plan, bank, key="", log=None):
    """3단계 편성표 칸마다 줄 효과음(meme_slots 뒤에 돈다 — 짤이 정해진 뒤). 돌려주는 것 = [{"beat_idx","sfx"(bool),"why"|"asset_id","cat"}].
    ★사람이 3단계에서 고른 효과음(match_type manual 또는 line+manual)·뺀 칸(sfx_off)은 그대로. 2단계 사람 고름(sfx_pick, sfx_auto 없음)은 그 소리.
    자동은 sfx_category 로 다시 정한다 — 짤을 빼면(cutaway 없음) 짤 효과음도 빠진다."""
    beats = [b for b in (plan or {}).get("beats") or [] if isinstance(b, dict)]
    out = []
    for i, b in enumerate(beats):
        bi = b.get("beat_idx")
        cur = b.get("sfx") or {}
        if cur.get("match_type") == "manual" or (cur.get("match_type") == "line" and cur.get("manual")):
            out.append({"beat_idx": bi, "sfx": True, "asset_id": cur.get("asset_id"), "cat": cur.get("cat"), "why": "사람이 고른 효과음"})
            continue
        if cur.get("match_type") == "line":
            b.pop("sfx", None)          # 옛 자동 줄 효과음은 지금 짤·대본으로 다시 정한다
        if b.get("sfx_off"):
            out.append({"beat_idx": bi, "sfx": False, "why": "사람이 뺌"})
            continue
        if b.get("sfx_pick") and not b.get("sfx_auto"):
            b["sfx"] = sfx_line(b["sfx_pick"], manual=True)
            out.append({"beat_idx": bi, "sfx": True, "asset_id": int(b["sfx_pick"]), "cat": None, "why": "2단계에서 고름"})
            continue
        cw = b.get("cutaway") or {}
        emo = (cw.get("emotion") or "리액션") if cw.get("match_type") == "meme" else None
        cat = sfx_category(b.get("narration") or b.get("line") or "", i == len(beats) - 1, emo)
        if not cat:
            continue
        a = sfx_choose(cat, bank, key, i, b.get("sfx_pick"), emo)
        if a is None:
            out.append({"beat_idx": bi, "sfx": False, "cat": cat, "why": "효과음 없음(%s)" % cat})
            continue
        b["sfx"] = sfx_line(a["asset_id"], cat)
        out.append({"beat_idx": bi, "sfx": True, "asset_id": int(a["asset_id"]), "cat": cat})
    if log is not None:
        for r in out:
            log(r)
    return out


def _apply_role_picks(slots, roles_pick):
    """★손님이 상자에 담은 조각의 자리(사장님 10-05): 상자 이름은 짐작이라 **AI가 고른 칸을 존중**한다.
      · 훅 상자 → 반드시 첫 칸 맨 앞(코드가 보장)
      · CTA 상자 → 스타일에 CTA 칸이 있을 때만 그 칸 맨 앞. 없으면 넣지 않는다(칸을 만들지 않는다)
      · 그 밖 → AI가 어느 칸에 넣었으면 그대로. 안 넣었으면 같은 이름 칸이 있을 때만 그 칸 맨 앞
      · 끝내 못 넣은 조각은 left 로 돌려준다 — 화면이 맨 아래 칸에 카드로 보여 준다(조용히 버리지 않는다)."""
    moved, left = [], []
    key = lambda sl: str(sl.get("slot") or "").lower().split("_")[0]

    def _put(tgt, sid, box):
        for j, sl in enumerate(slots):
            if j != tgt and sid in (sl.get("ids") or []):
                sl["ids"] = [c for c in sl["ids"] if c != sid]
        slots[tgt]["ids"] = [sid] + [c for c in (slots[tgt].get("ids") or []) if c != sid]
        slots[tgt].setdefault("picked", [])
        if sid not in slots[tgt]["picked"]:
            slots[tgt]["picked"].insert(0, sid)
        moved.append((box, sid, tgt))

    for part in (roles_pick or "").split(" / "):
        box, _, ids_s = part.partition(": ")
        box = box.strip()
        keys = BOX_SLOTS.get(box)
        ids = [x.strip() for x in ids_s.split(",") if x.strip()]
        if not keys or not ids or not slots:
            continue
        # ★첫 칸은 어떤 이름이든 훅이다(사장님 10-05 "첫칸은 그냥 후킹") — 「단돈 OO원이면」의 price 첫 칸에 CTA 장면을 넣지 않는다
        named = next((i for i, sl in enumerate(slots) if key(sl) in keys and not (box != "훅" and i == 0)), None)
        for sid in reversed(ids):
            where = next((i for i, sl in enumerate(slots) if sid in (sl.get("ids") or [])), None)
            if box == "훅":
                _put(0, sid, box)
            elif box == "CTA·가격":
                if named is None:
                    if where is not None:   # CTA 칸이 없는 스타일 — AI가 다른 칸에 넣었어도 빼고 남긴다(사장님 "배치하지 말고 냅둬")
                        slots[where]["ids"] = [c for c in slots[where]["ids"] if c != sid]
                    left.append({"box": box, "id": sid, "why": "이 스타일엔 CTA 칸이 없어요"})
                else:
                    _put(named, sid, box)
            elif where is not None:
                slots[where].setdefault("picked", [])
                if sid not in slots[where]["picked"]:
                    slots[where]["picked"].insert(0, sid)
                moved.append((box, sid, where))
            elif named is not None:
                _put(named, sid, box)
            else:
                left.append({"box": box, "id": sid, "why": "맞는 칸을 못 찾았어요"})
    return moved, left


def slot_checks(slots, segs):
    """줄마다 '문장 X초 · 장면 Y초' — 보드 만들기·끼워 넣기·화면에서 고친 뒤(/picks) 모두 이 함수 하나로 잰다.
    문장 초 = edit_plan.narr_secs(말속도 주인), 장면 초 = 그 줄에 든 조각 길이 합(segs: 조각 → 초).
    short = 장면이 문장보다 모자람(장면 1.2배 여유, 0.2초 허용)."""
    check, seen = [], set()
    for x in slots or []:
        x = x if isinstance(x, dict) else {}
        ids = [c for c in (x.get("ids") or []) if c]
        c_ = {"bad_ids": [c for c in ids if c not in segs], "dup_ids": [c for c in ids if c in seen],
              "have": round(sum(segs.get(c, 0) for c in ids), 1), "need": round(narr_secs(x.get("line") or ""), 1)}
        c_["short"] = c_["have"] * 1.2 < c_["need"] - 0.2
        check.append(c_)
        seen.update(ids)
    return check


def _board(fam, pan, r1, groups_txt, star, segs, texts, creative=None, roles_pick="", extra=None, prev=None, key=""):
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
    from shopping_shorts import story_writer as _sw
    yt = _is_yt(fam)
    sigw = _sw.storyboard_signals(signal_kinds([{"slot": r} for r in roles]), key, 0, "yt" if yt else "ig")
    slot_txt = "\n".join("  %d. %s — %s\n     문장 틀: %s%s" % (i + 1, r, (fam["chain"][i] if i < len(fam["chain"]) else ""),
                                                      " / ".join((fam["tpl"].get(r) or [])[:4]) or "(없음)",
                                                      ("\n     ★이 칸 문장은 「%s」로 시작(뒷말이 그 신호어에 자연스럽게 이어지게)" % sigw[i]) if sigw[i] else "")
                         for i, r in enumerate(roles))
    _ws = _sw.pick_signals("yt" if yt else "ig", key, 0)[1]
    sig_note = ("\n★신호어 — 고조 칸(효능을 한 단계씩 쌓는 칸)은 순서대로 %s, 반전(twist) 칸은 「%s」로 시작하라. "
                "한 편에 같은 신호어를 두 번 쓰지 마라(코드가 확인해 고친다).\n") % (
        " → ".join("「%s」" % w for w in _ws[:2] if w) or "(없음)", _ws[2])
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
                                         ", ".join(fam["names"]), " → ".join(roles), creative) + add + sig_note, S3, note=n3, vertex=True) or {}
    else:
        r3 = sg._call_json(head + P3 % (r1.get("kind") or "", pan or "", groups_txt, " / ".join(r1.get("missing") or []), ", ".join(star) or "(없음)", roles_pick or "(없음)",
                                        ", ".join(fam["names"]) + _core_txt(fam), voice, len(roles), slot_txt), S3, note=n3, vertex=True) or {}
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
                                             ", ".join(fam["names"]), " → ".join(roles), creative) + add + sig_note + "★직전 답에서 끼울 칸이 빠졌거나 칸이 줄었다. 반드시 넣어라.", S3, note=n3, vertex=True) or r3
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
    apply_signals(slots, key, 0, yt)      # 생성·사실 검수 뒤 코드가 신호어를 확인·보정(사실 검수가 줄을 고쳐도 신호어가 남게)
    check = slot_checks(slots, segs)
    used = {c for sl in slots for c in (sl.get("ids") or [])}
    star_missing = [c for c in star if c not in used]
    role_fixed, role_left = _apply_role_picks(slots, roles_pick)
    return {"names": fam["names"], "pan": pan, "first_line_style": r3.get("first_line_style") or "", "slots": slots, "check": check,
            "fixed": fixed, "left_flags": {str(k): v for k, v in _code_flags(slots, lambda c: texts.get(c, "")).items()},
            "star_missing": star_missing, "role_fixed": role_fixed, "role_left": role_left, "extra": extra, "extra_missing": r3.get("extra_missing") or [],
            "sig_key": key, "sig_yt": yt, "auth": [n3.get("auth"), n4.get("auth")]}


def inventory(db_path, jid, star_s="", role_s="", ex=None):
    """① 장면 목록 묶기 + ② 스타일 추천(3.6 2번). 결과는 data/storyboard/<작업>.json — 스토리보드 만들기가 이어 쓴다."""
    db = _ro(db_path)
    fams = _families(db)
    t0 = time.time()
    segs, texts, order, rows = _materials(db, jid, ex, keep=_keep_ids(star_s, role_s), with_seed=True)
    star = [next((sid for sid in order if sid.endswith(x.strip())), x.strip()) for x in star_s.split(",") if x.strip()]
    role_pick = {}
    for part in role_s.split("|"):
        r, _, ids = part.partition("=")
        if r.strip() and ids.strip():
            role_pick[r.strip()] = [next((sid for sid in order if sid.endswith(x.strip())), x.strip()) for x in ids.split(",") if x.strip()]
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
    out = {"job": jid, "mat_sig": (mat_sig(ex) if ex is not None else None), "secs": round(time.time() - t0, 1), "star": star, "role_pick": role_pick, "inventory": r1,
           "styles": r2.get("styles") or [], "boards": {},
           "family_names": {str(n): f["names"] for n, f, _ in fams},
           "family_first": {str(n): (f["tpl"].get((f["roles"] or ["hook"])[0]) or [""])[0] for n, f, _ in fams},
           "auth": [n1.get("auth"), n2.get("auth")]}
    json.dump(out, open(_state_path(jid), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


def make_boards(db_path, jid, keys, star_s="", role_s="", extra_s="", prev_s="", R=None, ex=None):
    """고른 스타일들의 스토리보드(스타일당 3.6 2번). 장면 목록(inventory)을 먼저 만들어 둬야 한다. keys: 'auto' 또는 스타일 묶음 번호."""
    db = _ro(db_path)
    fams = _families(db)
    R = R or load_state(jid)
    # 재료(ex)는 라이브에서 늘 app 이 넘긴다. 안 넘긴 시험 도구 경로는 지문을 비교하지 않는다.
    if ex is not None and R and R.get("inventory") and not inventory_fresh(R, ex):
        # ★재료가 바뀐 장면 목록으로 보드를 만들지 않는다 — 여기서 다시 묶는다(보드를 만드는 모든 길이 여길 지난다, 관제 147)
        print("   장면 목록이 지금 재료와 달라 다시 묶는다: %s → %s" % (R.get("mat_sig"), mat_sig(ex)), flush=True)
        R = inventory(db_path, jid, star_s, role_s, ex=ex)
    if not R:
        raise ValueError("장면 목록을 먼저 만들어야 합니다")
    r1 = R["inventory"]
    segs, texts, order, _rows = _materials(db, jid, ex, keep=_keep_ids(star_s, role_s))
    tag_of = r1.get("tag_of") or {}
    groups_txt = "\n".join("  %s: %s" % (g["name"], ", ".join("%s(%.1f초%s)" % (c, segs.get(c, 0), ("·" + "/".join(tag_of[c])) if tag_of.get(c) else "")
                                                              for c in g["ids"] if c in segs)) for g in r1["groups"]
                            if any(c in segs for c in g["ids"]))   # 씨앗 조각은 후보로 안 싣는다 — ★씨앗만 든 묶음은 이름도 안 싣는다(실으면 모델이 묶음 이름을 장면 번호 자리에 적는다, 관제 147)
    star = [x for x in star_s.split(",") if x]
    roles_txt = " / ".join("%s: %s" % (p.split("=")[0], p.split("=")[1]) for p in role_s.split("|") if "=" in p)
    pan_of = {str(s.get("family")): s.get("pan") for s in R.get("styles") or []}
    out = {}
    for k in keys:
        if k == "auto":
            top = next((f for n, f, _ in fams if R.get("styles") and n == R["styles"][0].get("family")), fams[0][1])
            from shopping_shorts.store import Store
            from shopping_shorts import bank_assemble as _bk
            creative = _bk.parts_block(Store(db_path))
            out["auto"] = _board(top, "", r1, groups_txt, star, segs, texts, creative=creative, roles_pick=roles_txt, extra=extra_s.split(","), prev=prev_s.split(","), key="%s:auto" % jid)
            out["auto"]["names"] = ["AI 자동"]
        else:
            fam = next((f for n, f, _ in fams if str(n) == str(k)), None)
            if fam:
                out[str(k)] = _board(fam, pan_of.get(str(k)) or "", r1, groups_txt, star, segs, texts, roles_pick=roles_txt, extra=extra_s.split(","), key="%s:%s" % (jid, k))
    _ss = seed_sig(ex) if ex is not None else None
    for b in out.values():
        if isinstance(b, dict):
            b["seed_sig"] = _ss        # 이 보드를 만든 때의 씨앗 — 미리 만들기가 씨앗이 바뀌었나를 이걸로 본다(관제 147)
    return out


def families(db_path):
    """[화면용] 스타일 카드 — 칸 구조가 같은 스타일을 한 카드로. 플랫폼·맞는 종류·첫 줄 틀들·칸 구조."""
    db = _ro(db_path)
    out = []
    for n, f, _ in _families(db):
        first = f["tpl"].get((f["roles"] or ["hook"])[0]) or []
        out.append({"id": n, "names": f["names"], "yt": any(str(x).startswith("유튜브") for x in f["names"]) or f["roles"][:1] == ["title"],
                    "fit": sorted(f["fit"]), "first": first[:6], "roles": f["roles"], "chain": f["chain"], "arc": f["arc"], "sit": f["sit"]})
    return out


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
    from shopping_shorts import story_writer as _sw      # 신호어 낱말은 story_writer 풀이 주인(자리별 최다 빈도 둘씩)
    conj = " / ".join([w for k in (1, 2, 3) for w, _ in _sw.YT_POOLS[k][:2]] + ["알고 보니", "그래서", "덕분에", "이 정도면"])
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


def insert(db_path, jid, payload, R=None, ex=None):
    """[모드 insert] stdin = {"board": 지금 스토리보드, "extra": [칸...]} → 그 스토리보드에 고른 칸만 끼운 결과(3.6 1번)."""
    db = _ro(db_path)
    R = R or load_state(jid) or {"inventory": {}}
    tag_of = R["inventory"].get("tag_of") or {}
    bd = payload["board"]
    # 보드에 이미 있는 조각(사람이 담은 씨앗 포함)은 재료로 인정 — 새 후보(cand)는 씨앗을 뺀 재료에서만 고른다
    segs, texts, _order, _rows = _materials(db, jid, ex, keep={c for x in bd.get("slots") or [] for c in (x.get("ids") or [])})
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
    if ins:      # 끼운 칸·흐름 검수 뒤에도 신호어 자리를 다시 맞춘다(같은 key → 같은 낱말, 자리만 새 칸 구조로)
        apply_signals(slots, bd.get("sig_key") or "%s:%s" % (jid, ",".join(bd.get("names") or [])), 0, bd.get("sig_yt", True))
    check = slot_checks(slots, segs)
    out = dict(bd, slots=slots, check=check, extra=sorted(set((bd.get("extra") or []) + [x["slot"] for x in ins])),
               extra_missing=[e for e in extra if e not in [x["slot"] for x in ins]], touched=touched, flow_fixed=flow_fixed, auth=[n.get("auth"), auth2], mode="insert",
               prompt_chars=len(prompt))
    return out
