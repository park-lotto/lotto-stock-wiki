"""
pdf_ingest.py — 리포트 MD 파일의 PDF URL을 Gemini로 읽어 원자화.

MD 파일 구조:
    - **PDF**: [다운로드](https://stock.pstatic.net/.../xxx.pdf)
    - **증권사**: 증권사명
    - **날짜**: 26.06.05

사용법:
    python -m pipeline.atoms.pdf_ingest raw/report/2026-06-05/xxx.md
    python -m pipeline.atoms.pdf_ingest --all              # 전체 미처리
    python -m pipeline.atoms.pdf_ingest --date 2026-06-05  # 날짜 필터
    python -m pipeline.atoms.pdf_ingest --limit 10         # N개만
    python -m pipeline.atoms.pdf_ingest --dry-run          # 목록만
"""
import sys
import re
import tempfile
import argparse
from pathlib import Path
from datetime import datetime

import requests
from google import genai
from google.genai import types

from .atomizer import _load_gemini_key, _make_id, _calc_strength
from .db import init_db, insert_atom, get_conn
from .vector_db import embed_and_store

RAW_ROOT = Path(__file__).parent.parent.parent / "raw"
_MODEL = "gemini-3.1-flash-lite"

_PROMPT = """당신은 한국 주식시장 전문 애널리스트입니다.
아래 증권사 리포트 PDF를 읽고, 투자 판단에 실질적으로 쓸 수 있는 정보만 '원자' 단위로 추출하라.

## 원자란
하나의 명확한 주제(종목/섹터/이벤트)에 대한 최소 의미 단위.
- 분량: 2~5문장
- 원문 표현 최대한 보존 (요약 금지, 축약 금지)
- 수치·날짜·비율이 있으면 반드시 포함
- 애매한 "긍정적", "부정적" 표현은 구체적 근거로 대체

## 반드시 포착해야 할 핵심 정보
1. **투자의견 변경** — BUY/HOLD/SELL 변경 + 이유
2. **목표주가 변경** — 기존 → 신규 + 변경 근거
3. **실적 서프라이즈·쇼크** — 예상 대비 실제 수치
4. **EPS·매출 추정 변경** — 컨센서스 대비 상향/하향 및 수치
5. **수급·수요 변화** — 외국인/기관 동향, 발주·수주 규모
6. **밸류에이션 근거** — PER/PBR/EV/EBITDA 등 수치 포함
7. **리스크 요인** — 구체적 조건과 시나리오
8. **섹터 업황 전환점** — 피크아웃·바닥·회복 근거 데이터
9. **공급망·경쟁구도 변화** — 고객사·경쟁사 동향
10. **이벤트 드라이버** — 날짜 명시된 촉매(실적발표·IR·출시·정책)

## 제외 대상 (원자로 만들지 말 것)
- 면책조항, 공시 문구, 법적 경고 ("당사는 해당 종목을 보유하지 않습니다" 등)
- 투자주의/경고/위험 종목 여부 체크 표 (X/O 형태)
- 한국거래소 시장경보제도 등 제도 안내·설명 문구
- 날짜+가격+거래량만 나열된 차트 테이블 (분석 없는 단순 수치 나열)
- 시가/고가/저가/종가/거래량 단독 수치 나열
- 투자의견 분포 통계 ("Buy 95%, Hold 4%" 등 단순 비율 공시)
- 이미 알려진 일반 상식 수준의 설명
- 리포트 표지·헤더·목차 정보

## 메타데이터 부여 기준
- sector: 반도체/조선/로봇/방산/바이오/전력/2차전지/자동차/통신/AI소프트웨어/우주/소비내수/기타
- asset: 종목명(코드 제외) 또는 섹터명 — 가능한 한 구체적으로
- asset_level: stock(개별종목) / sector(업종) / market(시장전체) / macro(거시) / theme(테마)
- signal:
    bullish  = 상승 근거 명확 (목표가상향, 실적호조, 수주증가 등)
    bearish  = 하락 근거 명확 (목표가하향, 실적쇼크, 수요감소 등)
    neutral  = 중립적 정보
    risk     = 리스크 요인 (불확실성, 하락 시나리오)
    catalyst = 단기 상승 촉매 (이벤트, 발표 예정)
    data     = 수치 데이터 중심
- event_type: earnings/consensus/supply/demand/policy/momentum/macro/report/event
- magnitude:
    major = 목표가 10%+변경, 실적 컨센대비 5%+, 업황 전환점, 대규모 수주
    minor = 소폭 조정, 일상적 업데이트
- content_type: fact(확인된 사실) / data(수치) / analysis(분석·해석) / opinion(의견)
- validity_type: permanent / date(특정 기간) / event(이벤트 발생 시)
- validity_until: 실적 발표 후 만료되는 경우 날짜 명시, 아니면 null

## 출력 형식
JSON 배열만 반환. 다른 텍스트 절대 금지.
[{"content": "...", "sector": "...", "asset": "...", "asset_level": "...", "signal": "...", "event_type": "...", "magnitude": "...", "content_type": "...", "validity_type": "...", "validity_until": null}, ...]"""


def _extract_pdf_url(md_path: Path) -> str | None:
    """MD 파일에서 PDF 다운로드 URL 추출."""
    text = md_path.read_text(encoding="utf-8-sig", errors="replace")
    m = re.search(r'\*\*PDF\*\*.*?\[다운로드\]\((https?://[^\)]+)\)', text)
    if m:
        return m.group(1)
    # 대체 패턴
    m = re.search(r'(https?://\S+\.pdf)', text)
    return m.group(1) if m else None


def _extract_meta(md_path: Path) -> dict:
    """MD 파일에서 증권사, 날짜, 제목 추출."""
    text = md_path.read_text(encoding="utf-8-sig", errors="replace")
    broker = re.search(r'\*\*증권사\*\*[:\s]+(.+)', text)
    date_raw = re.search(r'\*\*날짜\*\*[:\s]+(.+)', text)
    title = md_path.stem

    broker = broker.group(1).strip() if broker else md_path.stem
    # "26.06.05" → "2026-06-05"
    date_str = ""
    if date_raw:
        d = date_raw.group(1).strip()
        m = re.match(r'(\d{2})\.(\d{2})\.(\d{2})', d)
        if m:
            date_str = f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if not date_str:
        m = re.search(r'(\d{4}-\d{2}-\d{2})', str(md_path))
        date_str = m.group(1) if m else datetime.now().strftime("%Y-%m-%d")

    return {"broker": broker, "date": date_str, "title": title}


def _download_pdf(url: str, dest: Path) -> bool:
    """PDF URL을 로컬 파일로 다운로드."""
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 1000:
            dest.write_bytes(r.content)
            return True
        print(f"  [WARN] PDF 다운로드 실패: HTTP {r.status_code} ({url[:60]}...)")
    except Exception as e:
        print(f"  [WARN] PDF 다운로드 오류: {e}")
    return False


def _pdf_to_atoms(pdf_path: Path, meta: dict) -> list[dict]:
    """Gemini로 PDF 읽어 원자 리스트 반환."""
    import json as _json

    client = genai.Client(api_key=_load_gemini_key())

    # Gemini Files API에 업로드
    try:
        with open(pdf_path, "rb") as fh:
            file_obj = client.files.upload(
                file=fh,
                config=types.UploadFileConfig(mime_type="application/pdf"),
            )
    except Exception as e:
        print(f"  [WARN] Gemini 파일 업로드 실패: {e}")
        return []

    try:
        response = client.models.generate_content(
            model=_MODEL,
            contents=[file_obj, _PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        raw_atoms: list[dict] = _json.loads(response.text)
    except Exception as e:
        print(f"  [WARN] Gemini 분석 실패: {e}")
        return []
    finally:
        # 업로드 파일 삭제 (Gemini 저장소 정리)
        try:
            client.files.delete(name=file_obj.name)
        except Exception:
            pass

    atoms = []
    for i, a in enumerate(raw_atoms):
        content = a.get("content", "").strip()
        if not content:
            continue
        atoms.append({
            "id": _make_id(meta["date"], meta["broker"], i),
            "date": meta["date"],
            "source_type": "report",
            "source_name": meta["broker"],
            "source_trust": "A",
            "raw_file": str(pdf_path),
            "layer": "L5",
            "sector": a.get("sector", "기타"),
            "asset": a.get("asset", ""),
            "asset_level": a.get("asset_level", "stock"),
            "signal": a.get("signal", "neutral"),
            "event_type": a.get("event_type", "report"),
            "magnitude": a.get("magnitude", "minor"),
            "content_type": a.get("content_type", "analysis"),
            "strength_score": _calc_strength(a, "A"),
            "validity_type": a.get("validity_type", "permanent"),
            "validity_until": a.get("validity_until"),
            "is_active": 1,
            "content": content,
            "relations": [],
        })
    return atoms


def get_done_pdf_files() -> set[str]:
    """이미 처리된 PDF raw_file 경로 집합."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT raw_file FROM atoms WHERE source_type='report'"
    ).fetchall()
    conn.close()
    return {r[0].replace("\\", "/") for r in rows}


def get_pending_md_files(date_filter: str = None) -> list[Path]:
    """PDF URL이 있는 미처리 MD 파일 목록 (최신순)."""
    done = get_done_pdf_files()
    pending = []

    for f in sorted(RAW_ROOT.rglob("*.md")):
        if "/report" not in str(f).replace("\\", "/"):
            continue
        if date_filter and date_filter not in str(f):
            continue
        url = _extract_pdf_url(f)
        if not url:
            continue
        # PDF 경로로 중복 체크 (같은 URL은 같은 내용)
        if any(Path(d).name == f.stem + ".pdf" for d in done):
            continue
        # 이미 같은 MD raw_file로 처리됐는지도 체크
        rel = str(f).replace("\\", "/")
        if any(rel in d for d in done):
            continue
        pending.append(f)

    return sorted(pending, reverse=True)  # 최신순


def ingest_pdf_from_md(md_path: Path) -> int:
    """MD 파일 → PDF 다운로드 → Gemini 읽기 → atoms 저장."""
    url = _extract_pdf_url(md_path)
    if not url:
        print(f"  [SKIP] PDF URL 없음: {md_path.name}")
        return 0

    meta = _extract_meta(md_path)

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / (md_path.stem + ".pdf")

        if not _download_pdf(url, pdf_path):
            return 0

        size_kb = pdf_path.stat().st_size // 1024
        print(f"  PDF {size_kb}KB 다운로드 완료")

        atoms = _pdf_to_atoms(pdf_path, meta)

    for atom in atoms:
        insert_atom(atom)
        embed_and_store(atom)

    return len(atoms)


def main():
    parser = argparse.ArgumentParser(description="리포트 PDF Gemini 원자화")
    parser.add_argument("file", nargs="?", help="단일 MD 파일 경로")
    parser.add_argument("--all", action="store_true", help="전체 미처리")
    parser.add_argument("--date", default=None, help="날짜 필터 YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=10, help="처리 수 (기본 10)")
    parser.add_argument("--dry-run", action="store_true", help="목록만 출력")
    args = parser.parse_args()

    print("[DEPRECATED] pdf_ingest는 '중요한 걸 골라라' 방식 — 질문지 방식 권장: "
          "python -m pipeline.atoms.report_ingest --dir <폴더> "
          "(일일 파이프라인 교체는 report_ingest --all 패리티 후)")

    init_db()

    if args.file:
        targets = [Path(args.file)]
    else:
        pending = get_pending_md_files(args.date)
        targets = pending[:args.limit]
        print(f"미처리 MD: {len(pending)}개 | 이번: {len(targets)}개\n")

    if args.dry_run:
        for f in targets:
            url = _extract_pdf_url(f)
            print(f"  {f.name}")
            print(f"    URL: {url[:70] if url else '없음'}")
        return

    total_atoms = 0
    for i, f in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {f.name}")
        count = ingest_pdf_from_md(f)
        total_atoms += count
        print(f"  → {count}개 원자")

    print(f"\n완료: {len(targets)}개 파일, {total_atoms}개 원자")


if __name__ == "__main__":
    main()
