"""대본 md → 읽기 좋은 HTML(베이지 톤, 나레이션 인용 블록 강조). 바탕화면에도 복사."""
import os, markdown

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "데일리_1편_대본_페이블.md")
OUT = os.path.join(HERE, "데일리_1편_대본_페이블.html")
DESK = r"C:\Users\TheRose\Desktop\숏클_1편_대본_페이블.html"

CSS = """body{background:#EFE9DF;color:#1C1B19;font-family:Pretendard,'Malgun Gothic',sans-serif;line-height:1.7;word-break:keep-all;margin:0}
.w{max-width:900px;margin:0 auto;padding:40px 20px 100px}
h1{font-family:'Gowun Batang',Batang,serif;font-size:34px}
h2{font-family:'Gowun Batang',Batang,serif;font-size:24px;margin-top:44px;border-top:1px solid #DDD4C7;padding-top:20px}
blockquote{margin:12px 0;padding:14px 20px;background:#F8F4ED;border-left:5px solid #E07A2B;border-radius:8px;font-size:19px}
blockquote p{margin:4px 0}
table{border-collapse:collapse;width:100%;background:#F8F4ED}
td,th{border:1px solid #DDD4C7;padding:8px;font-size:14px;text-align:left}
p,li{font-size:15px;color:#3a3833}"""

body = markdown.markdown(open(SRC, encoding="utf-8").read(), extensions=["tables"])
html = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>숏클 1편 대본</title>'
        f'<style>{CSS}</style></head><body><div class="w">{body}</div></body></html>')
for p in (OUT, DESK):
    open(p, "w", encoding="utf-8").write(html)
print(OUT, html.count("<blockquote>"))
