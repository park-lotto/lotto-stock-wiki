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


def support_from_phrases(phrases: object) -> str:
    """훅 서브카피 한 줄을 **대본 구절에서** 고른다(모델 호출 0회).

    ★왜 필요한가(2026-09-21 실측): 썰쇼핑형 20종 중 **16종**의 훅에 서브카피 띠가 있고
      크기가 전부 화면의 9.4%다. 그런데 그 자리에 들어갈 ``subline``을 파이프라인이
      **한 번도 만들지 않았다**(최근 job 40개 전수: subline 있는 것 0개). 그래서 템플릿
      1/10이 늘 빈 흰 칸이었다.
    ★새 문장을 **지어내지 않는다** — 대본에 실제로 있는 구절만 쓴다. 지어내면 화면과
      나레이션이 어긋나고, 없는 사실이 제목처럼 보인다.
    ★구절 나누기는 렌더 자막과 같은 단위를 그대로 받는다(video_assemble.caption_schedule).
      여기서 따로 자르면 화면마다 다른 문장이 나온다(0순위-B).
    ★길이 계약은 이 파일의 support_max 한 곳이다. 넘치면 낱말 단위로 줄이고,
      그래도 너무 짧아지면(6자 미만) **쓰지 않는다** — 토막난 말보다 빈칸이 낫다.
    """
    limit = EVEN_SHOPPING.support_max
    for phrase in (phrases or []):
        text = _one_line(phrase)
        if not text:
            continue
        if len(text) <= limit:
            return text if len(text) >= 6 else ""
        words, kept = text.split(), []
        for word in words:
            if len(" ".join(kept + [word])) > limit:
                break
            kept.append(word)
        trimmed = " ".join(kept)
        return trimmed if len(trimmed) >= 6 else ""
    return ""


def scene_text(headcopy: object) -> dict[str, str]:
    """저장된 제목 세트를 장면꾸미기 슬롯으로 한 번만 변환한다."""
    source = headcopy if isinstance(headcopy, dict) else {}
    hook1, hook2 = split_hook(source.get("text"))
    # 2026-09-21 사장님: 보조 문구가 없으면 비워 둔다 — 제목을 그대로 복사해 훅에 같은 글이 두 번 나왔다.
    support = _one_line(source.get("subline"))
    # ★사람이 넣은 서브카피(subline)는 종전대로 **본문 제목까지 몬다**
    #   (test_support_copy_drives_hook_band_and_body_title이 지키는 계약).
    # ★반면 대본에서 **자동으로 채운** 서브카피(subline_auto)는 훅 띠만 채우고 본문 제목은
    #   건드리지 않는다(2026-09-21). 자동 채움이 본문 상단 제목까지 대본 한 구절로 바꿔
    #   버리면, 사장님이 보던 본문 화면이 통째로 달라진다.
    auto_support = _one_line(source.get("subline_auto"))
    if not support:
        support = auto_support
    body_title = (_one_line(source.get("body_title"))
                  or _one_line(source.get("subline"))
                  or _one_line(f"{hook1} {hook2}"))   # 본문 제목은 비면 제목을 쓴다
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
