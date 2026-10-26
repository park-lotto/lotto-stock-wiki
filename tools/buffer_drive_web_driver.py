# -*- coding: utf-8 -*-
"""웹 구글 드라이브 손조작 도우미 — 이동 창은 일반 셀렉터로 안 잡힌다(2026-10-26 실측) → 화면 좌표로 누른다.
한 창을 띄워 두고 <작업폴더>/cmd.txt 를 한 줄씩 읽는다. 단계마다 shot 으로 찍어 눈으로 확인하고 다음 줄을 쓴다.
    py tools/buffer_drive_web_driver.py <작업폴더>
    명령: goto <폴더id> | rclick <파일 data-id> | menu 정리 | menu 이동 | click x y | shot 이름 | ids | quit
이동 순서(1400x900 창): goto 계정폴더 → rclick 파일 → menu 정리 → menu 이동 → click 560 272(현재 위치 = 그 계정폴더 안으로)
  → shot 으로 '내 드라이브 > 버퍼예약 > <계정폴더>' 경로·목록 확인 → 예약/완료 줄 click → shot 확인 → click 946 666(이동)
  → goto 대상폴더 → ids 에 그 파일 id 가 있는지로 확인.
★'추천' 탭엔 다른 계정의 예약/완료가 섞여 있다 — 거기서 고르지 마라. 폴더 id 는 buffer_drive_web_tree.py 결과에 있다.
"""
# 명령 파일을 읽어 한 창에서 단계별로 조작: goto <fid> | rclick <data-id> | menu <글자> | click x y | shot 이름 | ids <fid> | quit
import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
from tools.google_browser import google_page
D = sys.argv[1]   # 작업 폴더: cmd.txt 에 명령을 한 줄씩 덧붙이면 실행, cmd.log 에 결과
CMD, LOG = D + r"\cmd.txt", D + r"\cmd.log"
open(CMD, "w").close()
def log(s):
    with open(LOG, "a", encoding="utf-8") as f: f.write(s + "\n")
with google_page() as pg:
    pg.set_viewport_size({"width": 1400, "height": 900})
    log("ready")
    done = 0
    while True:
        lines = open(CMD, encoding="utf-8").read().splitlines()
        if len(lines) <= done: time.sleep(0.5); continue
        c = lines[done].split(" "); done += 1
        try:
            if c[0] == "quit": log("bye"); break
            if c[0] == "goto": pg.goto(f"https://drive.google.com/drive/folders/{c[1]}?authuser=parklotto12@gmail.com", wait_until="domcontentloaded"); time.sleep(6)
            if c[0] == "rclick": pg.locator(f'[data-id="{c[1]}"]').first.click(button="right"); time.sleep(1.5)
            if c[0] == "menu": pg.locator('[role=menuitem]:visible', has_text=" ".join(c[1:])).last.hover(); time.sleep(0.5); pg.locator('[role=menuitem]:visible', has_text=" ".join(c[1:])).last.click() if c[1] != "정리" else None; time.sleep(2.5)
            if c[0] == "click": pg.mouse.click(int(c[1]), int(c[2])); time.sleep(2.5)
            if c[0] == "shot": pg.screenshot(path=D + rf"\{c[1]}.png")
            if c[0] == "ids": log("ids " + " ".join(pg.evaluate("() => [...new Set([...document.querySelectorAll('[data-id]')].map(e=>e.getAttribute('data-id')))]")))
            log("ok " + " ".join(c))
        except Exception as e:
            log("ERR " + " ".join(c) + " " + str(e)[:200])
