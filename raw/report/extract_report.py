# -*- coding: utf-8 -*-
"""
증권사 리포트 PDF -> 구조화 요약 자동 추출기
Gemini Flash API 사용

5가지 리포트 유형 (폴더 기준 자동 라우팅):
  종목보고서/      → 개별 종목 분석 (단건/일람표 자동 감지)
  산업보고서/      → 섹터 산업 분석
  경제분석보고서/  → 매크로 경제
  시황 보고서/     → 시장 전반 시황
  투자정보 보고서/ → 투자 전략·테마

사용법:
  python extract_report.py                          # 전체 처리
  python extract_report.py 종목보고서/파일명.pdf    # 단건 처리
"""

import os
import sys
import pathlib
import time
from datetime import datetime
from dotenv import load_dotenv

from google import genai
from google.genai import types

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: .env에 GEMINI_API_KEY 없음")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

REPORT_DIR = pathlib.Path(__file__).parent
SUMMARY_DIR = REPORT_DIR / "요약"
SUMMARY_DIR.mkdir(exist_ok=True)

MODEL = "models/gemini-3-flash-preview"

# 폴더명 → 유형 코드 매핑
FOLDER_TYPE = {
    "종목보고서": "company",
    "산업보고서": "industry",
    "경제분석보고서": "economy",
    "시황 보고서": "market",
    "투자정보 보고서": "invest",
}

# ── 프롬프트 ──────────────────────────────────────────

PROMPT_COMPANY_SINGLE = """이 증권사 애널리스트 리포트를 분석하고 아래 형식으로만 출력하세요.
다른 설명 없이 형식 그대로만 출력하세요. 모르는 항목은 N/A로 쓰세요.

종목명: (한글 종목명. 특정 종목 없는 산업리포트면 "산업리포트")
종목코드: (6자리 숫자. 없으면 N/A)
증권사: (증권사명)
애널리스트: (이름)
투자의견: (매수/중립/매도/Overweight/Neutral/Positive 등)
이전의견: (있으면 기재, 없으면 N/A)
TP: (목표주가 숫자만, 원화면 원단위. 없으면 N/A)
이전TP: (이전 목표주가 숫자만. 없으면 N/A)
TP변화: (상향/하향/유지/신규/N/A)
리레이팅: (True 또는 False. Multiple/밸류에이션 체계 자체가 바뀐 경우만 True)
리레이팅근거: (True일 때 Multiple 또는 밸류에이션 변화 근거 1줄. False면 N/A)
핵심논리1: (핵심 투자 논리 첫번째, 1~2문장)
핵심논리2: (핵심 투자 논리 두번째, 1~2문장. 없으면 N/A)
섹터: (반도체/조선/방산/화학/자동차/바이오/제약/전력기기/건설/은행/화장품/식품/PCB/배터리 등)
리포트날짜: (YYYY-MM-DD 형식. 없으면 N/A)
"""

PROMPT_COMPANY_TABLE = """이 PDF는 여러 종목의 목표주가·투자의견이 담긴 일람표입니다.
모든 종목 데이터를 아래 형식으로 추출하세요.
종목이 여러 개면 --- 구분선으로 나눠서 반복하세요.

종목명: (한글 종목명)
종목코드: (6자리 숫자. 없으면 N/A)
증권사: (증권사명)
애널리스트: (이름. 없으면 N/A)
투자의견: (매수/중립/매도/Buy/Hold 등)
이전의견: (있으면, 없으면 N/A)
TP: (목표주가 숫자만)
이전TP: (이전 목표주가 숫자만. 없으면 N/A)
TP변화: (상향/하향/유지/신규/N/A)
리레이팅: (False)
리레이팅근거: (N/A)
핵심논리1: (제목이나 한줄 요약. 없으면 N/A)
핵심논리2: (N/A)
섹터: (반도체/조선/방산/화학/자동차/바이오/제약/전력기기/건설/은행/화장품/식품/PCB/배터리 등)
리포트날짜: (YYYY-MM-DD 형식. 없으면 N/A)
---
(다음 종목 반복)
"""

PROMPT_INDUSTRY = """이 증권사 산업 리포트를 분석하고 아래 형식으로만 출력하세요.
다른 설명 없이 형식 그대로만 출력하세요. 모르는 항목은 N/A로 쓰세요.

섹터: (반도체/조선/방산/화학/자동차/바이오/제약/전력기기/건설/은행/화장품/식품/PCB/배터리/LNG/로봇 등)
서브섹터: (더 구체적인 분류. 없으면 N/A)
증권사: (증권사명)
애널리스트: (이름)
리포트제목: (리포트 제목 그대로)
전망: (긍정/중립/부정)
핵심테마1: (핵심 투자 테마 첫번째, 1~2문장)
핵심테마2: (핵심 투자 테마 두번째, 1~2문장. 없으면 N/A)
관련종목: (언급된 한국 종목명 쉼표로 나열. 없으면 N/A)
촉매: (주요 촉매 이벤트 1줄. 없으면 N/A)
리포트날짜: (YYYY-MM-DD 형식. 없으면 N/A)
"""

PROMPT_ECONOMY = """이 경제분석 리포트를 분석하고 아래 형식으로만 출력하세요.
다른 설명 없이 형식 그대로만 출력하세요. 모르는 항목은 N/A로 쓰세요.

주제: (무역/금리/환율/GDP/인플레이션/고용/중앙은행/지정학 등 핵심 주제)
증권사: (증권사 또는 기관명)
애널리스트: (이름. 없으면 N/A)
리포트제목: (리포트 제목)
핵심주장1: (핵심 주장 첫번째, 1~2문장)
핵심주장2: (핵심 주장 두번째, 1~2문장. 없으면 N/A)
영향섹터: (이 분석이 영향을 미치는 한국 섹터. 없으면 N/A)
영향방향: (긍정/부정/혼재/중립)
리포트날짜: (YYYY-MM-DD 형식. 없으면 N/A)
"""

PROMPT_MARKET = """이 시황 리포트를 분석하고 아래 형식으로만 출력하세요.
다른 설명 없이 형식 그대로만 출력하세요. 모르는 항목은 N/A로 쓰세요.

증권사: (증권사명)
애널리스트: (이름. 없으면 N/A)
리포트제목: (리포트 제목)
시장방향: (상승/하락/중립/변동성확대)
주목섹터: (오늘 주목할 섹터 쉼표로 나열. 없으면 N/A)
핵심이슈1: (핵심 시장 이슈 첫번째, 1~2문장)
핵심이슈2: (핵심 시장 이슈 두번째. 없으면 N/A)
주목종목: (언급된 특정 종목. 없으면 N/A)
리포트날짜: (YYYY-MM-DD 형식. 없으면 N/A)
"""

PROMPT_INVEST = """이 투자정보/전략 리포트를 분석하고 아래 형식으로만 출력하세요.
다른 설명 없이 형식 그대로만 출력하세요. 모르는 항목은 N/A로 쓰세요.

주제: (테마/전략/스타일 핵심 키워드)
증권사: (증권사명)
애널리스트: (이름. 없으면 N/A)
리포트제목: (리포트 제목)
핵심논리1: (핵심 투자 논리 첫번째, 1~2문장)
핵심논리2: (핵심 투자 논리 두번째. 없으면 N/A)
유망섹터: (추천 섹터 쉼표로 나열. 없으면 N/A)
유망종목: (추천 또는 언급 종목 쉼표로 나열. 없으면 N/A)
주의섹터: (리스크 언급 섹터. 없으면 N/A)
리포트날짜: (YYYY-MM-DD 형식. 없으면 N/A)
"""

# ── 파싱 ──────────────────────────────────────────────

def parse_single(text: str) -> dict:
    result = {}
    for line in text.strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            k, v = key.strip(), val.strip()
            if k and v:
                result[k] = v
    return result


def parse_table(text: str) -> list[dict]:
    blocks = text.strip().split("---")
    results = []
    for block in blocks:
        d = parse_single(block)
        if d.get("종목명") and d.get("종목명") not in ("N/A", ""):
            results.append(d)
    return results


def is_empty_company(data: dict) -> bool:
    if len(data) < 3:
        return True
    name = data.get("종목명", "N/A")
    if name in ("N/A", "", "?", "산업리포트"):
        return True
    na_count = sum(1 for v in data.values() if v in ("N/A", "", "?"))
    return na_count >= 8


def is_empty_generic(data: dict) -> bool:
    if len(data) < 3:
        return True
    na_count = sum(1 for v in data.values() if v in ("N/A", "", "?"))
    return na_count >= len(data) - 2


# ── 마크다운 생성 ──────────────────────────────────────

def to_md_company(data: dict, source_file: str) -> str:
    tp = data.get("TP", "N/A")
    prev_tp = data.get("이전TP", "N/A")
    tp_clean = tp.rstrip("원").strip() if tp not in ("N/A", "") else tp
    prev_tp_clean = prev_tp.rstrip("원").strip() if prev_tp not in ("N/A", "") else prev_tp
    tp_str = f"{tp_clean}원" if tp_clean not in ("N/A", "") else "N/A"
    prev_tp_str = f"(이전 {prev_tp_clean}원)" if prev_tp_clean not in ("N/A", "") else ""

    rerating = data.get("리레이팅", "False")
    label = "[리레이팅]" if rerating == "True" else "[TP업]"
    reason = data.get("리레이팅근거", "N/A")

    lines = [
        f"## {data.get('리포트날짜', 'N/A')} — {data.get('증권사', 'N/A')} / {data.get('애널리스트', 'N/A')}",
        "",
        "| 항목 | 내용 |",
        "|------|------|",
        f"| 종목 | **{data.get('종목명', 'N/A')}** ({data.get('종목코드', 'N/A')}) |",
        f"| 섹터 | {data.get('섹터', 'N/A')} |",
        f"| 투자의견 | {data.get('투자의견', 'N/A')} → 이전: {data.get('이전의견', 'N/A')} |",
        f"| TP | {tp_str} {prev_tp_str} — {data.get('TP변화', 'N/A')} |",
        f"| 유형 | {label} |",
        f"| 리레이팅근거 | {reason} |",
        "",
        "**핵심논리**:",
        f"- {data.get('핵심논리1', 'N/A')}",
    ]
    if data.get("핵심논리2", "N/A") not in ("N/A", ""):
        lines.append(f"- {data.get('핵심논리2')}")
    lines += ["", f"> 소스: `{source_file}`", ""]
    return "\n".join(lines)


def to_md_industry(data: dict, source_file: str) -> str:
    lines = [
        f"## {data.get('리포트날짜', 'N/A')} — {data.get('증권사', 'N/A')} / {data.get('애널리스트', 'N/A')}",
        "",
        f"**{data.get('리포트제목', 'N/A')}**",
        "",
        "| 항목 | 내용 |",
        "|------|------|",
        f"| 섹터 | {data.get('섹터', 'N/A')} / {data.get('서브섹터', 'N/A')} |",
        f"| 전망 | {data.get('전망', 'N/A')} |",
        f"| 촉매 | {data.get('촉매', 'N/A')} |",
        f"| 관련종목 | {data.get('관련종목', 'N/A')} |",
        "",
        "**핵심테마**:",
        f"- {data.get('핵심테마1', 'N/A')}",
    ]
    if data.get("핵심테마2", "N/A") not in ("N/A", ""):
        lines.append(f"- {data.get('핵심테마2')}")
    lines += ["", f"> 소스: `{source_file}`", ""]
    return "\n".join(lines)


def to_md_economy(data: dict, source_file: str) -> str:
    lines = [
        f"## {data.get('리포트날짜', 'N/A')} — {data.get('증권사', 'N/A')} / {data.get('애널리스트', 'N/A')}",
        "",
        f"**{data.get('리포트제목', 'N/A')}**",
        "",
        "| 항목 | 내용 |",
        "|------|------|",
        f"| 주제 | {data.get('주제', 'N/A')} |",
        f"| 영향섹터 | {data.get('영향섹터', 'N/A')} |",
        f"| 영향방향 | {data.get('영향방향', 'N/A')} |",
        "",
        "**핵심주장**:",
        f"- {data.get('핵심주장1', 'N/A')}",
    ]
    if data.get("핵심주장2", "N/A") not in ("N/A", ""):
        lines.append(f"- {data.get('핵심주장2')}")
    lines += ["", f"> 소스: `{source_file}`", ""]
    return "\n".join(lines)


def to_md_market(data: dict, source_file: str) -> str:
    lines = [
        f"## {data.get('리포트날짜', 'N/A')} — {data.get('증권사', 'N/A')} / {data.get('애널리스트', 'N/A')}",
        "",
        f"**{data.get('리포트제목', 'N/A')}**",
        "",
        "| 항목 | 내용 |",
        "|------|------|",
        f"| 시장방향 | {data.get('시장방향', 'N/A')} |",
        f"| 주목섹터 | {data.get('주목섹터', 'N/A')} |",
        f"| 주목종목 | {data.get('주목종목', 'N/A')} |",
        "",
        "**핵심이슈**:",
        f"- {data.get('핵심이슈1', 'N/A')}",
    ]
    if data.get("핵심이슈2", "N/A") not in ("N/A", ""):
        lines.append(f"- {data.get('핵심이슈2')}")
    lines += ["", f"> 소스: `{source_file}`", ""]
    return "\n".join(lines)


def to_md_invest(data: dict, source_file: str) -> str:
    lines = [
        f"## {data.get('리포트날짜', 'N/A')} — {data.get('증권사', 'N/A')} / {data.get('애널리스트', 'N/A')}",
        "",
        f"**{data.get('리포트제목', 'N/A')}**",
        "",
        "| 항목 | 내용 |",
        "|------|------|",
        f"| 주제 | {data.get('주제', 'N/A')} |",
        f"| 유망섹터 | {data.get('유망섹터', 'N/A')} |",
        f"| 유망종목 | {data.get('유망종목', 'N/A')} |",
        f"| 주의섹터 | {data.get('주의섹터', 'N/A')} |",
        "",
        "**핵심논리**:",
        f"- {data.get('핵심논리1', 'N/A')}",
    ]
    if data.get("핵심논리2", "N/A") not in ("N/A", ""):
        lines.append(f"- {data.get('핵심논리2')}")
    lines += ["", f"> 소스: `{source_file}`", ""]
    return "\n".join(lines)


TO_MD = {
    "company": to_md_company,
    "industry": to_md_industry,
    "economy": to_md_economy,
    "market": to_md_market,
    "invest": to_md_invest,
}

# ── Gemini 호출 ────────────────────────────────────────

def call_gemini(pdf_path: pathlib.Path, prompt: str) -> str:
    with open(pdf_path, "rb") as f:
        uploaded = client.files.upload(
            file=f,
            config={"display_name": pdf_path.name, "mime_type": "application/pdf"},
        )
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_uri(file_uri=uploaded.uri, mime_type="application/pdf"),
            prompt,
        ],
    )
    client.files.delete(name=uploaded.name)
    return response.text


# ── PDF 처리 (유형별) ─────────────────────────────────

def process_company(pdf_path: pathlib.Path) -> list[dict]:
    raw = call_gemini(pdf_path, PROMPT_COMPANY_SINGLE)
    data = parse_single(raw)
    if not is_empty_company(data):
        print(f"  [단건] {data.get('종목명', '?')} / TP {data.get('TP', '?')} / {data.get('TP변화', '?')}")
        return [data]
    print(f"  [일람표 감지] 테이블 추출 전환...")
    raw2 = call_gemini(pdf_path, PROMPT_COMPANY_TABLE)
    records = parse_table(raw2)
    print(f"  [일람표] {len(records)}개 종목 추출")
    for r in records:
        print(f"    → {r.get('종목명','?')} / TP {r.get('TP','?')} / {r.get('TP변화','?')}")
    return records


def process_generic(pdf_path: pathlib.Path, prompt: str, rtype: str) -> list[dict]:
    raw = call_gemini(pdf_path, prompt)
    data = parse_single(raw)
    if is_empty_generic(data):
        print(f"  [경고] 추출 실패 — N/A 과다")
        return []
    title = data.get("리포트제목", data.get("주제", "?"))
    print(f"  [{rtype}] {title[:40]}")
    return [data]


PROCESSORS = {
    "company": lambda p: process_company(p),
    "industry": lambda p: process_generic(p, PROMPT_INDUSTRY, "산업"),
    "economy": lambda p: process_generic(p, PROMPT_ECONOMY, "경제"),
    "market": lambda p: process_generic(p, PROMPT_MARKET, "시황"),
    "invest": lambda p: process_generic(p, PROMPT_INVEST, "투자정보"),
}

# ── 배치 실행 ──────────────────────────────────────────

def process_all():
    today = datetime.now().strftime("%Y%m%d")
    daily_path = SUMMARY_DIR / f"{today}_요약.md"

    sections: dict[str, list[str]] = {t: [] for t in FOLDER_TYPE.values()}
    section_labels = {
        "company": "종목보고서",
        "industry": "산업보고서",
        "economy": "경제분석보고서",
        "market": "시황보고서",
        "invest": "투자정보보고서",
    }

    total = 0
    for folder_name, rtype in FOLDER_TYPE.items():
        folder = REPORT_DIR / folder_name
        if not folder.exists():
            continue
        pdfs = sorted(folder.glob("*.pdf"))
        if not pdfs:
            continue

        print(f"\n[{folder_name}] {len(pdfs)}개")
        for pdf in pdfs:
            done = SUMMARY_DIR / f"{pdf.stem}_done.txt"
            if done.exists():
                print(f"  [스킵] {pdf.name}")
                continue

            print(f"  {pdf.name}")
            try:
                records = PROCESSORS[rtype](pdf)
                if not records:
                    continue

                md_fn = TO_MD[rtype]
                mds = [md_fn(r, f"{folder_name}/{pdf.name}") for r in records]
                sections[rtype].extend(mds)
                total += len(mds)

                (SUMMARY_DIR / f"{pdf.stem}_요약.md").write_text(
                    "\n---\n\n".join(mds), encoding="utf-8"
                )
                done.write_text(today, encoding="utf-8")
                time.sleep(1)

            except Exception as e:
                print(f"  [오류] {e}")

    if total == 0:
        print("\n처리된 파일 없음")
        return

    # 일일 요약 MD 생성 (유형별 섹션)
    parts = [
        f"# 리포트 요약 — {today}\n\n"
        f"> Gemini {MODEL} 자동 생성 | "
        f"`/ingest raw/report/요약/{today}_요약.md`\n"
    ]
    for rtype, label in section_labels.items():
        if sections[rtype]:
            parts.append(f"\n---\n\n# {label}\n\n" + "\n---\n\n".join(sections[rtype]))

    daily_path.write_text("".join(parts), encoding="utf-8")
    print(f"\n완료: {daily_path.name}  ({total}건)")
    print(f"다음: /ingest raw/report/요약/{today}_요약.md")


# ── 진입점 ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = pathlib.Path(sys.argv[1])
        pdf = REPORT_DIR / arg if not arg.is_absolute() else arg
        if not pdf.exists():
            print(f"파일 없음: {pdf}")
            sys.exit(1)

        # 폴더명으로 유형 판별
        folder_name = pdf.parent.name
        rtype = FOLDER_TYPE.get(folder_name, "company")
        print(f"\n[{pdf.name}] ({folder_name} → {rtype})")
        records = PROCESSORS[rtype](pdf)
        md_fn = TO_MD[rtype]
        for r in records:
            print(to_md_company(r, pdf.name) if rtype == "company" else md_fn(r, pdf.name))
            print("---")
    else:
        process_all()
