"""gemini_q10_lib.py — 섹터 Q10 딥리서치 resume 스크립트들의 공통 헬퍼.

gemini_defense_q9to10_resume.py / gemini_robot_q5to10_resume.py /
gemini_sector_q7_resume.py 3개에 손으로 복사돼있던 로직(Gemini 호출+429 재시도,
이전 답변 요약 파싱, 원본/위키 파일 갱신, log.md 기록)을 여기 하나로 모았다.

각 스크립트의 섹터별 질문 텍스트(Q1~Q10)는 원래 스크립트에 그대로 남겨둔다 —
프롬프트 자체는 섹터마다 다른 콘텐츠라 통합 대상이 아니다.
"""
import re
import time
from pathlib import Path


def load_env(root: Path) -> dict:
    env = {}
    env_path = root / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def get_client(env: dict):
    from google import genai
    api_key = env.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 없음")
    return genai.Client(api_key=api_key)


def extract_retry_seconds(error_msg: str, default: float = 65.0, margin: float = 5.0) -> float:
    """429 오류 메시지에서 retryDelay 초 추출."""
    m = re.search(r"retryDelay.*?(\d+(?:\.\d+)?)s", str(error_msg))
    return float(m.group(1)) + margin if m else default


def call_gemini(client, prompt: str, model: str = "gemini-3-flash-preview",
                 max_retries: int = 5, retry_wait_margin: float = 5.0) -> str:
    """429면 자동 대기 후 재시도. 그 외 오류는 '[오류: ...]'로 반환."""
    from google.genai import types
    for attempt in range(max_retries):
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3,
                ),
            )
            return resp.text if resp.text is not None else "[오류: 응답 없음]"
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = extract_retry_seconds(err, margin=retry_wait_margin)
                print(f"  ⏳ 429 — {wait:.0f}초 대기 (시도 {attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                print(f"  ❌ 오류: {e}")
                return f"[오류: {e}]"
    return "[오류: 최대 재시도 초과]"


def build_context(base_ctx: str, summaries: dict, qorder: list[str]) -> str:
    """base_ctx + 이전 Q 요약(qorder 순서대로, summaries에 있는 것만)."""
    ctx = base_ctx + "\n\n이전 Q 요약:\n"
    for qn in qorder:
        if qn in summaries:
            ctx += f"[{qn}] {summaries[qn]}\n\n"
    ctx += "---\n다음 질문에 답해줘:\n\n"
    return ctx


def load_prior_summaries(raw_file: Path, qnums: list[str], char_limit: int = 600) -> dict:
    """이미 저장된 raw 마크다운에서 '## Qn — ...' 섹션의 답변을 정규식으로 복구."""
    summaries = {}
    if not raw_file.exists():
        return summaries
    raw_text = raw_file.read_text(encoding="utf-8")
    for qn in qnums:
        pattern = rf"## {qn} — .*?\n\n\*\*질문:\*\*.*?\n\*\*답변:\*\*\n(.*?)(?=\n---\n|\Z)"
        m = re.search(pattern, raw_text, re.DOTALL)
        if m:
            summaries[qn] = m.group(1).strip()[:char_limit]
    return summaries


def update_raw_file(raw_file: Path, results: dict, header_if_new: str) -> None:
    """'## Qn — title' 섹션을 있으면 교체, 없으면 append."""
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_content = raw_file.read_text(encoding="utf-8") if raw_file.exists() else header_if_new
    for qnum, data in results.items():
        block = f"## {qnum} — {data['title']}\n\n**질문:**\n{data.get('question','')}\n\n**답변:**\n{data['answer']}\n\n---\n\n"
        if f"## {qnum} —" in raw_content:
            raw_content = re.sub(rf"## {qnum} —.*?(?=\n## |\Z)", block, raw_content, flags=re.DOTALL)
        else:
            raw_content += block
    raw_file.write_text(raw_content, encoding="utf-8")


def update_sector_wiki(sector_file: Path, results: dict, title_map: dict, header_if_new: str) -> None:
    """'### Qn — title' 섹션을 있으면 교체, 없으면 append."""
    sector_file.parent.mkdir(parents=True, exist_ok=True)
    content = sector_file.read_text(encoding="utf-8") if sector_file.exists() else header_if_new
    for qnum, data in results.items():
        section_title = title_map.get(qnum, data.get("title", qnum))
        new_section = f"\n### {qnum} — {section_title}\n\n{data['answer']}\n\n---\n"
        if f"### {qnum} —" in content:
            content = re.sub(rf"### {qnum} —.*?(?=\n### |\Z)", new_section.strip() + "\n", content, flags=re.DOTALL)
        else:
            content += new_section
    sector_file.write_text(content, encoding="utf-8")


def log_completion(log_file: Path, entry: str) -> None:
    """log.md 맨 위에 한 줄 prepend."""
    log = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
    log_file.write_text(entry + log, encoding="utf-8")
