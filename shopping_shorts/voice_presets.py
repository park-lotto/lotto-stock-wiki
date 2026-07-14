"""큐레이션 보이스 프리셋(assets/voice_presets.json)을 읽어 DB로 seed한다.

파일이 소스오브트루스 — 기동 시 seed_presets로 upsert(origin=curated). 유저 생성분은
DB에만 존재(origin=generated)하며 여기서 건드리지 않는다."""
import json
from pathlib import Path

PRESETS_JSON = Path(__file__).parent / "assets" / "voice_presets.json"
SAMPLES_DIR = Path(__file__).parent / "assets" / "voice_samples"


def load_presets_file():
    """assets/voice_presets.json → list[dict]. 파일 없으면 빈 리스트."""
    if not PRESETS_JSON.exists():
        return []
    return json.loads(PRESETS_JSON.read_text(encoding="utf-8"))


def seed_presets(store):
    """큐레이션 프리셋을 DB에 upsert. 파일에서 빠진 옛 프리셋은 정리(prune). 등록 건수 반환(idempotent)."""
    rows = load_presets_file()
    for p in rows:
        store.upsert_voice_preset(p)
    store.prune_voice_presets([p["preset_id"] for p in rows])
    return len(rows)
