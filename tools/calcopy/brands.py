"""칼카피 우리 브랜드 장부 읽기 — 주인 데이터 channel/브랜드.json(벤치 slug ↔ 브랜드 이름) · 스타일 장부 channel/스타일.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / "channel" / "브랜드.json"


def load() -> dict:
    return json.loads(BOOK.read_text(encoding="utf-8"))["brands"]


def brand(slug: str | None) -> str | None:
    """벤치 slug → 우리 브랜드 이름(장부에 없으면 None)."""
    return (load().get(slug or "") or {}).get("brand")


STYLES = ROOT / "channel" / "스타일.json"


def styles() -> dict:
    """채널을 가로지르는 스타일 장부(현장썰·대사썰·나레썰·자막썰)."""
    return json.loads(STYLES.read_text(encoding="utf-8"))["styles"]


def style_of(audio_kind: str | None) -> str | None:
    """뜯기 audio.composition.kind → 스타일 이름. 모르는 kind 는 None.
    kind 만으로는 대사썰을 놓친다(대사가 나레 구절에 묻힘) — 전수 판정은 channel/sseolpulda/style_classify.py:classify(피치 보정)."""
    for name, st in styles().items():
        if audio_kind in st["audio_kinds"]:
            return name
    return None
