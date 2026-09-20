import json
import subprocess

import pytest

from tg_bot.ask import AskError, ask, blocked_reason, build_args


class FakeRun:
    """subprocess.run 흉내 — 호출 인자를 기록한다."""

    def __init__(self, payload=None, rc=0, stdout=None, raises=None):
        self.payload = payload if payload is not None else {
            "result": "답변", "session_id": "S1"}
        self.rc = rc
        self.stdout = stdout
        self.raises = raises
        self.calls = []

    def __call__(self, args, **kw):
        self.calls.append((args, kw))
        if self.raises:
            raise self.raises

        class R:
            returncode = self.rc
            stdout = self.stdout if self.stdout is not None else json.dumps(
                self.payload)
            stderr = "" if self.rc == 0 else "터졌다"
        return R()


# ── 위험 명령 차단 ────────────────────────────────────────────────

def test_rm_rf는_막는다():
    assert blocked_reason("rm -rf / 해줘") is not None


def test_대문자여도_막는다():
    assert blocked_reason("RM -RF /tmp") is not None


def test_DB_삭제도_막는다():
    assert blocked_reason("DROP TABLE customers") is not None


def test_강제푸시도_막는다():
    assert blocked_reason("git push --force origin main") is not None


def test_평범한_요청은_안_막는다():
    assert blocked_reason("이 파일 좀 고쳐줘") is None


def test_막힌_요청은_실행_자체를_안_한다():
    """★막았다고 말만 하고 실제로 부르면 소용없다."""
    run = FakeRun()
    with pytest.raises(AskError) as e:
        ask("rm -rf /", _run=run)
    assert run.calls == []
    assert "되돌릴 수 없" in str(e.value)


# ── 대화 이어짐 ───────────────────────────────────────────────────

def test_첫_질문엔_resume가_없다():
    args = build_args("안녕")
    assert "--resume" not in args


def test_세션이_있으면_resume로_잇는다():
    """★2026-09-02 실측: --resume <id> 로 대화가 실제로 이어진다."""
    args = build_args("이어서", session_id="S9")
    assert args[args.index("--resume") + 1] == "S9"


def test_session_id를_돌려준다():
    run = FakeRun({"result": "답", "session_id": "S7"})
    text, sid = ask("질문", _run=run)
    assert (text, sid) == ("답", "S7")


def test_json_출력형식을_반드시_쓴다():
    """session_id를 받으려면 이 옵션이 있어야 한다."""
    args = build_args("x")
    assert args[args.index("--output-format") + 1] == "json"


def test_restricted면_실행도구를_뺀다():
    assert "--restricted" in build_args("x", restricted=True)


def test_기본은_되묻지_않는다():
    """사장님 본인 용도 — 폰에서 매번 승인 누르게 하면 안 쓴다."""
    args = build_args("x")
    assert args[args.index("--permission-mode") + 1] == "acceptEdits"


# ── 실패를 뭉개지 않는다 ──────────────────────────────────────────

def test_rc가_0이_아니면_사유를_보여준다():
    with pytest.raises(AskError) as e:
        ask("질문", _run=FakeRun(rc=1))
    assert "터졌다" in str(e.value)


def test_시간초과는_그렇게_말한다():
    run = FakeRun(raises=subprocess.TimeoutExpired("claude", 1))
    with pytest.raises(AskError) as e:
        ask("질문", _run=run)
    assert "끝나지 않았" in str(e.value)


def test_claude가_없으면_그렇게_말한다():
    run = FakeRun(raises=FileNotFoundError())
    with pytest.raises(AskError) as e:
        ask("질문", _run=run)
    assert "찾지 못했" in str(e.value)


def test_JSON이_아니면_원문을_보여준다():
    with pytest.raises(AskError) as e:
        ask("질문", _run=FakeRun(stdout="이건 JSON이 아니다"))
    assert "JSON 아님" in str(e.value)


def test_클로드가_오류를_내면_그대로_전한다():
    run = FakeRun({"is_error": True, "result": "한도 초과"})
    with pytest.raises(AskError) as e:
        ask("질문", _run=run)
    assert "한도 초과" in str(e.value)
