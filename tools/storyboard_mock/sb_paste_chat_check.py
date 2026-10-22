# -*- coding: utf-8 -*-
"""2단계 스토리보드 — 대본 한 번에 붙여넣기 · 칸에 여러 줄 Ctrl+V · AI 대화 고치기(관제 253) 결과물 검사.

라이브 작업을 **관리자로, 읽기 전용**(GET 만 라이브로, 나머지 POST 는 막고 본문만 잡는다)으로 열고,
--local 이면 화면 파일을 이 폴더의 produce.html 로 바꿔 끼운다. AI 대화(/api/script/chat)는 이 폴더 코드로 띄운
로컬 서버로 보내 **진짜 AI**를 부른다(로컬 서버는 계정 미상 = 무료 키 길).

    py tools/storyboard_mock/sb_paste_chat_check.py <work_id> [--local] [--ai-server] [--shot <png>]

--ai-server: 이 PC 무료 키가 소진됐을 때 — 이 폴더의 script_chat.py 를 서버 /tmp 에 올려 **서버 환경(키풀)으로** revise 를
  돌린다(저장소·서비스는 안 건드림, 계정 미상 = 무료 키 길). 화면 → 응답 → [적용] 흐름은 같다.

잰다:
 ① 📋 상자에 제미나이식 대본(번호·빈 줄 섞임, 칸보다 2줄 많게)을 넣고 [칸에 나눠 넣기]
    → 칸 수 = 줄 수, 칸 글 = 번호 뗀 줄 그대로, 초 다시 재기(/picks) 요청에 그 줄들이 실린다
 ② 2번 칸에 3줄을 Ctrl+V → 2·3·4번 칸이 그 3줄, 나머지 칸은 그대로
 ③ AI 대화 "2번째 줄 …" → 바뀐 줄 제안 → [적용] → 바뀐 줄만 칸에 들어가고 나머지 칸은 그대로
 ④ [이 대본으로 확정] → 확정 대본(S2 안)·서버로 나가는 요청에 칸 글이 줄마다 그대로 실린다
고치기 전 화면(라이브 그대로, --local 없이)에서는 버튼이 없어 ①부터 실패해야 한다.
"""
import json
import os
import pathlib
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PORT = 8796
SSH = ["ssh", "-i", os.path.join(os.path.expanduser("~"), "crawling_bot_client", "LightsailDefaultKey-ap-northeast-2.pem"),
       "ubuntu@3.35.251.172"]
_RUNNER = r"""
import importlib.util, json, sys
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
spec = importlib.util.spec_from_file_location("shopping_shorts.script_chat_chk", "/tmp/sb_chat_chk/script_chat.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
b = json.loads(sys.stdin.read())
try:
    print(json.dumps({"ok": True, **m.revise(b.get("lines") or [], b.get("message") or "", b.get("history") or [], b.get("product") or "")}, ensure_ascii=False))
except ValueError as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
"""


def _server_upload():
    import subprocess
    subprocess.run(SSH + ["mkdir -p /tmp/sb_chat_chk"], check=True)
    subprocess.run(["scp", "-q", "-i", SSH[2], str(ROOT / "shopping_shorts" / "script_chat.py"),
                    "ubuntu@3.35.251.172:/tmp/sb_chat_chk/script_chat.py"], check=True)
    subprocess.run(SSH + ["cat > /tmp/sb_chat_chk/run.py"], input=_RUNNER.encode(), check=True)


def _server_chat(body):
    import subprocess
    cmd = "cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && python3 /tmp/sb_chat_chk/run.py 2>/dev/null"
    r = subprocess.run(SSH + [cmd], input=body.encode(), capture_output=True, timeout=240)
    out = r.stdout.decode("utf-8", "replace").strip().splitlines()
    d = json.loads(out[-1]) if out else {"ok": False, "error": "서버 실행 실패: " + r.stderr.decode("utf-8", "replace")[-200:]}
    return (200 if d.get("ok") else 422), json.dumps(d, ensure_ascii=False).encode()

PASTE = "1. 이거 하나면 아침이 달라집니다\n\n2) 매일 아침 십 분씩 걸리던 일이\n- 단 삼십 초면 끝나요\n• 손에 묻지도 않고요\n씻는 것도 물로 한 번이면 끝\n지금 안 사면 또 품절이에요"
PASTE_LINES = ["이거 하나면 아침이 달라집니다", "매일 아침 십 분씩 걸리던 일이", "단 삼십 초면 끝나요",
               "손에 묻지도 않고요", "씻는 것도 물로 한 번이면 끝", "지금 안 사면 또 품절이에요"]
CTRLV = ["두 번째 칸에 붙인 첫 줄", "두 번째 칸에 붙인 둘째 줄", "두 번째 칸에 붙인 셋째 줄"]
ASK = "2번째 줄을 더 짧고 강하게 바꿔줘. 다른 줄은 그대로 둬."

LINES_JS = "() => [...document.querySelectorAll('#s2Storyboard .sb-row .sb-line')].map(x => x.innerText.trim())"


def _local_app():
    from shopping_shorts import app as appmod
    from shopping_shorts.store import Store
    import uvicorn
    db = os.path.join(tempfile.mkdtemp(), "t.db")
    appmod.DB_PATH = db
    appmod._AUTH_ON = False
    Store(db)
    threading.Thread(target=lambda: uvicorn.run(appmod.app, host="127.0.0.1", port=PORT, log_level="warning"),
                     daemon=True).start()
    time.sleep(4)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    work = argv[0]
    local = "--local" in argv
    shot = argv[argv.index("--shot") + 1] if "--shot" in argv else ""
    via_server = "--ai-server" in argv
    if via_server:
        _server_upload()
    else:
        _local_app()
    from playwright.sync_api import sync_playwright
    from tools.live_admin import BASE, admin_cookie
    ck = admin_cookie()
    html = (ROOT / "shopping_shorts" / "static" / "produce.html").read_bytes()
    res, posts, errs = {}, [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1700, "height": 1100})
        ctx.add_cookies([{"name": "dash_auth", "value": ck, "domain": "shoppingshorts.duckdns.org", "path": "/",
                          "httpOnly": True, "secure": True, "sameSite": "Lax"}])
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))

        def route(r):
            q = r.request
            if q.method != "GET":
                if q.url.endswith("/api/script/chat") and via_server:   # 진짜 AI — 서버 키풀로 이 폴더 revise
                    st, body = _server_chat(q.post_data or "{}")
                    posts.append((q.url, q.post_data or ""))
                    return r.fulfill(status=st, content_type="application/json", body=body)
                if q.url.endswith("/api/script/chat"):          # 진짜 AI — 이 폴더 코드로 띄운 서버
                    req = urllib.request.Request("http://127.0.0.1:%d/api/script/chat" % PORT, data=(q.post_data or "").encode(),
                                                 headers={"Content-Type": "application/json"}, method="POST")
                    try:
                        with urllib.request.urlopen(req, timeout=180) as rr:
                            body, st = rr.read(), rr.status
                    except urllib.error.HTTPError as e:
                        body, st = e.read(), e.code
                    posts.append((q.url, q.post_data or ""))
                    return r.fulfill(status=st, content_type="application/json", body=body)
                posts.append((q.url, q.post_data or ""))         # 읽기 전용 — 라이브 작업을 건드리지 않는다
                return r.abort()
            if local and q.resource_type == "document" and "/produce" in q.url:
                return r.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
            return r.continue_()

        pg.route("**/*", route)
        pg.goto(BASE + "/produce?work=" + work, wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        ready = pg.evaluate("""async () => { const w=ms=>new Promise(r=>setTimeout(r,ms));
            for(let k=0;k<60&&!(window.STORYBOARD_ON&&SB.data&&Object.keys(SB.made||{}).length);k++) await w(500);
            if(!(window.STORYBOARD_ON&&Object.keys(SB.made||{}).length)) return null;
            if(!SB.made[SB.view]) SB.view=Object.keys(SB.made)[0]; cur=8; showPanel(); sbRender(); return SB.view; }""")
        if not ready:
            print("✖ 스토리보드가 있는 작업을 못 열었다(스위치·작업 확인)", errs[:2])
            return 1
        before = pg.evaluate(LINES_JS)
        res["처음 칸 수"] = len(before)
        # ① 붙여넣기 상자
        btn = pg.locator("#s2Storyboard button", has_text="대본 한 번에 붙여넣기")
        if not btn.count():
            print("✖ ① 「📋 대본 한 번에 붙여넣기」 버튼이 없다(고치기 전 화면)")
            b.close()
            return 1
        n0 = len(posts)
        btn.first.click()
        pg.fill("#sbPasteIn", PASTE)
        res["①줄수표시"] = pg.locator("#sbPasteN").inner_text()
        pg.locator("#s2Storyboard button", has_text="칸에 나눠 넣기").click()
        pg.wait_for_timeout(1500)
        got1 = pg.evaluate(LINES_JS)
        picks1 = [json.loads(bd) for u, bd in posts[n0:] if u.endswith("/picks")]
        sent1 = [s.get("line") for s in (picks1[-1]["slots"] if picks1 else [])]
        nonempty = [x for x in got1 if x]
        ok1 = nonempty == PASTE_LINES and got1[:len(PASTE_LINES)] == PASTE_LINES and sent1[:len(PASTE_LINES)] == PASTE_LINES
        res["①칸"] = got1
        res["①picks요청"] = len(picks1)
        # ② 2번 칸(번호 1)에 3줄 Ctrl+V
        pg.evaluate("""(t) => { const el=document.querySelectorAll('#s2Storyboard .sb-row .sb-line')[1]; el.focus();
            const dt=new DataTransfer(); dt.setData('text/plain', t);
            el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""", "\n".join(CTRLV))
        pg.wait_for_timeout(1500)
        got2 = pg.evaluate(LINES_JS)
        exp2 = [got1[0]] + CTRLV + got1[4:]
        ok2 = got2 == exp2
        res["②칸"] = got2
        # ③ AI 대화
        pg.locator("#s2Storyboard button", has_text="AI와 대본 고치기").first.click()
        pg.fill("#sbChatIn", ASK)
        pg.press("#sbChatIn", "Enter")
        t0 = time.time()
        prop = None
        while time.time() - t0 < 180:
            pg.wait_for_timeout(2000)
            prop = pg.evaluate("() => SB.chat.prop ? JSON.parse(JSON.stringify(SB.chat.prop)) : (SB.chat.busy ? null : 'done')")
            if prop:
                break
        res["③AI답"] = pg.evaluate("() => SB.chat.msgs.map(m => m.role + ':' + m.text + (m.auth ? ' [' + m.auth + ']' : ''))")
        res["③걸린초"] = round(time.time() - t0)
        ok3 = False
        if isinstance(prop, dict) and prop.get("changed"):
            res["③바뀐줄"] = prop["changed"]
            pg.locator("#s2Storyboard button", has_text="적용").first.click()
            pg.wait_for_timeout(1500)
            got3 = pg.evaluate(LINES_JS)
            res["③칸"] = got3
            ok3 = (1 in prop["changed"]) and got3[1] == prop["lines"][1] and got3[1] != got2[1] \
                and all(got3[k] == got2[k] for k in range(len(got2)) if k not in prop["changed"])
        else:
            got3 = got2
        if shot:
            pg.locator("#s2Storyboard").screenshot(path=shot)
        # ④ 확정 — 확정 대본과 서버로 나가는 요청에 칸 글이 줄마다 실리는가
        n4 = len(posts)
        pg.evaluate("() => { try { sbConfirm(); } catch (e) { window.__cfErr = String(e); } }")
        pg.wait_for_timeout(3000)
        dr = pg.evaluate("() => { const d=(S2.drafts||[]).filter(x=>x&&x.storyboard).slice(-1)[0]; return d ? {script:d.script, beats:d.beats.map(b=>b.text)} : null; }")
        want = [x for x in got3 if x]
        out_bodies = " ".join(bd for u, bd in posts[n4:])
        in_req = all(json.dumps(x, ensure_ascii=False)[1:-1] in out_bodies or x in out_bodies for x in want)
        ok4 = bool(dr) and dr["beats"] == want and dr["script"] == "\n".join(want)
        res["④확정줄"] = dr and dr["beats"]
        res["④요청"] = [u.split("shoppingshorts.duckdns.org")[-1] for u, bd in posts[n4:]]
        res["④요청에줄실림"] = in_req
        b.close()
    for k, v in res.items():
        print(k, json.dumps(v, ensure_ascii=False)[:600])
    print("페이지 오류", errs[:3])
    print("① 붙여넣기 %s · ② Ctrl+V %s · ③ AI 대화 %s · ④ 확정 %s" % tuple("통과" if x else "실패" for x in (ok1, ok2, ok3, ok4 and in_req)))
    ok = ok1 and ok2 and ok3 and ok4 and in_req and not errs
    print("✅ 통과" if ok else "✖ 실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
