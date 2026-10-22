"""2단계 대본 AI 대화 고치기(관제 253, 2026-10-22 사장님 "대본단계에서 ai채팅창을 주고 대화하면서 수정").

판단 주인: revise() — 회원 요청 한 마디 + 지금 대본 줄 → 고친 줄(같은 줄 수) + 짧은 답.
  · 줄 하나 = 스토리보드 칸 하나 = 3단계 장면 한 칸. 칸마다 장면이 붙어 있으므로 **줄 수는 바꾸지 않는다**
    (줄을 늘리고 빼는 건 화면의 [＋ 칸 추가]·[🗑 빼기]가 장면과 함께 한다 — 여기서 하면 장면이 한 칸씩 밀린다).
  · AI 호출은 script_generate._call_json 깔때기 그대로 — 버텍스 등록 회원은 자기 프로젝트, 관리자는 사장님 프로젝트,
    그 외는 무료 키풀(vertex_route.plan 한 곳이 가른다). 여기서 따로 길을 정하지 않는다(0순위-B).
  · 화면은 돌려받은 줄을 바로 덮지 않고 바뀐 줄을 보여 준 뒤 [적용]을 눌러야 칸에 넣는다.
"""
import json

from shopping_shorts import script_generate

MAX_LINES = 60
MAX_LINE_CHARS = 300
MAX_MSG_CHARS = 1000
MAX_HISTORY = 8

_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "lines": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["reply", "lines"],
}

_PROMPT = """너는 한국어 쇼츠(60초 이하 세로 영상) 나레이션 대본을 고쳐 주는 편집자다.
대본은 줄 단위다. 줄 하나가 영상의 장면 한 칸이고 성우가 그대로 읽는다.

[지금 대본 — {n}줄]
{lines}
{product_hint}
[지금까지 대화]
{history}
[회원 요청]
{message}

지킬 것:
- 회원 요청대로 고친 **전체 대본**을 lines 에 정확히 {n}줄로 돌려준다. 요청과 상관없는 줄은 글자 하나 바꾸지 말고 그대로 둔다.
- 줄을 더하거나 빼 달라는 요청이어도 줄 수는 {n}줄 그대로 두고, reply 에 "화면의 ＋ 칸 추가 / 🗑 빼기 버튼으로 칸을 늘리거나 빼 주세요"라고 알려 준다.
- 질문만 했으면 lines 는 지금 대본 그대로 돌려주고 reply 에 답한다.
- 대본에 없는 사실·수치·효과를 지어내지 않는다. 말투(존댓말·반말·어미)는 지금 대본을 따른다.
- 줄 번호·따옴표·기호·괄호 설명을 줄 안에 넣지 않는다. 성우가 읽을 문장만 쓴다.
- reply 는 무엇을 바꿨는지 한두 문장 한국어로.
"""


def _clean_lines(lines):
    out = [str(x or "").strip() for x in (lines or []) if isinstance(x, (str, int, float))]
    return out


def revise(lines, message, history=None, product="", *, call=None, tries=2):
    """→ {"reply": str, "lines": [...같은 줄 수], "changed": [바뀐 줄 번호], "auth": "vertex"|"free"}.
    입력이 잘못됐거나 AI가 계약(줄 수·빈 줄)을 못 지키면 ValueError — 호출부가 그대로 화면에 띄운다.
    call: 테스트가 갈아끼우는 (prompt, schema) -> dict."""
    src = _clean_lines(lines)
    if not src or not any(src):
        raise ValueError("고칠 대본이 없어요 — 칸에 문장을 먼저 넣어 주세요")
    if len(src) > MAX_LINES:
        raise ValueError("줄이 너무 많아요(%d줄 초과)" % MAX_LINES)
    msg = str(message or "").strip()
    if not msg:
        raise ValueError("요청을 적어 주세요")
    msg = msg[:MAX_MSG_CHARS]
    hist = []
    for h in (history or [])[-MAX_HISTORY:]:
        if not isinstance(h, dict):
            continue
        who = "회원" if h.get("role") == "user" else "편집자"
        t = str(h.get("text") or "").strip()[:MAX_MSG_CHARS]
        if t:
            hist.append("%s: %s" % (who, t))
    numbered = "\n".join("%d. %s" % (i + 1, x or "(빈 칸)") for i, x in enumerate(src))
    hint = ("\n[상품] %s\n" % product.strip()) if (product or "").strip() else ""
    prompt = _PROMPT.format(n=len(src), lines=numbered, product_hint=hint,
                            history="\n".join(hist) or "(없음)", message=msg)
    note = {}   # _call_json 이 실제로 탄 길을 적는다(auth="vertex") — 화면이 "내 버텍스 / 무료 제미나이"를 말한다
    call = call or (lambda p, s: script_generate._call_json(p, s, note=note))
    last = ""
    for _ in range(max(1, tries)):
        got = call(prompt, _SCHEMA) or {}
        if not got.get("lines"):
            last = "AI 응답이 비었어요(키 소진·응답 오류)"
            continue
        out = [str(x or "").strip()[:MAX_LINE_CHARS] for x in (got.get("lines") or [])]
        if len(out) != len(src):
            last = "줄 수가 안 맞아요(지금 %d줄 → 답 %d줄)" % (len(src), len(out))
            continue
        # 원래 글이 있던 줄이 비어 오면 받지 않는다(빈 칸은 빈 채로 와도 된다)
        if any(s and not o for s, o in zip(src, out)):
            last = "빈 줄이 섞여 나왔어요"
            continue
        reply = str(got.get("reply") or "").strip()[:MAX_MSG_CHARS] or "고쳤어요."
        changed = [i for i, (s, o) in enumerate(zip(src, out)) if s != o]
        return {"reply": reply, "lines": out, "changed": changed,
                "auth": "vertex" if note.get("auth") == "vertex" else "free"}
    raise ValueError("AI가 대본을 못 고쳤어요 — " + (last or "AI 응답이 비었어요") + ". 잠시 후 다시 보내 주세요")
