"""전장면 고정형 20종의 제목/하단 출처 영역을 한 장에서 검수한다."""
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "out" / "continuous20-data.js"
OUT = ROOT / "out" / "continuous20-cleanup-audit.png"
RENDERED_OUT = ROOT / "out" / "continuous20-cleanup-rendered.png"
STORY_RENDERED_OUT = ROOT / "out" / "story20-cleanup-rendered.png"


def load_rows():
    raw = DATA.read_text(encoding="utf-8").strip()
    return json.loads(raw.removeprefix("window.CONTINUOUS20=").removesuffix(";"))


def main():
    rows = load_rows()
    cell_w, cell_h, cols = 360, 360, 4
    sheet = Image.new("RGB", (cell_w * cols, cell_h * 5), "#071620")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, row in enumerate(rows):
        image = Image.open(ROOT / "out" / row["frame_image"]).convert("RGB")
        width, height = image.size
        top = image.crop((0, 0, width, round(height * .38))).resize((240, 162))
        bottom = image.crop((0, round(height * .65), width, height)).resize((240, 149))
        col, line = index % cols, index // cols
        x, y = col * cell_w, line * cell_h
        sheet.paste(top, (x + 8, y + 30))
        sheet.paste(bottom, (x + 8, y + 200))
        slot = row["frame"]["caption_slot"]
        title = f'{index:02d} {row["source_id"]} {row["name"]} / {slot["mode"]}'
        draw.text((x + 8, y + 8), title, fill="white", font=font)
        draw.rectangle((x + 7, y + 29, x + 248, y + 192), outline="#3FE0BB", width=2)
        draw.rectangle((x + 7, y + 199, x + 248, y + 349), outline="#FFB84D", width=2)
    sheet.save(OUT)
    rendered = Image.new("RGB", (320 * 5, 600 * 4), "#071620")
    rendered_draw = ImageDraw.Draw(rendered)
    temp = Path(os.environ.get("TEMP", "."))
    for index, row in enumerate(rows):
        path = temp / f'cleanup-{index:02d}-{row["source_id"]}.png'
        if not path.exists():
            continue
        image = Image.open(path).convert("RGB")
        image.thumbnail((300, 540))
        col, line = index % 5, index // 5
        x, y = col * 320, line * 600
        rendered.paste(image, (x + (300 - image.width) // 2, y + 28))
        rendered_draw.text((x + 8, y + 8), f'{index:02d} {row["source_id"]} {row["name"]}', fill="white", font=font)
    rendered.save(RENDERED_OUT)
    story_raw = (ROOT / "out" / "precision20-data.js").read_text(encoding="utf-8").strip()
    story_rows = json.loads(story_raw.removeprefix("window.PRECISION20=").removesuffix(";"))
    story = Image.new("RGB", (320 * 5, 600 * 4), "#071620")
    story_draw = ImageDraw.Draw(story)
    for index, row in enumerate(story_rows):
        path = temp / f'cleanup-story-{index:02d}-{row["id"]}.png'
        if not path.exists():
            continue
        image = Image.open(path).convert("RGB")
        image.thumbnail((300, 540))
        col, line = index % 5, index // 5
        x, y = col * 320, line * 600
        story.paste(image, (x + (300 - image.width) // 2, y + 28))
        story_draw.text((x + 8, y + 8), f'{index:02d} {row["id"]} {row["name"]}', fill="white", font=font)
    story.save(STORY_RENDERED_OUT)
    print(OUT)
    print(RENDERED_OUT)
    print(STORY_RENDERED_OUT)


if __name__ == "__main__":
    main()
