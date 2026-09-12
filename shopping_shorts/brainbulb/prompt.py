# -*- coding: utf-8 -*-
"""대본 생성 요청 — 소재 + 규칙표 지시문(lint.prompt_block) + 8편 분포 목표 → JSON 대본.

LLM 호출기는 주입한다(`call(prompt:str) -> str`). 키·모델 선택은 pipeline/호출자 몫 — 테스트는 가짜 호출기로 돈다.
"""
import json
import re

from . import spec, lint

SCHEMA_EXAMPLE = {
    "title": {"h1": "흰 윗줄 9~13자", "h2": "노란 아랫줄 12~15자 숫자 포함", "card": "오프닝에서 읽어주는 한 문장 26~33자",
              "youtube": "유튜브 제목 구두점 없이"},
    "region": {"region": "국내", "place": "장소", "reason": "왜 국내인지"},
    "groups": [
        {"text": "첫 컷은 문장을 끝내지 않고", "color": "WHITE", "role": "NARR", "img": 1},
        {"text": "벌써 나온다고", "color": "RED", "role": "CHAR", "meme": "경악/충격"},
        {"text": "사과보다 복귀가 빨랐다", "color": "RED", "role": "PUNCH", "meme": "무표정/멍"},
    ],
}

TARGETS = (
    "- 컷 22~32개, 컷당 한 호흡(6~14자). 총 35~55초 분량.\n"
    "- 색 분포: WHITE 과반(NARR), RED 3~4컷(CHAR 대사·마지막 PUNCH), YELLOW 2~4, PINK 정확히 1, ORANGE 0~1.\n"
    "- 역할: NARR 16~27, CHAR 3~7, PUNCH 정확히 1(마지막 컷, RED, 밈).\n"
    "- 밈 4~5컷(전체 14~18%). 첫 밈은 6~8번째 컷. RED 컷은 전부 밈 컷. 마지막 컷도 밈(무표정/멍이 관행).\n"
    "- 이미지 슬롯 9~11개(img 번호 1부터). 한 슬롯을 2~3컷이 이어서 공유.\n"
    "- 말투는 하나로 통일: '~였다/~했다' 계열 또는 '~임/~됨/~음' 계열."
)

# 마지막 두 컷은 반려가 가장 잦은 자리다(실측: 테이저건 편이 4회 만에 통과). 글로 설명하는 대신
# **실제 채널 5편의 끝맺음을 그대로 보여준다** — 앞 컷이 닫히고 마지막이 독립 문장인 것이 한눈에 보인다.
ENDING_EXAMPLES = (
    "\n[끝맺음 예시 — 실제 이 채널 5편의 마지막 두 컷. 이 모양을 따라라]\n"
    "  · 앞 «침묵은 딱 2주였다»          → 마지막 «사과보다 복귀가 빨랐다»\n"
    "  · 앞 «코로나 때 급증한 카페가 정점 찍은 셈» → 마지막 «떠난 뒤 남은 건 녹색 연못뿐임»\n"
    "  · 앞 «애들이 보여달란다고 꺼낼 장비가 아닌데» → 마지막 «몰랐다는 말로 끝날 일이 아니다»\n"
    "  · 앞 «대원들은 비만 기다린다»      → 마지막 «사람이 낸 불이다»\n"
    "  · 앞 «박위는 아직 조용하다»        → 마지막 «이제 침묵이 더 위험하다»\n"
    "  ★공통점: 앞 컷에서 문장이 **끝난다**. 마지막 컷은 주어까지 갖춘 새 문장이고, 그것만 읽어도 말이 된다.\n"
    "  ✘ 이렇게 쓰지 마라: 앞 «학부모는 분통을» → 마지막 «터뜨리는 중임»  (한 문장을 둘로 잘랐다 — 반려된다)\n"
)


def build(source_text, *, feedback=""):
    return (
        "너는 '뇌전구' 채널의 숏폼 대본 작가다. 아래 소재(기사)를 **다시 써서** 자막 컷 대본을 만든다.\n"
        "출력은 JSON 하나만. 설명·코드펜스 없이 JSON만.\n\n"
        f"[규칙 — 어기면 반려된다]\n{lint.prompt_block()}\n\n"
        f"[분포 목표 — 실제 채널 8편 실측]\n{TARGETS}\n"
        f"{ENDING_EXAMPLES}\n"
        f"[출력 형식 예시]\n{json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False, indent=1)}\n\n"
        f"[소재]\n{source_text.strip()}\n"
        f"{feedback}"
    )


def parse_any(raw):
    """LLM 응답 → dict (스키마 검사 없음). 코드펜스·앞뒤 잡문을 걷어내고 첫 JSON 객체만."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.S)
    start = s.find("{")
    if start < 0:
        raise ValueError("응답에 JSON 객체가 없습니다")
    try:
        d, _end = json.JSONDecoder().raw_decode(s[start:])
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 파싱 실패: {e}") from e
    return d


def parse(raw):
    """LLM 응답 → dict. 코드펜스·앞뒤 잡문을 걷어낸다. 실패하면 ValueError(원인 포함)."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.S)
    start = s.find("{")
    if start < 0:
        raise ValueError("응답에 JSON 객체가 없습니다")
    try:
        d, _end = json.JSONDecoder().raw_decode(s[start:])   # 첫 객체 하나만 — 뒤에 잡문·둘째 객체가 붙어도 산다(실측 'Extra data')
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 파싱 실패: {e}") from e
    for k in ("title", "groups"):
        if k not in d:
            raise ValueError(f"대본에 '{k}'가 없습니다")
    for g in d["groups"]:
        g.pop("lines", None)          # 줄나눔은 우리가 한다 — LLM lines는 버린다(볼케이노와 같다)
    return d


def generate(source_text, call, *, max_rewrites=None, fonts_dir=None, log=print):
    """생성 → 린트 → 반려면 사유를 붙여 재작성 (볼케이노 30→2→0 루프). → (script_with_lines, issues, attempts)"""
    max_rewrites = spec.POLICY_MAX_REWRITES if max_rewrites is None else max_rewrites
    fb = ""
    last = None
    for attempt in range(max_rewrites + 1):
        raw = call(build(source_text, feedback=fb))
        try:
            script = parse(raw)
        except ValueError as e:                     # 형식 오류도 반려처럼 — 사유를 붙여 다시 쓰게 한다
            log(f"[brainbulb.script] 시도 {attempt + 1}: 형식 오류 — {e}")
            fb = f"\n\n[재작성 지시 — 출력 형식 오류: {e}. 설명·코드펜스 없이 JSON 객체 **하나만** 출력하라]"
            if last is None:
                last = ({"title": {}, "groups": []}, [lint.Issue("format", lint.REJECT, "output", str(e)[:80], "JSON 객체 하나만")], attempt + 1)
            continue
        issues, laid = lint.lint(script, source_text=source_text, fonts_dir=fonts_dir)
        rej = lint.rejects(issues)
        log(f"[brainbulb.script] 시도 {attempt + 1}: 컷 {len(script['groups'])} · 반려 {len(rej)} · 경고 {len(issues) - len(rej)}")
        last = (laid, issues, attempt + 1)
        if not rej:
            return last
        fb = lint.feedback(issues)
    return last
