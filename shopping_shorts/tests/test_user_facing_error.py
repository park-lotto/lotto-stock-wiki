# -*- coding: utf-8 -*-
"""실패 사유가 고객에게 **말이 되게** 나가는지.

★왜 있나(2026-09-01 사장님 지시 "3단계에 실패사유 지금 안나오는것들 다 적어줘야대").
  _USER_ERROR_RULES에 안 걸리는 사유가 전부 "처리 중 문제가 발생했습니다"로 뭉개져,
  애써 만든 안내가 고객에게 통째로 사라졌다. 실측(라이브, 최근 30일 실패 100건):
    · 가로형 영상 섞임 + 문제 영상 URL      20건 → "처리 중 문제가…"
    · 소스 못 받음 + 실패한 URL 목록          6건 → URL이 사라진 일반 문구
    · 402 결제 필요                        26건 → "처리 중 문제가…"
  고객은 무엇을 고쳐야 하는지 알 수 없어 그대로 멈춘다.
"""
import io
import os

_SRC = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _load():
    """app.py 전체를 import하지 않고 이 규칙 블록만 떼어 돌린다(무거운 임포트 회피)."""
    src = io.open(_SRC, encoding="utf-8").read()
    i, j = src.index("_USER_ERROR_RULES = ("), src.index("def _script_hash")
    ns = {}
    exec(compile(src[i:j], "app_rules", "exec"), ns)   # noqa: S102 — 테스트 전용 슬라이스
    return ns["_user_facing_error"]


def test_사람말로_쓴_안내는_그대로_나간다():
    """고객이 **무엇을 고쳐야 하는지**가 담긴 문장은 순화하면 안 된다 — URL이 사라진다."""
    f = _load()
    가로형 = ("가로형(롱폼) 영상이 1개 섞여 있어요 — 세로 숏폼으로 만들면 좌우가 잘려"
             " 원본과 다르게 나옵니다. 아래 영상을 빼고 다시 만들어 주세요:\n"
             "· https://www.tiktok.com/@x/video/1 (1920x1080 가로)")
    assert f(가로형) == 가로형, "문제 영상 URL이 담긴 안내가 뭉개지면 고객은 고칠 수 없다"

    못받음 = "소스 영상을 하나도 못 받았습니다 — 모든 URL 다운로드 실패: · https://a/b"
    assert f(못받음) == 못받음, "'다운로드 실패'가 규칙에 걸려 URL 목록째 지워지면 안 된다"


def test_개발자_원문은_고객말로_바뀐다():
    f = _load()
    for raw in ("402 Client Error: Payment Required for url: https://api.x",
                "401 Client Error: Unauthorized for url: https://api.x",
                "Command '['ffmpeg', '-y']' returned non-zero exit status 1",
                "No module named 'alibabacloud_oss_v2'",
                "[60002] You don't have enough credits for this",
                "EDL 비어있음(plan_empty) — 대본은 820자 뽑혔는데 편집안(EDL)이 비었습니다"):
        out = f(raw)
        assert out != raw, f"개발자 원문이 그대로 샜다: {raw[:40]}"
        assert "Error" not in out and "module" not in out


def test_고객잘못이_아닌_것은_그렇게_말한다():
    """402·401·서버오류는 고객이 고칠 수 없다. '다시 시도'만 시키면 무한히 헤맨다."""
    f = _load()
    for raw in ("402 Client Error: Payment Required for url: https://x",
                "No module named 'alibabacloud_oss_v2'"):
        assert "고객님 잘못이 아니" in f(raw)


def test_모르는_사유도_최소한_말은_된다():
    f = _load()
    out = f("zzz unknown weirdness 12345")
    assert out and "처리 중 문제" in out
