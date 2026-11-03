# -*- coding: utf-8 -*-
"""마크다운 → 단일 HTML (표·제목·코드·목록·굵게·코드만, 외부 의존 없음). 사장님 "html로 열어" 용.
사용: py tools/md2html_simple.py <입력.md> <출력.html> [제목]
"""
import re, sys, html, pathlib

src_p, dst_p = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
title = sys.argv[3] if len(sys.argv) > 3 else src_p.stem
src = src_p.read_text(encoding="utf-8")


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"~~(.+?)~~", r"<s>\1</s>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


out, lines, i = [], src.split("\n"), 0
while i < len(lines):
    l = lines[i]
    if l.startswith("```"):
        j = i + 1; buf = []
        while j < len(lines) and not lines[j].startswith("```"): buf.append(lines[j]); j += 1
        out.append("<pre>" + html.escape("\n".join(buf)) + "</pre>"); i = j + 1; continue
    if l.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"): rows.append(lines[i]); i += 1
        cells = [[inline(c.strip()) for c in r.strip().strip("|").split("|")] for r in rows if not re.match(r"^\|[\s\-:|]+\|$", r)]
        t = "<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cells[0]) + "</tr></thead><tbody>"
        t += "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in cells[1:]) + "</tbody></table>"
        out.append(t); continue
    m = re.match(r"^(#{1,4}) (.*)", l)
    if m: out.append(f"<h{len(m.group(1))}>{inline(m.group(2))}</h{len(m.group(1))}>"); i += 1; continue
    if l.strip() == "---": out.append("<hr>"); i += 1; continue
    if l.startswith("- ") or re.match(r"^\d+\. ", l):
        items = []
        while i < len(lines) and (lines[i].startswith("- ") or re.match(r"^\d+\. ", lines[i])):
            items.append(re.sub(r"^(- |\d+\. )", "", lines[i])); i += 1
        out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>"); continue
    if l.strip(): out.append(f"<p>{inline(l)}</p>")
    i += 1
body = "\n".join(out)
css = """body{font-family:'Malgun Gothic',Pretendard,sans-serif;max-width:1500px;margin:24px auto;padding:0 20px;line-height:1.5;color:#222;background:#fafafa}
h1{font-size:26px;border-bottom:3px solid #e6402a;padding-bottom:6px}h2{font-size:20px;margin-top:36px;border-left:6px solid #e6402a;padding-left:10px}h3{font-size:16px}
table{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0 18px}th{background:#333;color:#fff;padding:6px 8px;text-align:left;position:sticky;top:0}
td{border:1px solid #ddd;padding:5px 8px;vertical-align:top}tr:nth-child(even) td{background:#f2f2f2}
code{background:#eee;padding:1px 4px;border-radius:3px;font-size:12px}pre{background:#222;color:#eee;padding:10px;overflow-x:auto;font-size:12px}
b{color:#b3200f}s{color:#888}hr{border:0;border-top:1px solid #ccc;margin:28px 0}"""
dst_p.parent.mkdir(parents=True, exist_ok=True)
dst_p.write_text(f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>{css}</style></head><body>{body}</body></html>', encoding="utf-8")
print(dst_p, len(body), "bytes, 표", body.count("<table>"), "h2", body.count("<h2>"))
