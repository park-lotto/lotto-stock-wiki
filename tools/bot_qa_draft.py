"""핸드오프·화면 안내문 → 고객용 Q&A 초안(2026-08-25).

★핸드오프는 개발 기록이라 그대로 못 쓴다 — 실측으로 "사장님"이 916번 나오고
  버그·실패·내부 사정이 적혀 있다. 그래서 **고객 언어로 다시 쓴 초안**을 만들고
  사장님이 검수(승인/수정/버림)한다.
★항상 draft로 들어간다 — 승인 전에는 봇이 절대 쓰지 않는다.

    py tools/bot_qa_draft.py --limit 30
    py tools/bot_qa_draft.py --dry-run --limit 5   ← Gemini 호출·DB쓰기 없이 배선만 확인
"""
import argparse
import glob
import io
import re
import sys

sys.path.insert(0, ".")
from shopping_shorts.script_generate import _call_json      # noqa: E402
from shopping_shorts.store import Store                     # noqa: E402
from shopping_shorts.config import DB_PATH                  # noqa: E402

_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"question": {"type": "string"},
                       "answer": {"type": "string"},
                       "tags": {"type": "string"}},
        "required": ["question", "answer", "tags"]}}},
    "required": ["items"],
}

# ★.format(doc=...)을 쓰지 않는다 — 핸드오프 문서는 개발 기록이라 코드·JSON이 섞여
#   중괄호 { } 가 흔하다(실측: handoff/*.md 150개 중 83개에 { 있음, 최다 44개).
#   .format()은 그 중괄호를 전부 플레이스홀더로 읽어 KeyError/IndexError로 죽는다.
#   문서는 프롬프트에 끼워 넣는 '데이터'일 뿐이므로 단순 문자열 이어붙이기로 넣는다.
_PROMPT_HEAD = """아래는 '숏템메이커'라는 영상 제작 서비스의 **내부 개발 기록**이다.
이걸 읽고, 고객이 실제로 물어볼 만한 질문과 답을 만들어라.

[반드시 지켜라]
- 개발 사정·버그·담당자 이야기는 **빼라**. 고객은 그걸 알 필요가 없다.
- "사장님"·"트랙"·"커밋"·"핸드오프" 같은 내부 용어를 쓰지 마라.
- 기록에 **없는 기능을 지어내지 마라**. 확실한 것만 적어라.
- 답은 존댓말로 2~4문장.
- 만들 게 없으면 items를 빈 배열로 두어라.

[기록]
"""

# ★화면 안내문에서 뽑을 때 쓰는 프롬프트(--source screen).
#   개발 기록과 달리 이건 고객이 실제로 보는 글이라, "무엇이 바뀌었나"가 아니라
#   "지금 어떻게 쓰나"를 묻고 답하게 만든다.
_PROMPT_SCREEN = """아래는 '숏템메이커'라는 영상 제작 서비스에서 **고객이 실제로 보는 화면의 안내문**이다.
이걸 읽고, 이 화면을 쓰는 고객이 실제로 물어볼 만한 질문과 답을 만들어라.

[반드시 지켜라]
- ★"개선했습니다"·"업데이트했습니다"·"수정했습니다" 같은 **변경 이력 말투를 절대 쓰지 마라**.
  고객은 지금 화면을 보고 있다. 과거에 뭐가 바뀌었는지는 알 필요가 없다.
  → "지금 이렇게 됩니다"·"여기서 이렇게 하시면 됩니다"로만 써라.
- 질문은 고객이 **입력창에 칠 법한 말**로 써라. ("자막이 안 보여요", "영상은 어디서 받나요")
- 안내문에 **없는 기능을 지어내지 마라**. 버튼 이름·메뉴 이름은 안내문에 있는 그대로 써라.
- 화면 안에 있어도 관리자 전용·내부 설정으로 보이는 것은 빼라.
- 답은 존댓말로 2~4문장.
- 만들 게 없으면 items를 빈 배열로 두어라.

[화면 안내문]
"""

# 화면에 안 보이는 것(스크립트·스타일·주석)과 태그를 걷어내고 사람이 읽는 글만 남긴다.
_STRIP = re.compile(r"<(script|style)\b.*?</\1>|<!--.*?-->", re.S | re.I)


def _screen_text(html):
    t = _STRIP.sub(" ", html)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = re.sub(r"&#\d+;|&#x[0-9a-fA-F]+;", "", t)
    t = (t.replace("&nbsp;", " ").replace("&amp;", "&")
          .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    lines = []
    for ln in t.splitlines():
        ln = ln.strip()
        # 한글이 없는 줄은 코드 찌꺼기·영문 클래스명일 가능성이 높다
        if len(ln) < 4 or not re.search(r"[가-힣]", ln):
            continue
        if ln not in lines:
            lines.append(ln)
    return "\n".join(lines)


def _build_prompt(doc, head=_PROMPT_HEAD):
    """문서를 프롬프트에 안전하게 끼워 넣는다. doc 안의 {}는 그대로 텍스트로 남는다."""
    return head + doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30, help="만들 초안 개수 상한")
    ap.add_argument("--source", choices=("handoff", "screen"), default="screen",
                     help="초안을 뽑을 원본: screen=고객이 보는 화면 안내문(기본), handoff=개발 기록")
    ap.add_argument("--dry-run", action="store_true",
                     help="Gemini 호출·DB쓰기 없이 프롬프트 생성·파일 순회만 확인")
    args = ap.parse_args()

    store = None if args.dry_run else Store(DB_PATH)
    made = 0
    if args.source == "screen":
        _ADMIN_ONLY = ("admin.html", "ops.html", "bot_admin.html")
        paths = [f for f in sorted(glob.glob("shopping_shorts/static/*.html"))
                 if not f.replace(chr(92), "/").split("/")[-1] in _ADMIN_ONLY]
        head = _PROMPT_SCREEN
    else:
        paths = sorted(glob.glob("handoff/*.md"))
        head = _PROMPT_HEAD

    for path in paths:
        if made >= args.limit:
            break
        raw = io.open(path, encoding="utf-8", errors="replace").read()
        doc = _screen_text(raw) if args.source == "screen" else raw
        doc = doc[:12000]
        # 안내문이 거의 없는 화면(코드만 있는 페이지)은 물어볼 게 없다
        if len(doc) < 300:
            continue
        prompt = _build_prompt(doc, head)

        if args.dry_run:
            # 실제 호출 없이 프롬프트가 만들어지는지만 확인
            print("%s -> prompt %d chars (dry-run, no call)" % (path, len(prompt)))
            made += 1
            continue

        data = _call_json(prompt, _SCHEMA) or {}
        for it in (data.get("items") or []):
            if made >= args.limit:
                break
            q, a = (it.get("question") or "").strip(), (it.get("answer") or "").strip()
            if not q or not a:
                continue
            store.bot_qa_add(room="공통", question=q, answer=a,
                             tags=it.get("tags") or "", source=path)
            made += 1
        print("%s -> %d" % (path, made))
    print("draft created: %d" % made)


if __name__ == "__main__":
    main()
