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
TEXTS = {
    "s0034": ["흑백요리사 박은영셰프가", "추천하는 공필러??"], "s0035": ["계약은 끝났지만", "우리의 찐사랑"],
    "s0090": ["몰라서 못 샀던", "주방꿀템 3가지"], "s0093": ["꿀쌀들과 쉬쉬하며 사용한", "1만원 대 명품관 향"],
    "s0121": ["촬영 전 연예인들이 챙겨 먹는", "생활약속 기분전환 알파플러스"], "s0144": ["한번 까기 시작하면 끝장", "승은이가 추천하는 간식"],
    "s0145": ["BTS 뷔가 요즘 맨날", "들고 다닌다는", "스마일 가방 정체"], "s0155": ["다이소 5천원 크림 세 개 중에", "이거 골라야 함"],
    "s0195": ["10년 만의 동창회에서", "친구들이 놀란 이유"], "s0217": ["10살 어려보이는", "복숭아빛 메이크업"],
    "s0218": ["모델인 아일릿 원희도", "몰랐던 화장품의 반전"], "s0234": ["나이키가 만든", "미친 슬리퍼"],
    "s0241": ["물로만 끝? 일본", "360만개 팔린 청소템"], "s0291": ["신민아 루이비통", "대신 든 가을가방"],
    "s0311": ["BTS 제이홉 애착템", "없으면 안되는 립밤", ""], "s0340": ["티파니 윤아도 탐낸", "안보현의 다이어트 꿀템"],
    "s0430": ["이지혜 극찬 500만원 테이블", "'반값'에 구매하는 방법"], "s0431": ["집안 옷장 냄새 박멸", "봉태규의 비밀 아이템"],
    "s0446": ["강민경도 반했다는", "제니 가방 대체 얼마길래?"], "s0460": ["케이크 다 못 먹잖아요", "이렇게 하면 되네요"],
}
FONT_BY_SLUG = {"s0093": "GmarketSansBold", "s0121": "GmarketSansBold", "s0195": "GmarketSansBold", "s0218": "GmarketSansBold", "s0340": "GmarketSansBold", "s0431": "GmarketSansBold", "s0234": "BMDOHYEON"}
ITALIC_SLUGS = {"s0093", "s0431"}


def compact(slug, frame):
    width, height = map(int, frame["size"].split("x"))
    lines = []
    for index, source in enumerate(frame.get("lines", [])):
        line = dict(source)
        line["bind"] = "hook1" if index == 0 else "hook2" if index == 1 else "bodyTitle"
        line["font_family"] = FONT_BY_SLUG.get(slug, "TmonMonsori")
        line["font_weight"] = 400
        multiline = slug == "s0155" and index == 0
        line["font_size"] = max(15, round(line["h"] * (.48 if multiline else .94), 1))
        if multiline:
            line["max_lines"] = 2
        if slug in ITALIC_SLUGS:
            line["font_style"] = "italic"
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
        frame = compact(slug, row["hook"])
        image = f"장면꾸미기_작업대/스타일수집/프레임/{slug}_{row['name']}_훅.png"
        colors = [line.get("color", "#FFFFFF") for line in frame["lines"]]
        rows.append({
            "id": f"fixed_{slug}", "source_id": slug, "name": row["name"], "views": 0,
            "mode": "continuous", "frame_image": image, "thumbnail_image": image,
            "sample": {"channel": "숏템메이커", "hook1": TEXTS[slug][0], "hook2": TEXTS[slug][1],
                       "bodyTitle": TEXTS[slug][2] if len(TEXTS[slug]) > 2 else "", "caption": ""},
            "frame": frame,
            "thumb": {"bg": frame.get("title_bg") or "#111111", "c1": colors[0] if colors else "#FFFFFF",
                      "c2": colors[1] if len(colors) > 1 else colors[0] if colors else "#FFE500"},
        })
    assert len(rows) == 20 and len({row["id"] for row in rows}) == 20
    OUT.write_text("window.CONTINUOUS20=" + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"{OUT} ({len(rows)} presets)")


if __name__ == "__main__":
    main()
