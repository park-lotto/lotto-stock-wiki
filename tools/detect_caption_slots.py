"""고정형 원본 프레임의 하단 단색 자막 여백을 점검한다."""
import json
from pathlib import Path

from caption_slot_detection import detect_bottom_caption_slot


ROOT = Path(__file__).resolve().parents[1]
COLLECT = ROOT / "out" / "장면꾸미기_작업대" / "스타일수집"
SLUGS = [
    "s0034", "s0035", "s0090", "s0093", "s0121", "s0144", "s0145", "s0155",
    "s0195", "s0217", "s0218", "s0234", "s0241", "s0291", "s0311", "s0340",
    "s0430", "s0431", "s0446", "s0460",
]


source = json.loads((COLLECT / "final_styles.json").read_text(encoding="utf-8"))
by_slug = {row["slug"]: row for row in source}
for slug in SLUGS:
    row = by_slug[slug]
    path = COLLECT / "프레임" / f"{slug}_{row['name']}_훅.png"
    slot = detect_bottom_caption_slot(path)
    print(f"{slug}|{row['name']}|mode={slot['mode']}|ratio={slot['ratio']:.3f}|top={slot['y']}")
