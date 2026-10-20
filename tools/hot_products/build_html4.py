"""시안 v4 HTML — work/v4_data.json + template4.html + view4.js → out/인기상품랭킹_시안_v4.html. 실행: py -I build_html4.py"""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "out", "인기상품랭킹_시안_v4.html")
t = open(os.path.join(HERE, "template4.html"), encoding="utf-8").read()
js = open(os.path.join(HERE, "view4.js"), encoding="utf-8").read()
d = open(os.path.join(HERE, "work", "v4_data.json"), encoding="utf-8").read().replace("</", "<\\/")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(t.replace("__JS__", js.replace("__DATA__", d)))
print("저장", os.path.abspath(OUT), os.path.getsize(OUT))
