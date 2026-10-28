# -*- coding: utf-8 -*-
"""정적 화면에서 버튼에 붙인 btn 계열 클래스가 CSS 에 정의돼 있는지 검사한다(관제 140).

정의가 없으면 브라우저 기본 버튼으로 나와 고객 PC 마다 모양이 달라진다(2026-10-05 고객 캡처: 8단계 버튼이 안 보임).

    py tools/check_btn_classes.py                     # shopping_shorts/static/*.html 전부
    py tools/check_btn_classes.py produce.html        # 한 파일만

검사 대상: class 속성의 'btn' / 'btn-*' / 'primary' 클래스. CSS 는 그 파일의 <style> + 링크된 theme.css 를 본다.
미정의가 하나라도 있으면 종료코드 1.
"""
import pathlib
import re
import sys

STATIC = pathlib.Path(__file__).resolve().parent.parent / "shopping_shorts" / "static"
WANT = re.compile(r"^(btn(-[\w-]+)?|primary)$")


def css_of(html, path):
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
    for href in re.findall(r'<link[^>]+href="([^"?]+\.css)', html):
        f = path.parent / href
        if f.exists():
            css += "\n" + f.read_text(encoding="utf-8", errors="ignore")
    return css


def check(path):
    html = path.read_text(encoding="utf-8", errors="ignore")
    css = css_of(html, path)
    used = set()
    for cls in re.findall(r'class="([^"$`{]*)"', html):
        used.update(c for c in cls.split() if WANT.match(c))
    missing = []
    for c in sorted(used):
        if c == "primary":
            ok = re.search(r"\.btn\.primary(?![\w-])|\.primary(?![\w-])", css)
        else:
            ok = re.search(r"\." + re.escape(c) + r"(?![\w-])", css)
        if not ok:
            missing.append(c)
    return used, missing


def main(argv):
    files = [STATIC / a for a in argv] if argv else sorted(STATIC.glob("*.html"))
    bad = 0
    for f in files:
        used, missing = check(f)
        if not used:
            continue
        print("%s  사용 %d  미정의 %s" % (f.name, len(used), missing or 0))
        bad += len(missing)
    print("합계 미정의", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
