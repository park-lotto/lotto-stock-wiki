"""폰 화면 점검 (관제 276) — 라이브 화면을 폰 크기로 열어 '밀어도 닿지 않는 잘림'·'짓눌림'을 센다.

가로 스크롤 띠(메뉴·탭) 안에서 화면 밖으로 나간 것은 손가락으로 밀면 보이므로 결함이 아니다.
결함 = ① 잘림: 화면 밖으로 나갔는데 조상 중에 가로로 밀 수 있는 상자가 하나도 없는 요소
       ② 짓눌림: 칸이 좁아 글자가 한 줄에 1~2자씩 세로로 쪼개진 곳
       ③ 페이지 가로 밀림: 문서 전체가 화면보다 넓다
       ④ 작은 버튼: 높이 32px 미만(참고 — 60대 손가락 기준은 44px)

    py tools/mobile_audit.py                  # 고객 화면 전부 + 제작소 10단계 + 장면꾸미기 편집기
    py tools/mobile_audit.py produce#6 editor # 몇 개만 (produce#N = 제작소 N단계, editor = 장면꾸미기 편집기)
    py tools/mobile_audit.py --width 360      # 더 좁은 폰
    py tools/mobile_audit.py --preview        # 이 폴더(트랙)에서 고친 static/편집기 파일을 라이브 화면에 끼워 본다(배포 전 확인)

제작소 단계는 jump() 를 안 쓴다 — jump 는 단계를 서버에 저장하고 장면 매칭(과금)을 시작할 수 있다. 패널 표시만 바꾼다.
캡처·결과는 %TEMP%/mobile_audit/ (저장소에 안 남긴다).
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PAGES = ["", "produce", "refs", "discover", "overseas_ref", "fav_channels", "collection",
         "archive", "scene_library", "shortem_packs", "shortem_preset", "meme_pack",
         "cardnews", "yt_studio", "challenge", "help", "fx_samples", "outreach"]
TARGETS = PAGES + ["produce#%d" % i for i in range(1, 11)] + ["editor"]

JS = r"""() => {
  const vw = innerWidth;
  const scroller = el => {
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && p.scrollWidth > p.clientWidth + 1) return true;
    }
    return false;
  };
  const hidden = el => {
    for (let p = el; p; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.visibility === 'hidden' || cs.opacity === '0' || cs.display === 'none') return true;
    }
    return false;
  };
  // 일부러 '…'으로 줄인 글자 자리(text-overflow:ellipsis)는 설계다 — 잘림으로 안 센다
  const ellipsis = el => {
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.textOverflow === 'ellipsis' && cs.overflowX === 'hidden') return true;
    }
    return false;
  };
  // 사진·영상이 화면 안의 틀(overflow:hidden)에 맞춰 잘려 보이는 건 설계다(편집기 미리보기 폰 틀).
  //   단추·글자가 틀에 잘린 건 결함으로 센다(랭킹 카드 쿠팡 버튼이 그랬다).
  const mediaCrop = el => {
    if (!/^(IMG|VIDEO|CANVAS|PICTURE)$/.test(el.tagName)) return false;
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p), b = p.getBoundingClientRect();
      if (/hidden|clip/.test(cs.overflowX) && b.left >= -2 && b.right <= vw + 2) return true;
    }
    return false;
  };
  const bad = [];
  for (const el of document.querySelectorAll('body *')) {
    const b = el.getBoundingClientRect();
    if (b.width < 2 || b.height < 2) continue;
    if (b.right <= vw + 2 && b.left >= -2) continue;
    if (scroller(el) || hidden(el) || ellipsis(el) || mediaCrop(el)) continue;
    if (bad.some(o => o.contains(el))) continue;
    bad.push(el);
  }
  const desc = el => {
    const b = el.getBoundingClientRect();
    const id = el.id ? '#' + el.id : '';
    const cls = (el.className && typeof el.className === 'string') ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
    return {sel: el.tagName.toLowerCase() + id + cls, left: Math.round(b.left), right: Math.round(b.right),
            w: Math.round(b.width), text: (el.innerText || '').trim().slice(0, 30)};
  };
  // 작은 단추: 줄글 속 글자 링크(display:inline 인 a — 채널 이름 등)는 글 흐름이라 뺀다. 체크박스·라디오도 뺀다.
  const taps = [...document.querySelectorAll('button,a,[role=button],input,select')].filter(e => {
    if (e.tagName === 'A' && getComputedStyle(e).display === 'inline') return false;
    if (e.tagName === 'INPUT' && /checkbox|radio|range|color|file|hidden/.test(e.type)) return false;
    const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && b.height < 32 && !hidden(e);
  }).length;
  // 짓눌림: 칸이 좁아 글자가 한 줄에 1~2자씩 세로로 쪼개진 곳('숏템/고품/질 자/막제/거').
  //   글자 조각(text node)마다 줄 수를 센다(기준은 아래 bad4·bad2).
  const squeezed = [];
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    const t = n.textContent.replace(/\s+/g, '');
    if (t.length < 2 || !n.parentElement || hidden(n.parentElement)) continue;
    const rg = document.createRange(); rg.selectNodeContents(n);
    const tops = new Set([...rg.getClientRects()].filter(r => r.width > 0).map(r => Math.round(r.top)));
    // 4자 이상: 3줄 이상·줄당 2.5자 이하 / 2~3자 버튼 글자('숏/폼', '본/문'): 한 글자씩 쪼개짐(줄당 1.5자 이하) — 편집기에서 놓친 것(실측)
    const bad4 = t.length >= 4 && tops.size >= 3 && t.length / tops.size <= 2.5;
    const bad2 = t.length < 4 && tops.size >= 2 && t.length / tops.size <= 1.5;
    if ((bad4 || bad2) && !squeezed.includes(n.parentElement)) squeezed.push(n.parentElement);
  }
  return {path: location.pathname, vw, page_scroll: document.documentElement.scrollWidth - vw,
          cut: bad.length, cut_list: bad.slice(0, 12).map(desc), small_taps: taps,
          squeezed: squeezed.length, squeezed_list: squeezed.slice(0, 12).map(desc)};
}"""

ST = "shopping_shorts/static/"
# 편집기는 서버가 /api/produce/scene-style/assets/<경로> 로 저장소의 파일을 그대로 준다
_PREVIEW_FILES = {"sidebar.js": ST + "sidebar.js", "scene-style-ui-showcase.html": "out/scene-style-ui-showcase.html",
                  "scene-style-connect.css": "out/scene-style-connect.css", "scene-style-produce.js": ST + "scene-style-produce.js"}


def _base():
    """트랙이 갈라진 지점 — origin/main 과 직접 비교하면 그 뒤 남이 병합한 변경이 거꾸로 섞인다."""
    return subprocess.run(["git", "-C", ROOT, "merge-base", "HEAD", "origin/main"], capture_output=True, text=True).stdout.strip()


def _hunks(rel):
    """트랙에서 고친 덩어리(앞뒤 2줄 문맥 포함) — 라이브 본문에서 찾아 바꿔 끼운다(서버가 넣는 내용은 살린다)."""
    d = subprocess.run(["git", "-C", ROOT, "diff", "-U2", _base(), "--", rel], capture_output=True).stdout.decode("utf-8")
    reps, old, new = [], [], []
    for ln in d.splitlines()[4:]:
        if ln.startswith("@@"):
            if old or new:
                reps.append(("\n".join(old), "\n".join(new)))
            old, new = [], []
            continue
        if ln.startswith("\\"):
            continue
        t, body = ln[:1], ln[1:]
        if t in (" ", "-"):
            old.append(body)
        if t in (" ", "+"):
            new.append(body)
    if old or new:
        reps.append(("\n".join(old), "\n".join(new)))
    return reps


# 점검은 읽기만 한다 — GET 아닌 요청은 전부 막는다(autoload 도: 담긴 영상 내려받기·분석이라 포인트가 들 수 있다).
#   실사고(10-26): 열고 나서 새로고침하자 화면이 불러오는 도중 pagehide 저장(POST /api/produce/works)이 나가
#   관리자 계정에 대본 없는 작업 사본이 생기고 그게 '지금 작업'이 됐다. 점검 도구가 고객·관리자 데이터를 바꾸면 안 된다.
_ALLOW_WRITE = ()


def _guard_and_preview(pg, preview, misses, blocked):
    """첫 요청 전에 건다(admin_page setup). 쓰기 차단 + (preview 면) 트랙에서 고친 파일 끼우기."""
    whole, html = {}, {}
    if preview:
        whole = {k: open(os.path.join(ROOT, v), encoding="utf-8").read() for k, v in _PREVIEW_FILES.items()}
        changed = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", _base(), "--", ST],
                                 capture_output=True).stdout.decode("utf-8").split()
        html = {os.path.basename(f): _hunks(f) for f in changed if f.endswith(".html")}

    def handler(route, _req=None):
        if route.request.method != "GET" and not any(a in route.request.url for a in _ALLOW_WRITE):
            blocked.append(route.request.method + " " + route.request.url.split("?")[0][-60:])
            return route.abort()
        if not preview:
            return route.fallback()
        url = route.request.url.split("?")[0]
        name = url.rsplit("/", 1)[-1] or "index.html"
        if name in whole:
            ctype = {"js": "application/javascript", "css": "text/css"}.get(name.rsplit(".", 1)[-1], "text/html; charset=utf-8")
            return route.fulfill(status=200, content_type=ctype, body=whole[name])
        if route.request.resource_type == "document":
            key = name if name.endswith(".html") else (name + ".html")
            if url.rstrip("/").count("/") == 2:
                key = "index.html"
            if key in html:
                resp = route.fetch()
                body = resp.text().replace("\r\n", "\n")
                for a, b in html[key]:
                    if a in body:
                        body = body.replace(a, b, 1)
                    else:
                        misses.append(key + ": " + a[:40])
                return route.fulfill(response=resp, body=body)
        return route.fallback()
    pg.route("**/*", handler)


def _open_target(pg, target):
    """produce#N → 패널 표시만 바꾼다(저장·매칭 없음). editor → 장면꾸미기 편집기를 열고 그 iframe 을 돌려준다."""
    if target.startswith("produce#"):
        o = int(target.split("#")[1]) - 1
        pg.evaluate("o=>{const p=ORB_TO_PANEL[o];document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('show', +x.dataset.step===p));scrollTo(0,0)}", o)
        pg.wait_for_timeout(4000)   # 패널 내용이 늦게 그려진다 — 1.2초에 재면 5단계 짓눌림을 놓쳤다(실측)
        return pg.main_frame
    if target == "editor":
        pg.evaluate("()=>{const p=PANEL_BY_KEY.deco;document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('show', +x.dataset.step===p));scrollTo(0,0)}")
        pg.evaluate("()=>{ if(typeof openSceneStyleEditor==='function') return openSceneStyleEditor(); }")
        for _ in range(30):
            pg.wait_for_timeout(1000)
            fr = next((f for f in pg.frames if "scene-style-ui-showcase" in f.url), None)
            if fr:
                try:
                    fr.wait_for_load_state("load", timeout=15000)
                    pg.wait_for_timeout(2500)
                    return fr
                except Exception:
                    pass
        raise RuntimeError("장면꾸미기 편집기가 안 열렸다")
    pg.wait_for_timeout(1500)
    return pg.main_frame


def _editor_work(width, height):
    from tools.live_admin import admin_page
    with admin_page("help", viewport=(width, height)) as pg:
        ws = pg.evaluate("()=>fetch('/api/produce/works',{cache:'no-store'}).then(r=>r.json())").get("works") or []
    w = next((w for w in ws if w.get("job_id") and (w.get("step") or 0) >= 6), None)
    return w and w["work_id"]


def audit(targets, width=390, height=844, out_dir=None, preview=False):
    from tools.live_admin import admin_page
    out_dir = out_dir or os.path.join(tempfile.gettempdir(), "mobile_audit")   # 캡처는 저장소에 안 남긴다
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    editor_work = None
    for t in targets:
        page = "produce" if (t.startswith("produce#") or t == "editor") else t
        if t == "editor":
            # 관리자 '지금 작업'에 장면이 없으면 편집기가 안 열린다 → 장면이 준비된 최근 작업을 ?work= 로 연다(읽기만)
            editor_work = editor_work or _editor_work(width, height)
            page = "produce?work=" + editor_work if editor_work else page
        misses, blocked = [], []
        try:
            with admin_page(page, viewport=(width, height),
                            setup=lambda pg: _guard_and_preview(pg, preview, misses, blocked)) as pg:
                fr = _open_target(pg, t)
                r = fr.evaluate(JS)
                r["target"] = t
                r["errors"] = len(pg.errors)
                r["shot"] = os.path.join(out_dir, "%d_%s.png" % (width, t.replace("/", "_").replace("#", "_") or "home"))
                pg.screenshot(path=r["shot"])
        except Exception as e:
            r = {"target": t, "error": str(e)[:200]}
        if misses:
            r["preview_miss"] = misses
        if blocked:
            r["blocked_writes"] = blocked
        rows.append(r)
        print(f"{(t or '/'):<16} 잘림 {r.get('cut', '?'):>3}  짓눌림 {r.get('squeezed', '?'):>3}  페이지가로 {r.get('page_scroll', '?'):>4}"
              f"  작은버튼 {r.get('small_taps', '?'):>4}" + (f"  오류 {r['error']}" if "error" in r else "")
              + (f"  ⚠미리보기 못 끼움 {len(misses)}" if misses else ""), flush=True)
        for c in r.get("cut_list", [])[:5]:
            print(f"    - 잘림 {c['sel'][:50]}  [{c['left']}~{c['right']}]  {c['text'][:30]}")
        for c in r.get("squeezed_list", [])[:5]:
            print(f"    - 짓눌림 {c['sel'][:50]}  폭 {c['w']}  {c['text'][:30]}")
    with open(os.path.join(out_dir, "result_%d.json" % width), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    _sheet([r["shot"] for r in rows if r.get("shot")], os.path.join(out_dir, "sheet_%d.png" % width))
    return rows


def _sheet(paths, dst, per_row=6):
    from PIL import Image
    ims = [Image.open(x) for x in paths if os.path.exists(x)]
    if not ims:
        return
    w, h = ims[0].size
    rows = (len(ims) + per_row - 1) // per_row
    s = Image.new("RGB", (per_row * (w + 10), rows * (h + 10)), "white")
    for i, im in enumerate(ims):
        s.paste(im.resize((w, h)) if im.size != (w, h) else im, ((i % per_row) * (w + 10), (i // per_row) * (h + 10)))
    s.thumbnail((1800, 1800))
    s.save(dst)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    width = 390
    if "--width" in args:
        i = args.index("--width")
        width = int(args[i + 1])
        del args[i:i + 2]
    preview = "--preview" in args
    args = [a for a in args if a != "--preview"]
    targets = [("" if a in ("/", "home") else a.strip("/")) for a in args] or TARGETS
    rows = audit(targets, width=width, preview=preview)
    print(f"\n합계({width}px{' · 미리보기' if preview else ''}): 잘림 {sum(r.get('cut', 0) for r in rows)} · 짓눌림 {sum(r.get('squeezed', 0) for r in rows)}"
          f" · 페이지 가로 밀림 {sum(1 for r in rows if r.get('page_scroll', 0) > 0)}화면 · 오류 {sum(1 for r in rows if 'error' in r)}")
    print("캡처:", os.path.join(tempfile.gettempdir(), "mobile_audit", "sheet_%d.png" % width))
