"""claude CLI 를 불러 대화한다.

★사장님 PC에서 돌기 때문에 로컬 **구독 인증**을 그대로 쓴다 → API 비용 0원.
  (서버 상주 Agent SDK로 만들면 종량 과금이 된다. 구독 크레딧 제도는 2026-06-15 보류됨)

★대화가 이어진다: `--output-format json` 으로 session_id를 받아 두고, 다음 질문에
  `--resume <id>` 로 넘긴다. 2026-09-02 실측으로 확인함(이름을 기억시켰다가 되물어 확인).

★한 곳에서만 정한다(0순위-B): 어떤 옵션으로 부를지는 여기서만 결정한다.
"""
import json
import os
import subprocess

# 폰에서 실수로 부르면 되돌릴 수 없는 것들. 사장님 본인이라도 텔레그램에서는 막는다 —
# 터미널과 달리 오타·자동완성으로 흘러나가기 쉽고, 되묻는 화면도 없다.
_BLOCKED = (
    "rm -rf", "rm -fr", "drop table", "delete from", "truncate",
    "git push --force", "git reset --hard", "shutdown", "mkfs",
    "format c:", ":(){", "dd if=",
)

_TIMEOUT_SEC = int(os.environ.get("BOT_ASK_TIMEOUT", "600"))


class AskError(Exception):
    """호출 실패. ★사유를 뭉개지 않는다."""


def blocked_reason(text):
    """폰에서 막아야 할 요청이면 사유를, 아니면 None."""
    low = (text or "").lower()
    for bad in _BLOCKED:
        if bad in low:
            return (f"'{bad}' 이 들어 있어 텔레그램에서는 실행하지 않습니다.\n"
                    "되돌릴 수 없는 명령이라 PC 터미널에서 직접 해주세요.")
    return None


def build_args(prompt, *, session_id=None, cwd=None, restricted=False):
    """claude CLI 인자를 만든다. 테스트가 이 함수만 보면 옵션을 검증할 수 있다."""
    args = ["claude", "-p", prompt, "--output-format", "json"]
    if session_id:
        args += ["--resume", session_id]
    if restricted:
        args.append("--restricted")     # Bash 등 실행 도구를 뺀다
    else:
        # 사장님 본인 용도라 되묻지 않는다. 위험한 것은 blocked_reason 이 미리 거른다.
        args += ["--permission-mode", "acceptEdits"]
    return args


def ask(prompt, *, session_id=None, cwd=None, restricted=False, _run=None):
    """클로드에게 묻고 (답, session_id) 를 돌려준다."""
    why = blocked_reason(prompt)
    if why:
        raise AskError(why)

    run = _run or subprocess.run
    args = build_args(prompt, session_id=session_id, restricted=restricted)
    try:
        r = run(args, capture_output=True, text=True,
                timeout=_TIMEOUT_SEC, encoding="utf-8", cwd=cwd)
    except subprocess.TimeoutExpired:
        raise AskError(f"{_TIMEOUT_SEC}초 안에 끝나지 않았습니다. "
                       "긴 작업이면 PC에서 확인해 주세요.") from None
    except FileNotFoundError:
        raise AskError("claude 명령을 찾지 못했습니다. PATH를 확인하세요.") from None

    if r.returncode != 0:
        err = (r.stderr or "").strip() or f"rc={r.returncode}"
        raise AskError(f"클로드 호출이 실패했습니다: {err[:300]}")

    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        raise AskError("응답을 읽지 못했습니다(JSON 아님): "
                       + (r.stdout or "")[:200]) from None

    if data.get("is_error"):
        raise AskError(f"클로드가 오류를 냈습니다: {str(data.get('result'))[:300]}")

    return str(data.get("result") or "").strip(), data.get("session_id")
