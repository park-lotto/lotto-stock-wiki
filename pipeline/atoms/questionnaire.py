"""리포트 질문지 추출 — Gemini가 PDF를 고정 슬롯에 옮긴다."""
import hashlib
import json
from pathlib import Path

from google import genai
from google.genai import types

from .atomizer import _load_gemini_key
from .codemap import is_korean_stock

_MODEL = "gemini-3.1-flash-lite"

QUESTIONNAIRE_PROMPT = """너는 증권사 리포트를 '정해진 질문지'에 옮겨 적는 사람이다.
무엇이 중요한지 판단하지 마라. 칸을 채우는 것이 전부다.

## 철칙
1. 칸에 해당하는 내용이 리포트에 없으면 그 값은 null. 절대 지어내지 마라.
2. 모든 수치·날짜·종목명은 원문 그대로(축자). 반올림·재서술 금지.
3. 핵심 슬롯에는 "quote"(근거가 된 원문 문장 그대로)를 짝으로 붙여라.
4. 면책조항·독립성 고지·보유율(1% 미만 등)·법적 경고 문구는 완전히 무시하라.
   설령 그것이 요약의 전부처럼 보여도, 본문에서 실제 분석 내용을 찾아 채워라.
5. 증권사명·애널리스트명은 PDF 표지/머리글/꼬리글에서 찾아라. (파일명엔 없을 수 있음)

## STEP 0 — target_kind 판별
- "stock"  : 특정 종목에 목표주가가 제시됨
- "sector" : 단일 업종/테마 전반의 전망 (개별 목표가 없이 업종을 논함)
- "market" : 시장 전체/매크로/전략, 또는 2개 이상 섹터를 묶은 데일리·위클리
판별 근거는 네이버 카테고리나 제목이 아니라 본문 내용이다.

## STEP 1 — 공통 헤더
broker(증권사), analyst(애널리스트), report_date

## STEP 2 — target_kind별 질문지

[stock] 각 종목별로 stocks 배열:
  name, code(PDF에 6자리 있으면, 없으면 null),
  rating, rating_changed,
  tp_new, tp_prev, tp_direction(up/down/flat/null),
  earnings_outlook(이번·차기 분기 실적·판매량·매출·영익 전망. 컨센/YoY/QoQ 수치가
    하나라도 있으면 반드시 채워라. 빈칸으로 넘기지 마라),
  estimate_revision, next_catalyst,
  thesis(최대 3개 배열), valuation_basis, risk, supply_comment, quote

[sector]
  sector_name, sector_view(비중확대/중립/축소),
  thesis(배열), timeline(배열),
  top_picks: [{name, reason, tp}]
    — 본문에 매수·선호·수혜·주목·탑픽·1선/2선으로 종목명이 거론된 곳을 빠짐없이.
      단 하나의 종목명도 없을 때만 null.
  risk, quote

[market]
  market_direction, macro_vars(배열),
  recommended_sectors: [{sector, stance, reason}],
  style, event_calendar: [{date, event}],
  top_picks(거론 종목 배열 또는 null), risk, quote

## 출력
질문지 1장을 JSON 객체 하나로. target_kind에 해당하는 칸만 채우고 나머지는 생략.
다른 텍스트 절대 금지."""


def extract_questionnaire(pdf_path: Path) -> dict:
    """PDF를 Gemini로 읽어 채워진 질문지 dict 반환. 실패 시 {}."""
    client = genai.Client(api_key=_load_gemini_key())
    try:
        with open(pdf_path, "rb") as fh:
            fobj = client.files.upload(
                file=fh, config=types.UploadFileConfig(mime_type="application/pdf")
            )
    except Exception as e:
        print(f"  [WARN] 업로드 실패: {e}")
        return {}
    try:
        resp = client.models.generate_content(
            model=_MODEL,
            contents=[fobj, QUESTIONNAIRE_PROMPT],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(resp.text)
    except Exception as e:
        print(f"  [WARN] 추출 실패: {e}")
        return {}
    finally:
        try:
            client.files.delete(name=fobj.name)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────
# 질문지 → 원자 변환 (fan-out)
# ─────────────────────────────────────────────────────────────────

_SECTOR_LIST = [
    "반도체", "조선", "로봇", "방산", "바이오", "전력", "2차전지",
    "자동차", "통신", "AI소프트웨어", "우주", "소비내수", "미용",
    "LNG", "신재생", "기타",
]


def _norm_sector(s: str) -> str:
    if not s:
        return "기타"
    for k in _SECTOR_LIST:
        if k in s:
            return k
    return "기타"


def _is_bullish_view(v: str) -> bool:
    return bool(v) and ("확대" in v or "overweight" in v.lower())


def _mk_id(date: str, broker: str, raw_file: str, tag: str, i: int) -> str:
    raw = f"{date}_{broker}_{raw_file}_{tag}_{i}"
    return "atom_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _base(meta: dict, **kw) -> dict:
    """원자 공통 필드 + 기본값. kw로 덮어쓴다."""
    d = {
        "id": "",
        "date": meta["date"],
        "source_type": "report",
        "source_name": meta["broker"],
        "source_trust": "A",
        "raw_file": meta["raw_file"],
        "layer": "L5",
        "sector": "기타",
        "asset": "",
        "asset_level": "stock",
        "signal": "neutral",
        "event_type": "report",
        "magnitude": "minor",
        "content_type": "analysis",
        "strength_score": 1,
        "validity_type": "permanent",
        "validity_until": None,
        "is_active": 1,
        "content": "",
        "relations": [],
    }
    d.update(kw)
    return d


def _stock_atom(meta, sector, name, content, *, strong, signal, i, tag) -> dict:
    return _base(
        meta,
        id=_mk_id(meta["date"], meta["broker"], meta["raw_file"], tag, i),
        sector=_norm_sector(sector),
        asset=name,
        asset_level="stock",
        signal=signal,
        magnitude="major" if strong else "minor",
        strength_score=4 if strong else 2,
        content=content,
    )


def _guess_sector_from_stock(name: str) -> str:
    """종목 섹터 추정 — 현재는 기타. 후속에서 종목→섹터 맵 연결."""
    return "기타"


def questionnaire_to_atoms(q: dict, meta: dict) -> list[dict]:
    """채워진 질문지 dict + meta → 원자 dict 리스트."""
    kind = q.get("target_kind")
    atoms: list[dict] = []

    if kind == "stock":
        for i, s in enumerate(q.get("stocks", [])):
            name = (s.get("name") or "").strip()
            if not name:
                continue
            sig = {"up": "bullish", "down": "bearish"}.get(s.get("tp_direction"), "neutral")
            parts = [
                f"투자의견 {s.get('rating')}({s.get('rating_changed') or ''})",
                f"목표가 {s.get('tp_prev')}→{s.get('tp_new')}" if s.get("tp_new") else "",
                s.get("earnings_outlook") or "",
                "; ".join(s.get("thesis") or []),
                f"리스크: {s.get('risk')}" if s.get("risk") else "",
            ]
            content = " / ".join(p for p in parts if p)
            atoms.append(_stock_atom(
                meta, _guess_sector_from_stock(name), name, content,
                strong=bool(s.get("tp_new")), signal=sig, i=i, tag="stk",
            ))

    elif kind == "sector":
        sec = _norm_sector(q.get("sector_name"))
        thesis = "; ".join(q.get("thesis") or [])
        atoms.append(_base(
            meta,
            id=_mk_id(meta["date"], meta["broker"], meta["raw_file"], "sec", 0),
            sector=sec, asset=q.get("sector_name") or sec, asset_level="sector",
            signal="bullish" if _is_bullish_view(q.get("sector_view")) else "neutral",
            event_type="report", magnitude="major", strength_score=4,
            content=f"[{q.get('sector_view')}] {thesis}",
        ))
        for i, p in enumerate(q.get("top_picks") or []):
            name = (p.get("name") or "").strip()
            if not is_korean_stock(name):
                continue
            atoms.append(_stock_atom(
                meta, sec, name, f"{sec} 섹터리포트 탑픽 거론: {p.get('reason') or ''}",
                strong=False, signal="bullish", i=i, tag="secpick",
            ))

    elif kind == "market":
        atoms.append(_base(
            meta,
            id=_mk_id(meta["date"], meta["broker"], meta["raw_file"], "mkt", 0),
            sector="기타", asset="시장", asset_level="market",
            signal="neutral", event_type="macro", magnitude="major", strength_score=3,
            content=q.get("market_direction") or "; ".join(
                rs.get("reason", "") for rs in q.get("recommended_sectors") or []
            ),
        ))
        for i, rs in enumerate(q.get("recommended_sectors") or []):
            sec = _norm_sector(rs.get("sector"))
            atoms.append(_base(
                meta,
                id=_mk_id(meta["date"], meta["broker"], meta["raw_file"], "mktsec", i),
                sector=sec, asset=rs.get("sector") or sec, asset_level="sector",
                signal="bullish" if _is_bullish_view(rs.get("stance")) else "neutral",
                event_type="report", magnitude="minor", strength_score=2,
                content=f"시황리포트 추천섹터: {rs.get('reason') or ''}",
            ))
        for i, name in enumerate(q.get("top_picks") or []):
            name = (name or "").strip()
            if not is_korean_stock(name):
                continue
            atoms.append(_stock_atom(
                meta, _guess_sector_from_stock(name), name,
                "시황리포트 탑픽 거론", strong=False, signal="bullish", i=i, tag="mktpick",
            ))

    return atoms
