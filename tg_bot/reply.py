"""조사 결과 → 사장님께 보낼 답변 문자열.

★고객 문구를 새로 지어내지 않는다. app.py 의 `_user_facing_error`가 **이미 완성돼 있다**
  (규칙 6종 + "이미 사람 말로 쓴 안내는 그대로" 판정, 2026-09-01에 실패 100건 분석해 갱신).
  베껴 적으면 저쪽이 바뀔 때 어긋난다 — 0순위-B가 경고하는 바로 그 모양이라 **그대로 부른다.**

★app.py를 통째로 import하지 않는다(18,011줄, DB·서버 기동 부작용). 필요한 함수만
  소스에서 떼어 실행한다. 못 떼면 뭉개지 않고 사유를 남긴 채 폴백한다.
"""
import os
import re

_FALLBACK = "처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."

# bot_qa.py:17 과 같은 목록 — 돈 얘기는 잘못 답하면 분쟁이다.
_SENSITIVE = ("환불", "결제", "계좌", "입금", "카드", "청구", "요금제", "해지", "탈퇴")

_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "shopping_shorts", "app.py")


def _load_user_facing_error():
    """app.py에서 변환표와 그 함수들만 떼어 온다.

    떼어 오는 것: _USER_ERROR_RULES · _DEV_ERROR_MARKS · _looks_user_written ·
                  _user_facing_error  — 넷 다 순수 함수/상수라 부작용이 없다.
    """
    try:
        src = open(_APP, encoding="utf-8").read()
    except OSError:
        return None

    wanted = ("_USER_ERROR_RULES", "_DEV_ERROR_MARKS",
              "_looks_user_written", "_user_facing_error")
    chunks = []
    for name in wanted:
        # 정의 시작부터 다음 최상위 정의 직전까지.
        m = re.search(rf"^(?:{re.escape(name)} = |def {re.escape(name)}\()",
                      src, re.M)
        if not m:
            return None
        rest = src[m.start():]
        # ★자기 자신의 첫 줄을 건너뛴다. rest[1:]로 한 글자만 건너뛰면 같은 줄이
        #   다시 걸려 정의가 1글자로 잘린다(2026-09-02에 실제로 그랬다).
        head = rest.index("\n") + 1
        nxt = re.search(r"^(?:def |@app\.|[A-Za-z_]+ = )", rest[head:], re.M)
        chunks.append(rest[: head + nxt.start()] if nxt else rest)

    ns = {}
    try:
        exec(compile("\n".join(chunks), "<app.py 발췌>", "exec"), ns)  # noqa: S102
    except Exception:       # noqa: BLE001 — 못 떼면 폴백한다. 봇을 죽이지 않는다.
        return None
    return ns.get("_user_facing_error")


_user_facing_error = _load_user_facing_error()


def customer_line(error):
    """오류 문자열 → 고객에게 그대로 보낼 수 있는 한 줄."""
    if _user_facing_error is not None:
        try:
            return _user_facing_error(error)
        except Exception:   # noqa: BLE001
            pass
    return _FALLBACK


def table_loaded():
    """app.py 변환표를 실제로 쓰고 있는가. 테스트·진단용."""
    return _user_facing_error is not None


def build(job_id, job, *, question=""):
    """조사 결과를 사장님이 읽을 형태로 조립한다."""
    status = (job or {}).get("status", "")
    error = (job or {}).get("error") or ""
    parts = [f"📋 job {job_id}", ""]

    if status == "failed" or error:
        parts += ["【원인】", f"  {error or '사유가 기록되지 않았습니다'}", ""]
        parts += ["【고객께 보낼 문구】", f"  {customer_line(error)}", ""]
    else:
        parts += [f"【상태】 정상 ({status or '진행 중'})", ""]

    if any(w in (question or "") for w in _SENSITIVE):
        parts += ["⚠️ 돈과 관련된 문의입니다. 사장님이 직접 확인해 주세요.", ""]

    return "\n".join(parts).rstrip()
