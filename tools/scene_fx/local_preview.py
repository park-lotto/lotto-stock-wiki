# -*- coding: utf-8 -*-
"""장면 효과(관제 124)를 로컬에서 직접 만져 보는 체험 페이지 — 숏템메이커 장면꾸미기와 같은 편집기를 같은 방식(같은 주소의
iframe + scene-style-context 메시지)으로 띄운다. 장면 그림·AI 제품 위치는 미리 만들어 둔 것을 정적 파일로 준다.

사용: py tools/scene_fx/local_preview.py --src <바탕영상.mp4> [--port 8765]
  → 브라우저에서 열리는 페이지에서 [효과] 탭 · [다음 ›] 장면 넘기기 · 자동 배치 · [이 영상에 적용](저장값을 아래 칸에 보여 줌)
  [완성본 만들기] 를 누르면 그 저장값으로 실제 렌더(scene_style.compose)를 돌려 mp4 를 연다.
"""
import argparse, http.server, json, os, subprocess, sys, threading, webbrowser
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
import cv2  # noqa: E402

DEMO = ROOT / "tools" / "scene_fx" / "_demo"          # gitignore 대상이 아니라도 커밋하지 말 것(그림·영상)
TIMELINE = [
    {"beat_idx": 0, "role": "훅", "narration": "이거 하나면 옷 정리 끝납니다", "t0": 0.0, "dur": 2.0},
    {"beat_idx": 1, "role": "문제", "narration": "택 달다가 손 다치셨죠", "t0": 2.0, "dur": 2.0},
    {"beat_idx": 2, "role": "공개", "narration": "이게 바로 그 태그건입니다", "t0": 4.0, "dur": 2.0},
    {"beat_idx": 3, "role": "고조1", "narration": "한 번에 딱 꽂혀요", "t0": 6.0, "dur": 1.5},
    {"beat_idx": 4, "role": "CTA", "narration": "링크는 댓글에 있어요", "t0": 7.5, "dur": 2.5},
]
HC = {"text": "옷 정리\n끝판왕"}

PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>장면 효과 로컬 체험</title>
<style>body{margin:0;background:#0b1117;color:#e8eef3;font:14px 'Malgun Gothic',sans-serif}header{padding:10px 16px;display:flex;gap:12px;align-items:center}
iframe{width:100%;height:calc(100vh - 170px);border:0}textarea{width:calc(100% - 32px);margin:0 16px;height:90px;background:#111a22;color:#9fe;border:1px solid #234}
button{background:#3ddcb0;border:0;border-radius:8px;padding:8px 14px;font-weight:700;cursor:pointer}small{color:#8aa}</style></head><body>
<header><b>장면 효과 로컬 체험</b><small>장면 5개(훅·문제·제품 공개·고조·CTA) · 효과 없는 영상으로 엶 → 자동 배치</small>
<button id="render">완성본 만들기</button><span id="st"></span></header>
<iframe id="ed" src="/out/scene-style-ui-showcase.html"></iframe>
<textarea id="snap" placeholder="편집기에서 [이 영상에 적용]을 누르면 저장값이 여기 나옵니다"></textarea>
<script>
const ctx=__CTX__;let last=null;const ed=document.getElementById('ed');
addEventListener('message',e=>{if(e.origin!==location.origin)return;
  if(e.data?.type==='scene-style-ready')ed.contentWindow.postMessage({type:'scene-style-context',context:ctx,snapshot:null},location.origin);
  if(e.data?.type==='scene-style-save'){last=e.data.snapshot;document.getElementById('snap').value=JSON.stringify(last.effects||{});
    ed.contentWindow.postMessage({type:'scene-style-saved',ok:true},location.origin);}});
document.getElementById('render').onclick=async()=>{const st=document.getElementById('st');
  const snap=last||ed.contentWindow.sceneStyle.snapshot();st.textContent='렌더 중… (1~2분)';
  const r=await fetch('/render',{method:'POST',body:JSON.stringify(snap)});const d=await r.json();st.textContent=d.ok?'완성: '+d.path:'실패: '+d.error;};
</script></body></html>"""


def build(src):
    from shopping_shorts import scene_style, video_analysis
    from pipeline.atoms import key_vault
    from verify_scene_fx import make_base, frame
    DEMO.mkdir(parents=True, exist_ok=True)
    (DEMO / "beatframe").mkdir(exist_ok=True); (DEMO / "scene_focus").mkdir(exist_ok=True)
    base = DEMO / "base.mp4"
    if not base.exists():
        make_base(src, base, sec=10.0)
    ctx = scene_style.context_for(TIMELINE, HC, {"version": 1, "mode": "story", "presetId": "t11"}, "demo")
    ctx["jobId"] = "demo"; ctx["fxEnabled"] = True
    key = key_vault.pick_paced_key(key_vault.get_live_keys("ingest")) if key_vault.get_live_keys("ingest") else None
    for si, sc in enumerate(ctx["scenes"]):
        pts = []
        for k, t in enumerate((sc["start"] + .05, (sc["start"] + sc["end"]) / 2, sc["end"] - .05)):
            name = f"{si}_{k}.jpg"
            p = DEMO / "beatframe" / name
            if not p.exists():
                cv2.imencode(".jpg", frame(base, round(t * 30)))[1].tofile(str(p))   # cv2.imwrite 는 한글 경로에 조용히 실패한다(실측)
            pts.append(f"/tools/scene_fx/_demo/beatframe/{name}")
            box_file = DEMO / "scene_focus" / name   # 편집기는 beatframe→scene_focus 로 바꿔 묻는다(라이브 주소 모양 그대로)
            if k == 1 and not box_file.exists():
                box = video_analysis.product_box(p.read_bytes(), sc["caption"], key=key) if key else None
                box_file.write_text(json.dumps({"ok": True, "box": box}), encoding="utf-8")
            elif k != 1 and not box_file.exists():
                box_file.write_text(json.dumps({"ok": True, "box": None}), encoding="utf-8")
        sc["media_points"] = pts; sc["media"] = pts[1]
    return ctx, base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    ctx, base = build(a.src)
    page = PAGE.replace("__CTX__", json.dumps(ctx, ensure_ascii=False))
    (DEMO / "index.html").write_text(page, encoding="utf-8")
    from shopping_shorts import scene_style

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *x, **k):
            super().__init__(*x, directory=str(ROOT), **k)

        def log_message(self, *x):
            pass

        def do_POST(self):
            if self.path != "/render":
                return self.send_error(404)
            snap = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
            out = DEMO / "완성본.mp4"
            try:
                scene_style.compose(str(base), TIMELINE, snap, str(out), DEMO / "render", HC)
                os.startfile(str(out))
                body = {"ok": True, "path": str(out)}
            except Exception as e:      # noqa: BLE001
                body = {"ok": False, "error": repr(e)[:300]}
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)

    # 윈도는 이미 쓰는 포트에도 조용히 붙는다(실측: 8765 에 다른 프로그램이 있어 요청이 그쪽으로 갔다) — 빈 포트를 직접 찾는다
    import socket
    while True:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", a.port)) != 0:
                break
        a.port += 1
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), H)
    url = f"http://127.0.0.1:{a.port}/tools/scene_fx/_demo/index.html"
    print("로컬 체험:", url, "(끝내려면 이 창에서 Ctrl+C)")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
