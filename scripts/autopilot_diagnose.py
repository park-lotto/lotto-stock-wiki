"""이상 채널 원인진단 — claude -p 헤드리스(서버 Max 구독), Edit/Bash 권한 없이 진단만.
오케스트레이터가 서버(3.39.179.148)에서 직접 실행되므로 크롤러 코드/로그도 로컬
파일시스템으로 읽는다(SSH 불필요)."""
import json
import re
import subprocess

_SYS = """너는 '로또의 스탁브레인' 크롤링 파이프라인 장애진단 담당이다.
텔레그램 채널 하나가 raw 데이터를 못 받고 있다. 아래 정보만 보고 원인을 분석해서
JSON 객체 하나만 출력해라(설명 금지, 코드펜스 금지):
{"root_cause":"<한두 문장>","target":"local|remote_crawler|unfixable","target_files":["<target=local이면 /home/ubuntu/lotto-stock-wiki 기준, remote_crawler면 크롤러 디렉터리 기준 상대경로>"],"fix_plan":"<구체적 수정 계획, unfixable이면 빈 문자열>","requires_destructive_action":false}

target 판단 기준:
- "local": 원인이 /home/ubuntu/lotto-stock-wiki/pipeline/atoms/ 안의 인제스트·질문지 코드에 있음
- "remote_crawler": 원인이 /home/ubuntu/kmong/crawling_bot/ 크롤러 코드/설정(config.yaml)에 있음
- "unfixable": 텔레그램 플랫폼 자체 제한(shadow limit 등) 등 코드로 근본 해결 불가능

requires_destructive_action: 수정이 데이터 삭제·DB 레코드 drop·force-push 등 파괴적 작업을
요구하면 true(그러면 target과 무관하게 사람에게 넘어간다)."""


def build_prompt(channel, anomaly, crawler_log_tail):
    return f"""{_SYS}

## 이상 채널
채널명: {channel}
상태: {anomaly['status']} (미해결 {anomaly.get('days_stale', '?')}일)
최근 raw 날짜: {anomaly.get('latest_date') or '없음'}

## 크롤러 최근 로그(/home/ubuntu/kmong/crawling_bot/logs/service.log 마지막 부분)
{crawler_log_tail or '(로그 없음)'}
"""


def parse_diagnosis(raw: str):
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(d, dict) or d.get("target") not in ("local", "remote_crawler", "unfixable"):
        return None
    d.setdefault("requires_destructive_action", False)
    d.setdefault("fix_plan", "")
    d.setdefault("target_files", [])
    return d


def diagnose(channel, anomaly, crawler_log_tail, cwd,
             claude_bin="claude", model="sonnet", timeout=120):
    prompt = build_prompt(channel, anomaly, crawler_log_tail)
    try:
        proc = subprocess.run(
            [claude_bin, "-p", prompt, "--model", model,
             "--output-format", "json", "--permission-mode", "bypassPermissions",
             "--disallowedTools", "Edit,Write,NotebookEdit,Bash"],
            cwd=cwd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        if proc.returncode != 0 or not proc.stdout:
            return None
        envelope = json.loads(proc.stdout)
        raw = envelope.get("result", "")
    except Exception:
        return None
    return parse_diagnosis(raw)


def read_log_tail(path, lines=100):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except Exception:
        return ""
