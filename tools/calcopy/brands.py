"""칼카피 우리 브랜드 장부 읽기 — 주인 데이터 channel/브랜드.json(벤치 slug ↔ 브랜드 이름 ↔ 도파민썰템 스타일)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / "channel" / "브랜드.json"


def load() -> dict:
    return json.loads(BOOK.read_text(encoding="utf-8"))["brands"]


def brand(slug: str | None) -> str | None:
    """벤치 slug → 우리 브랜드 이름(장부에 없으면 None)."""
    return (load().get(slug or "") or {}).get("brand")


def style_of(slug: str, audio_kind: str | None) -> str | None:
    """뜯기 audio.composition.kind → 그 브랜드의 스타일 이름(나레만·나레+원음·자막만). 스타일 없는 브랜드·모르는 kind 는 None."""
    for name, st in ((load().get(slug) or {}).get("styles") or {}).items():
        if audio_kind in st["audio_kinds"]:
            return name
    return None
