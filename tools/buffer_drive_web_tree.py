# -*- coding: utf-8 -*-
"""웹 구글 드라이브(parklotto12) 버퍼예약 폴더 전체 목록 → JSON {계정폴더: {id, files(꼭대기), 예약, 완료}}.
G: 동기화가 늦거나 안 내려올 때 '진짜 위치'는 이걸로 본다(2026-10-26 21 폴더 사례).
    py tools/buffer_drive_web_tree.py out.json      → buffer_link_audit.py --web out.json 로 대조
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
from tools.google_browser import google_page
OUT = sys.argv[1] if len(sys.argv) > 1 else "web_tree.json"
ROOT = "1kxCvsRRcM2Xu8iv3qqaiQC5HjnJNiUAG"
def rows(pg, fid):
    pg.goto(f"https://drive.google.com/drive/folders/{fid}?authuser=parklotto12@gmail.com", wait_until="domcontentloaded")
    time.sleep(5)
    rs = pg.evaluate("""() => [...document.querySelectorAll('[data-id]')].map(e=>({id:e.getAttribute('data-id'),t:(e.innerText||'').replace(/\s+/g,' ').trim()})).filter(r=>r.t && r.id!=='_gd' && !r.t.endsWith('추가 작업'))""")
    seen, out = set(), []
    for r in rs:
        if r["id"] in seen: continue
        seen.add(r["id"]); out.append(r)
    return out
tree = {}
with google_page() as pg:
    parents = {"0AAfkCm1B_yqrUk9PVA", ROOT}
    top = [r for r in rows(pg, ROOT) if r["id"] not in parents]
    for f in top:
        if "." in f["t"][-5:]: tree[f["t"]] = f["id"]; continue
        sub = [r for r in rows(pg, f["id"]) if r["id"] not in parents | {f["id"]}]
        node = {"id": f["id"], "files": {}}
        for s in sub:
            if s["t"] in ("예약", "완료"):
                node[s["t"]] = {r["t"]: r["id"] for r in rows(pg, s["id"]) if r["id"] not in parents | {f["id"], s["id"]}}
            else:
                node["files"][s["t"]] = s["id"]
        tree[f["t"]] = node
json.dump(tree, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(tree, ensure_ascii=False, indent=1))
