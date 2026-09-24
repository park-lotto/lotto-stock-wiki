# -*- coding: utf-8 -*-
"""대본 — 조사 원문 + 규칙표(lint.prompt_block) + 원본 구조 → JSON 대본. 반려되면 사유를 붙여 고쳐 쓰게 한다.

구조는 원본 6편 판독(channel/hotpeople/역분석_2026-09-25.md §4)에서 온다. 예시는 **모양만** 보여준다 —
원본 문장을 그대로 쓰지 않게 인물·내용이 다른 가짜 예시를 쓴다.
"""
from shopping_shorts.channelkit import lint
from . import spec
from shopping_shorts.channelkit.prompt import parse_any

_STRUCTURE = f"""[구조 — 원본 채널 6편 공통]
#1      훅(형광펜): 충격적인 인용이나 반전 사실 한 줄. 이름은 아직 안 밝힘
#2~#4   이름 공개: "그의 이름 \\"○○○\\"" 또는 "○○ 창업주 \\"○○○\\"" 식
#5~#11  시련: 무시·조롱·가난·실패 — 연도·숫자로 구체적으로
#12~#13 전환: 예) "{spec.PIVOT_LINE}" (그대로 써도 됨)
#14~#22 상승: 행동 → 결과, 숫자(순위·기록·금액·기간)
끝      마무리 셋 중 하나: ① 걸린 시간 "N년" ② "~ ○○○ 이야기임." ③ 형광펜 인용 펀치
말투: 반말 명사형(~음/~함/~임/~됨/~짐), 명사로 끊기, "~까지"로 다음 자막에 넘기기. 따옴표 인용 가능.
숫자: 거의 매 자막에 하나. 단, 아래 [조사 원문]에 있는 숫자만(원문 표기 그대로)."""

_SCHEMA = """[출력 — JSON 객체 하나만]
{"person": "주인공 이름",
 "title": {"h1": "헤드라인 윗줄", "h2": "아랫줄", "emph": 1 또는 2, "emph_color": "red" 또는 "yellow"},
 "groups": [
   {"lines": ["윗줄", "아랫줄"], "text": "윗줄 아랫줄", "mark": true, "red": [],
    "scene": "이 자막에 맞는 화면(영어, 구체적으로: who/what/where)", "query": "그 화면이 나올 유튜브 검색어"}
 ],
 "queries": ["인물 영어이름 interview", "…"]}"""

_EXAMPLE = """[예시 — 모양만. 이 인물·문장을 쓰지 마라]
{"person": "김가상", "title": {"h1": "공장 막내에서", "h2": "세계 1위가 된 남자", "emph": 2, "emph_color": "red"},
 "groups": [
  {"lines": ["\\"넌 평생 기계나 닦아라\\""], "text": "\\"넌 평생 기계나 닦아라\\"", "mark": true, "red": [], "scene": "old factory floor, young worker cleaning machine", "query": "Kim Gasang factory documentary"},
  {"lines": ["공장 막내 시절", "그의 이름 \\"김가상\\""], "text": "공장 막내 시절 그의 이름 \\"김가상\\"", "mark": false, "red": [], "scene": "portrait of Kim Gasang young", "query": "Kim Gasang interview"},
  {"lines": ["하지만 그는 달랐음."], "text": "하지만 그는 달랐음.", "mark": false, "red": [], "scene": "Kim Gasang training alone at night", "query": "Kim Gasang training"}
 ],
 "queries": ["Kim Gasang interview", "Kim Gasang final match", "김가상 다큐"]}"""


def build_prompt(research, feedback_text=""):
    return (
        "너는 인물 인간승리 숏폼 채널의 대본 작가다. 나레이션 없이 **자막과 실제 영상만**으로 50~60초.\n\n"
        f"[주인공] {research['name']}\n[주제] {research.get('topic') or '(자유 — 가장 극적인 반전 서사)'}\n\n"
        f"{_STRUCTURE}\n\n[규칙 — 어기면 반려된다]\n{lint.prompt_block()}\n\n{_SCHEMA}\n\n{_EXAMPLE}\n\n"
        f"[조사 원문 — 사실과 숫자는 여기서만]\n{research['text']}\n"
        + (feedback_text or "")
    )


def generate(research, call, *, max_rewrites=None, log=print):
    """→ (script, issues, attempts). 반려가 남으면 마지막 판을 그대로 돌려준다(호출부가 멈춘다)."""
    max_rewrites = spec.POLICY_MAX_REWRITES if max_rewrites is None else max_rewrites
    fb, last = "", None
    for attempt in range(max_rewrites + 1):
        raw = call(build_prompt(research, fb))
        try:
            script = parse_any(raw)
        except Exception as e:  # noqa: BLE001
            issues = [lint.Issue("format", lint.REJECT, "output", str(e)[:80], "JSON 객체 하나만")]
            last = ({"title": {}, "groups": []}, issues, attempt + 1)
            fb = "\n\n[재작성 지시] 방금 출력이 JSON이 아니었다. JSON 객체 하나만 출력하라."
            continue
        for g in script.get("groups") or []:
            if not g.get("text"):
                g["text"] = " ".join(g.get("lines") or [])
        issues, _ = lint.lint(script, source_text=research["text"], do_layout=False)
        rej = lint.rejects(issues)
        log(f"[hotpeople.script] 시도 {attempt + 1}: 자막 {len(script.get('groups') or [])}개, 반려 {len(rej)}")
        last = (script, issues, attempt + 1)
        if not rej:
            return last
        fb = lint.feedback(issues) + "\n\n방금 낸 JSON:\n" + raw.strip()[:12000]
    return last
