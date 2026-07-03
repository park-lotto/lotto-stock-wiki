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


_INSIGHT_PROMPT_TEMPLATE = """너는 오늘 시장 상황을 한눈에 설명하는 헤드라인
작성자다.

철칙:
- 전문용어 최소화, 쉬운 말투
- 아래 재료에 있는 사실만 써라. 이유 데이터가 없으면 "~로 보임"이라고 명시하며
  수급 관점으로 설명해라(지어내지 마라)
- 섹터 나열은 하지 마라 — 지수 흐름과 특징종목 이유에만 집중해라

## 오늘 지수 흐름 (실측)
시가 {open}, 저점 {low}({low_t}), 고점 {high}({high_t}), 현재 {current}
시가 대비 현재 등락률: {change_pct}% ← 상승/하락/보합 판단은 반드시 이 숫자를 그대로 써라.
직접 가격을 비교해서 계산하지 마라(계산 실수로 오판하는 사례 있었음). ±0.5% 이내일 때만 "보합"이라고 써라.

## 오늘 특징종목
{movers_text}

## 오늘 시장 관련 코멘트(텔레그램/리포트)
{atoms_text}

## 출력 형식 (정확히 이렇게)
헤드라인: <오늘 시장을 한 줄로 요약한 강한 제목, 12자 내외>
본문:
<짧은 문단 2~3개로 나눠서 써라(문단 사이 빈 줄 하나). 각 문단 앞에 어울리는
이모지 하나씩. 특징종목 이유가 있으면 자연스럽게 문단 안에 녹여서 언급해라>
"""


def build_insight_prompt(index_shape: dict | None, movers: list[dict],
                           market_atoms: list[str]) -> str | None:
    if not index_shape:
        return None
    movers_text = "\n".join(
        f"- {m['name']} {m['change_rate']}%: {m['news_reason'] or '이유 데이터 없음'}"
        for m in movers) or "(없음)"
    atoms_text = "\n".join(f"- {c}" for c in market_atoms) or "(없음)"
    change_pct = index_shape.get("change_pct")
    if change_pct is None:
        open_p = index_shape["open"]
        change_pct = round((index_shape["current"] - open_p) / open_p * 100, 2) if open_p else 0.0
    return _INSIGHT_PROMPT_TEMPLATE.format(
        open=index_shape["open"], low=index_shape["low"], low_t=index_shape["low_t"],
        high=index_shape["high"], high_t=index_shape["high_t"], current=index_shape["current"],
        change_pct=change_pct, movers_text=movers_text, atoms_text=atoms_text)


def parse_insight_response(text: str) -> dict | None:
    """헤드라인은 한 줄, 본문은 '본문:' 다음 줄부터 끝까지 전부(문단 구분용
    빈 줄 포함) 캡처 — 기존 parse_briefing_response와 달리 본문이 여러 줄이라
    single-line 캡처로는 문단이 다 잘려나간다."""
    text = (text or "").strip()
    if not text:
        return None
    lines = text.splitlines()
    headline = None
    body_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if headline is None and stripped.startswith("헤드라인:"):
            headline = stripped.split("헤드라인:", 1)[1].strip()
        elif stripped.startswith("본문:"):
            after = stripped.split("본문:", 1)[1].strip()
            body_start = i
            first_line = after
            break
    if headline is None or body_start is None:
        return None
    rest = lines[body_start + 1:]
    body = "\n".join(([first_line] if first_line else []) + rest).strip()
    if not body:
        return None
    return {"headline": headline, "body": body}
