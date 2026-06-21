"""질문지 추출 자동 검증 — 3단 게이트.

㉠ 인용 대조  : 수치·날짜가 PDF 원문에 실제 존재하는지 (PyMuPDF)
㉡ wisereport : tp_new·rating을 raw/wisereport/*_parsed.json 정답지와 대조
㉢ 구조 룰   : tp_direction vs 수치 모순, null 비율, stock인데 목표가 없음 등

반환: {"flags": [{"code": ..., "msg": ...}], "trust_score": float(0~1)}

trust_score → strength_score 환산 (report_ingest.py에서 사용):
    >= 0.8 → 변경 없음
    0.5~0.8 → -1
    < 0.5  → // 2
"""
import json
import re
from pathlib import Path

_WISE = Path(__file__).parent.parent.parent / "raw" / "wisereport"

# ──────────────────────────────────────────────
# ㉠ 인용 대조
# ──────────────────────────────────────────────

def _extract_pdf_text(pdf_path: Path) -> str:
    """PyMuPDF로 PDF 전체 텍스트 추출."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf_path))
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


def _normalise_number(s: str) -> str:
    """'800,000' → '800000', '15.3%' → '15.3' 등 숫자 정규화."""
    return re.sub(r"[,\s%원달러]", "", str(s))


def check_quotes(q: dict, pdf_text: str) -> list[dict]:
    """㉠ 핵심 수치가 PDF 원문에 실제 존재하는지 확인."""
    if not pdf_text:
        return [{"code": "Q_NO_PDF_TEXT", "msg": "PDF 텍스트 추출 실패 — 인용 대조 불가"}]

    flags: list[dict] = []
    kind = q.get("target_kind")

    candidates: list[tuple[str, str]] = []  # (슬롯명, 값)

    if kind == "stock":
        for s in q.get("stocks") or []:
            for slot in ("tp_new", "tp_prev"):
                v = s.get(slot)
                if v:
                    candidates.append((f"{s.get('name')}.{slot}", str(v)))
            quote = s.get("quote")
            if quote:
                candidates.append((f"{s.get('name')}.quote", quote))

    elif kind == "sector":
        if q.get("quote"):
            candidates.append(("sector.quote", q["quote"]))

    elif kind == "market":
        if q.get("quote"):
            candidates.append(("market.quote", q["quote"]))

    for slot, val in candidates:
        norm = _normalise_number(val)
        # 수치 슬롯: 정규화 후 원문 포함 여부
        if re.match(r"^\d[\d]*$", norm) and len(norm) >= 4:
            # 쉼표 포함 원문에서도 검색
            if norm not in _normalise_number(pdf_text):
                flags.append({
                    "code": "Q_NUM_NOT_FOUND",
                    "msg": f"수치 미발견: {slot}={val} (정규화={norm})",
                })
        # quote 슬롯: 원문의 10자 이상 구절이 PDF에 있는지
        elif len(val) >= 10:
            snippet = val[:20].strip()
            if snippet not in pdf_text:
                flags.append({
                    "code": "Q_QUOTE_NOT_FOUND",
                    "msg": f"인용구 미발견: {slot} 앞 20자 '{snippet}'",
                })

    return flags


# ──────────────────────────────────────────────
# ㉡ wisereport 정답지 대조
# ──────────────────────────────────────────────

def _load_wisereport(date: str) -> list[list]:
    """날짜에 해당하는 wisereport parsed.json의 corp 행 목록."""
    for f in _WISE.glob(f"{date}_parsed.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return data.get("corp", [])
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _tp_to_int(val) -> int | None:
    """'800,000' → 800000. 파싱 실패 시 None."""
    if not val:
        return None
    try:
        return int(str(val).replace(",", "").strip())
    except ValueError:
        return None


def check_wisereport(q: dict, meta: dict) -> list[dict]:
    """㉡ stock 리포트의 tp_new·rating을 wisereport 정답지와 대조."""
    flags: list[dict] = []
    if q.get("target_kind") != "stock":
        return flags

    rows = _load_wisereport(meta.get("date", ""))
    if not rows:
        return [{"code": "W_NO_ANSWER_KEY", "msg": f"wisereport 정답지 없음: {meta.get('date')}"}]

    broker_raw = (meta.get("broker") or "").replace(" ", "").lower()

    for s in q.get("stocks") or []:
        name = (s.get("name") or "").strip()
        if not name:
            continue

        # wisereport에서 같은 종목+증권사 행 찾기
        match = None
        for row in rows:
            if len(row) < 6:
                continue
            row_corp = str(row[1])  # "삼성화재[000810]"
            row_broker = str(row[0]).replace(" ", "").lower()  # "상상인증권김현수"
            if name in row_corp and broker_raw and broker_raw[:4] in row_broker:
                match = row
                break
        if not match:
            # 증권사 매칭 없이 종목만
            for row in rows:
                if len(row) < 6 and name in str(row[1] if len(row) > 1 else ""):
                    match = row
                    break

        if not match:
            continue  # wisereport에 없는 종목은 플래그 없음 (섹터/테마 리포트일 수 있음)

        # tp_new 대조
        ws_tp = _tp_to_int(match[5]) if len(match) > 5 else None
        q_tp = _tp_to_int(s.get("tp_new"))
        if ws_tp and q_tp and ws_tp != q_tp:
            flags.append({
                "code": "W_TP_MISMATCH",
                "msg": f"{name} tp_new 불일치: 질문지={q_tp:,} vs wisereport={ws_tp:,}",
            })

        # rating 대조 (대소문자 무시)
        ws_rating = str(match[3]).strip().upper() if len(match) > 3 else ""
        q_rating = str(s.get("rating") or "").strip().upper()
        if ws_rating and q_rating and ws_rating != q_rating:
            flags.append({
                "code": "W_RATING_MISMATCH",
                "msg": f"{name} rating 불일치: 질문지={q_rating} vs wisereport={ws_rating}",
            })

    return flags


# ──────────────────────────────────────────────
# ㉢ 구조 룰
# ──────────────────────────────────────────────

def check_structure(q: dict) -> list[dict]:
    """㉢ 구조적 모순·이상치 탐지."""
    flags: list[dict] = []
    kind = q.get("target_kind")

    if not kind:
        flags.append({"code": "S_NO_KIND", "msg": "target_kind 없음 — 라우팅 실패"})
        return flags

    if kind == "stock":
        stocks = q.get("stocks") or []
        if not stocks:
            flags.append({"code": "S_NO_STOCKS", "msg": "stock 타입인데 stocks 배열 비어있음"})
            return flags

        for s in stocks:
            name = s.get("name") or "?"
            tp_new = _tp_to_int(s.get("tp_new"))
            tp_prev = _tp_to_int(s.get("tp_prev"))
            direction = s.get("tp_direction")

            # tp_direction vs 실제 수치 모순
            if tp_new and tp_prev and direction:
                if direction == "up" and tp_new <= tp_prev:
                    flags.append({
                        "code": "S_TP_DIRECTION_UP_BUT_LOWER",
                        "msg": f"{name}: tp_direction=up 인데 tp_new({tp_new:,}) <= tp_prev({tp_prev:,})",
                    })
                elif direction == "down" and tp_new >= tp_prev:
                    flags.append({
                        "code": "S_TP_DIRECTION_DOWN_BUT_HIGHER",
                        "msg": f"{name}: tp_direction=down 인데 tp_new({tp_new:,}) >= tp_prev({tp_prev:,})",
                    })

            # stock 타입인데 목표가 없음
            if not tp_new:
                flags.append({
                    "code": "S_STOCK_NO_TP",
                    "msg": f"{name}: stock 타입인데 tp_new 없음 (섹터 리포트 오분류 의심)",
                })

        # null 비율 — 핵심 슬롯 기준 (quote 포함: 검증 불가 상태도 이상징후)
        core_slots = ["rating", "tp_new", "earnings_outlook", "thesis", "quote"]
        null_count = sum(
            1 for s in stocks for slot in core_slots if not s.get(slot)
        )
        total = len(stocks) * len(core_slots)
        null_ratio = null_count / total if total else 0
        if null_ratio >= 0.8:
            flags.append({
                "code": "S_HIGH_NULL_RATIO",
                "msg": f"핵심 슬롯 null 비율 {null_ratio:.0%} — 추출 실패 의심",
            })

        # quote 없는 종목
        no_quote = [s.get("name") or "?" for s in stocks if not s.get("quote")]
        if no_quote:
            flags.append({
                "code": "S_MISSING_QUOTE",
                "msg": f"quote 없는 종목: {', '.join(no_quote)}",
            })

    elif kind == "sector":
        if not q.get("sector_name"):
            flags.append({"code": "S_NO_SECTOR_NAME", "msg": "sector_name 없음"})
        if not q.get("thesis"):
            flags.append({"code": "S_NO_THESIS", "msg": "sector thesis 없음"})

    elif kind == "market":
        if not q.get("market_direction") and not q.get("recommended_sectors"):
            flags.append({
                "code": "S_MARKET_EMPTY",
                "msg": "market_direction·recommended_sectors 모두 없음",
            })

    return flags


# ──────────────────────────────────────────────
# 통합 실행 + trust_score
# ──────────────────────────────────────────────

def run_verification(
    q: dict, meta: dict, pdf_path: "Path | None" = None
) -> dict:
    """3단 검증 실행. 반환: {"flags": [...], "trust_score": float}"""
    flags: list[dict] = []

    # ㉠ 인용 대조
    if pdf_path:
        pdf_text = _extract_pdf_text(pdf_path)
        flags += check_quotes(q, pdf_text)
    else:
        flags.append({"code": "Q_SKIPPED", "msg": "PDF 경로 없음 — 인용 대조 생략"})

    # ㉡ wisereport 정답지
    flags += check_wisereport(q, meta)

    # ㉢ 구조 룰
    flags += check_structure(q)

    # trust_score: 심각 플래그 수로 감점
    # Q_SKIPPED·W_NO_ANSWER_KEY는 정보 없음 플래그 — 감점 제외
    INFO_ONLY = {"Q_SKIPPED", "W_NO_ANSWER_KEY", "Q_NO_PDF_TEXT"}
    penalty_flags = [f for f in flags if f["code"] not in INFO_ONLY]
    trust_score = max(0.0, 1.0 - len(penalty_flags) * 0.2)

    return {"flags": flags, "trust_score": round(trust_score, 2)}


def adjust_strength(strength: int, trust_score: float) -> int:
    """trust_score에 따라 strength_score 조정."""
    if trust_score >= 0.8:
        return strength
    if trust_score >= 0.5:
        return max(1, strength - 1)
    return max(1, strength // 2)
