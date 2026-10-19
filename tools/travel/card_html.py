# -*- coding: utf-8 -*-
"""스타일 카드(md) → 읽기 좋은 HTML 한 장(노바작가 대본 프롬프트 화면과 같은 쓰임). 머리·표·목록·인용·굵게만 다룬다.
사용: py tools/travel/card_html.py <카드.md> <출력.html>"""
import html
import re
import sys
from pathlib import Path


def inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def convert(md):
    out, i, lines = [], 0, md.splitlines()
    while i < len(lines):
        l = lines[i]
        if l.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-|]+\|$", lines[i + 1]):
            head = [c.strip() for c in l.strip("|").split("|")]
            rows, i = [], i + 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            out.append("<div class=tw><table><tr>" + "".join("<th>%s</th>" % inline(h) for h in head) + "</tr>"
                       + "".join("<tr>" + "".join("<td>%s</td>" % inline(c) for c in r) + "</tr>" for r in rows) + "</table></div>")
            continue
        m = re.match(r"^(#{1,3}) (.*)", l)
        if m:
            n = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (n, inline(m.group(2)), n))
        elif l.startswith("> "):
            out.append("<blockquote>%s</blockquote>" % inline(l[2:]))
        elif re.match(r"^\s*([-·]|\d+\.) ", l):
            items = []
            while i < len(lines) and re.match(r"^\s*([-·]|\d+\.) ", lines[i]):
                items.append(re.sub(r"^\s*([-·]|\d+\.) ", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join("<li>%s</li>" % inline(x) for x in items) + "</ul>")
            continue
        elif l.strip():
            out.append("<p>%s</p>" % inline(l))
        i += 1
    return "\n".join(out)


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    body = convert(src.read_text(encoding="utf-8"))
    title = "여행 대본 스타일 카드"
    page = """<!doctype html><html lang=ko><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>%s</title><style>
:root{--bg:#f6f4ef;--card:#fff;--ink:#1d1b18;--sub:#6b655c;--line:#e6e1d8;--acc:#b5532d;--code:#f1ede6}
@media (prefers-color-scheme:dark){:root{--bg:#141311;--card:#1d1b19;--ink:#ece8e1;--sub:#a59e93;--line:#34302b;--acc:#e58a62;--code:#2a2723}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,'Malgun Gothic',sans-serif;line-height:1.7;font-size:15px}
.w{max-width:1100px;margin:0 auto;padding:28px 16px 60px}.c{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px 26px}
h1{font-size:24px;margin:0 0 10px}h2{font-size:18px;color:var(--acc);border-bottom:1px solid var(--line);padding-bottom:6px;margin:28px 0 10px}
blockquote{margin:6px 0;padding:8px 12px;border-left:3px solid var(--acc);background:var(--code);border-radius:6px;font-size:13.5px;color:var(--sub)}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%%;font-size:13.5px;margin:6px 0}th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:var(--code)}code{background:var(--code);padding:0 4px;border-radius:4px;font-size:12.5px}li{margin:3px 0}
</style><div class=w><div class=c>%s</div></div></html>""" % (title, body)
    dst.write_text(page, encoding="utf-8")
    print(dst)


if __name__ == "__main__":
    main()
