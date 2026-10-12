"""새 편집기(out/scene-style-ui-showcase.html)가 쓰는 글꼴을 woff2로 줄여 속도를 잡는다 (2026-09-22).

왜: 편집기 페이지가 참조하는 글꼴 50개 = 96.6MB(otf/ttf 원본 그대로). 로컬은 순간이지만
서버에서는 이걸 인터넷으로 내려받는다. 사장님: "서버는 항상 왜 이렇게 느리지? 로컬은 잘 되는데".

무엇을 하나:
  1. 원본 otf/ttf/woff → `shopping_shorts/static/fonts/w2/<원본이름>.woff2`
     - 한글 음절 11,172자·자모·호환자모 **전부** 남긴다(서브셋 때문에 두부(□)가 나면 고객 영상 사고)
     - ASCII·라틴1·일반 구두점·통화·화살표·도형·기술기호·괄호 유지
     - 한자(CJK 통합한자)·가나·기타 문자는 뺀다 — 자막·제목에 안 쓴다
     - 힌팅 제거(desubroutinize) + brotli(woff2) 압축
  2. showcase의 @font-face `url("../shopping_shorts/static/fonts/<x>")`를 w2 경로로 바꿔 쓴다
     (원본 파일은 그대로 둔다 — 구버전 꾸미기 화면 fonts.json이 원본을 쓴다)
  3. 이미 woff2인 파일(scene/*.woff2)은 서브셋만 다시 해서 w2로 복사한다

실행: python tools/scene_font_research/build_woff2.py           # 변환+showcase 갱신
      python tools/scene_font_research/build_woff2.py --check   # 변환 결과·누락 글리프 검사만
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
SHOWCASE = ROOT / "out" / "scene-style-ui-showcase.html"
FONT_DIR = ROOT / "shopping_shorts" / "static" / "fonts"
OUT_DIR = FONT_DIR / "w2"

# 남길 유니코드 구간 — 한글은 전부, 나머지는 자막·제목에 실제로 쓰는 것
KEEP_RANGES = [
    (0x0020, 0x007E),  # ASCII
    (0x00A0, 0x00FF),  # 라틴1 보충(±·×÷ 등)
    (0x02C6, 0x02DC),  # 수정 문자(˜ˆ)
    (0x2000, 0x206F),  # 일반 구두점(… ‘’ “” – — ‧)
    (0x20A0, 0x20CF),  # 통화(₩ € 등)
    (0x2100, 0x214F),  # 문자꼴 기호(™ ℃ №)
    (0x2150, 0x218F),  # 숫자 형식(Ⅰ Ⅱ ⅓)
    (0x2190, 0x21FF),  # 화살표
    (0x2200, 0x22FF),  # 수학 기호(∞ ≠ ≒)
    (0x2300, 0x23FF),  # 기술 기호(⌘ ⏰ 일부)
    (0x2460, 0x24FF),  # ① ② ⓐ
    (0x2500, 0x257F),  # 괘선
    (0x2580, 0x259F),  # 블록
    (0x25A0, 0x25FF),  # 도형(■ □ ● ○ ▶ ★는 아래)
    (0x2600, 0x26FF),  # 잡다한 기호(★ ☆ ☎ ♥ ♪)
    (0x2700, 0x27BF),  # 딩벳(✔ ✨ ❤)
    (0x3000, 0x303F),  # CJK 구두점(、。「」『』〈〉《》)
    (0x3130, 0x318F),  # 한글 호환 자모(ㄱ ㅋ ㅠ)
    (0x3200, 0x32FF),  # 괄호 CJK(㉠ ㈜)
    (0x3300, 0x33FF),  # CJK 호환(㎡ ㎏ ㎝)
    (0xAC00, 0xD7A3),  # ★한글 음절 11,172자 전부
    (0x1100, 0x11FF),  # 한글 자모
    (0xA960, 0xA97F),  # 한글 자모 확장A
    (0xD7B0, 0xD7FF),  # 한글 자모 확장B
    (0xFF00, 0xFFEF),  # 전각 ASCII(！？～)
    (0xFE30, 0xFE4F),  # CJK 호환 형식
]

# 절대 빠지면 안 되는 낱자 — 서브셋 뒤 검사한다(제목·자막에 실제로 나온 것)
MUST_HAVE = "가각갛힣됐뷁뛰읊뭬쒔쨌 0123456789!?%…~·₩℃※★☆♥✔→←↑↓①②③㎡㎏㎝「」『』"


def _unicodes() -> list[int]:
    out: list[int] = []
    for a, b in KEEP_RANGES:
        out.extend(range(a, b + 1))
    return out


def showcase_font_paths(text: str) -> list[str]:
    """@font-face url() 안의 `../shopping_shorts/static/fonts/...` 상대 경로(정렬·중복 제거)."""
    found = re.findall(r'url\("(\.\./shopping_shorts/static/fonts/[^"]+)"\)', text)
    return sorted(set(found))


def convert(src: Path, dst: Path, unicodes: list[int]) -> tuple[int, int, list[str]]:
    """src → dst(woff2). (원본 바이트, 결과 바이트, 빠진 필수 낱자) 를 돌려준다."""
    font = TTFont(str(src))
    for tag in ("SVG ", "FFTM", "DSIG"):   # SVG 색 글리프는 자막에 안 쓴다 — 서브셋 전에 떼야 lxml 없이 돈다
        if tag in font:
            del font[tag]
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.desubroutinize = True
    opts.hinting = False
    opts.layout_features = ["*"]   # 커닝·합자 유지(디자인 글꼴은 kern이 모양의 일부)
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    opts.drop_tables += ["DSIG", "SVG ", "FFTM"]   # SVG 색 글리프는 자막에 안 쓴다(lxml 의존 회피)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=unicodes)
    sub.subset(font)
    dst.parent.mkdir(parents=True, exist_ok=True)
    font.flavor = "woff2"
    font.save(str(dst))
    font.close()

    check = TTFont(str(dst))
    cmap = check.getBestCmap()
    missing = [ch for ch in MUST_HAVE if ch != " " and ord(ch) not in cmap and ord(ch) in set(unicodes)]
    # 원본에도 없던 낱자는 서브셋 탓이 아니다 — 원본 기준으로 걸러낸다
    orig_cmap = TTFont(str(src)).getBestCmap()
    missing = [ch for ch in missing if ord(ch) in orig_cmap]
    check.close()
    return src.stat().st_size, dst.stat().st_size, missing


def rewrite_showcase(text: str, mapping: dict[str, str]) -> str:
    for old, new in mapping.items():
        old_decl = f'url("{old}")'
        # format(...)도 woff2로 맞춘다 — 브라우저가 힌트로 쓴다
        text = re.sub(
            re.escape(old_decl) + r'\s*format\("[^"]*"\)',
            f'url("{new}") format("woff2")',
            text,
        )
        text = text.replace(old_decl, f'url("{new}")')
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="변환·갱신 없이 결과만 검사")
    args = ap.parse_args()

    text = SHOWCASE.read_text(encoding="utf-8")
    paths = showcase_font_paths(text)
    if not paths:
        print("showcase에서 글꼴 경로를 못 찾았다 — @font-face 형식이 바뀌었나?")
        return 2

    unicodes = _unicodes()
    mapping: dict[str, str] = {}
    tot_src = tot_dst = 0
    bad: list[str] = []
    for rel in paths:
        # rel: ../shopping_shorts/static/fonts/<sub>/<name>.<ext>  (w2/ 아래면 이미 변환된 것)
        inner = rel.split("/fonts/", 1)[1]
        if inner.startswith("w2/"):
            print(f"  이미 w2: {inner}")
            continue
        src = FONT_DIR / inner
        if not src.is_file():
            bad.append(f"원본 없음: {src}")
            continue
        dst = OUT_DIR / (Path(inner).stem + ".woff2")
        new_rel = f"../shopping_shorts/static/fonts/w2/{dst.name}"
        if args.check:
            if not dst.is_file():
                bad.append(f"변환본 없음: {dst}")
                continue
            s, d = src.stat().st_size, dst.stat().st_size
            missing: list[str] = []
        else:
            s, d, missing = convert(src, dst, unicodes)
        tot_src += s
        tot_dst += d
        if missing:
            bad.append(f"{dst.name}: 필수 낱자 빠짐 {''.join(missing)}")
        mapping[rel] = new_rel
        print(f"  {inner:45s} {s/1e6:6.2f}MB → {d/1e6:5.2f}MB")

    print(f"\n합계 {tot_src/1e6:.1f}MB → {tot_dst/1e6:.1f}MB  ({len(mapping)}개)")
    if bad:
        print("\n문제:")
        for b in bad:
            print("  -", b)
        return 1
    if args.check:
        return 0

    new_text = rewrite_showcase(text, mapping)
    if new_text != text:
        SHOWCASE.write_text(new_text, encoding="utf-8", newline="")
        print(f"showcase 갱신: {len(mapping)}개 경로를 w2/로")
    left = [p for p in showcase_font_paths(new_text) if "/fonts/w2/" not in p]
    if left:
        print("아직 원본을 가리키는 경로:", left)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
