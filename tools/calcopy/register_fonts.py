"""글꼴 창고(shopping_shorts/static/fonts/*.ttf·*.otf) 중 장면꾸미기 렌더러에 @font-face 가 없는 것을 등록한다.

왜: 칼카피 글꼴 판별(engine/fontmatch.rank)은 창고 전부를 후보로 보는데, 렌더러(out/scene-style-ui-showcase.html)는 54개만
등록돼 있어 1위가 미등록이면 그릴 수 없었다(ZdeZ: Spoqa·IBMPlex·Pretendard-Bold 1~3위 전부 미등록, 2026-10-16).
어떻게: 파일을 새로 만들지 않고 창고의 ttf/otf 를 그대로 가리킨다(크롬은 ttf/otf 를 읽는다. 서버 자산 길
api_scene_style_asset 은 shopping_shorts/static/fonts/ 의 .ttf/.otf 를 이미 내준다). 글꼴은 쓰일 때만 내려받는다.
글꼴 이름 = "Cc" + 파일 줄기(영숫자·-_ 만) — 기존 이름과 겹치지 않게. to_frame.family_of 는 파일 줄기로 찾으므로 이름과 무관.
html 의 <!--CALCOPY-FONTS--> … <!--/CALCOPY-FONTS--> 사이만 다시 쓴다(여러 번 돌려도 같은 결과).
렌더 길: 편집 화면·렌더 레이어·썸네일이 모두 이 html 을 연다(캡컷은 그 PNG) — 등록은 이 한 곳.
판별 후보 중 channel_presets/brainbulb/fonts 의 S-CoreDream-6Bold·7ExtraBold 는 서버 자산 길이 그 폴더를 안 내줘 등록하지 않는다.

    py tools/calcopy/register_fonts.py [--check]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "out/scene-style-ui-showcase.html"
FONTS = ROOT / "shopping_shorts/static/fonts"
START, END = "<!--CALCOPY-FONTS-->", "<!--/CALCOPY-FONTS-->"


def registered_stems(html: str) -> set:
    return {Path(u).stem.lower() for u in re.findall(r'@font-face\s*\{[^}]*?src:\s*url\("([^"]+)"', html)}


def block(html_without: str) -> tuple[str, list]:
    have = registered_stems(html_without)
    rows, names = [], []
    for p in sorted(FONTS.glob("*")):
        if p.suffix.lower() not in (".ttf", ".otf") or p.stem.lower() in have:
            continue
        fam = "Cc" + re.sub(r"[^A-Za-z0-9_-]", "", p.stem)
        fmt = "opentype" if p.suffix.lower() == ".otf" else "truetype"
        rows.append(f'@font-face{{font-family:"{fam}";src:url("../shopping_shorts/static/fonts/{p.name}") format("{fmt}");font-weight:400;font-display:swap}}')
        names.append((fam, p.name))
    return (f"{START}<style>\n" + "\n".join(rows) + f"\n</style>{END}\n"), names


def main():
    html = HTML.read_text(encoding="utf-8")
    base = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", "", html, flags=re.S)
    text, names = block(base)
    new = base.replace("</head>", text + "</head>", 1)
    assert new != base, "</head> 를 못 찾음"
    if "--check" in sys.argv:
        print("최신" if new == html else "다시 등록 필요"); sys.exit(0 if new == html else 1)
    HTML.write_text(new, encoding="utf-8", newline="")
    print(f"등록 {len(names)}개:", ", ".join(f"{f}={n}" for f, n in names))


if __name__ == "__main__":
    main()
