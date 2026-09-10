"""실측 final_styles에서 훅/본문 구분 없는 전장면 고정형 20종을 만든다."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECT = ROOT / "out" / "장면꾸미기_작업대" / "스타일수집"
OUT = ROOT / "out" / "continuous20-data.js"

SLUGS = [
    "s0034", "s0035", "s0090", "s0093", "s0121", "s0144", "s0145", "s0155",
    "s0195", "s0217", "s0218", "s0234", "s0241", "s0291", "s0311", "s0340",
    "s0430", "s0431", "s0446", "s0460",
]
FONT_CYCLE = ["TmonMonsori", "GmarketSansBold", "BlackHanSans", "Pretendard"]


def compact(frame):
    width, height = map(int, frame["size"].split("x"))
    lines = []
    for index, source in enumerate(frame.get("lines", [])):
        line = dict(source)
        line["bind"] = "hook1" if index == 0 else "hook2" if index == 1 else "bodyTitle"
        line["font_family"] = FONT_CYCLE[index % len(FONT_CYCLE)]
        line["font_weight"] = 400
        line["font_size"] = max(15, round(line["h"] * .94, 1))
        line["letter_spacing"] = round(-line["font_size"] * .035, 1)
        line["stroke"] = max(0, round(line["font_size"] * .065, 1))
        line["shadow_y"] = max(1, round(line["font_size"] * .07, 1))
        line["background"] = frame.get("title_bg") or "#111111"
        line["no_patch"] = False
        lines.append(line)
    caption_y = max(round(height * .68), min(height - 42, (frame.get("video_from") or {}).get("y", 0) + 55))
    lines.append({
        "bind": "caption", "x0": 18, "x1": width - 18, "y0": caption_y, "y1": caption_y + 27, "h": 28,
        "lpct": 7.5, "rpct": 7.5, "color": "#FFFFFF", "background": "#111111",
        "font_size": 16, "font_family": "Pretendard", "font_weight": 700, "letter_spacing": -.4,
        "stroke": 0, "shadow_y": 1, "no_patch": False, "patch_top": 3, "patch_bottom": 3,
    })
    fixed_bands = []
    if frame.get("top_band"):
        fixed_bands.append({"y0": frame["top_band"]["y0"], "y1": frame["top_band"]["y1"], "color": frame["top_band"]["color"]})
    return {
        "width": width, "height": height, "top_band": frame.get("top_band"),
        "title_bg": frame.get("title_bg"), "font_family": "TmonMonsori", "font_weight": 400,
        "lines": lines, "white_box": None, "video_from": frame.get("video_from"), "fixed_bands": fixed_bands,
        "fingerprint": f"continuous-{frame.get('fingerprint', '')}",
        "channel_box": None, "channel_boxes": [], "boxes": frame.get("boxes", []),
    }


def main():
    source = json.loads((COLLECT / "final_styles.json").read_text(encoding="utf-8"))
    by_slug = {row["slug"]: row for row in source}
    rows = []
    for slug in SLUGS:
        row = by_slug[slug]
        frame = compact(row["hook"])
        image = f"장면꾸미기_작업대/스타일수집/프레임/{slug}_{row['name']}_훅.png"
        colors = [line.get("color", "#FFFFFF") for line in frame["lines"]]
        rows.append({
            "id": f"fixed_{slug}", "source_id": slug, "name": row["name"], "views": 0,
            "mode": "continuous", "frame_image": image, "thumbnail_image": image,
            "sample": {"channel": "숏템메이커", "hook1": "처음부터 끝까지", "hook2": "같은 디자인 유지",
                       "bodyTitle": "처음부터 끝까지 같은 디자인 유지", "caption": "장면마다 자막만 바뀝니다"},
            "frame": frame,
            "thumb": {"bg": frame.get("title_bg") or "#111111", "c1": colors[0] if colors else "#FFFFFF",
                      "c2": colors[1] if len(colors) > 1 else colors[0] if colors else "#FFE500"},
        })
    assert len(rows) == 20 and len({row["id"] for row in rows}) == 20
    OUT.write_text("window.CONTINUOUS20=" + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"{OUT} ({len(rows)} presets)")


if __name__ == "__main__":
    main()
