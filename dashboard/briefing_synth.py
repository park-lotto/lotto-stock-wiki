"""브리핑 종합층 — Gemini 프롬프트 조립 + 응답 파싱. 실제 API 호출은 Task5에서
기존 _gemini_text()로 수행(이 파일은 순수 함수만, API 의존성 없음)."""

_PROMPT_TEMPLATE = """너는 일반 투자자 구독자에게 지금 시장 상황을 쉽게 설명하는
브리핑 작성자다. 아래 재료를 보고, 지금 알려줄 만한 게 있으면 딱 1개만 써라.

철칙:
- 전문용어 최소화, 쉬운 말투("외국인이 오전 내내 팔다가 정오부터 매수로 돌아섬" 처럼)
- 아래 재료에 있는 사실만 써라. 추측이면 "~로 보임"이라고 명시해라.
- 알려줄 만큼 중요한 게 없으면 정확히 "브리핑 없음"이라고만 답해라.
- 있으면 정확히 이 형식으로: "헤드라인: <15자 내외 한 줄>\\n본문: <1~2문장>"

## 지수/수급 변동
{alerts_text}

## 최근 뉴스 제목
{headlines_text}

## 최근 시장 코멘트(텔레그램/리포트)
{atoms_text}

## 직전 브리핑(같은 얘기 반복하지 마라)
{prior_text}
"""


def build_briefing_prompt(alerts: list[dict], headlines: list[str],
                            atoms_content: list[str], prior_headlines: list[str]) -> str | None:
    if not alerts and not headlines and not atoms_content:
        return None
    alerts_text = "\n".join(
        f"- {a['label']}: {a['from']} → {a['to']} ({a['ts']})" for a in alerts) or "(없음)"
    headlines_text = "\n".join(f"- {h}" for h in headlines) or "(없음)"
    atoms_text = "\n".join(f"- {c}" for c in atoms_content) or "(없음)"
    prior_text = "\n".join(f"- {p}" for p in prior_headlines) or "(없음)"
    return _PROMPT_TEMPLATE.format(
        alerts_text=alerts_text, headlines_text=headlines_text,
        atoms_text=atoms_text, prior_text=prior_text)


def parse_briefing_response(text: str) -> dict | None:
    text = (text or "").strip()
    if not text or "브리핑 없음" in text:
        return None
    headline, body = None, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("헤드라인:"):
            headline = line.split("헤드라인:", 1)[1].strip()
        elif line.startswith("본문:"):
            body = line.split("본문:", 1)[1].strip()
    if not headline or not body:
        return None
    return {"headline": headline, "body": body}
