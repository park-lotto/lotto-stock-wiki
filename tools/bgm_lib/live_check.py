# -*- coding: utf-8 -*-
"""배경음 목록 라이브 실측(관제 146) — 관리자 세션(tools/live_admin)으로 사장님 계정의 **완성본이 없는 옛 작업** 하나에서:
  ① 3단계 화면(scene_lab)에 배경음 탭·24곡·음량/속도 슬라이더가 보이는가(화면 캡처)
  ② 화면에서 곡 고르기·음량 → 완성본 미리보기 렌더(/api/produce/mix/preview) → 소리 ↔ 곡 파형 상관(대조군: 다른 곡)
  ③ 속도 1.25 → 다시 렌더 → 음량 윤곽이 1.25배 곡과 더 닮았나(1배속보다)
  ④ 캡컷 초안: 배경음 소재·볼륨·배속
  ⑤ 끝나면 원래 배경음 설정으로 되돌린다(완성본이 없는 작업만 쓴다 — 고객·사장님 완성본을 무효로 만들지 않게)

  py tools/bgm_lib/live_check.py <job_id> [곡id=beggin] [대조곡=blue]
"""
import json, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np
from tools.live_admin import admin_page
from check_render_capcut import _pcm, _corr, _env_corr, _ff
from shopping_shorts import bgm_lib

job = sys.argv[1]
tid = sys.argv[2] if len(sys.argv) > 2 else "beggin"
ctrl = sys.argv[3] if len(sys.argv) > 3 else "blue"
tmp = Path(tempfile.mkdtemp(prefix="bgmlive_"))
ok = True


def check(c, msg):
    global ok
    print(("  ✅ " if c else "  ❌ ") + msg, flush=True); ok &= bool(c)


with admin_page("scene_lab.html?job=" + job, viewport=(1400, 1000)) as pg:
    api = lambda p: pg.evaluate("p => fetch(p, {cache:'no-store'}).then(r => r.json())", p)
    post = lambda p, b: pg.evaluate("([p, b]) => fetch(p, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(b)}).then(r => r.status)", [p, b])
    st0 = api("/api/produce/mix/bgm_lib/" + job)
    orig = st0.get("bgm") or {}
    gone = pg.evaluate("p => fetch(p).then(r => r.status)", "/api/mix/video/" + job)
    check(gone != 200, f"완성본 없는 작업(HTTP {gone}) — 바꿔도 잃을 완성본이 없다")
    if gone == 200:
        sys.exit(1)
    try:
        pg.wait_for_timeout(6000)
        # ① 화면
        pg.click('#sfxPanel .sfxtab[data-t="bgm"]'); pg.wait_for_timeout(500)
        n = pg.locator("#bgmList .bgmitem").count()
        check(n == len(bgm_lib.list_tracks()) + 1, f"라이브 3단계 배경음 탭 목록 {n}줄(곡 {len(bgm_lib.list_tracks())} + 없음)")
        check(pg.is_visible("#bgmVol") and pg.is_visible("#bgmSpeed"), "음량·속도 슬라이더가 보인다")
        # ② 화면에서 곡 고르기·음량 30
        pg.locator(f'#bgmList .bgmitem[data-id="{tid}"] .pick').click(); pg.wait_for_timeout(1500)
        pg.evaluate("v => { const e = document.querySelector('#bgmVol'); e.value = v; e.dispatchEvent(new Event('change')); }", "30")
        pg.wait_for_timeout(1500)
        b = api("/api/produce/mix/bgm_lib/" + job)["bgm"]
        check(b.get("lib") == tid and b.get("volume") == 30, f"화면에서 고르기·음량 → 라이브 저장 {b}")
        pg.screenshot(path=str(tmp / "live_bgm.png"))

        def render(tag):
            st = post("/api/produce/mix/preview", {"job_id": job})
            t0 = time.time()
            while time.time() - t0 < 600:
                time.sleep(10)
                r = pg.request.get("https://shoppingshorts.duckdns.org/api/produce/mix/preview/" + job)
                if r.status == 200:
                    p = tmp / f"{tag}.mp4"; p.write_bytes(r.body())
                    print(f"    렌더 {tag}: 시작 HTTP {st} · {int(time.time() - t0)}초 · {p.stat().st_size // 1024}KB", flush=True)
                    return p
            return None

        out1 = render("x1")
        check(out1 is not None, "완성본 미리보기 렌더(1배속)")
        if out1:
            dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out1)]).decode())
            w = _pcm(out1, 0, min(dur, 20))
            c_t = _corr(w, _pcm(bgm_lib.path_of(tid), 0, min(dur, 20)))
            c_c = _corr(w, _pcm(bgm_lib.path_of(ctrl), 0, min(dur, 20)))
            check(c_t > 3 * c_c and c_t > 0.1, f"완성본 소리 ↔ 고른 곡 상관 {c_t:.3f} / 대조곡({ctrl}) {c_c:.3f} (나레이션 섞인 상태)")
        # ③ 속도 1.25
        pg.evaluate("v => { const e = document.querySelector('#bgmSpeed'); e.value = v; e.dispatchEvent(new Event('change')); }", "1.25")
        pg.wait_for_timeout(1500)
        b = api("/api/produce/mix/bgm_lib/" + job)["bgm"]
        check(b.get("speed") == 1.25, f"화면에서 속도 1.25 → 라이브 저장 {b}")
        out2 = render("x125")
        check(out2 is not None, "완성본 미리보기 렌더(1.25배속)")
        if out1 and out2:
            ref = tmp / "ref125.wav"; _ff("-i", bgm_lib.path_of(tid), "-af", "atempo=1.25", "-t", "25", str(ref))
            w2 = _pcm(out2, 0, min(dur, 20))
            e_ref, e_1x = _env_corr(w2, _pcm(ref, 0, min(dur, 20))), _env_corr(w2, _pcm(bgm_lib.path_of(tid), 0, min(dur, 20)))
            d = float(np.abs(w2[:len(w)] - w[:len(w2)]).mean())
            check(e_ref > e_1x and d > 1e-4, f"1.25배 완성본 음량윤곽 ↔ 1.25배 곡 {e_ref:.3f} > 1배 곡 {e_1x:.3f} · 1배 완성본과 소리 차 {d:.4f}")
        # ④ 캡컷 초안
        cc = pg.evaluate("p => fetch(p).then(r => r.json())", "/api/mix/capcut/" + job + "?base=C:/capcutproject/CapCut%20Drafts")
        if cc.get("texts"):
            dr = json.loads(cc["texts"]["draft_content.json"])
            au = [m for m in dr["materials"]["audios"] if m["path"].endswith("bgm.mp3")]
            seg = next((s for t in dr["tracks"] if t["type"] == "audio" for s in t["segments"] if au and s["material_id"] == au[0]["id"]), None)
            check(bool(au and seg and abs(seg["speed"] - 1.25) < 1e-6 and abs(seg["volume"] - 0.30) < 1e-6),
                  f"라이브 캡컷 초안 배경음 칸 — 배속 {seg and seg['speed']} · 볼륨 {seg and seg['volume']}")
        elif "자막 없는 완성본" in str(cc.get("error")):
            print("    ⏭ 캡컷 건너뜀 — 이 작업엔 자막제거 완성본(유료)이 없다. 캡컷 경로는 check_render_capcut.py(실제 라우트)로 본다")
        else:
            check(False, f"라이브 캡컷 응답 {str(cc)[:120]}")
    finally:
        # ⑤ 원래대로
        post("/api/produce/mix/settings", {"job_id": job, "bgm_lib": str(orig.get("lib") or ""),
                                          "bgm_volume": int(orig.get("volume", 15) or 0), "bgm_speed": float(orig.get("speed", 1.0) or 1.0)})
        back = api("/api/produce/mix/bgm_lib/" + job)["bgm"]
        print(f"    되돌림: 원래 {orig} → 지금 {back}")
print("캡처:", tmp / "live_bgm.png")
print("결과:", "통과" if ok else "실패")
sys.exit(0 if ok else 1)
