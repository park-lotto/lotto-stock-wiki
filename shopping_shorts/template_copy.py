"""장면꾸미기 카피 구조 계약.

이븐쇼핑형과 인스타 관계썰형은 말투만 다르고 화면 슬롯은 같다. 생성기와
미리보기·렌더가 각자 글자 수와 줄 나누기를 정하면 같은 제목도 화면마다 달라지므로,
두 줄 훅과 보조 제목의 모양은 이 파일 한 곳에서만 정의한다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateCopyContract:
    hook_line_max: int
    hook_total_max: int
    hook2_line_max: int  # 둘째 줄은 글자가 더 커서(t11 50 vs 43) 한 글자 적다
    support_max: int
    body_title_max: int
    caption_max: int


# 제공된 이븐쇼핑 원본: 큰 제목 11자/10자, 흰 띠와 본문 제목은 한 줄이다.
# 인스타형도 내용만 다르고 이 슬롯 크기를 그대로 쓴다.
EVEN_SHOPPING = TemplateCopyContract(
    hook_line_max=11,
    hook_total_max=22,  # 첫 줄 11자 + 둘째 줄 10자 + 줄바꿈 1자
    # 2026-09-18 실측: 둘째 줄 11자「기차 케이크의 반전법」이 화면 양끝을 5px씩 넘어 잘렸다 → 원본 비율대로 10자.
    hook2_line_max=10,
    support_max=22,
    body_title_max=22,
    caption_max=22,
)


def _one_line(value: object) -> str:
    return " ".join(str(value or "").split())


def split_hook(value: object) -> tuple[str, str]:
    """저장된 제목의 명시적 두 줄을 보존하고, 옛 한 줄 데이터만 균형 분리한다.

    이 함수는 문구를 축약하거나 새 사실을 만들지 않는다. 길이 검증은 ``issues``가
    담당하며 UI는 실패한 문구를 작게 찌그러뜨리는 대신 적용을 막는다.
    """
    raw = str(value or "").strip()
    explicit = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(explicit) >= 2:
        return explicit[0], " ".join(explicit[1:])
    text = _one_line(raw)
    words = text.split()
    if len(words) < 2:
        return text, ""
    best = min(
        range(1, len(words)),
        key=lambda index: abs(
            len(" ".join(words[:index])) - len(" ".join(words[index:]))
        ),
    )
    # 2026-09-21 사장님: '무릎 탁 / 친 천재적인'처럼 한 글자 낱말이 둘째 줄 앞에 떨어지면 말이 끊겨 보인다.
    #   그런 경우 그 낱말을 윗줄로 올린다(전체 길이는 한 낱말만큼만 달라진다).
    if best < len(words) - 1 and len(words[best]) <= 1:
        best += 1
    return " ".join(words[:best]), " ".join(words[best:])


def scene_text(headcopy: object) -> dict[str, str]:
    """저장된 제목 세트를 장면꾸미기 슬롯으로 한 번만 변환한다."""
    source = headcopy if isinstance(headcopy, dict) else {}
    hook1, hook2 = split_hook(source.get("text"))
    # 2026-09-21 사장님: 보조 문구가 없으면 비워 둔다 — 제목을 그대로 복사해 훅에 같은 글이 두 번 나왔다.
    support = _one_line(source.get("subline"))
    body_title = _one_line(source.get("body_title")) or support or _one_line(f"{hook1} {hook2}")   # 본문 제목은 비면 제목을 쓴다
    return {
        "hook1": hook1,
        "hook2": hook2,
        "bodyTitle": body_title,
        "supportTitle": support,
    }


def issues(text: object, contract: TemplateCopyContract = EVEN_SHOPPING) -> list[str]:
    """템플릿에 넣기 전에 사람이 이해할 수 있는 구조 위반을 반환한다."""
    source = text if isinstance(text, dict) else {}
    found: list[str] = []
    for key, label, limit in (("hook1", "훅 제목 1", contract.hook_line_max),
                              ("hook2", "훅 제목 2", contract.hook2_line_max)):
        value = str(source.get(key) or "")
        if "\n" in value or "\r" in value:
            found.append(f"{label}은 한 줄이어야 합니다")
        if len(value) > limit:
            found.append(f"{label}은 공백 포함 {limit}자 이하여야 합니다")
    if not str(source.get("hook1") or "").strip() or not str(source.get("hook2") or "").strip():
        found.append("훅 제목은 두 줄이 모두 있어야 합니다")
    for key, label, limit in (
        ("bodyTitle", "보조·본문 제목", contract.body_title_max),
        ("caption", "본문 자막", contract.caption_max),
    ):
        value = str(source.get(key) or "")
        if len(value) > limit:
            found.append(f"{label}은 공백 포함 {limit}자 이하여야 합니다")
    return found
