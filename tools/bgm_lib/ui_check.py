# -*- coding: utf-8 -*-
"""3단계 🎵 배경음 탭(관제 146) 실브라우저 점검 — 격리 DB·작은 실제 job·로그인 게이트만 끈 실제 앱.

  py tools/bgm_lib/ui_check.py [out.png]

누르는 것: 배경음 탭 → 목록 수 → ▶ 미리듣기(파일 응답 200) → 곡 고르기(DB deco.bgm.lib) → 음량 슬라이더 25 · 속도 슬라이더 1.25(미리듣기 배속)
           → 새로고침해도 선택 유지 → 롱폼 막힘(409) → '배경음 없음'(lib 지워짐) · 효과음 스위치 꺼진 회원은 배경음 탭만.
"""
import json, subprocess, sys, tempfile, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from shopping_shorts.store import Store
from shopping_shorts import app as A, bgm_lib

out = sys.argv[1] if len(sys.argv) > 1 else str(Path(tempfile.gettempdir()) / "bgm_ui.png")
tmp = Path(tempfile.mkdtemp(prefix="bgmui_")); db = tmp / "t.db"; root = tmp / "mix_jobs"; work = root / "jui"
(work / "s0").mkdir(parents=True)


def _ff(*a):
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", *a], check=True, capture_output=True)


_ff("-f", "lavfi", "-i", "testsrc=s=360x640:r=30:d=6", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(work / "s0" / "src.mp4"))
t0 = work / "tts" / "beat_0.mp3"; t0.parent.mkdir()
_ff("-f", "lavfi", "-i", "sine=frequency=300:duration=2", str(t0))
t1 = work / "tts" / "beat_1.mp3"; _ff("-f", "lavfi", "-i", "sine=frequency=300:duration=1.5", str(t1))
final = work / "final.mp4"; _ff("-f", "lavfi", "-i", "testsrc=s=360x640:r=30:d=3.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(final))
st = Store(db)
st.create_mix_job("jui", ["https://www.instagram.com/reel/AAA111/"], 20, "free")
st.update_mix_job("jui", status="done", video_path=str(final), deco={"bgm": {"volume": 15}}, extract={
    "s0": {"video_id": "s0", "segments": [{"seg_id": f"s0-{i}", "start": float(i) * 2, "end": float(i) * 2 + 2.0,
                                            "text": "", "scene_desc": f"장면{i}"} for i in range(3)]}}, edit_plan={
    "structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "첫 장면이에요", "tts_path": str(t0), "caption_lines": ["첫 장면이에요"],
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0}},
        {"beat_idx": 1, "role": "본문", "narration": "둘째 장면", "tts_path": str(t1), "caption_lines": ["둘째 장면"],
         "primary": {"video_id": "s0", "seg_id": "s0-1", "start": 2.0, "end": 3.5}}]})
A.DB_PATH = str(db); A._MIX_WORK_DIR = root; A._AUTH_ON = False
import uvicorn
PORT = 8798
threading.Thread(target=lambda: uvicorn.run(A.app, host="127.0.0.1", port=PORT, log_level="warning"), daemon=True).start()
time.sleep(4)

ok = True


def check(cond, msg):
    global ok
    print(("  ✅ " if cond else "  ❌ ") + msg); ok &= bool(cond)


def bgm():
    return (Store(db).get_mix_job("jui")["deco"] or {}).get("bgm") or {}


from playwright.sync_api import sync_playwright
n_tracks = len(bgm_lib.list_tracks())
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1100})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    sounds = []; pg.on("response", lambda r: sounds.append(r.status) if "/api/produce/bgm_lib/sound/" in r.url else None)
    url = f"http://127.0.0.1:{PORT}/scene_lab.html?job=jui"
    pg.goto(url, wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
    check(pg.is_visible("#sfxPanel"), "효과음 스위치 꺼진 작업에도 패널이 보인다")
    check(not pg.is_visible('#sfxPanel .sfxtab[data-t="sfx"]'), "효과음 탭은 숨고 배경음 탭만")
    check(pg.is_visible("#sfxBodyBgm"), "배경음 본문이 열려 있다")
    rows = pg.locator("#bgmList .bgmitem").count()
    check(rows == n_tracks + 1, f"목록 {rows}줄 = 곡 {n_tracks} + 없음 1")
    check(pg.locator("#bgmList .bgmitem.on").inner_text().startswith("배경음 없음"), "처음엔 '배경음 없음' 선택")
    pg.locator('#bgmList .bgmitem[data-id="blue"] button').first.click(); pg.wait_for_timeout(1500)
    check(200 in sounds or 206 in sounds, f"▶ 미리듣기 파일 응답 {sounds[:2]}")
    pg.locator('#bgmList .bgmitem[data-id="blue"] .pick').click(); pg.wait_for_timeout(1500)
    check(bgm().get("lib") == "blue", f"고르기 → DB deco.bgm = {bgm()}")
    check(pg.locator('#bgmList .bgmitem.on').get_attribute("data-id") == "blue", "고른 곡이 선택 표시")
    def slide(sel, v):                      # 슬라이더를 끌어 놓은 것과 같다(input → change)
        pg.evaluate("([s, v]) => { const e = document.querySelector(s); e.value = v; e.dispatchEvent(new Event('input')); e.dispatchEvent(new Event('change')); }", [sel, v])
        pg.wait_for_timeout(1200)
    slide("#bgmVol", "25")
    check(bgm() == {"lib": "blue", "volume": 25}, f"음량 25 → {bgm()}")
    check(pg.locator("#bgmVolV").inner_text() == "25%", "음량 숫자 표시 25%")
    slide("#bgmSpeed", "1.25")
    check(bgm() == {"lib": "blue", "volume": 25, "speed": 1.25}, f"속도 1.25 → {bgm()}")
    check(pg.locator("#bgmSpeedV").inner_text() == "1.25x", "속도 숫자 표시 1.25x")
    if pg.evaluate("() => _bgmPlaying"):    # 앞에서 튼 미리듣기가 아직 재생 중이면 먼저 멈춘다(버튼이 재생/정지 토글)
        pg.locator('#bgmList .bgmitem[data-id="blue"] button').first.click(); pg.wait_for_timeout(300)
    pg.locator('#bgmList .bgmitem[data-id="blue"] button').first.click(); pg.wait_for_timeout(800)
    check(abs(pg.evaluate("() => _bgmAudio ? _bgmAudio.playbackRate : 0") - 1.25) < 1e-6, "미리듣기도 1.25배속")
    check(abs(pg.evaluate("() => _bgmAudio ? _bgmAudio.volume : -1") - 0.25) < 1e-6, "미리듣기도 음량 25%")
    pg.evaluate("() => { const e = document.querySelector('#bgmVol'); e.value = 50; e.dispatchEvent(new Event('input')); }")
    check(abs(pg.evaluate("() => _bgmAudio ? _bgmAudio.volume : -1") - 0.5) < 1e-6, "재생 중 음량 슬라이더 → 미리듣기 크기 즉시 50%")
    pg.evaluate("() => { const e = document.querySelector('#bgmVol'); e.value = 25; e.dispatchEvent(new Event('input')); }")
    pg.locator('#bgmList .bgmitem[data-id="blue"] button').first.click()
    pg.screenshot(path=out, full_page=False)
    pg.goto(url, wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
    check(pg.locator('#bgmList .bgmitem.on').get_attribute("data-id") == "blue", "새로고침 뒤에도 선택 유지")
    check(pg.locator("#bgmVol").input_value() == "25" and pg.locator("#bgmSpeed").input_value() == "1.25",
          "새로고침 뒤에도 음량·속도 유지")
    pg.locator("#bgmSpeedReset").click(); pg.wait_for_timeout(1200)
    check(bgm() == {"lib": "blue", "volume": 25}, f"1x 버튼 → 속도 원래대로 {bgm()}")
    # 곡을 바꾸면 옛 완성본은 무효가 된다 → '완성본 다시 만들기'가 끝난 상태로 두고 롱폼 만들기를 누른다
    Store(db).update_mix_job("jui", status="done", video_path=str(final))
    r = pg.request.post(f"http://127.0.0.1:{PORT}/api/mix/longform_link/jui", data={})
    check(r.status == 409 and "쇼츠 전용" in r.text(), f"쇼츠 전용 곡 → 롱폼 만들기 막힘(HTTP {r.status})")
    pg.locator("#bgmList .bgmitem").first.locator(".pick").click(); pg.wait_for_timeout(1500)
    check("lib" not in bgm() and bgm().get("volume") == 25, f"'배경음 없음' → {bgm()}")
    check(not errs, f"페이지 오류 {errs[:3]}")
    # 효과음 스위치 켠 관리자 작업: 두 탭 다 보인다
    Store(db).set_setting("sfx_pack_enabled", "1")
    pg.goto(url, wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
    check(pg.is_visible('#sfxPanel .sfxtab[data-t="sfx"]') and pg.is_visible('#sfxPanel .sfxtab[data-t="bgm"]'),
          "효과음 켠 작업은 두 탭 다")
    # 회원 작업(관리자 전용 기본): 배경음 탭이 없다 — 효과음만
    st2 = Store(db); st2.create_mix_job("jmem", ["u"], 20, "free", customer_id=7)
    row = Store(db).get_mix_job("jui")
    st2.update_mix_job("jmem", status="done", video_path=str(final), deco={"bgm": {"volume": 15}},
                       extract=row["extract"], edit_plan=row["edit_plan"])
    pg.goto(f"http://127.0.0.1:{PORT}/scene_lab.html?job=jmem", wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
    check(not pg.is_visible('#sfxPanel .sfxtab[data-t="bgm"]') and pg.locator("#bgmList .bgmitem").count() == 0,
          "회원 작업엔 배경음 탭·목록 없음(관리자 전용)")
    check(pg.is_visible('#sfxBodySfx'), "회원 작업은 효과음 본문이 열린다")
    b.close()
print("캡처:", out)
print("결과:", "통과" if ok else "실패")
sys.exit(0 if ok else 1)
