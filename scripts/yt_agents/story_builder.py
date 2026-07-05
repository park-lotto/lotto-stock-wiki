"""스토리라인 강화 — 믹스 초안(뼈대) → ⑤a 서사 설계도 → (사람 편집) → ⑤b 완성 대본.
claude -p(Opus/Sonnet, Max 구독) 호출 + Gemini 폴백. briefing_weather와 동일 방식.
"""
import sys
import re
import json
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gemini_client as G


def _parse_json_lenient(raw: str) -> dict:
    """LLM JSON 관용 파싱 — 코드펜스·잡텍스트·trailing comma 처리.
    Opus/Gemini가 긴 배열 끝에 쉼표를 남기는 경우가 잦아 gemini_client 기본 파서보다 관대하게."""
    if not raw or not raw.strip():
        raise ValueError("빈 응답")
    s = re.sub(r"```(?:json)?\s*", "", raw).strip().strip("`").strip()
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        s = m.group(0)
    s = re.sub(r",(\s*[}\]])", r"\1", s)   # ,} 또는 ,] 의 후행 쉼표 제거
    return json.loads(s)

# 채널 정체성 — 두 단계 프롬프트 모두에 주입.
# 원칙: 부정 지시("~하지 마라")·유행어 강요를 빼고, 정보 자체로 승부하는 자연스러운 톤.
_CHANNEL = """우리 채널 = "스탁브레인".
- 타겟 시청자 = 주식에 관심 있는 개인투자자(초보~중급).
- 채널의 관점: 시장을 중심에서 '흐름'으로 관찰하는 시각을 전한다. 특정 종목을 "사라"는
  리딩이 아니라, "지금 시장이 이렇게 움직인다"를 스스로 읽는 눈을 길러주는 것이 목표.
- 제공하는 것(대본 CTA는 이걸로 자연스럽게 연결):
  · 스탁 히트맵 — 시장 전체 돈 흐름을 한눈에 (전원 무료 공개 예정)
  · 인사이트 페이지 — 정리된 시황·종목 인사이트 (베타 무료 → 이후 유료 전환)
  · 크롤링 도구 — 필요한 것만 개별 판매
- 대본 톤 원칙:
  · 정보 자체로 승부한다. 특정 유행어·말버릇을 억지로 끼워넣지 않는다.
  · 소재에 맞는 자연스러운 구어체. 시청자에게 담백하게 말 걸듯이.
  · 70/20/10 (70 순수 정보 / 20 "나는 이렇게 본다" 방법 / 10 마지막 CTA 딱 한 번)."""


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
         timeout: int = 240) -> dict:
    """claude(Opus) 시도 → 실패 시 Gemini 폴백. 파싱된 dict + _model 메타 반환."""
    raw = _claude(prompt, model, claude_bin, cwd, timeout)
    used = f"claude:{model}"
    # claude가 응답했지만 파싱 불가(잘린 JSON 등)면 Gemini로 재시도
    d = None
    if raw:
        try:
            d = _parse_json_lenient(raw)
        except Exception:
            d = None
    if d is None:
        raw = G.call(prompt, temperature=0.7)
        used = "gemini"
        d = _parse_json_lenient(raw)   # 여기서도 실패하면 엔드포인트가 error로 잡음
    d["_model"] = used
    return d


# ── ⑤a 서사 설계도 ──────────────────────────────────────────
def _factpack_block(factpack: str) -> str:
    """주장별 근거 리서치 결과가 있으면 프롬프트에 넣을 블록. 없으면 빈 문자열."""
    if not factpack or not factpack.strip():
        return ""
    return f"""
=== 주장별 근거 검증(오늘 시점 리서치) — 대본은 이 근거를 따라야 한다 ===
{factpack}
※ 규칙:
  1. 근거 '충분 ✅'인 주장만 사실로 단정하라. 그 근거(기사·수치)를 대본에 녹여라.
  2. 근거 '없음 ⚠️'으로 표시된 주장은 단정하지 마라 — 약화하거나("~일 수 있다"), 질문형으로
     돌리거나, 아예 빼라. 근거 없이 우기면 안 된다.
  3. 현재 주가 방향과 어긋나는 서술(상승중인데 하락 얘기 등) 금지.
  4. 여기 없는 수치·사실을 지어내지 마라.
"""


def _storyline_prompt(draft: dict, category: str, factpack: str = "") -> str:
    titles = " / ".join(draft.get("제목후보", []) or [])
    gu = "\n".join(f"- {x}" for x in (draft.get("구성") or []))
    pts = "\n".join(f"- {x}" for x in (draft.get("핵심대본_포인트") or []))
    return f"""너는 '스탁브레인' 채널의 수석 대본 작가다. 아래는 검증된(터진) 레퍼런스 영상들을
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
{_factpack_block(factpack)}
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
                    claude_bin: str = "claude", cwd: str = ".", factpack: str = "") -> dict:
    """믹스 초안 → 서사 설계도(dict). claude Opus, 실패 시 Gemini. factpack=검증된 최신 사실."""
    out = _gen(_storyline_prompt(draft, category, factpack), claude_bin, cwd)
    out["_category"] = category
    return out


# ── ⑤b 완성 대본 ────────────────────────────────────────────
def _script_prompt(storyline_text: str, category: str, factpack: str = "") -> str:
    return f"""너는 '스탁브레인' 채널의 수석 대본 작가다. 아래는 사람이 검토·수정한 '{category}' 영상의
서사 설계도다. 이 설계도를 그대로 따라, 바로 녹음 가능한 '완성 대본'을 써라.

=== 서사 설계도(사람 확정본) ===
{storyline_text}
{_factpack_block(factpack)}
=== {_CHANNEL} ===

작성 원칙:
1. 설계도의 씬 순서·역할·긴장 곡선을 그대로 지켜라. 임의로 구조를 바꾸지 마라.
2. 각 씬의 '나레이션'은 실제 말하는 대본 전문으로. 구어체, 시청자에게 말 걸듯이.
3. 70/20/10: 대부분 순수 정보, 방법 노출은 "나는 이렇게 본다" 수준만, CTA는 마지막에 딱 한 번.
4. 리딩·"이 종목 사라" 금지. 시각·판단 근거를 보여주는 톤.
5. 화면지시는 선택(자막 강조·차트·B롤 힌트 정도만, 없으면 생략).
6. 검증된 최신 사실 블록이 있으면 그 사실·주가 방향과 어긋나지 않게. 없는 수치는 지어내지 마라.

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
                 claude_bin: str = "claude", cwd: str = ".", factpack: str = "") -> dict:
    """(편집된) 설계도 텍스트 → 완성 대본(dict). claude Opus, 실패 시 Gemini."""
    out = _gen(_script_prompt(storyline_text, category, factpack), claude_bin, cwd, timeout=420)
    out["_category"] = category
    return out
