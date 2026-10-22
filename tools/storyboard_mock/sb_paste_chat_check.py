# -*- coding: utf-8 -*-
"""2단계 스토리보드 — 대본 한 번에 붙여넣기 · 칸에 여러 줄 Ctrl+V · AI 대화 고치기(관제 253) 결과물 검사.

라이브 작업을 **관리자로, 읽기 전용**(GET 만 라이브로, 나머지 POST 는 막고 본문만 잡는다)으로 열고,
--local 이면 화면 파일을 이 폴더의 produce.html 로 바꿔 끼운다. AI 대화(/api/script/chat)는 이 폴더 코드로 띄운
로컬 서버로 보내 **진짜 AI**를 부른다(로컬 서버는 계정 미상 = 무료 키 길).

    py tools/storyboard_mock/sb_paste_chat_check.py <work_id> [--local] [--ai-server [--ai-cid 0]] [--shot <png>]
        [--shot-chat <png>] [--shot-row <png>]

--ai-cid: --ai-server 때 그 계정 주인으로 부른다(0 = 관리자 → 사장님 버텍스, 비우면 계정 미상 = 무료 키).
--shot-chat: [적용] 전 제안이 뜬 대화창 캡처 · --shot-row: 한 줄 요구 뒤 그 칸 캡처.

--ai-server: 이 PC 무료 키가 소진됐을 때 — 이 폴더의 script_chat.py 를 서버 /tmp 에 올려 **서버 환경(키풀)으로** revise 를
  돌린다(저장소·서비스는 안 건드림, 계정 미상 = 무료 키 길). 화면 → 응답 → [적용] 흐름은 같다.

잰다:
 ① 📋 상자에 제미나이식 대본(번호·빈 줄 섞임, 칸보다 2줄 많게)을 넣고 [칸에 나눠 넣기]
    → 칸 수 = 줄 수, 칸 글 = 번호 뗀 줄 그대로, 초 다시 재기(/picks) 요청에 그 줄들이 실린다
 ② 2번 칸에 3줄을 Ctrl+V → 2·3·4번 칸이 그 3줄, 나머지 칸은 그대로
 ③ AI 대화 2턴: "훅 후보 3개" → 답만(대본 그대로·제안 없음) / "2번째 후보로 훅 바꿔줘" → 훅만, 앞 답의 그 후보 문장으로 → [적용]
 ⑤ 4번 칸 아래 한 줄 요구창 "연결어로 시작하게" → 4번 칸만 바뀜 → ↩ 되돌리기 → 원래대로
 ⑥ 요구창에 치는 도중 다시 그려져도 커서·글자가 남는다
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
from shopping_shorts import keyctx
b = json.loads(sys.stdin.read())
if len(sys.argv) > 1:          # --ai-cid: 그 계정이 부른 것처럼(라이브 미들웨어 keyctx.set_owner 와 같다) — 0 = 관리자 → 사장님 버텍스
    keyctx.set_owner(int(sys.argv[1]))
try:
    print(json.dumps({"ok": True, **m.revise(b.get("lines") or [], b.get("message") or "", b.get("history") or [], b.get("product") or "",
                                             b.get("roles"), b.get("only"))}, ensure_ascii=False))
except ValueError as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
"""


def _server_upload():
    import subprocess
    subprocess.run(SSH + ["mkdir -p /tmp/sb_chat_chk"], check=True)
    subprocess.run(["scp", "-q", "-i", SSH[2], str(ROOT / "shopping_shorts" / "script_chat.py"),
                    "ubuntu@3.35.251.172:/tmp/sb_chat_chk/script_chat.py"], check=True)
    subprocess.run(SSH + ["cat > /tmp/sb_chat_chk/run.py"], input=_RUNNER.encode(), check=True)


def _server_chat(body, cid=""):
    import subprocess
    cmd = "cd /home/ubuntu/lotto-stock-wiki && set -a && . /etc/shopping-shorts.env && set +a && python3 /tmp/sb_chat_chk/run.py %s 2>/dev/null" % (cid or "")
    r = subprocess.run(SSH + [cmd], input=body.encode(), capture_output=True, timeout=240)
    out = r.stdout.decode("utf-8", "replace").strip().splitlines()
    d = json.loads(out[-1]) if out else {"ok": False, "error": "서버 실행 실패: " + r.stderr.decode("utf-8", "replace")[-200:]}
    return (200 if d.get("ok") else 422), json.dumps(d, ensure_ascii=False).encode()

PASTE = "1. 이거 하나면 아침이 달라집니다\n\n2) 매일 아침 십 분씩 걸리던 일이\n- 단 삼십 초면 끝나요\n• 손에 묻지도 않고요\n씻는 것도 물로 한 번이면 끝\n지금 안 사면 또 품절이에요"
PASTE_LINES = ["이거 하나면 아침이 달라집니다", "매일 아침 십 분씩 걸리던 일이", "단 삼십 초면 끝나요",
               "손에 묻지도 않고요", "씻는 것도 물로 한 번이면 끝", "지금 안 사면 또 품절이에요"]
CTRLV = ["두 번째 칸에 붙인 첫 줄", "두 번째 칸에 붙인 둘째 줄", "두 번째 칸에 붙인 셋째 줄"]
ASK1 = "훅 후보 3개만 추천해줘. 대본은 아직 바꾸지 마."
ASK2 = "2번째 후보로 훅 바꿔줘"
ASK_ROW = "연결어로 시작하게 바꿔줘"

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
    shot_row = argv[argv.index("--shot-row") + 1] if "--shot-row" in argv else ""
    ai_cid = argv[argv.index("--ai-cid") + 1] if "--ai-cid" in argv else ""
    shot_chat = argv[argv.index("--shot-chat") + 1] if "--shot-chat" in argv else ""
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
                    st, body = _server_chat(q.post_data or "{}", ai_cid)
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
        # ③ AI 대화 — 2턴: 추천만 받으면 대본 그대로 → "2번째 후보로 훅 바꿔줘"면 그 후보로 훅(1번 칸)만 바뀐다
        def wait_chat(n_before):
            t0 = time.time()
            while time.time() - t0 < 180:
                pg.wait_for_timeout(1500)
                if pg.evaluate("(n) => !SB.chat.busy && SB.chat.msgs.length > n", n_before):
                    break
            return round(time.time() - t0)
        pg.locator("#s2Storyboard button", has_text="AI와 대화").first.click()
        n = pg.evaluate("() => SB.chat.msgs.length")
        pg.fill("#sbChatIn", ASK1)
        pg.press("#sbChatIn", "Enter")
        res["③-1걸린초"] = wait_chat(n + 1)
        ans1 = pg.evaluate("() => SB.chat.msgs.slice(-1)[0]")
        prop1 = pg.evaluate("() => SB.chat.prop")
        lines_after1 = pg.evaluate(LINES_JS)
        res["③-1답"] = ans1
        ok3a = bool(ans1 and ans1.get("role") == "ai" and not ans1["text"].startswith("❌") and len(ans1["text"]) > 20) \
            and prop1 is None and lines_after1 == got2
        n = pg.evaluate("() => SB.chat.msgs.length")
        pg.fill("#sbChatIn", ASK2)
        pg.press("#sbChatIn", "Enter")
        res["③-2걸린초"] = wait_chat(n + 1)
        prop = pg.evaluate("() => SB.chat.prop ? JSON.parse(JSON.stringify(SB.chat.prop)) : null")
        res["③-2답"] = pg.evaluate("() => SB.chat.msgs.slice(-1)[0]")
        ok3 = False
        got3 = got2
        if isinstance(prop, dict) and prop.get("changed"):
            res["③-2제안"] = {k + 1: [got2[k], prop["lines"][k]] for k in prop["changed"]}
            if shot_chat:
                pg.locator("#s2Storyboard .sb-chat").screenshot(path=shot_chat)
            pg.locator("#s2Storyboard .sb-chat button", has_text="적용").first.click()
            pg.wait_for_timeout(1500)
            got3 = pg.evaluate(LINES_JS)
            res["③칸"] = got3
            # 훅 **하나만** 바뀌고, 그 문장이 앞 답(후보 목록) 안에 있어야 한다(이어받기). 빈 칸 표시가 새면 실패
            ok3 = prop["changed"] == [0] and got3[0] == prop["lines"][0] and got3[0] != got2[0] \
                and got3[0].strip(" .!?") in ans1["text"] \
                and not any("빈 칸" in x or "빈칸" in x for x in got3) and got3[1:] == got2[1:]
        ok3 = ok3a and ok3
        # ⑤ 칸 아래 한 줄 요구창 — 4번 칸만 바뀌고 ↩ 되돌리기로 원래대로
        row = 3
        before5 = pg.evaluate(LINES_JS)
        ask_in = pg.locator("#s2Storyboard .sb-row").nth(row).locator(".sb-ask input")
        ok5 = False
        if ask_in.count():
            ask_in.fill(ASK_ROW)
            ask_in.press("Enter")
            t0 = time.time()
            while time.time() - t0 < 180:
                pg.wait_for_timeout(1500)
                if not pg.evaluate("() => Object.keys(SB.askBusy).length"):
                    break
            pg.wait_for_timeout(800)
            got5 = pg.evaluate(LINES_JS)
            res["⑤한줄요구"] = [before5[row], got5[row]]
            if shot_row:
                pg.locator("#s2Storyboard .sb-row").nth(row).screenshot(path=shot_row)
            undo = pg.locator("#s2Storyboard .sb-row").nth(row).locator("button", has_text="되돌리기")
            changed_only = got5[row] != before5[row] and all(got5[k] == before5[k] for k in range(len(before5)) if k != row)
            if undo.count():
                undo.click()
                pg.wait_for_timeout(1200)
            got5b = pg.evaluate(LINES_JS)
            ok5 = changed_only and got5b == before5
            res["⑤되돌린뒤같음"] = got5b == before5
        # ⑥ 요구창에 치는 도중 화면이 다시 그려져도(초 다시 재기 등) 커서·글자가 남는가
        ask2 = pg.locator("#s2Storyboard .sb-row").nth(2).locator(".sb-ask input")
        ask2.click()
        ask2.type("연결어")
        pg.evaluate("() => sbRender()")
        f6 = pg.evaluate("""() => { const a=document.activeElement, all=[...document.querySelectorAll('#s2Storyboard .sb-ask input')];
            return {ix: all.indexOf(a), val: a && a.value}; }""")
        ok6 = f6 == {"ix": 2, "val": "연결어"}
        res["⑥다시그린뒤커서"] = f6
        pg.evaluate("() => { SB.ask = {}; sbRender(); }")
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
    print("① 붙여넣기 %s · ② Ctrl+V %s · ③ AI 대화 %s · ④ 확정 %s · ⑤ 한 줄 요구 %s · ⑥ 커서 유지 %s" % tuple(
        "통과" if x else "실패" for x in (ok1, ok2, ok3, ok4 and in_req, ok5, ok6)))
    ok = ok1 and ok2 and ok3 and ok4 and in_req and ok5 and ok6 and not errs
    print("✅ 통과" if ok else "✖ 실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
