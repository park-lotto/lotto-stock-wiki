"""칼카피 트랙 세션 시작 알림 — 지침서(channel/칼카피_시작.md)를 무조건 읽고 시작하게 한다.

사장님(2026-10-19): "이 트랙 전체에서 작업하는 것들 아주 중요한 규칙이니까 새 규칙 나오면 세션 공유하고
새로 시작할 때 무조건 읽고 시작하고 지침서를 확실하게 만들어놔."
SessionStart 훅이 부른다. 칼카피 트랙 폴더가 아니면 아무것도 안 낸다. 어떤 오류에도 exit 0(세션을 막지 않는다).
"""
import json, os, sys

DOC = os.path.join("channel", "칼카피_시작.md")
TRACK = "칼카피숏템엔진"


def notice(root):
    text = open(os.path.join(root, DOC), encoding="utf-8").read()
    lines = text.splitlines()
    updated = next((l.strip("> ").strip() for l in lines if "마지막 갱신" in l), "")
    top = lines[:lines.index(next(l for l in lines if l.startswith("## ")))]
    box = [l for l in top if l.startswith("> 🛑") or (l.startswith("> ") and l[2:3].isdigit())]
    heads = [l.lstrip("# ").strip() for l in lines if l.startswith("## ")]
    return ("★칼카피 트랙 세션이다. 다른 일보다 먼저 `channel/칼카피_시작.md`(지침서)를 Read 로 끝까지 읽고 시작하라.\n"
            "★사장님이 '<채널> 칼카피하자' 라고 하면 = tools/calcopy/칼카피_분석지침서.md §1 실행 대본대로 "
            "`py tools/calcopy/engine/kal.py <채널> --slug … --brand … --hybrid …` 부터(10-20).\n"
            f"{updated}\n" + "\n".join(box) + "\n절 목록: " + " | ".join(heads))


def main():
    try:
        d = os.getcwd()
        if TRACK not in d:
            return
        while not os.path.isfile(os.path.join(d, DOC)):
            n = os.path.dirname(d)
            if n == d:
                return
            d = n
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": notice(d)}}
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False))
    except Exception:
        pass


if __name__ == "__main__":
    main()
