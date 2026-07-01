"""텔레그램 타입별 질문지 프롬프트 + Gemini 추출."""
import hashlib
import json
import re as _re
from pathlib import Path

from google import genai
from google.genai import types

from .atomizer import _load_gemini_key
from .stock_resolve import resolve_stock, foreign_sectors, log_foreign_unmapped
from .sector_classify import resolve_sector, sectors_list

_MODEL = "gemini-3.1-flash-lite"

_COMMON = """너는 텔레그램 주식 채널의 하루치 메시지를 '정해진 칸'에 옮겨 적는 사람이다.
판단하지 말고 칸을 채워라. 잡담·인사·이미지설명·외부링크는 버려라.
철칙: 없으면 null(지어내지 마라) / 수치·종목명·날짜는 원문 그대로 /
각 항목에 ts(원문 메시지 시각 HH:MM)와 quote(근거 원문 문장 그대로)를 짝으로 붙여라 /
comment·reason은 재서술 허용하되 quote는 반드시 원문 축자.
출력: 해당 칸만 채운 JSON 1개. 다른 텍스트 금지.
"""

_SECTOR_RULE = (
    "각 종목에는 sector를 붙여라. 아래 목록에서 정확히 하나만 고른다(모르면 \"기타\"): "
    + " / ".join(sectors_list()) + "\n"
)
_COMMON = _COMMON + _SECTOR_RULE

QUESTIONNAIRES = {
    "sector": _COMMON + """
이 채널 타입: sector
칸: sector_name, sector_view(긍정/중립/부정), points(코멘트 배열),
stocks_mentioned:[{name, comment, ts, quote, sector}],
events:[{fact, ts, quote}], quote(핵심 한 문장)""",

    "market": _COMMON + """
이 채널 타입: market
칸: market_direction, macro_events:[{fact, ts, quote}],
sectors_mentioned:[{sector, stance, comment}], quote""",

    "stock_tips": _COMMON + """
이 채널 타입: stock_tips
칸: stocks:[{name, signal(bull/bear/neutral), reason, ts, quote, sector}],
news_items:[{fact, ts, quote}], quote""",

    "insight": _COMMON + """
이 채널 타입: insight (잡담 많음 — 투자 인사이트만 추려라)
칸: leading_sectors(배열),
stance:[{target(종목 또는 섹터), view(긍정/중립/부정), ts, quote}],
methods:[{rule, quote}]  (종목 무관 매매규칙),
stocks_mentioned:[{name, comment, ts, quote, sector}],
noise_ratio(0~1 추정), quote(가장 통찰력 있는 한 문장)""",

    "report_relay": _COMMON + """
이 채널 타입: report_relay (증권사 리포트 중계)
칸: reports:[{broker, stock, rating, tp, ts, quote, sector}], quote""",
}


_TRUST_BASE = {"A": 4, "B": 3, "C": 2, "D": 1}
_LAYER_W = {"fact": 1.0, "stance": 0.8, "method": 0.7}
_SECTOR_KEYS = sectors_list()


def _mk_id(channel: str, date: str, tag: str, i: int) -> str:
    raw = f"{channel}_{date}_{tag}_{i}"
    return "atom_tg_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _strength(trust: str, layer_tag: str, mention_count: int) -> int:
    base = _TRUST_BASE.get(trust, 1) * _LAYER_W.get(layer_tag, 1.0)
    return max(1, min(4, round(base + (mention_count - 1))))


def _event_key(fact: str) -> str:
    norm = _re.sub(r"[^가-힣A-Za-z0-9]", "", fact or "")
    return hashlib.md5(norm.encode()).hexdigest()[:10]


def _norm_sector(s: str) -> str:
    if not s:
        return "기타"
    for k in _SECTOR_KEYS:
        if k in s:
            return k
    return "기타"


def _base(meta: dict, **kw) -> dict:
    d = {
        "id": "", "date": meta["date"], "source_type": meta.get("source_type", "telegram"),
        "source_name": meta["channel"], "source_trust": meta.get("trust", "C"),
        "raw_file": meta.get("raw_file", ""), "layer": "L5",
        "sector": meta.get("sector") or "기타", "asset": "", "asset_level": "sector",
        "signal": "neutral", "event_type": "report", "magnitude": "minor",
        "content_type": "fact", "strength_score": 1, "validity_type": "permanent",
        "validity_until": None, "is_active": 1, "content": "", "relations": [],
        "stance_key": None, "mention_channels": [meta["channel"]],
        "mention_count": 1, "msg_ts": None,
    }
    d.update(kw)
    return d


def _stock_atom(meta, name_info, content, *, ts, i, sector, layer_tag="fact"):
    return _base(
        meta,
        id=_mk_id(meta["channel"], meta["date"], "stk", i),
        sector=sector,
        asset=name_info["name"], asset_level="stock",
        content_type="fact", msg_ts=ts,
        strength_score=_strength(meta.get("trust", "C"), layer_tag, 1),
        content=content,
    )


def _foreign_sector_atom(meta, sector, name, comment, *, ts, i):
    """외국주 언급 → 매핑 섹터의 컨텍스트 원자 (글로벌 동향). 약한 신호."""
    return _base(
        meta,
        id=_mk_id(meta["channel"], meta["date"], "fgn", i),
        sector=sector, asset=sector, asset_level="sector",
        content_type="fact", msg_ts=ts,
        strength_score=max(1, _strength(meta.get("trust", "C"), "stance", 1) - 1),
        content=f"글로벌 {name}: {comment}".strip(),
    )


def questionnaire_to_atoms_tg(q: dict, meta: dict) -> list[dict]:
    ctype = meta["type"]
    atoms: list[dict] = []
    trust = meta.get("trust", "C")

    def add_stocks(items, key_name, key_text):
        """한국주(매칭)=종목원자(hint 섹터) / 비매칭=외국주 경로(map→hint→기타 컨텍스트원자)."""
        for s in items or []:
            raw = (s.get(key_name) or "").strip()
            if not raw:
                continue
            info = resolve_stock(raw, date=meta["date"], channel=meta["channel"], skip_log=True)
            quote = s.get("quote") or s.get(key_text) or ""
            comment = s.get(key_text) or quote
            hint = s.get("sector")
            if info["matched"]:
                secs, _ = resolve_sector(info["name"], hint, is_foreign=False)
                atoms.append(_stock_atom(meta, info, quote, ts=s.get("ts"),
                                         i=len(atoms), sector=secs[0]))
                continue
            # 비매칭 = 외국주 경로 (codemap이 KRX 전종목이라 미매칭 한국주는 희소)
            secs, src = resolve_sector(info["name"], hint, is_foreign=True)
            for sec in secs:
                atoms.append(_foreign_sector_atom(
                    meta, sec, info["name"], comment, ts=s.get("ts"), i=len(atoms)))
            if src == "fallback":
                log_foreign_unmapped(info["name"], meta["date"], meta["channel"])

    if ctype == "sector":
        sec = meta.get("sector") or _norm_sector(q.get("sector_name")) or "기타"
        add_stocks(q.get("stocks_mentioned"), "name", "comment")
        body = "; ".join(q.get("points") or [])
        atoms.append(_base(
            meta,
            id=_mk_id(meta["channel"], meta["date"], "sec", 0),
            sector=sec, asset=sec,
            asset_level="sector",
            signal="bullish" if q.get("sector_view") == "긍정" else "neutral",
            strength_score=_strength(trust, "fact", 1),
            content=f"[{q.get('sector_view')}] {body}",
        ))
        for i, ev in enumerate(q.get("events") or []):
            atoms.append(_base(
                meta, id=_mk_id(meta["channel"], meta["date"], "ev", i),
                sector=sec, asset=sec, asset_level="sector",
                event_type="event", validity_type="event", msg_ts=ev.get("ts"),
                content=ev.get("fact") or "", strength_score=_strength(trust, "fact", 1),
            ))

    elif ctype == "market":
        atoms.append(_base(
            meta, id=_mk_id(meta["channel"], meta["date"], "mkt", 0),
            asset="시장", asset_level="market", event_type="macro",
            content=q.get("market_direction") or "",
            strength_score=_strength(trust, "fact", 1),
        ))
        for i, ev in enumerate(q.get("macro_events") or []):
            fact = ev.get("fact") if isinstance(ev, dict) else str(ev)
            atoms.append(_base(
                meta, id=_mk_id(meta["channel"], meta["date"], "macro", i),
                asset="시장", asset_level="market", event_type="macro",
                validity_type="event", msg_ts=ev.get("ts") if isinstance(ev, dict) else None,
                content=fact or "", strength_score=_strength(trust, "fact", 1),
            ))
        for i, sm in enumerate(q.get("sectors_mentioned") or []):
            atoms.append(_base(
                meta, id=_mk_id(meta["channel"], meta["date"], "mktsec", i),
                sector=_norm_sector(sm.get("sector")), asset=sm.get("sector") or "기타",
                asset_level="sector", content=sm.get("comment") or "",
                strength_score=_strength(trust, "stance", 1),
            ))

    elif ctype == "stock_tips":
        add_stocks(q.get("stocks"), "name", "reason")
        for i, nw in enumerate(q.get("news_items") or []):
            fact = nw.get("fact") if isinstance(nw, dict) else str(nw)
            atoms.append(_base(
                meta, id=_mk_id(meta["channel"], meta["date"], "news", i),
                asset_level="market", event_type="event", validity_type="event",
                msg_ts=nw.get("ts") if isinstance(nw, dict) else None,
                content=fact or "",
                strength_score=_strength(trust, "fact", 1),
            ))

    elif ctype == "insight":
        for i, st in enumerate(q.get("stance") or []):
            target = (st.get("target") or "").strip()
            if not target:
                continue
            atoms.append(_base(
                meta, id=_mk_id(meta["channel"], meta["date"], "stance", i),
                asset=target, asset_level="stance",
                stance_key=f"{meta['channel']}|{target}",
                content_type="opinion", msg_ts=st.get("ts"),
                signal="bullish" if st.get("view") == "긍정" else "neutral",
                content=f"{st.get('view')}: {st.get('quote') or ''}",
                strength_score=_strength(trust, "stance", 1),
            ))
        for i, m in enumerate(q.get("methods") or []):
            atoms.append(_base(
                meta, id=_mk_id(meta["channel"], meta["date"], "method", i),
                asset_level="method", content_type="opinion",
                content=m.get("rule") or "", strength_score=_strength(trust, "method", 1),
            ))
        add_stocks(q.get("stocks_mentioned"), "name", "comment")

    elif ctype == "report_relay":
        for i, rp in enumerate(q.get("reports") or []):
            raw = (rp.get("stock") or "").strip()
            if not raw:
                continue
            info = resolve_stock(raw, date=meta["date"], channel=meta["channel"], skip_log=True)
            if info["matched"]:
                secs, _ = resolve_sector(info["name"], rp.get("sector"), is_foreign=False)
                atoms.append(_stock_atom(
                    meta, info,
                    f"[중계:{rp.get('broker')}] 목표가 {rp.get('tp')} {rp.get('rating')} / {rp.get('quote') or ''}",
                    ts=rp.get("ts"), i=len(atoms), sector=secs[0]))

    return atoms


def extract_telegram(md_path: Path, ctype: str) -> dict:
    """채널 .md를 Gemini로 읽어 채워진 질문지 반환. 실패 시 {}."""
    prompt = QUESTIONNAIRES.get(ctype)
    if not prompt:
        return {}
    text = md_path.read_text(encoding="utf-8")
    from .atomizer import _get_client, _rotate_key
    for _attempt in range(4):
        try:
            resp = _get_client().models.generate_content(
                model=_MODEL, contents=[text, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return json.loads(resp.text)
        except Exception as e:
            _m = str(e)
            if any(c in _m for c in ("429", "RESOURCE_EXHAUSTED")):
                if _rotate_key():
                    continue
            print(f"  [WARN] 추출 실패({ctype}): {e}")
            return {}
    return {}
