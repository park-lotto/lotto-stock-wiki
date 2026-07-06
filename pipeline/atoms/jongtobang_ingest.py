"""종토방(네이버 종목토론방) → atoms 인제스트 (Phase4).

종토방 글은 루머·심리 티어(🟠, source_trust='D'). 캐스케이드 원인추적에서
공시·뉴스·텔레 다음 단계로 소비된다(cause_hunt). 사실처럼 다루지 않도록 저신뢰로 저장.

구조:
- post_to_atom / signal_from_text: 순수(테스트 가능). 글 텍스트 → 종토방 원자.
- ingest_posts: 원자 삽입.
- crawl_and_ingest: naver_crawl.py(bodies 모드) 서브프로세스로 본문을 받아 인제스트.
  ⚠️ 글 목록(nids) 수집 크롤은 미구현 — 네이버 종토방 목록 API 라이브 발굴 필요(후속).
  당장은 호출자가 nids를 주거나, 다른 경로로 확보한 posts를 ingest_posts로 넣는다.
"""
import subprocess
import sys
import json
import pathlib
from datetime import datetime

from pipeline.atoms import db as _db

ROOT = pathlib.Path(__file__).resolve().parents[2]

_BULL_KW = ("호재", "상한가", "급등", "돌파", "수급", "체결강도", "매수", "목표가", "실적")
_BEAR_KW = ("악재", "하한가", "급락", "손절", "물렸", "매도", "폭락", "적자")


def signal_from_text(text: str) -> str:
    """종토방 글의 방향을 키워드로 거칠게 판정(LLM 없이). 루머 티어라 정밀도보다 커버리지."""
    t = text or ""
    b = sum(k in t for k in _BULL_KW)
    s = sum(k in t for k in _BEAR_KW)
    if b > s:
        return "bullish"
    if s > b:
        return "bearish"
    return "neutral"


def post_to_atom(post: dict, code: str, name: str, date: str = None) -> dict:
    """종토방 글 {nid, body} → 종토방 원자(🟠, 저신뢰). insert_atom 요구 필드 완비."""
    body = (post or {}).get("body") or ""
    nid = (post or {}).get("nid") or ""
    return {
        "id": f"jtb_{code}_{nid}",
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "source_type": "종토방",
        "source_name": f"네이버종토방:{name}",
        "source_trust": "D",
        "raw_file": None, "layer": None, "sector": None,
        "asset": name, "asset_level": "stock",
        "signal": signal_from_text(body),
        "event_type": "sentiment", "magnitude": "minor",
        "content_type": "rumor", "strength_score": 1,
        "validity_type": "transient", "validity_until": None,
        "is_active": 1, "content": body[:1000], "relations": [],
    }


def ingest_posts(posts: list, code: str, name: str, date: str = None) -> int:
    """종토방 글 리스트를 원자로 삽입. 빈 본문은 건너뜀. 반환=삽입 수."""
    n = 0
    for p in posts or []:
        if not (p or {}).get("body"):
            continue
        _db.insert_atom(post_to_atom(p, code, name, date=date))
        n += 1
    return n


def crawl_and_ingest(code: str, name: str, nids: list, date: str = None) -> int:
    """naver_crawl.py(bodies)로 본문을 받아 종토방 원자로 인제스트(impure 엔트리).
    nids는 호출자가 제공(목록 크롤은 후속 — 미구현)."""
    if not nids:
        return 0
    req = json.dumps({"mode": "bodies", "code": code, "nids": [str(x) for x in nids]},
                     ensure_ascii=False)
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "naver_crawl.py"), req],
                          capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))
    try:
        bodies = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return 0
    posts = [{"nid": nid, "body": body} for nid, body in bodies.items()]
    return ingest_posts(posts, code, name, date=date)
