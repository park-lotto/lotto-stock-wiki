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


def _build_prompt(doc):
    """문서를 프롬프트에 안전하게 끼워 넣는다. doc 안의 {}는 그대로 텍스트로 남는다."""
    return _PROMPT_HEAD + doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30, help="만들 초안 개수 상한")
    ap.add_argument("--dry-run", action="store_true",
                     help="Gemini 호출·DB쓰기 없이 프롬프트 생성·파일 순회만 확인")
    args = ap.parse_args()

    store = None if args.dry_run else Store(DB_PATH)
    made = 0
    for path in sorted(glob.glob("handoff/*.md")):
        if made >= args.limit:
            break
        doc = io.open(path, encoding="utf-8").read()[:12000]
        prompt = _build_prompt(doc)

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
