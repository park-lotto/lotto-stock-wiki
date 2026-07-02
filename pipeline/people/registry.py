"""registry.py — 사람 레지스트리 로더 (people.json)."""
import json
from pathlib import Path

_REGISTRY_PATH = Path(__file__).parent / "people.json"


def load_registry() -> dict:
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))


def get_person(name: str) -> dict:
    reg = load_registry()
    if name not in reg:
        raise KeyError(f"사람 레지스트리에 없음: {name}")
    return reg[name]


def source_names(name: str) -> list[str]:
    return list(get_person(name).get("sources", []))
