"""골루프 Stage0 — NotebookLM 기반 아침 브리핑 콘텐츠 생성.
A(구조화 카드용 텍스트)와 B(심층 리포트)를 각각 만든다. B는 비차단(실패해도 A 발행에 영향 없음)."""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
OUT_DIR = ROOT / "out"

import nlm_bridge  # noqa: E402

_CARD_FORMAT_INSTRUCTIONS = """\
아래 형식을 그대로 써라. 형식 밖으로 나오지 마라.

규칙:
- 한 줄 = 한 문장. 절대 길게 쓰지 마라.
- 숫자 없으면 쓰지 마라. 막연한 표현 금지.
- 종목 표는 칸 맞춰서.
- 주식 1년차도 바로 이해하는 쉬운 말로 써라.
- 전문용어 변환 규칙 (반드시 지켜라):
  ETF → 펀드 / TP → 목표주가 / 리밸런싱 → 비중 조정
  Capex → 설비 투자 / 지정학 → 전쟁·분쟁 / 역성장 → 판매 감소
  수급 → 돈 흐름 / 자금 쏠림 → 돈이 몰리는 중
- 말투: "~야", "~있어", "~중", "~예정" 처럼 자연스럽게. 딱딱한 명사형 금지.
- 핵심 이유는 "왜 중요한지" 한 줄로. "~해서 주가 오를 수 있어" 처럼.

━━━ {date} 시장 브리핑 ━━━

📌 오늘 핵심
• (자금 흐름 한 줄 — 어디서 빠져서 어디로)
• (오늘 가장 중요한 이슈 한 줄)
• (시장 분위기 한 줄)

🔴 강세 종목
종목명        TP·수치          핵심 이유
(종목1)       TP XXX만 (+XX%) 이유 10자
(종목2)       TP XXX만 (+XX%) 이유 10자
(종목3)       수치             이유 10자

🔵 리스크 종목 (있으면)
종목명        수치             이유 10자

⚠️ 리스크
• (리스크1 — 수치 포함)
• (리스크2 — 수치 포함)
• (리스크3 — 수치 포함)

📅 챙길 일정
• (날짜/시점 + 이벤트)
• (날짜/시점 + 이벤트)

💡 시나리오
강세: (조건) → (흐름)
약세: (조건) → (흐름)

🎯 오늘 한 줄
(행동 지침 포함, 20자 이내)
"""


def build_notebook(date: str) -> dict:
    """오늘 텔레·리포트·블로그 원자 → 새 노트북 생성+소스추가.
    원자 0건이거나 생성 실패 시 notebook_id=None (호출측이 C1 가드로 처리)."""
    bundle = nlm_bridge._build_notebook_bundle(
        q="", cats=["telegram", "report", "blog"], period="today", limit=200)
    if not bundle or bundle.get("atoms_n", 0) == 0:
        return {"notebook_id": None, "atoms_n": 0, "url": None}

    cr = nlm_bridge.create_notebook(f"[골루프] 아침브리핑 {date}")
    if not cr["ok"]:
        return {"notebook_id": None, "atoms_n": bundle["atoms_n"], "url": None}
    nb_id = cr["notebook_id"]

    out_dir = OUT_DIR / "goal_loop"
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, (src_title, md_text) in enumerate(bundle["md_files"]):
        mp = out_dir / f"stage0_{date}_{i}.md"
        mp.write_text(md_text, encoding="utf-8")
        nlm_bridge.add_source_file(nb_id, str(mp), src_title)

    return {"notebook_id": nb_id, "atoms_n": bundle["atoms_n"],
            "url": f"https://notebooklm.google.com/notebook/{nb_id}"}


def query_card_content(notebook_id: str, date: str) -> str:
    """A: 카드용 구조화 텍스트(daily_scenario 포맷). 실패 시 빈 문자열(C1 가드로 처리)."""
    question = _CARD_FORMAT_INSTRUCTIONS.replace("{date}", date)
    r = nlm_bridge.notebook_query(notebook_id, question, timeout=180)
    if not r["ok"]:
        return ""
    return r["answer"]


def generate_deep_report(notebook_id: str, date: str) -> str:
    """B: 심층 리포트(NotebookLM Briefing Doc). 비차단 — 실패하면 None만 반환, 예외 전파 안 함."""
    try:
        r = nlm_bridge.create_report(notebook_id, fmt="Briefing Doc", language="ko",
                                     out_dir=str(OUT_DIR / "insights_notebook"))
        if r.get("ok") and r.get("ready"):
            return r.get("url") or None
        return None
    except Exception:
        return None
