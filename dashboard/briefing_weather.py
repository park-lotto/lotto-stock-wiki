"""장중 시황 브리핑 — 종합엔진. claude -p(Opus/Sonnet, Max 구독) 호출 + Gemini 폴백."""
import json
import re
import subprocess
import time as _time

_SYS = """너는 '로또의 스탁브레인' 장중 시황 브리핑 작성자다.
관심종목만 보는 투자자에게 지금 시장 전체 흐름을 한눈에 알려준다.
철칙:
- 아래 '재료(사실)'에 있는 것만 써라. 없으면 지어내지 마라.
- 단순 나열 금지. "그래서 지금 분위기가 어떻다"는 판단까지.
- 아침부터 지금까지의 흐름을 이어서 서술하라(직전 브리핑 대비 무엇이 바뀌었나).
매 순간 답할 것: 돈이 들어오나 / 외인기관 스탠스 전환 / 분기점 / 프로그램 / 미선물 / 나스닥 디커플링 / 외부충격.
출력은 반드시 아래 JSON 객체 하나만(설명 금지):
{"verdict":{"tone":"<🟢/🟡/🔴 + 한단어>","line":"<핵심 한줄>"},"narrative":"<이모지 문단 2~3개>","new_turning_points":[{"ts":"HH:MM","label":"...","major":true}],"used_news_ids":[]}"""


def build_prompt(facts: dict, events: list, story: dict, news: list, phase: str, focus: str = "") -> str:
    ev = "\n".join(f"- {e.get('label','')}" for e in (events or [])) or "(없음)"
    nw = "\n".join(f"- {n}" for n in (news or [])) or "(없음)"
    tp = "\n".join(f"- {t.get('ts','')} {t.get('label','')}"
                   for t in (story or {}).get("turning_points", [])) or "(없음)"
    prevv = ((story or {}).get("verdict") or {}).get("line", "(없음)")
    focus_block = f"\n## 이 시간대 브리핑 초점\n{focus}\n" if focus else ""
    return f"""{_SYS}

## 세션: {phase}
{focus_block}## 지수/수급 사실
{json.dumps(facts, ensure_ascii=False)}
## 직전 대비 새 이벤트
{ev}
## 오늘 시장 뉴스 후보(S급만 골라 녹여라)
{nw}
## 오늘의 스토리(직전)
직전 판정: {prevv}
전환점:
{tp}
"""


def parse_result(raw: str):
    """claude .result(모델이 낸 JSON 문자열) 파싱. 코드펜스/잡음 관용 처리."""
    if not raw:
        return None
    s = raw.strip()
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(d, dict) or "verdict" not in d or "narrative" not in d:
        return None
    d.setdefault("new_turning_points", [])
    d.setdefault("used_news_ids", [])
    return d


def synthesize(facts, events, story, news, phase, model="opus",
               gemini_fn=None, cwd="/home/ubuntu/briefing_agent",
               claude_bin="claude", timeout=90, focus="") -> dict | None:
    """claude -p(Max 구독) 호출 → 파싱. 실패 시 gemini_fn 폴백. 메타(_model,_latency_ms) 포함."""
    prompt = build_prompt(facts, events, story, news, phase, focus=focus)
    t0 = _time.time()
    raw = None
    try:
        proc = subprocess.run(
            [claude_bin, "-p", prompt, "--model", model,
             "--output-format", "json", "--permission-mode", "bypassPermissions"],
            cwd=cwd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        if proc.returncode == 0 and proc.stdout:
            envelope = json.loads(proc.stdout)
            raw = envelope.get("result", "")
    except Exception:
        raw = None
    parsed = parse_result(raw) if raw else None
    used = f"claude:{model}"
    if parsed is None and gemini_fn is not None:
        try:
            g = gemini_fn(prompt)
            parsed = parse_result((g or {}).get("analysis", "")) if isinstance(g, dict) else parse_result(g)
            used = "gemini"
        except Exception:
            parsed = None
    if parsed is not None:
        parsed["_model"] = used
        parsed["_latency_ms"] = int((_time.time() - t0) * 1000)
    return parsed
