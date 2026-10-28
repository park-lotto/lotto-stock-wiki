"""qa_pixel_diff.js 결과(JSON)를 한 줄씩 보여준다. 실행: py tools/qa_pixel_diff_summary.py <결과.json>"""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(sys.argv[1], encoding="utf-8"))
print("비교", d["비교한칸"], "| 같음", d["같은칸"], "| 다름", d["다른칸"])
for r in d["다른칸목록"]:
    print("  ", r["파일"].ljust(36), r.get("다른픽셀"), "px", r.get("범위") or r.get("크기다름"))
