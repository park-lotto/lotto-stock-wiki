"""샘플 LLM 순응 채점 — 은행 주입 job 중 N에 1편만, 제미니가 주입 아크/부품을 실제로
따랐는지 채점(그대로 베낀 건 오히려 감점). 순수함수: call 주입점으로 실호출 회피."""
import sys

_SCORE = {"type": "integer"}   # 0~5
_COMPLIANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "arc_follow": _SCORE,
        "flavor_follow": _SCORE,
        "verbatim_copy": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["arc_follow", "flavor_follow", "verbatim_copy"],
}


def _script_block(beats):
    return "\n".join(f"{i+1}. {(b.get('narration') or '').strip()}"
                     for i, b in enumerate(beats or []))


def _prompt(bank_context, beats):
    return (
        "너는 한국 쇼핑 숏폼 대본 감수자다. 아래 '주입 은행자료'는 대본 생성 시 참고하라고 "
        "넣어준 학습된 아크·부품이다. 생성된 대본이 그 아크(이야기 골격·비트 흐름)를 따랐는지, "
        "부품의 결(훅 톤·CTA 스타일)을 참고했는지 0~5로 채점해라(5=충실).\n"
        "★단 그대로 베낀 건 순응이 아니라 표절이다 — 문장을 거의 그대로 옮겼으면 "
        "verbatim_copy=true로 표시하고 점수를 낮춰라.\n\n"
        f"[주입 은행자료]\n{(bank_context or '')[:1800]}\n\n"
        f"[생성된 대본]\n{_script_block(beats)}\n\n"
        "arc_follow·flavor_follow(0~5 정수)·verbatim_copy(bool)·reason(한 줄) JSON만 출력.")


def judge_compliance(bank_context, beats, call):
    """주입 은행자료 vs 생성 대본 순응 채점. 실패/빈 beats/무키 → None(결정적 신호로 폴백)."""
    if not beats:
        return None
    try:
        res = call(_prompt(bank_context, beats), _COMPLIANCE_SCHEMA)
    except Exception as e:  # noqa: BLE001
        print(f"bank_compliance.judge_compliance: {e!r}", file=sys.stderr)
        return None
    if not res or not isinstance(res, dict):
        return None

    def _c(k):
        try:
            return max(0, min(5, int(res.get(k, 0))))
        except (TypeError, ValueError):
            return 0

    return {"arc_follow": _c("arc_follow"), "flavor_follow": _c("flavor_follow"),
            "verbatim_copy": bool(res.get("verbatim_copy")),
            "reason": (res.get("reason") or "").strip()}
