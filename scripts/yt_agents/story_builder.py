"""스토리라인 강화 — 믹스 초안(뼈대) → ⑤a 서사 설계도 → (사람 편집) → ⑤b 완성 대본.
claude -p(Opus/Sonnet, Max 구독) 호출 + Gemini 폴백. briefing_weather와 동일 방식.
"""
import sys
import json
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gemini_client as G

# 채널 정체성 — 두 단계 프롬프트 모두에 주입 (clip_teardown._CHANNEL과 동일 취지)
_CHANNEL = """우리 채널 = "로또의 주식/스탁브레인".
- 타겟 시청자 = 주식에 관심 있는 모든 사람(초보~중급 개인투자자 포함). AI 관심층 한정 아님.
- 파는 것: 리딩(뭘 사라) 아니라 "나는 시장을 이렇게 본다"는 시각·방법.
- 다루는 소재: 오늘 반도체 왜 폭락했나 / 종가·시가 배팅법 / 섹터 흐름 읽기 / 정보 활용법 등 주식 실전·시황 전반.
- 활용 도구는 여러 개(섹터 히트맵·주도섹터 강도·시황 해석·매매 원칙·차트 해석 등). '수급빈집'은 그중 하나일 뿐.
  🚫 '수급빈집'을 제목·핵심에 억지로 넣지 말 것. 기본은 소재 자체로 승부.
- 유튜브 70/20/10 (70 순수정보 / 20 방법노출은 "나는 이렇게 한다" 수준만 / 10 마지막 CTA 딱 한 번)."""


def _claude(prompt: str, model: str, claude_bin: str, cwd: str, timeout: int) -> "str | None":
    """claude -p(Max 구독) 호출 → result 텍스트. 실패 시 None."""
    try:
        proc = subprocess.run(
            [claude_bin, "-p", prompt, "--model", model,
             "--output-format", "json", "--permission-mode", "bypassPermissions"],
            cwd=cwd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        if proc.returncode == 0 and proc.stdout:
            return json.loads(proc.stdout).get("result", "") or None
    except Exception:
        pass
    return None


def _gen(prompt: str, claude_bin: str, cwd: str, model: str = "opus",
         timeout: int = 180) -> dict:
    """claude(Opus) 시도 → 실패 시 Gemini 폴백. 파싱된 dict + _model 메타 반환."""
    raw = _claude(prompt, model, claude_bin, cwd, timeout)
    used = f"claude:{model}"
    if not raw:
        raw = G.call(prompt, temperature=0.7)
        used = "gemini"
    d = G._parse_json_text(raw)
    d["_model"] = used
    return d


# ── ⑤a 서사 설계도 ──────────────────────────────────────────
def _storyline_prompt(draft: dict, category: str) -> str:
    titles = " / ".join(draft.get("제목후보", []) or [])
    gu = "\n".join(f"- {x}" for x in (draft.get("구성") or []))
    pts = "\n".join(f"- {x}" for x in (draft.get("핵심대본_포인트") or []))
    return f"""너는 '로또의 주식' 채널의 수석 대본 작가다. 아래는 검증된(터진) 레퍼런스 영상들을
해체·믹스해서 나온 '{category}' 새 영상의 대본 초안(뼈대)이다. 이 뼈대를 받아,
시청자가 끝까지 이탈 없이 보게 만드는 '탄탄한 서사 설계도'로 발전시켜라.

=== 믹스 초안(뼈대) ===
제목후보: {titles}
훅(첫20초): {draft.get('훅_첫20초','')}
구성:
{gu}
핵심 포인트:
{pts}
차별화: {draft.get('차별화_빈틈공략','')}
CTA: {draft.get('CTA','')}

=== {_CHANNEL} ===

설계 원칙:
1. 씬 6~9개로 재구성. 각 씬은 '이탈방지 목적'이 분명해야 한다(왜 이 씬에서 안 나가나).
2. 긴장 곡선을 명시하라 — 어디서 당기고(질문·충격), 어디서 풀고(해소), 클라이맥스는 어디.
3. 씬과 씬 사이 '연결(전환 문장)'을 넣어 매끄럽게 이어라. 단절 금지.
4. 우리 채널 시각("나는 시장을 이렇게 본다")을 서사의 뼈대로. 리딩·정답제시 톤 금지.
5. 70/20/10 준수. 아직 완성 대본은 쓰지 마라 — 이건 '설계도'다.

JSON으로만 답하라:
{{
  "제목확정": "후보 중 제일 강한 것 1개(개선 가능)",
  "로그라인": "이 영상이 시청자에게 주는 약속 한 문장",
  "타겟_후킹": "누가·왜 끝까지 보는지 한 문장",
  "씬": [
    {{"구간":"00:00~00:20","역할":"훅/전개/전환/클라이맥스/CTA 중","목표":"이 씬의 이탈방지 목적","핵심":"무슨 내용을 어떻게","긴장":"당김/유지/풂 중 + 이유","연결":"다음 씬으로 넘기는 전환 한 문장"}}
  ],
  "긴장곡선": "전체 리텐션 설계 요약(당김→해소→클라이맥스 흐름)",
  "차별화": "레퍼런스들이 못 채운 우리만의 각",
  "cta": "마지막 10% 문구"
}}"""


def build_storyline(draft: dict, category: str = "",
                    claude_bin: str = "claude", cwd: str = ".") -> dict:
    """믹스 초안 → 서사 설계도(dict). claude Opus, 실패 시 Gemini."""
    out = _gen(_storyline_prompt(draft, category), claude_bin, cwd)
    out["_category"] = category
    return out


# ── ⑤b 완성 대본 ────────────────────────────────────────────
def _script_prompt(storyline_text: str, category: str) -> str:
    return f"""너는 '로또의 주식' 채널의 수석 대본 작가다. 아래는 사람이 검토·수정한 '{category}' 영상의
서사 설계도다. 이 설계도를 그대로 따라, 바로 녹음 가능한 '완성 대본'을 써라.

=== 서사 설계도(사람 확정본) ===
{storyline_text}

=== {_CHANNEL} ===

작성 원칙:
1. 설계도의 씬 순서·역할·긴장 곡선을 그대로 지켜라. 임의로 구조를 바꾸지 마라.
2. 각 씬의 '나레이션'은 실제 말하는 대본 전문으로. 구어체, 시청자에게 말 걸듯이.
3. 70/20/10: 대부분 순수 정보, 방법 노출은 "나는 이렇게 본다" 수준만, CTA는 마지막에 딱 한 번.
4. 리딩·"이 종목 사라" 금지. 시각·판단 근거를 보여주는 톤.
5. 화면지시는 선택(자막 강조·차트·B롤 힌트 정도만, 없으면 생략).

JSON으로만 답하라:
{{
  "제목": "최종 제목",
  "썸네일_문구": "썸네일에 박을 짧은 카피",
  "대본": [
    {{"구간":"00:00~00:20","역할":"훅 등","나레이션":"실제 발화 대본 전문","화면지시":"(선택)"}}
  ],
  "예상길이": "약 N분",
  "제작메모": "촬영·편집 시 주의할 점 한두 개"
}}"""


def build_script(storyline_text: str, category: str = "",
                 claude_bin: str = "claude", cwd: str = ".") -> dict:
    """(편집된) 설계도 텍스트 → 완성 대본(dict). claude Opus, 실패 시 Gemini."""
    out = _gen(_script_prompt(storyline_text, category), claude_bin, cwd, timeout=240)
    out["_category"] = category
    return out
