# -*- coding: utf-8 -*-
"""두 모델 논의 — 클로드가 코덱스를 **직접 불러** 주고받는다 (2026-09-09).

사장님: "주고받고 대화를 할 수 있는 방법을 만들어봐"

## 어떻게 되나

클로드(이 세션)가 Bash로 `codex exec`를 부른다. 즉 **사람이 파일을 옮길 필요가 없다** —
클로드가 질문을 던지고, 답을 받고, 비판하고, 다시 던진다. 전 과정이 한 파일에 쌓인다.

    py tools/discuss.py ask   "<주제>" "<질문>"      # 코덱스에 묻는다
    py tools/discuss.py show  "<주제>"               # 지금까지 오간 것
    py tools/discuss.py log   "<주제>" 클로드 "<내용>"  # 내 답·비판을 같은 파일에 남긴다

기록: `docs/decide/<날짜>-<주제>.md`

## 왜 read-only인가

논의는 **말로 하는 것**이다. 코덱스가 논의 중에 파일을 고치면 클로드의 트랙과 부딪혀
서로의 작업을 덮는다(이 저장소가 트랙을 나누는 이유와 같다). 그래서 `-s read-only`로
묶는다 — 코드는 각자 자기 트랙에서 고친다.

## 왜 "각자 먼저, 그다음 비판"인가

먼저 나온 답을 보고 쓰면 그쪽으로 끌려간다. 그러면 두 모델을 쓴 의미가 없다.
그래서 `ask`는 **내 답을 파일에 남긴 뒤** 부르는 것을 전제로 한다(규약 ②).
규약 전문: `docs/2모델_논의규약.md`
"""
import datetime as _dt
import io as _io
import pathlib
import re
import shutil
import subprocess
import sys

# ★윈도우 콘솔은 cp949라 한글 출력이 그냥 죽는다(UnicodeEncodeError).
#   기록 파일은 늘 UTF-8이고, 화면 출력만 여기서 안전하게 바꾼다.
for _st in ("stdout", "stderr"):
    try:
        getattr(sys, _st).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

BASE = pathlib.Path(__file__).resolve().parent.parent
OUT = BASE / "docs" / "decide"
TIMEOUT_S = 900          # 코덱스가 저장소를 읽고 생각할 시간. 넘으면 그 사실을 남긴다


def _path(topic):
    slug = re.sub(r"[^\w가-힣-]+", "-", topic).strip("-")[:50]
    return OUT / ("%s-%s.md" % (_dt.date.today().isoformat(), slug))


def _append(topic, who, text):
    p = _path(topic)
    p.parent.mkdir(parents=True, exist_ok=True)
    head = "" if p.exists() else "# %s\n\n_%s · 참여: 코덱스 / 클로드_\n" % (
        topic, _dt.date.today().isoformat())
    stamp = _dt.datetime.now().strftime("%H:%M")
    with p.open("a", encoding="utf-8") as f:
        f.write("%s\n---\n\n## %s · %s\n\n%s\n\n" % (head, who, stamp, text.strip()))
    return p


def _clean(raw):
    """codex exec 출력에서 **답만** 건져낸다.

    출력은 헤더(sandbox·session id) → `--------` → `user` 블록 → `codex` 블록 →
    `tokens used` 순이다. 형식이 바뀌어도 통째로 남기도록 폴백을 둔다 —
    조용히 빈 문자열을 돌려주면 "코덱스가 답을 안 했다"로 오독한다.
    """
    if "\ncodex\n" in raw:
        tail = raw.rsplit("\ncodex\n", 1)[1]
        return re.split(r"\ntokens used\n", tail)[0].strip() or raw.strip()
    return raw.strip()


def ask(topic, question, model=None):
    """코덱스에 묻고 답을 받아 같은 파일에 남긴다."""
    ctx = ("너는 지금 다른 AI(클로드)와 **최고의 결정을 찾는 논의** 중이다.\n"
           "규약: docs/2모델_논의규약.md — 읽고 따르라.\n"
           "★동의만 하지 마라. 근거의 구멍을 짚어라.\n"
           "★추측 금지 — 저장소 파일·실측 수치로 답하라. 확인 못 한 건 그렇다고 적어라.\n"
           "★코드를 고치지 마라(읽기 전용). 고칠 것이 있으면 말로 적어라.\n"
           "★마지막에 반드시: [결론] 한 줄 / [약점] 내 답이 틀렸다면 무엇 때문인가 /\n"
           "  [재는 법] 의견이 갈리면 무엇을 재면 갈리나\n\n"
           "지금까지 오간 논의:\n%s\n\n=== 질문 ===\n%s")
    p = _path(topic)
    prior = p.read_text(encoding="utf-8")[-6000:] if p.exists() else "(없음)"
    # ★윈도우에서 `codex`는 npm이 깐 **셸 래퍼**라 subprocess가 그대로는 못 찾는다
    #   (FileNotFoundError → "codex CLI 없음"으로 오독했다). .cmd를 직접 찾아 쓴다.
    exe = shutil.which("codex") or shutil.which("codex.cmd")
    if not exe:
        _append(topic, "코덱스", "(codex CLI를 못 찾았다 — `npm i -g @openai/codex`)")
        print("codex CLI 없음")
        return
    cmd = [exe, "exec", "-s", "read-only", "-C", str(BASE)]
    if model:
        cmd += ["-m", model]
    cmd.append(ctx % (prior, question))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        ans = _clean(r.stdout or "") or ("(빈 응답) stderr: " + (r.stderr or "")[:400])
    except subprocess.TimeoutExpired:
        ans = "(코덱스 응답 없음 — %d초 초과. 질문을 쪼개서 다시 물어라)" % TIMEOUT_S
    except FileNotFoundError:
        ans = "(codex CLI 없음 — `npm i -g @openai/codex`)"
    f = _append(topic, "코덱스", "**질문**: %s\n\n%s" % (question, ans))
    print(ans)
    print("\n[기록] %s" % f)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    cmd, topic = sys.argv[1], sys.argv[2]
    if cmd == "ask":
        ask(topic, sys.argv[3], model=(sys.argv[4] if len(sys.argv) > 4 else None))
    elif cmd == "log":
        print("[기록] %s" % _append(topic, sys.argv[3], sys.argv[4]))
    elif cmd == "show":
        p = _path(topic)
        print(p.read_text(encoding="utf-8") if p.exists() else "(아직 없음: %s)" % p)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
