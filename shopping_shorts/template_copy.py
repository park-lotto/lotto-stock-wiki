"""장면꾸미기 카피 구조 계약.

이븐쇼핑형과 인스타 관계썰형은 말투만 다르고 화면 슬롯은 같다. 생성기와
미리보기·렌더가 각자 글자 수와 줄 나누기를 정하면 같은 제목도 화면마다 달라지므로,
두 줄 훅과 보조 제목의 모양은 이 파일 한 곳에서만 정의한다.
"""
from __future__ import annotations

import re
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


# 첫 줄이 이것으로 끝나면 말이 끊긴다 — 뒤 낱말과 한 덩어리인 자리다.
#   "아니 텀블러이 / 있다고?"처럼 조사에서 끊으면 읽는 사람이 다시 읽는다(2026-09-22 사장님 제보).
_CUT_BAD_END = re.compile(
    r"(?:이|가|을|를|은|는|에|와|과|도|만|의|로|으로|부터|까지|에서|한테|보다|랑|이랑|처럼|마다|께|께서)$"
)
# 둘째 줄이 이것으로 시작해도 말이 끊긴다 — 앞 명사를 꾸미던 말이 떨어져 나온 자리다.
#   "코스트코 본사도 / 몰랐던 천재 아이디어" → "코스트코 본사도 몰랐던 / 천재 아이디어"
_CUT_BAD_START = re.compile(
    r"^(?:몰랐던|못한|있는|없는|하는|되는|만든|나온|생긴|좋은|같은|아닌|쓰는|보는|드는|넘는|맞는"
    r"|싶은|받는|사는|먹는|찾는|남는|난|된|한|할|될|그|이|저|더|또|안|못)$"
)
# 첫 줄이 이것으로 끝나면 **좋은 자리**다 — 한 마디가 여기서 닫힌다.
#   실측(템플릿 견본 20개): 살려낸·몰랐던·발견한·놀랄·못한·덕후들의·보였지·있었지 — 전부 이 모양.
_CUT_GOOD_END = re.compile(
    r"(?:은|는|던|한|된|난|낸|랄|을|를)$"           # 관형형 어미 — 뒤 명사를 꾸미고 닫힌다
    r"|(?:지|네|군|다|까|요|음|임)$"                # 종결어미 — 한 마디가 끝난다
    r"|(?:는데|니까|어서|아서|면서|지만|는지|다가|거나|든지)$"   # 연결어미
)


# 관형형 어미 — 이걸로 끝나는 낱말은 **뒤 명사를 꾸민다**(천재적인 활용법 / 몰랐던 생활).
_MODIFIER_END = re.compile(r"(?:인|은|는|던|한|될|을|ㄹ)$")


def _cut_is_clean(before: list[str], after: list[str]) -> bool:
    """이 자리에서 끊으면 말이 안 끊기나."""
    if not before or not after:
        return False
    last = before[-1]
    # 한 글자 낱말이 줄 끝/줄 앞에 혼자 떨어지면 읽기 나쁘다(2026-09-21 '무릎 탁 / 친 천재적인').
    if len(last) <= 1 or len(after[0]) <= 1:
        return False
    if len(last) > 1 and _CUT_BAD_END.search(last):
        return False
    if _CUT_BAD_START.match(after[0]):
        return False
    # ★꾸미는 말은 **뒤 명사를 데리고 가야** 한다 — 첫 줄 끝이 관형형인데 뒤에 명사가 더 있으면,
    #   그 꾸밈말을 둘째 줄로 내려 '천재적인 활용법'처럼 한 덩어리로 만드는 쪽이 낫다.
    #   (2026-09-22 실측: '다이소 덕후들의 천재적인 / 활용법' → '다이소 덕후들의 / 천재적인 활용법')
    if _MODIFIER_END.search(last) and len(after) == 1:
        return False
    return True


def split_hook(value: object, contract: "TemplateCopyContract | None" = None) -> tuple[str, str]:
    """저장된 제목의 명시적 두 줄을 보존하고, 한 줄 데이터를 **두 줄 제목**으로 나눈다.

    ★2026-09-22 사장님 결정 — 대본 첫 문장이 그대로 들어오므로 두 가지를 지킨다:
      ①**말이 안 끊기는 자리 우선**. 조사로 끝나거나(텀블러'이') 꾸미는 말이 떨어지는
        ('몰랐던' 천재…) 자리는 피한다. 길이 균형은 그다음이다.
      ②**줄 길이 상한 안에서만 담는다**(이븐쇼핑 실측 11자/10자). 60자짜리 대본 문장이
        통째로 들어오면 앞부분만 쓰고 나머지는 버린다 — 화면이 글자를 못 담는다.

    이 함수는 문구를 축약하거나 새 사실을 만들지 않는다(자르기만 한다). 길이 검증은
    ``issues``가 담당하며 UI는 실패한 문구를 작게 찌그러뜨리는 대신 적용을 막는다.
    """
    contract = contract or EVEN_SHOPPING
    raw = str(value or "").strip()
    explicit = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(explicit) >= 2:
        return explicit[0], " ".join(explicit[1:])
    text = _one_line(raw)
    words = text.split()
    if len(words) < 2:
        return text, ""

    # ★길이 상한은 **낱말을 자르는 데 쓰지 않는다**(2026-09-22 실측).
    #   템플릿 견본 20개 중 둘째 줄이 계약 10자를 넘는 것이 13개(65%)였다 — '놀라운 생활
    #   아이디어'(11자)가 실제로 화면에 들어간다. 상한으로 낱말을 자르면 '아이디어'가 사라진다.
    #   그래서 상한은 **두 줄에 담을 낱말을 고르는 기준**으로만 쓰고, 고른 낱말은 통째로 남긴다.
    max1, max2 = contract.hook_line_max, contract.hook2_line_max

    def line_len(items: list[str]) -> int:
        return len(" ".join(items))

    # ① 두 줄에 담을 낱말 — 두 줄 상한의 합까지 담되, **낱말은 절대 자르지 않는다**.
    #    한 낱말을 더 담아 상한을 살짝 넘는 쪽이, 낱말을 잘라 '놀라운 생활 아이디어'를
    #    '놀라운 생활'로 만드는 것보다 낫다(2026-09-22 실측: 견본 13개가 상한을 넘는다).
    room = max1 + max2 + 1
    head = [words[0]]
    for word in words[1:]:
        if line_len(head + [word]) > room + len(word) - 1:
            break
        head.append(word)
        if line_len(head) >= room:
            break
    if len(head) < 2:
        return " ".join(head), ""

    # ② 끊는 자리 — ⑴말이 끊기지 않고 ⑵어미로 닫히고 ⑶화면에 들어가고 ⑷두 줄이 고른 자리.
    #    ★'어미로 닫히는 자리'가 여럿이면 **앞쪽**을 고른다. 뒤로 갈수록 첫 줄이 길어져
    #      '다이소 덕후들의 천재적인 / 활용법'처럼 둘째 줄이 한 낱말만 남는다(2026-09-22 실측).
    def score(index: int) -> tuple[int, int, int, int]:
        before, after = head[:index], head[index:]
        clean = 0 if _cut_is_clean(before, after) else 1           # 0이 좋다 — 말이 먼저
        good = 0 if _CUT_GOOD_END.search(before[-1]) else 1        # 어미로 닫히면 좋다
        over = max(0, line_len(before) - max1) + max(0, line_len(after) - max2)
        # 첫 줄이 상한 안에 들어오면 길이 균형 대신 **앞쪽 자리**를 선호한다.
        gap = line_len(before) if line_len(before) <= max1 else abs(line_len(before) - line_len(after))
        return (clean, good, over, gap)

    best = min(range(1, len(head)), key=score)
    return " ".join(head[:best]), " ".join(head[best:])


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
