# -*- coding: utf-8 -*-
"""폰트 목록 정본(fonts.json) → 화면 파일들에 반영한다.

★왜 이 도구가 있나 (0순위-B — 같은 판단을 두 번 적지 않는다)
   종전엔 폰트 목록이 **세 벌**로 흩어져 있었다:
     ① produce.html      @font-face 22줄
     ② produce.html      HC_FONTS 배열 22줄
     ③ produce_intro.html @font-face 22줄  ← 체험판 화면. HC_FONTS는 없다
   폰트 하나를 넣으려면 세 곳을 손으로 맞춰야 했고, 한 곳만 빠지면
   **미리보기나 최종 렌더 중 한쪽에서 조용히 안 나온다**(오류도 안 난다).

   이제 정본은 `shopping_shorts/static/fonts.json` 하나뿐이고,
   이 도구가 ①②③을 거기서 다시 써 넣는다.

★왜 런타임 JS 주입이 아니라 빌드 스크립트인가 (사장님 선택 2026-08-25)
   @font-face를 브라우저에서 만들어 넣으면 폰트 로드가 한 박자 늦어
   첫 화면에서 글꼴이 잠깐 기본체로 보인다(FOUT). 고객이 보는 화면이라
   그 위험을 안 지기로 했다. CSS는 지금처럼 정적으로 박혀 있고,
   대신 **사람이 손으로 맞추던 일을 도구가 한다**.

쓰는 법
   1) shopping_shorts/static/fonts/ 에 폰트 파일을 넣는다
   2) shopping_shorts/static/fonts.json 에 한 줄 추가한다
   3) py tools/sync_fonts.py          ← 반영
      py tools/sync_fonts.py --check  ← 반영됐는지 검사만(고치지 않음, CI/테스트용)

서버·렌더는 손댈 필요가 없다(실측 2026-08-25):
   - `/fonts/*.ttf` URL   : static/ 전체가 루트 마운트라 파일만 넣으면 열린다
   - `video_assemble.py`  : 파일명을 받아 _FONT_DIR에서 찾는다(목록 없음)
   - `deco_frame.py`      : override로 파일명을 받는다(목록 없음)
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 이 파일은 한글 메시지를 찍는다. 윈도우 기본 콘솔·서브프로세스 파이프는 cp949라
# '—' 같은 글자에서 UnicodeEncodeError로 죽는다(2026-08-26 테스트가 잡음).
# 출력만 UTF-8로 바꿔 준다 — 실패를 조용히 삼키지 않으려면 여기서 확실히 해둔다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE = Path(__file__).resolve().parent.parent
STATIC = BASE / "shopping_shorts" / "static"
FONTS_JSON = STATIC / "fonts.json"
FONT_DIR = STATIC / "fonts"

# 이 표식 사이를 도구가 갈아끼운다. 표식 자체는 손으로 지우지 마라.
CSS_BEGIN = "/* @@FONTS:BEGIN — tools/sync_fonts.py가 생성. 직접 고치지 마라 */"
CSS_END = "/* @@FONTS:END */"
JS_BEGIN = "// @@FONTS:BEGIN — tools/sync_fonts.py가 생성. 직접 고치지 마라"
JS_END = "// @@FONTS:END"


def load_fonts():
    fonts = json.loads(FONTS_JSON.read_text(encoding="utf-8"))
    seen_file, seen_css = set(), set()
    for f in fonts:
        for k in ("name", "file", "css"):
            if not f.get(k):
                raise SystemExit(f"[오류] '{k}' 가 빈 항목이 있다: {f}")
        # css는 CSS 식별자로 쓰인다 — 따옴표·공백이 섞이면 스타일이 통째로 깨진다
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", f["css"]):
            raise SystemExit(f"[오류] css 이름이 CSS 식별자가 아니다: {f['css']}")
        if f["file"] in seen_file:
            raise SystemExit(f"[오류] file 중복: {f['file']}")
        if f["css"] in seen_css:
            raise SystemExit(f"[오류] css 중복: {f['css']} — 다른 폰트를 덮어쓴다")
        seen_file.add(f["file"])
        seen_css.add(f["css"])
        if not (FONT_DIR / f["file"]).exists():
            raise SystemExit(
                f"[오류] 폰트 파일이 없다: static/fonts/{f['file']}\n"
                f"       파일을 넣고 다시 실행해라. 목록에만 있으면 화면에서 기본체로 나온다.")
    return fonts


def render_css(fonts):
    lines = [CSS_BEGIN]
    for f in fonts:
        lines.append(
            f"    @font-face{{font-family:'{f['css']}';src:url('/fonts/{f['file']}')}}")
    lines.append("    " + CSS_END)
    return "\n".join(lines)


def render_js(fonts):
    """HC_FONTS 배열. ⭐는 name에 붙여 종전 표기를 그대로 유지한다(화면 문구 불변)."""
    w_name = max(len(_disp(f)) for f in fonts) + 2
    w_file = max(len(f["file"]) for f in fonts) + 3
    lines = [JS_BEGIN, "const HC_FONTS=["]
    for f in fonts:
        nm = f"'{_disp(f)}',".ljust(w_name + 2)
        fl = f"file:'{f['file']}',".ljust(w_file + 6)
        lines.append(f"  {{name:{nm}{fl}css:'{f['css']}'}},")
    lines.append("];")
    lines.append(JS_END)
    return "\n".join(lines)


def _disp(f):
    return ("⭐ " + f["name"]) if f.get("star") else f["name"]


def _swap(text, begin, end, new, path, what):
    i = text.find(begin)
    j = text.find(end)
    if i < 0 or j < 0:
        raise SystemExit(
            f"[오류] {path.name} 에서 {what} 표식을 못 찾았다.\n"
            f"       표식이 지워졌다면 되살려야 한다 — 이 도구가 갈아끼울 자리다.")
    return text[:i] + new + text[j + len(end):]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="고치지 않고 최신인지 검사만(다르면 종료코드 1)")
    args = ap.parse_args()

    fonts = load_fonts()
    css, js = render_css(fonts), render_js(fonts)

    targets = [
        (STATIC / "produce.html", [(CSS_BEGIN, CSS_END, css, "@font-face"),
                                   (JS_BEGIN, JS_END, js, "HC_FONTS")]),
        (STATIC / "produce_intro.html", [(CSS_BEGIN, CSS_END, css, "@font-face")]),
    ]

    stale = []
    for path, jobs in targets:
        text = original = path.read_text(encoding="utf-8")
        for begin, end, new, what in jobs:
            text = _swap(text, begin, end, new, path, what)
        if text != original:
            if args.check:
                stale.append(path.name)
            else:
                path.write_text(text, encoding="utf-8")
                print(f"  갱신: {path.name}")
        elif not args.check:
            print(f"  변화없음: {path.name}")

    if args.check:
        if stale:
            print("[낡음] fonts.json 과 어긋난 파일: " + ", ".join(stale))
            print("       py tools/sync_fonts.py 를 실행해라.")
            return 1
        print(f"[최신] 폰트 {len(fonts)}종 — 모든 화면이 fonts.json 과 일치")
        return 0

    print(f"완료 — 폰트 {len(fonts)}종 반영")
    return 0


if __name__ == "__main__":
    sys.exit(main())
