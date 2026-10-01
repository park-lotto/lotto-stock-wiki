# -*- coding: utf-8 -*-
"""3단계 장면 편집기를 **열기만** 했을 때 vs **재생을 눌렀을 때** 내려받는 양을 잰다(관제 061, 2026-10-01).

  py tools/scene_bench/open_bytes.py <job_id> <job_row.json>
    job_id      : shopping_shorts/data/mix_jobs/<job_id>/ 에 소스(s0..)·tts·pvproxy 가 있어야 한다(서버에서 복사)
    job_row.json: 서버 mix_jobs 행(dict) — 격리 DB에 넣는다

출력: 경로별 바이트(열기 8초 / 칸 재생 6초 / 전체 재생 8초) + 재생 끊김(waiting) 횟수.
'됐다'의 기준: 열기 구간의 /api/mix/src 바이트가 0.
"""
import sys, json, tempfile, threading, time, sqlite3, collections, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from shopping_shorts.store import Store
from shopping_shorts import app as A

job_id, row_path = sys.argv[1], sys.argv[2]
VIA = sys.argv[3] if len(sys.argv) > 3 else "scene_lab"       # scene_lab | produce(고객 경로: 3단계 안 iframe)
row = json.load(open(row_path, encoding="utf-8"))
# ★서버 절대경로(/home/ubuntu/…/shopping_shorts/data/…) → 이 저장소 경로. 안 바꾸면 음성이 404 → 화면이 TTS 재생성(유료)을 부른다.
_srv = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/"
_loc = str(ROOT / "shopping_shorts" / "data").replace("\\", "/") + "/"
row = {k: (v.replace(_srv, _loc) if isinstance(v, str) else v) for k, v in row.items()}
tmp = Path(tempfile.mkdtemp(prefix="openbytes_")); db = tmp / "t.db"
Store(str(db))                                   # 스키마
con = sqlite3.connect(str(db))
cols = [r[1] for r in con.execute("pragma table_info(mix_jobs)")]
use = [c for c in cols if c in row]
con.execute("insert into mix_jobs (%s) values (%s)" % (",".join(use), ",".join("?" * len(use))), [row[c] for c in use])
con.commit(); con.close()
A.DB_PATH = str(db); A._AUTH_ON = False
import uvicorn
PORT = 8796
threading.Thread(target=lambda: uvicorn.run(A.app, host="127.0.0.1", port=PORT, log_level="warning"), daemon=True).start()
time.sleep(4)

from playwright.sync_api import sync_playwright
def key(u):
    u = u.replace(f"http://127.0.0.1:{PORT}", "").split("?")[0]
    u = re.sub(r"/[0-9a-f]{8,}", "/<id>", u); u = re.sub(r"/\d+$", "/<n>", u)
    return u
def grp(rs):
    out = collections.Counter(); n = collections.Counter()
    for u, b in rs: out[key(u)] += b; n[key(u)] += 1
    return out, n
def show(title, rs):
    out, n = grp(rs); tot = sum(out.values())
    print(f"\n[{title}] 합계 {tot/1048576:.1f}MB · 요청 {len(rs)}개")
    for k, b in out.most_common(8):
        print(f"   {b/1048576:7.2f}MB {n[k]:4d}  {k}")
    src = sum(b for k, b in out.items() if k.startswith("/api/mix/src"))
    return tot, src

with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(viewport={"width": 1500, "height": 1000})
    rs = []
    def on_resp(r):
        try:
            if r.url.startswith(f"http://127.0.0.1:{PORT}/api/") or "/api/" in r.url:
                rs.append((r.url, len(r.body()) if r.status in (200, 206) else 0))
        except Exception:
            pass
    pg.on("response", on_resp)
    # 누가 원본을 요청했나 — CDP initiator 스택(열기 구간만)
    cdp = pg.context.new_cdp_session(pg); cdp.send("Network.enable")
    inits = []
    def on_req(ev):
        u = ev.get("request", {}).get("url", "")
        if "/api/mix/src/" in u and len(inits) < 6:
            st = (ev.get("initiator") or {}).get("stack") or {}
            frames = st.get("callFrames") or []
            inits.append((u.split("/")[-1], (ev.get("initiator") or {}).get("type"), [f"{f.get('functionName') or '?'}@{f.get('url','').split('/')[-1].split('?')[0]}:{f.get('lineNumber')}" for f in frames[:4]]))
    cdp.on("Network.requestWillBeSent", on_req)
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    if VIA == "produce":
        pg.goto(f"http://127.0.0.1:{PORT}/produce.html", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
        pg.evaluate(f"() => {{ MIX_JOB='{job_id}'; stepGo('mix'); try{{ loadMixReview(); }}catch(e){{}} }}")
        pg.wait_for_timeout(9000)
        fr = next((f for f in pg.frames if "scene_lab" in f.url), None)
        if fr is None:
            print("★ produce 안에 scene_lab iframe이 없다 — 경로 확인"); b.close(); sys.exit(1)
        W = fr
    else:
        pg.goto(f"http://127.0.0.1:{PORT}/scene_lab.html?job={job_id}", wait_until="domcontentloaded")
        pg.wait_for_timeout(8000)
        W = pg
    print(f"경로: {VIA}")
    # 필름(영상 전체 필름)이 그림을 채웠나 — 원본을 안 받아도 칸 그림은 나와야 한다
    film = W.evaluate("""() => { const cells=[...document.querySelectorAll('.frbelt .frcell, .frbelt canvas, .frbelt img')]; const filled=cells.filter(c => (c.tagName==='IMG' && c.src) || (c.tagName==='CANVAS' && c.width>0) || (c.style && c.style.backgroundImage)); return {cells: cells.length, filled: filled.length, key: (typeof ROLL!=='undefined'?ROLL.key:'?')}; }""")
    print("   필름 칸:", film)
    vids = W.evaluate("() => document.querySelectorAll('video').length")
    # 어느 재생기가 받았나 — src 꼬리·preload·readyState·networkState·버퍼
    for d in W.evaluate("""() => [...document.querySelectorAll('video')].map(v => ({id: v.id||'', cls: v.className||'', src: (v.currentSrc||v.src||'').split('/').slice(-2).join('/').slice(0,40), pre: v.preload, rs: v.readyState, ns: v.networkState, buf: v.buffered.length ? +v.buffered.end(v.buffered.length-1).toFixed(1) : 0})).filter(x => x.rs > 0 || x.buf > 0 || x.ns === 2)"""):
        print("   받은 재생기:", d)
    for d in W.evaluate("""() => [...document.querySelectorAll('video')].filter(v => v.readyState > 0 || v.buffered.length).map(v => { const chain=[]; let e=v; for(let i=0;i<5&&e;i++){ chain.push((e.tagName||'')+(e.id?'#'+e.id:'')+(e.className&&typeof e.className==='string'?'.'+e.className.split(' ').slice(0,2).join('.'):'')); e=e.parentElement; } return chain.join(' < '); })"""):
        print("   재생기 위치:", d)
    print("   localStorage:", W.evaluate("() => Object.keys(localStorage).slice(0,6)"), "· ROLL.key:", W.evaluate("() => (typeof ROLL!=='undefined'?ROLL.key:'?')+'/'+(typeof ROLLS!=='undefined'?ROLLS.key:'?')+'/'+(typeof ROLLB!=='undefined'?ROLLB.key:'?')"))
    open_tot, open_src = show("열기 8초", rs); rs.clear()
    for i in inits: print("   요청 출처:", i)
    print("   PLAY_ARMED =", W.evaluate("() => typeof PLAY_ARMED !== 'undefined' ? PLAY_ARMED : 'n/a'"), "· blobs =", W.evaluate("() => typeof _blobs !== 'undefined' ? Object.keys(_blobs) : []"))
    print(f"   <video> 요소 {vids}개")
    W.evaluate("""() => { window.__wait=0; document.querySelectorAll('video').forEach(v => v.addEventListener('waiting', () => window.__wait++)); }""")
    prog = "() => { const v=[...document.querySelectorAll('video')].find(x => !x.paused && x.currentTime>0); return {key: (typeof playKey!=='undefined'?playKey:'?'), seqI: (typeof seqI!=='undefined'?seqI:-1), t: v ? +v.currentTime.toFixed(2) : null, px: !!(typeof seq!=='undefined' && seq && seq[0] && seq[0]._px)}; }"
    W.evaluate("() => { try { playBeat(1); } catch(e) { console.log('playBeat 실패', e); } }")
    pg.wait_for_timeout(2500); p1 = W.evaluate(prog); pg.wait_for_timeout(2500); p2 = W.evaluate(prog); pg.wait_for_timeout(1000)
    beat_tot, _ = show("칸 재생 6초", rs); rs.clear()
    print(f"   재생 진행: {p1} → {p2}  ({'합본' if p1['px'] else '원본'} 경로, {'흐름' if (p1['t'] is not None and p2['t'] is not None and p2['t'] > p1['t']) else '★멈춤/끝'})")
    w1 = W.evaluate("() => window.__wait")
    W.evaluate("() => { try { stopPlay(); playAll(); } catch(e) { console.log('playAll 실패', e); } }")
    pg.wait_for_timeout(3000); a1 = W.evaluate(prog); pg.wait_for_timeout(3000); a2 = W.evaluate(prog); pg.wait_for_timeout(2000)
    all_tot, _ = show("전체 재생 8초", rs)
    print(f"   재생 진행: {a1} → {a2}  ({'합본' if a1['px'] else '원본'} 경로, {'흐름' if (a1['t'] is not None and a2['t'] is not None and (a2['t'] > a1['t'] or a2['seqI'] > a1['seqI'])) else '★멈춤/끝'})")
    w2 = W.evaluate("() => window.__wait")
    playing = W.evaluate("() => [...document.querySelectorAll('video')].filter(v => !v.paused && v.currentTime > 0).length")
    print(f"\n재생 끊김(waiting): 칸 재생 {w1}회 · 전체 재생 누적 {w2}회 · 재생 중인 video {playing}개 · 페이지 오류 {errs[:2]}")
    print(f"\n★열기 때 원본(/api/mix/src) 전송: {open_src/1048576:.1f}MB  → 기준(0MB) {'통과' if open_src == 0 else '미달'}")
    b.close()
