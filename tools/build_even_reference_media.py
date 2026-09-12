"""사용자 제공 원본에서 영상 영역만 추출. 하단 플레이어 진행선은 제외한다."""
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1] / "out"
for kind, box in {"hook": (0, 285, 425, 695), "body": (0, 229, 420, 695)}.items():
    with Image.open(root / "template_refs" / f"even-{kind}-reference.png") as source:
        source.crop(box).save(root / "assets" / "scene-style" / f"even-{kind}-media.png")
