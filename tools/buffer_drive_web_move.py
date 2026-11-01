# -*- coding: utf-8 -*-
"""웹 드라이브(parklotto12)에서 계정 폴더 꼭대기 파일을 그 폴더의 예약\ 으로 끌어다 놓는다(2026-10-27 실측: 이동 창 좌표 조작 없이 drag_to 로 된다).
    py tools/buffer_drive_web_move.py <web_tree.json 있는 폴더> "<계정폴더>" <파일명> [파일명…]
옮긴 뒤 예약 안에 있는지·꼭대기가 비었는지 다시 열어 확인해 찍는다. 예약 폴더가 없으면 멈춘다(웹 "신규 → 새 폴더"로 먼저 만든다).
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
from tools.google_browser import google_page
SP = sys.argv[1]; acc = sys.argv[2]; names = sys.argv[3:]
T = json.load(open(SP + "/web_tree.json", encoding="utf-8"))
node = T[acc]
def rows(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('[data-id]')].map(e=>({id:e.getAttribute('data-id'),t:(e.innerText||'').replace(/\s+/g,' ').trim()})).filter(r=>r.t)""")
with google_page() as pg:
    pg.set_viewport_size({"width": 1400, "height": 900})
    pg.goto(f"https://drive.google.com/drive/folders/{node['id']}?authuser=parklotto12@gmail.com", wait_until="domcontentloaded"); time.sleep(6)
    rs = rows(pg)
    rsv = next(r["id"] for r in rs if r["t"].startswith("예약"))
    for n in names:
        fid = node["files"][n]
        src = pg.locator(f'[data-id="{fid}"]').first; dst = pg.locator(f'[data-id="{rsv}"]').first
        src.drag_to(dst); time.sleep(4)
    pg.goto(f"https://drive.google.com/drive/folders/{rsv}?authuser=parklotto12@gmail.com", wait_until="domcontentloaded"); time.sleep(6)
    ins = {r["id"] for r in rows(pg)}
    for n in names: print(acc, n, "예약 안에 있음" if node["files"][n] in ins else "★없음")
    pg.goto(f"https://drive.google.com/drive/folders/{node['id']}?authuser=parklotto12@gmail.com", wait_until="domcontentloaded"); time.sleep(6)
    top = {r["id"] for r in rows(pg)}
    for n in names: print(acc, n, "꼭대기에 ★남음" if node["files"][n] in top else "꼭대기 비움")
