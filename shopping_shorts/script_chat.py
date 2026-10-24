"""2단계 대본 AI 대화(관제 253, 2026-10-22 사장님 "대본단계에서 ai채팅창을 주고 대화하면서 수정" /
"ai와 대화 대답까지 하는 제미니창 — api로 버텍스").

판단 주인: revise() — 회원 말 한 마디 + 지금 대본 줄 + 앞 대화 → 제미나이식 답(자유 대화) + 필요할 때만 고친 대본.
  · 질문·아이디어·후보 추천·설명은 reply 로 길게 답하고 대본은 안 건드린다(edit=false).
  · 회원이 대본을 바꿔 달라고 할 때만 edit=true + 같은 줄 수의 전체 대본(lines). 앞에서 낸 후보("2번째 걸로")도 이어받는다.
  · 줄 하나 = 스토리보드 칸 하나 = 3단계 장면 한 칸. 칸마다 장면이 붙어 있으므로 **줄 수는 바꾸지 않는다**
    (줄을 늘리고 빼는 건 화면의 [＋ 칸 추가]·[🗑 빼기]가 장면과 함께 한다 — 여기서 하면 장면이 한 칸씩 밀린다).
  · AI 호출은 script_generate._call_json 깔때기 그대로 — 버텍스 등록 회원은 자기 버텍스, 관리자는 사장님 버텍스,
    그 외는 무료 키풀(vertex_route.plan 한 곳이 가른다). 여기서 따로 길을 정하지 않는다(0순위-B).
  · 화면은 돌려받은 줄을 바로 덮지 않고 바뀐 줄을 보여 준 뒤 [적용]을 눌러야 칸에 넣는다.
"""
from shopping_shorts import script_generate

MAX_LINES = 60
MAX_LINE_CHARS = 300
MAX_MSG_CHARS = 2000
MAX_REPLY_CHARS = 4000
MAX_HISTORY = 16

_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "edit": {"type": "boolean"},
        "lines": {"type": "array", "items": {"type": "string"}},
        "scenes": {"type": "boolean"},
        "scene_rows": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["reply", "edit"],
}

_PROMPT = """너는 한국어 쇼츠(60초 이하 세로 영상) 대본을 함께 쓰는 AI 작가다. 회원과 제미나이처럼 자연스럽게 대화한다.
대본은 줄 단위다. 줄 하나가 영상의 장면 한 칸이고 성우가 그대로 읽는다. 줄 앞 [ ]는 그 칸 이름(훅·문제·해결 등)이다 —
회원이 "훅", "첫 줄", "마지막", "CTA"처럼 칸 이름·위치로 말하면 그 줄 이야기다.

[지금 대본 — {n}줄]
{lines}
{product_hint}
[지금까지 대화]
{history}
[회원 말]
{message}

답하는 법:
- reply: 회원 말에 대한 대화 답(한국어). 질문·의견·아이디어·후보 추천·이유 설명 모두 여기서 성의 있게 답한다.
  후보를 낼 때는 번호를 붙여 줄바꿈으로 나열한다(회원이 "2번째 걸로 해줘"처럼 이어 말할 수 있게). 마크다운 기호(**, #)는 쓰지 않는다.
- edit: 회원이 대본을 **바꿔/고쳐/넣어/적용해 달라고** 할 때만 true. 질문·추천·상의만 하면 false(대본은 그대로).
- edit=true 이면 lines 에 고친 **전체 대본**을 정확히 {n}줄로 준다. 요청과 상관없는 줄은 글자 하나 바꾸지 말고 그대로 둔다.
  앞 대화에서 낸 후보를 고르라고 하면("2번째 걸로") 그 후보 문장을 그대로 쓴다. 회원이 문장을 불러 주면 그대로 쓴다.
  reply 에는 무엇을 바꿨는지 짧게 말한다.
- 줄을 더하거나 빼 달라고 하면 줄 수는 {n}줄 그대로 두고, reply 에 "화면의 ＋ 칸 추가 / 🗑 빼기 버튼으로 칸을 늘리거나 빼 주세요"라고 알려 준다.
- 대본에 없는 사실·수치·효과를 지어내지 않는다(숫자는 대본·상품에 있을 때만). 말투(존댓말·반말·어미)는 지금 대본을 따른다.
- lines 의 줄에는 번호·칸 이름·따옴표·기호·괄호 설명을 넣지 않는다. 성우가 읽을 문장만 쓴다.
- scenes: 회원이 **장면·화면·영상 조각**이 문장과 맞는지 봐 달라거나 바꿔 달라고 하면 true(예: "장면 점검해줘", "3번째 줄 장면 더 역동적인 걸로").
  그때 scene_rows 에 해당 줄 번호(1부터)를, 전체면 빈 목록을 준다. 장면 판단은 장면 목록을 보는 다른 단계가 하므로
  reply 에는 "장면을 점검할게요" 정도만 짧게 쓰고 장면을 지어내 말하지 않는다. 대본 문장 이야기만 하면 false.
"""


# 대화창 모델 선택(2026-10-22 사장님 "API 연결한 사람 등급에 맞게 위쪽까지 대화창에서").
#   버텍스로 도는 계정(등록 회원=자기 버텍스·관리자=사장님 버텍스)만 고른다 — 무료 키 계정은 키풀 모델 하나.
#   목록·기본값은 여기 한 곳(화면은 /api/script/chat/models 로 받아 그린다). 실측 2026-10-22 사장님 버텍스:
#   대화 요청 3.6-flash 7~15초 · 3.1-pro-preview 17초(서버 호출 실측). 가격(USD/1M, ai.google.dev 2026-10-22): flash 0.75/3.75 · pro 2/12
CHAT_MODELS = [
    {"id": "gemini-3.6-flash", "label": "Flash 3.6", "note": "빠름(10초 안팎) · 대화 1번 약 6원"},
    {"id": "gemini-3.1-pro-preview", "label": "Pro 3.1", "note": "가장 똑똑함 · 조금 느림(20초 안팎) · 대화 1번 약 20~35원"},
]
DEFAULT_CHAT_MODEL = "gemini-3.6-flash"


def models_for(cid=None):
    """이 계정이 대화창에서 고를 수 있는 모델 — {"vertex": bool, "models": [...], "default": id}.
    버텍스로 도는지는 vertex_route.plan 한 곳이 정한다(member/owner). 무료 계정은 models 가 빈 목록."""
    from shopping_shorts import vertex_route
    vx = vertex_route.plan(cid) in ("member", "owner")
    return {"vertex": vx, "models": CHAT_MODELS if vx else [], "default": DEFAULT_CHAT_MODEL if vx else ""}


EMPTY_MARK = "(빈 칸)"


def _unplaceholder(t):
    return "" if t.replace(" ", "").strip("()[]") in ("빈칸", "") else t


def _clean_lines(lines):
    out = [str(x or "").strip() for x in (lines or []) if isinstance(x, (str, int, float))]
    return out


def _scenes(got, n, only=None):
    """대화 답에 '장면 점검해 달라'가 들었나(관제 257) → {"scenes": bool, "scene_rows": [줄 번호 0부터]}(빈 목록 = 전체).
    장면 판단 자체는 storyboard.scene_review 가 한다 — 여기선 회원 말이 그 부탁인지만 넘긴다. 한 줄 요구창은 그 줄만."""
    if not got.get("scenes"):
        return {"scenes": False, "scene_rows": []}
    if only is not None:
        return {"scenes": True, "scene_rows": [only]}
    rows = sorted({r - 1 for r in (got.get("scene_rows") or []) if isinstance(r, int) and 1 <= r <= n})
    return {"scenes": True, "scene_rows": rows}


def revise(lines, message, history=None, product="", roles=None, only=None, model=None, *, call=None, tries=2):
    """→ {"reply", "lines"(같은 줄 수), "changed"(바뀐 줄 번호), "auth": "vertex"|"free", "model": 실제로 답한 모델}.
    model: CHAT_MODELS 의 id(버텍스 계정만 뜻이 있다). 목록 밖이면 기본값. 버텍스가 실패해 무료 키로 넘어가면 auth="free"·model=키풀 모델.
    대화만 했으면(edit=false) lines = 지금 대본 그대로, changed = [].
    only=줄 번호(0부터): 칸 아래 한 줄 요구창(2026-10-22 사장님 "다른 스타일로·연결어로 바꿔줘 같은 한 줄짜리 간단 요구").
      그 줄만 고친다 — 대화 없이 바로 고치고, AI가 다른 줄을 건드려도 서버가 원래대로 되돌린다.
    입력이 잘못됐거나 AI가 계약(줄 수·빈 줄)을 못 지키면 ValueError — 호출부가 그대로 화면에 띄운다.
    call: 테스트가 갈아끼우는 (prompt, schema) -> dict."""
    src = _clean_lines(lines)
    if not src:
        raise ValueError("대본 칸이 없어요 — 스토리보드를 먼저 만들어 주세요")
    if len(src) > MAX_LINES:
        raise ValueError("줄이 너무 많아요(%d줄 초과)" % MAX_LINES)
    msg = str(message or "").strip()
    if not msg:
        raise ValueError("말을 적어 주세요")
    msg = msg[:MAX_MSG_CHARS]
    if only is not None:
        if not isinstance(only, int) or not 0 <= only < len(src):
            raise ValueError("고칠 줄 번호가 맞지 않아요")
        name = str(roles[only] or "").strip()[:20] if roles and only < len(roles) else ""
        msg = ("%d번 줄%s만 고친다(반드시 edit=true, 다른 줄은 그대로 · 단 이 줄의 장면을 봐 달라는 말이면 edit=false, scenes=true): %s"
               % (only + 1, "(%s)" % name if name else "", msg))
    hist = []
    for h in (history or [])[-MAX_HISTORY:]:
        if not isinstance(h, dict):
            continue
        who = "회원" if h.get("role") == "user" else "AI"
        t = str(h.get("text") or "").strip()[:MAX_REPLY_CHARS]
        if t:
            hist.append("%s: %s" % (who, t))
    # 칸 이름(훅·문제·해결…)을 줄 앞에 붙인다 — "훅쪽에 OO 해줘"처럼 칸 이름으로 부탁해도 어느 줄인지 안다
    names = [str(x or "").strip()[:20] for x in (roles or [])]
    numbered = "\n".join("%d. %s%s" % (i + 1, ("[%s] " % names[i]) if i < len(names) and names[i] else "", x or EMPTY_MARK)
                         for i, x in enumerate(src))
    hint = ("\n[상품] %s\n" % product.strip()) if (product or "").strip() else ""
    prompt = _PROMPT.format(n=len(src), lines=numbered, product_hint=hint,
                            history="\n".join(hist) or "(없음)", message=msg)
    note = {}   # _call_json 이 실제로 탄 길을 적는다(auth="vertex", model) — 화면이 "구글 버텍스 Pro 3.1 / 무료 제미나이"를 말한다
    vm = model if model in {m["id"] for m in CHAT_MODELS} else DEFAULT_CHAT_MODEL
    call = call or (lambda p, s: script_generate._call_json(p, s, note=note, vertex_model=vm))
    auth = lambda: "vertex" if note.get("auth") == "vertex" else "free"
    used = lambda: note.get("model") or (vm if note.get("auth") == "vertex" else script_generate._MODEL)
    last = ""
    for _ in range(max(1, tries)):
        got = call(prompt, _SCHEMA) or {}
        reply = str(got.get("reply") or "").strip()[:MAX_REPLY_CHARS]
        if not got.get("edit"):
            if only is not None and got.get("scenes"):   # 한 줄 요구창에서 "장면 바꿔줘" — 문장은 그대로, 장면 점검으로 넘긴다(관제 257)
                return {"reply": reply or "이 줄 장면을 점검할게요.", "lines": list(src), "changed": [], "auth": auth(), "model": used(),
                        **_scenes(got, len(src), only)}
            if only is not None:
                last = "AI가 줄을 고치지 않았어요"
                continue
            if not reply:
                last = "AI 응답이 비었어요(키 소진·응답 오류)"
                continue
            return {"reply": reply, "lines": list(src), "changed": [], "auth": auth(), "model": used(), **_scenes(got, len(src), only)}
        # 프롬프트의 빈 칸 표시("(빈 칸)")를 AI가 그대로 돌려주면 성우가 읽는다 — 빈 칸으로 되돌린다(2026-10-22 실측: 3칸)
        out = [_unplaceholder(str(x or "").strip()[:MAX_LINE_CHARS]) for x in (got.get("lines") or [])]
        if len(out) != len(src):
            last = "줄 수가 안 맞아요(지금 %d줄 → 답 %d줄)" % (len(src), len(out))
            continue
        # 원래 글이 있던 줄이 비어 오면 받지 않는다(빈 칸은 빈 채로 와도 된다)
        if any(s and not o for s, o in zip(src, out)):
            last = "빈 줄이 섞여 나왔어요"
            continue
        if only is not None:   # 한 줄 요구 — 그 줄 말고는 원래대로(AI가 건드려도)
            out = [o if i == only else s for i, (s, o) in enumerate(zip(src, out))]
            if out[only] == src[only]:
                last = "AI가 같은 문장을 돌려줬어요"
                continue
        changed = [i for i, (s, o) in enumerate(zip(src, out)) if s != o]
        return {"reply": reply or "고쳤어요.", "lines": out, "changed": changed, "auth": auth(), "model": used(), **_scenes(got, len(src), only)}
    raise ValueError("AI가 답하지 못했어요 — " + (last or "AI 응답이 비었어요") + ". 잠시 후 다시 보내 주세요")
