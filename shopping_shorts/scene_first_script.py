# -*- coding: utf-8 -*-
"""장면-먼저 이븐쇼핑 대본 (2026-09-30 사장님 "장면을 먼저 하는데 이븐쇼핑 스타일로 … 버텍스로 / 내꺼만 켜봐").

    ① 장면표 먼저 — 칸(이븐쇼핑 골격)마다 재료 컷과 **초**를 모델이 고른다(버텍스 1회)
    ② 코드 검산 — 실재 컷·한 컷 한 칸·칸 길이 ≤ 가장 짧은 컷 × 컷 수(넘치면 같은 장면이 반복된다)
    ③ 칸마다 "이 화면·이 초·약 N자"로 대사(버텍스 1회) — **글자 수는 장면 길이에서 나온다**
    ④ 신호어는 코드가 붙인다 · 넘친 줄/마무리 어미만 1회 다시 쓰기

★왜(실측 2026-09-29~30): 대본-먼저(이야기 작가)는 재료에 없는 상황(곰팡이·습기)을 쓰고 컷을 아무거나 붙였다
  (같은 재료 라이브 job 7c6c929065ba: 화면에 없는 줄 2 · 같은 장면 반복 10쌍). 백본(backbone_assemble.write_lines)은
  장면을 먼저 골라도 문장 길이를 **전체 초 ÷ 줄 수로 균등**하게 줘서 결국 대본이 길이를 정했다(`per_line`).
  썰 히트작 10편 정독: 훅·미끼만 화면 자유, 원래용도·공개·고조는 줄마다 그 장면이 보인다.
  실험 job sf3974bec811(열수축 필름): 7줄 전부 화면 안 · 반복 0.

판단 주인: 이 파일 `make_drafts` 하나(칸 골격·컷 개수·글자 예산·신호어). 렌더는 표식 script_structure.scene_cut 이 있으면
  넘긴 컷을 그대로 두고 구절맞춤을 끈다(mix_pipeline._trim_for_cut_rhythm keep_cuts) — 여기서 정한 컷 수를 따른다.
결과물 검사: tools/scene_first_check.py <job>
"""
import json
import time
from pathlib import Path

# 이븐쇼핑 골격(히트작 정독 + docs/cut_rhythm_2026-09-22.md 1EJB 정렬) — (이름, 종류, 설명, 최소초, 최대초)
#   free = 화면 자유(제품이 멋지게 보이는 컷), exact = 말한 것이 화면에 보여야 함
SLOTS = [
    ("훅", "free", "OO를 OO하게 만든 천재의 발명품. — 제목형 한 문장", 2.0, 3.0),
    ("미끼", "free", "최근 딱 봤을 때는 평범한 ~ SNS에서 바이럴이 폭발하며 (품절·논란·업계 긴장) ~했다는데 — 화면과 상관없는 떡밥", 4.0, 6.0),
    ("공개", "exact", "이건 바로 (제품 이름). — 제품이 또렷이 보이는 컷", 2.0, 3.5),
    ("고조1", "exact", "이게 말도 안 되는게 ~해버린다는 거. — 핵심 기능 시연을 길게 붙잡는 칸", 3.5, 6.5),
    ("고조2", "exact", "심지어 ~까지 ~한다는 거. — 두 번째 기능", 2.5, 4.5),
    ("충격", "exact", "근데 진짜 충격적인 포인트는 ~다고. — 의외의 용도·결과", 3.0, 5.0),
    ("마무리", "free", "~라는데. / ~해준다고. — 짧게 닫기(CTA 없음)", 1.5, 2.5),
]
# 신호어는 코드가 붙인다 — 모델에게 맡기면 글자 수와 부딪혀 뺀다(실험 실측: 다시 쓰기에서 4/4줄이 신호어를 뺐다)
PREFIX = {"공개": "이건 바로", "고조1": "이게 말도 안 되는게", "고조2": "심지어", "충격": "근데 진짜 충격적인 포인트는"}
END_OK = {"마무리": ("라는데", "준다고", "다고")}
CUT_SECS = 2.5          # 컷 하나가 맡는 초(mix_pipeline._trim_for_cut_rhythm 의 칸 길이 ÷ 2.5 와 같은 리듬)
MIN_CUT = 0.8           # 이보다 짧은 컷은 후보에서 뺀다(backbone_assemble.MIN_CUT_SECS 와 같은 값)
FIT_SLACK = -0.2        # 추정 대사가 화면보다 이만큼 **짧아야** 통과 — 목소리는 대본 뒤(4단계)에 정해져 실제 길이를 모른다
BUDGET = 0.85           # 글자 예산 = 장면 초 × 말 속도 × 이 값(여유). 실측: 기본 목소리(kr-mina 1.0·추임새)는 추정보다
                        #   길었다(훅 2.2→2.54초, job sf1c2f259d78) — 708줄 표본 중앙은 추정의 0.72~0.82배
REDO_ROUNDS = 2         # 넘친 줄·어미 틀린 줄 다시 쓰기 최대 횟수
MADE_BY = "장면먼저"
_EXAMPLES = Path(__file__).parent / "assets" / "scene_first_even_examples.json"


def _cps():
    # 글자→초 계수의 단일 출처(edit_plan.speech_cps). 이븐쇼핑 초안은 한국어 대본이다.
    from shopping_shorts.edit_plan import speech_cps
    return speech_cps(lang="ko")


def _narr(t):
    from shopping_shorts.edit_plan import narr_secs
    return narr_secs(t)


def cuts_for(slot_idx, secs):
    """이 칸에 몇 컷 — 훅은 1컷(첫 인상 홀드), 나머지는 칸 초 ÷ CUT_SECS 반올림(1~4)."""
    if slot_idx == 0:
        return 1
    return max(1, min(4, int(round(float(secs) / CUT_SECS))))


def seg_rows(sources):
    """모델에게 줄 컷 목록 + 코드 검산용 표 {seg_id: {secs, desc}}."""
    idx, rows = {}, []
    for s in sources:
        for x in s.get("segments") or []:
            sid = x.get("seg_id")
            try:
                secs = round(float(x.get("end") or 0) - float(x.get("start") or 0), 2)
            except (TypeError, ValueError):
                secs = 0.0
            if not sid or secs < MIN_CUT:
                continue
            pb = x.get("product_benefits") or []
            ben = pb if isinstance(pb, str) else " / ".join(str(b) for b in pb[:2])
            idx[str(sid)] = {"secs": secs, "desc": (x.get("scene_desc") or "").strip()}
            rows.append("[%s] %.1f초 | 역할:%s | 화면:%s | 변화:%s | 특징:%s" % (
                sid, secs, x.get("shot_role") or "", (x.get("scene_desc") or "")[:90],
                (x.get("change") or "")[:50], ben[:90]))
    return idx, rows


SB_SCHEMA = {"type": "object", "properties": {
    "product": {"type": "string"},
    "slots": {"type": "array", "items": {"type": "object", "properties": {
        "slot": {"type": "integer"}, "cuts": {"type": "array", "items": {"type": "string"}},
        "secs": {"type": "number"}, "shows": {"type": "string"}},
        "required": ["slot", "cuts", "secs", "shows"]}}},
    "required": ["product", "slots"]}
LN_SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
    "slot": {"type": "integer"}, "text": {"type": "string"}}, "required": ["slot", "text"]}}}, "required": ["lines"]}


def storyboard_prompt(rows):
    slot_txt = "\n".join("%d. %s (%s) %.1f~%.1f초 — %s" % (
        i, n, "화면 자유: 제품이 멋지게 보이는 컷" if k == "free" else "★말한 것이 화면에 보여야 함", a, b, d)
        for i, (n, k, d, a, b) in enumerate(SLOTS))
    return (
        "쇼핑 숏폼(유튜브 썰, 이븐쇼핑 채널 형식)을 **화면부터** 짠다. 아래는 담아 온 영상 컷 목록(태깅)이다.\n"
        "칸마다 쓸 컷과 그 칸의 길이(초)를 정하라. 대본은 나중에 이 화면에 맞춰 쓴다.\n"
        "규칙:\n- 칸 순서·길이 범위는 아래 골격 그대로. 합계 22~27초.\n"
        "- '★말한 것이 화면에 보여야 함' 칸은 그 칸이 말할 기능이 **화면에 실제로 보이는 컷**만. shows에 그 컷이 보여주는 것(= 그 칸이 말할 내용)을 한 줄로.\n"
        "- '화면 자유' 칸은 제품이 멋지게·결과가 잘 보이는 컷.\n"
        "- 한 컷은 한 칸에만. 칸의 secs는 고른 컷 길이 합을 넘지 마라.\n"
        "- ★칸당 컷 개수 = 훅은 1개, 나머지는 반올림(secs÷%.1f)개(최소 1·최대 4). 그리고 **각 컷 길이가 secs÷컷개수 이상**인 컷만 골라라"
        "(짧은 컷을 고르면 같은 장면이 반복된다).\n"
        "- product: 제품 이름 한국어 한 줄.\n- 컷 번호는 목록에 있는 것만.\n\n"
        "[골격]\n%s\n\n[컷 목록]\n%s") % (CUT_SECS, slot_txt, "\n".join(rows))


def check_board(sb, idx):
    """모델 장면표 → 검산된 칸 목록. (board, problems). board 가 칸 수보다 적으면 쓰지 않는다."""
    used, board, problems = set(), [], []
    got_by = {x.get("slot"): x for x in (sb or {}).get("slots") or [] if isinstance(x, dict)}
    cps = _cps()
    for i, (n, k, _d, a, b) in enumerate(SLOTS):
        got = got_by.get(i)
        if not got:
            problems.append("칸%d %s 없음" % (i, n))
            continue
        cuts = []
        for c in got.get("cuts") or []:
            c = str(c)
            if c in idx and c not in used and c not in cuts:
                cuts.append(c)
            else:
                problems.append("칸%d 없는·중복 컷 %s" % (i, c))
        try:
            want_secs = float(got.get("secs") or a)
        except (TypeError, ValueError):
            want_secs = a
        want = cuts_for(i, want_secs)
        if len(cuts) > want:
            problems.append("칸%d 컷 %d개 → %d개" % (i, len(cuts), want))
            cuts = cuts[:want]
        if not cuts:
            problems.append("칸%d %s 쓸 컷 없음" % (i, n))
            continue
        secs = min(want_secs, sum(idx[c]["secs"] for c in cuts), b)
        cap = min(idx[c]["secs"] for c in cuts) * len(cuts)
        if cap + 1e-3 < secs:
            problems.append("칸%d %.1f초 → %.1f초(가장 짧은 컷 × %d)" % (i, secs, cap, len(cuts)))
            secs = cap
        if secs + 1e-3 < a:
            problems.append("칸%d %s 화면 %.1f초 < 하한 %.1f" % (i, n, secs, a))
        used.update(cuts)
        pf = PREFIX.get(n, "")
        chars = int(secs * cps * BUDGET)
        board.append({"slot": i, "name": n, "kind": k, "cuts": cuts, "secs": round(secs, 2), "chars": chars,
                      "prefix": pf, "rest_chars": max(6, chars - len(pf) - 1) if pf else chars,
                      "shows": str(got.get("shows") or ""), "desc": [idx[c]["desc"] for c in cuts]})
    return board, problems


def lines_prompt(board, product, examples):
    brd = "\n".join("칸%d %s [%s] %.1f초 → %s | 화면: %s" % (
        x["slot"], x["name"], "화면에 보이는 것만" if x["kind"] == "exact" else "화면 밖 이야기 허용", x["secs"],
        ("앞말 '%s'는 코드가 붙인다 — **이어지는 말만** 약 %d자" % (x["prefix"], x["rest_chars"])) if x["prefix"]
        else "약 %d자" % x["chars"],
        x["shows"] or " / ".join(x["desc"])[:120]) for x in board)
    return (
        "이븐쇼핑 채널 문체로 대사를 쓴다. 화면은 이미 정해졌다 — **칸마다 그 화면이 나오는 동안 읽을 말**을 쓴다.\n"
        "제품: %s\n\n[칸별 화면과 글자 수]\n%s\n\n"
        "규칙:\n- 모든 줄은 한국어. 칸마다 한 줄, 글자 수는 '약 N자'를 넘지 마라(공백 포함, ±3자).\n"
        "- '화면에 보이는 것만' 칸은 그 화면이 보여주는 기능만 말한다(화면에 없는 기능 금지).\n"
        "- '화면 밖 이야기 허용' 칸(훅·미끼·마무리)은 화면 설명을 하지 마라. 이븐쇼핑처럼 떡밥을 던진다 — 훅 'OO를 OO하게 만든 천재의 발명품', "
        "미끼 '최근 딱 봤을 때는 평범한 OO처럼 생긴 이 제품이 SNS에서 바이럴이 폭발하며 (품절·논란·업계 긴장) ~했다는데'. 나라·수치·인물은 지어내지 마라.\n"
        "- 공개 칸의 이어지는 말은 제품 이름(쉬운 한국어)으로 끝낸다.\n"
        "- 마무리 칸은 '~라는데.' 또는 '~준다고.'로 닫는다(효과를 한 번 더 세게).\n"
        "- 이븐쇼핑 문체: 반말 서술(~한다는 거 / ~라는데 / ~다고). 원문 문장을 베끼지 말고 이 제품 내용으로 새로 쓴다. CTA·댓글 유도 금지.\n\n"
        "[이븐쇼핑 원문 본보기]\n%s") % (product, brd, "\n\n".join(examples))


def join_prefix(prefix, text):
    t = (text or "").strip()
    if prefix and not t.startswith(prefix):
        t = (prefix + " " + t).strip()
    return t


def end_bad(name, text):
    ok = END_OK.get(name)
    if not ok:
        return ""
    return "" if (text or "").strip().rstrip(".!? ").endswith(ok) else "'%s'로 끝" % "/".join(ok)


def _examples():
    try:
        return [e["text"] for e in json.loads(_EXAMPLES.read_text(encoding="utf-8"))]
    except Exception:      # noqa: BLE001 — 본보기 없이도 쓴다(문체 설명은 프롬프트에 있다)
        return []


def _vertex_call(cid):
    """(prompt, schema) → dict. 버텍스만 — 키풀로 조용히 넘어가지 않는다(사장님 "버텍스로")."""
    from google.genai import types
    from shopping_shorts import vertex_route

    def call(prompt, schema):
        cl, m = vertex_route.client(cid), vertex_route.model()
        r = cl.models.generate_content(model=m, contents=prompt, config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=schema))
        return json.loads(r.text)
    return call


def _visual_sources(job, seed_text=""):
    """화면 재료 = job 추출 소스에서 씨앗 영상을 뺀 것(story_writer.make_drafts 와 같은 규칙)."""
    from shopping_shorts import backbone_assemble as ba
    srcs = ba.sources_from_extract((job or {}).get("extract") or {})
    key = "".join((seed_text or "").split())
    if len(key) >= 60:
        vis = [s for s in srcs if "".join((s.get("full_text_ko") or s.get("full_text") or "").split()) != key]
        return vis or srcs
    return ba._drop_seed(srcs, ba.seed_source(srcs, (job or {}).get("backbone_main")))


def make_drafts(job, cid=0, seed_text="", call=None, note=None):
    """(drafts, why) — app._backbone_drafts 와 같은 계약(비면 why 에 이유, 조용한 폴백 금지).
    call: (prompt, schema) → dict. 기본 = 버텍스(cid 의 프로젝트). 테스트는 가짜를 넣는다."""
    from shopping_shorts import backbone_assemble as ba
    note = {} if note is None else note
    call = call or _vertex_call(cid)
    vis = _visual_sources(job, seed_text)
    idx, rows = seg_rows(vis)
    if len(idx) < len(SLOTS):
        return [], "장면먼저: 쓸 컷이 %d개뿐(칸 %d개)" % (len(idx), len(SLOTS))
    t0 = time.time()
    try:
        sb = call(storyboard_prompt(rows), SB_SCHEMA) or {}
    except Exception as e:      # noqa: BLE001
        return [], "장면먼저: 장면표 실패 %r" % (e,)
    board, problems = check_board(sb, idx)
    note["board"], note["problems"] = board, problems
    if len(board) < len(SLOTS):
        return [], "장면먼저: 장면표 칸 부족 — %s" % "; ".join(problems)[:300]
    try:
        ln = call(lines_prompt(board, sb.get("product") or "", _examples()), LN_SCHEMA) or {}
    except Exception as e:      # noqa: BLE001
        return [], "장면먼저: 대사 실패 %r" % (e,)
    by = {x["slot"]: x for x in board}
    lines = {}
    for x in ln.get("lines") or []:
        s = x.get("slot")
        if s in by and (x.get("text") or "").strip():
            lines[s] = join_prefix(by[s]["prefix"], x["text"])
    def _needs(x):
        t = lines.get(x["slot"])
        return (not t) or _narr(t) > x["secs"] + FIT_SLACK or bool(end_bad(x["name"], t))

    def _rest(x):
        t, pf = (lines.get(x["slot"]) or "").strip(), x["prefix"]
        return t[len(pf):].strip() if pf and t.startswith(pf) else t

    # 다시 쓰기는 **신호어 뒷말만** 보여주고 뒷말 글자 수로 요구한다 — 줄 전체를 주면 모델이 신호어를 빼거나
    #   비슷한 말("진짜 대박인 건")을 또 붙여 넘친다(실측 e2e3). 최대 REDO_ROUNDS 번.
    note["redo"] = []
    for _round in range(REDO_ROUNDS):
        redo = [x for x in board if _needs(x)]
        if not redo:
            break
        note["redo"].append([x["name"] for x in redo])
        fix = ("아래 줄들을 고쳐라. 뜻과 문체(이븐쇼핑 반말 서술)는 유지. 한국어. 글자 수 상한과 지시를 꼭 지켜라.\n"
               "앞말이 적힌 칸은 **이어지는 말만** 써라(앞말은 코드가 붙인다 — 비슷한 감탄을 또 넣지 마라).\n" +
               "\n".join("칸%d (%s%d자 이하%s): %s" % (
                   x["slot"], ("앞말 '%s' 뒤에 이어지는 말만, " % x["prefix"]) if x["prefix"] else "",
                   x["rest_chars"] if x["prefix"] else x["chars"],
                   (", 반드시 " + end_bad(x["name"], lines.get(x["slot"]))) if end_bad(x["name"], lines.get(x["slot"])) else "",
                   _rest(x) or x["shows"]) for x in redo))
        try:
            for x in (call(fix, LN_SCHEMA) or {}).get("lines") or []:
                s = x.get("slot")
                if s in by and (x.get("text") or "").strip():
                    lines[s] = join_prefix(by[s]["prefix"], x["text"])
        except Exception as e:      # noqa: BLE001 — 다시 쓰기 실패면 그 판으로 판정
            note["redo_error"] = repr(e)[:200]
            break
    final = []
    for x in board:
        t = lines.get(x["slot"], "")
        final.append({"name": x["name"], "text": t, "narr": round(_narr(t), 2), "screen": x["secs"], "cuts": x["cuts"],
                      "fits": bool(t) and _narr(t) <= x["secs"] + FIT_SLACK, "end": end_bad(x["name"], t)})
    # 3단계 상속은 대본을 **문장 단위**로 세어 출처와 짝짓는다(edit_plan.build_inherit_plan) — 한 줄에 문장이 둘이면
    #   개수가 어긋나 상속이 통째로 꺼진다. 줄마다 정확히 한 문장인지 같은 함수로 잰다.
    from shopping_shorts.edit_plan import script_sentences, _narr_key
    for f in final:
        f["sentences"] = len([s for s in script_sentences(f["text"]) if _narr_key(s)])
    note["final"], note["sec"] = final, round(time.time() - t0, 1)
    bad = [f for f in final if not f["fits"] or f["end"] or f["sentences"] != 1]
    if bad:
        return [], "장면먼저: 화면보다 긴 줄·어미·문장 수 불일치 %s" % "; ".join(
            "%s(대사 %.1f/화면 %.1f%s%s)" % (f["name"], f["narr"], f["screen"], " " + f["end"] if f["end"] else "",
                                         "" if f["sentences"] == 1 else " 문장%d개" % f["sentences"]) for f in bad)
    given = "\n".join(f["text"] for f in final)
    beat_sources = [{"role": f["name"], "seg": f["cuts"][0], "segs": f["cuts"]} for f in final]
    d = ba.to_draft(given, beat_sources, {"spine": {"id": None, "name": "장면먼저 · 이븐쇼핑"}})
    d.update({"made_by": MADE_BY, "style_name": "장면먼저 · 이븐쇼핑", "scene_cut": True,
              "scene_board": [{"name": f["name"], "screen": f["screen"], "narr": f["narr"], "cuts": f["cuts"]} for f in final]})
    return [d], ""
