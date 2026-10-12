"""qa_channel_box_fit.js 결과(JSON)를 칸별로 묶어 보여준다 — 건수만 보면 같은 칸의 중복이 부풀린다.
실행: py tools/qa_channel_box_summary.py <결과.json> [...]"""
import json, sys, collections, os
sys.stdout.reconfigure(encoding="utf-8")
for f in sys.argv[1:]:
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        print("===", os.path.basename(f), "읽기 실패:", open(f, encoding="utf-8", errors="replace").read()[-300:])
        continue
    cells = collections.OrderedDict()
    for t in d["실패목록"]:
        key = t.split(" 기본(")[0].split(" 키운뒤(")[0].split(" 원복")[0].split(" →")[0]
        tag = "[기본]" if " 기본(" in t else "[키움]" if " 키운뒤(" in t else "[원복]"
        cells.setdefault(key, []).append(t.split("→")[1].strip()[:34] + tag)
    print("===", os.path.basename(f), "| 잰칸", d["잰칸"], d["기준집계"], "| 실패", d["실패"], "건 /", len(cells), "칸 | 페이지오류", d["페이지오류"][:2])
    for k, v in cells.items():
        print("  ", k, "|", " / ".join(v)[:170])
