"""소스별 콘텐츠 프로필 레지스트리 — 채널 성격에 맞는 전용 질문지 선택.
채널 온보딩 스킬(.agents/skills/channel-onboard/)이 이 레지스트리를 채운다."""
import json
import hashlib
from pathlib import Path

from .sector_classify import sectors_list, resolve_sector

_DIR = Path(__file__).parent
_YOUTUBE_REGISTRY_PATH = _DIR / "youtube_registry.json"
_YOUTUBE_REGISTRY_CACHE: dict = {}

_DAYTRADING_PROMPT = """너는 데이트레이딩(단기매매) 유튜브 영상 자막을 '정해진 칸'에
옮겨 적는 사람이다. 판단하지 말고 칸을 채워라. 잡담·인사는 버려라.
철칙: 없으면 null(지어내지 마라) / 수치는 원문 그대로 /
각 매매에 quote(근거 원문 문장)와 sector를 붙여라. sector는 아래 목록에서 정확히
하나(모르면 "기타"): """ + " / ".join(sectors_list()) + """

## 칸
trades: [{
  name(종목명), entry_price(진입가), stop_loss(손절가), target_price(목표가),
  hold_period(보유기간, 예: "2~3일"), chart_pattern(진입 근거가 된 차트패턴·기술적 신호),
  sector, quote
}]

## 출력
trades 배열만 채운 JSON 1개. 다른 텍스트 금지."""

# 프로필명 -> {"prompt": Gemini 질문지 문자열, "slots": 저장해야 할 슬롯 키 목록}
# 채널 온보딩 스킬로 검증된 프로필만 여기 등록한다.
YOUTUBE_PROFILES: dict[str, dict] = {
    "데이트레이딩": {
        "prompt": _DAYTRADING_PROMPT,
        "slots": ["name", "entry_price", "stop_loss", "target_price",
                  "hold_period", "chart_pattern", "sector", "quote"],
    },
}


def youtube_channel_profile(channel_name: str) -> str | None:
    """youtube_registry.json에서 채널의 기본 프로필 태그를 조회.
    등록 안 됐거나 profile 필드가 없으면 None(기존 POST_PROMPT 경로 사용)."""
    if not _YOUTUBE_REGISTRY_CACHE:
        try:
            _YOUTUBE_REGISTRY_CACHE.update(
                json.loads(_YOUTUBE_REGISTRY_PATH.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    entry = _YOUTUBE_REGISTRY_CACHE.get((channel_name or "").strip())
    if not isinstance(entry, dict):
        return None
    return entry.get("profile")


def _mk_daytrading_id(meta: dict, i: int) -> str:
    raw = f"{meta.get('channel', '')}_{meta.get('date', '')}_{meta.get('raw_file', '')}_dt_{i}"
    return "atom_yt_dt_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def daytrading_atoms(q: dict, meta: dict) -> list[dict]:
    """데이트레이딩 프로필 질문지 dict -> 원자 리스트. entry_price/stop_loss 등은
    atoms 공통 컬럼이 아니라 structured_fields JSON으로 원본 그대로 보존한다."""
    atoms: list[dict] = []
    for i, t in enumerate(q.get("trades") or []):
        name = (t.get("name") or "").strip()
        if not name:
            continue
        sector = resolve_sector(name, t.get("sector"), is_foreign=False)[0][0]
        structured = {
            "entry_price": t.get("entry_price"), "stop_loss": t.get("stop_loss"),
            "target_price": t.get("target_price"), "hold_period": t.get("hold_period"),
            "chart_pattern": t.get("chart_pattern"),
        }
        content = (
            f"진입 {t.get('entry_price')} / 손절 {t.get('stop_loss')} / "
            f"목표 {t.get('target_price')} / 보유 {t.get('hold_period')} — "
            f"{t.get('chart_pattern') or ''}"
        ).strip()
        atoms.append({
            "id": _mk_daytrading_id(meta, i),
            "date": meta["date"], "source_type": meta.get("source_type", "youtube"),
            "source_name": meta["channel"], "source_trust": meta.get("trust", "C"),
            "raw_file": meta.get("raw_file", ""), "layer": "L5",
            "sector": sector, "asset": name, "asset_level": "stock",
            "signal": "bullish", "event_type": "report", "magnitude": "major",
            "content_type": "fact", "strength_score": 3, "validity_type": "event",
            "validity_until": None, "is_active": 1,
            "content": content, "relations": [],
            "structured_fields": json.dumps(structured, ensure_ascii=False),
        })
    return atoms
