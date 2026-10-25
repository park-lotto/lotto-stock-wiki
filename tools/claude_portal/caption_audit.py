# -*- coding: utf-8 -*-
"""숏템 '내 채널 설정' 꾸미기 단계 — 프리셋마다 '자막을 바꾸면 미리보기 자막이 실제로 바뀌나' 전수 점검.

실제 브라우저(playwright, 헤드리스)로 화면을 열고, 진짜 마우스 클릭/입력으로 자막 컨트롤을 만진 뒤
미리보기(#a-live-preview) 안 자막 요소의 계산된 스타일과 미리보기 픽셀이 바뀌었는지 잰다.

  PYTHONUTF8=1 py tools/claude_portal/caption_audit.py [--base http://127.0.0.1:18867/claude/studio/]
        [--out <그림 폴더>] [--only p_xxx,p_yyy] [--json <결과 json>]

순서(프리셋마다)
  ① 서버 API 로 프리셋 선택(POST api/select) → 새 브라우저(저장소 깨끗) → '꾸미기' 단계 → iframe 편집기
  ② '다음 ›' 으로 본문 장면(자막이 보이는 장면)까지 이동 → 오른쪽 '자막' 줄 펼침
  ③ 무변경 대조: 아무것도 안 하고 두 번 재서 '안 바뀜'이 나와야 한다(아니면 그 프리셋 판정은 '불안정')
  ④ 컨트롤마다(문구·크기＋·위치↓·자막 색·자막박스 색·자막박스 너비·글꼴(폰트 탭)) 만지고 전/후를 잰다
       바뀜      = 그 컨트롤이 바꿔야 할 값(글자/크기/위치/색/글꼴)이 바뀌고 미리보기 픽셀도 바뀜
       안 바뀜   = 컨트롤은 있고 만졌는데 미리보기가 그대로(전/후 그림 경로를 남긴다)
       컨트롤 없음 = 자막 칸이 숨겨져 있거나 그 입력이 없다
       자막 안 보임 = 본문 장면 미리보기에 자막 요소가 없다
  ⑤ 끝나면 프리셋 선택을 처음 것(state.current)으로 되돌린다

결과: 표(표준출력) + <out>/result.json · 그림 <out>/<pid>/<컨트롤>_전|후.png
rc=0 전부 바뀜(또는 컨트롤 없음 아님) / rc=1 하나라도 '안 바뀜'·'컨트롤 없음'·'자막 안 보임'
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

DEF_BASE = "http://127.0.0.1:18867/claude/studio/"
DEF_OUT = Path(r"C:\Users\CH\AppData\Local\Temp\claude\C--Users-CH-Desktop-------\fd2d18f7-f06d-4b64-8c29-5cb99e8f59a3\scratchpad\caption_audit")
PIX_MIN = 0.0005   # 미리보기 픽셀 중 바뀐 비율 하한(0.05%) — 무변경 대조로 잡음이 0인지 먼저 확인한다

# 미리보기 안 자막 요소: 편집기가 그리는 글자 요소는 data-edit-bind 로 칸 이름을 단다(precision20-ui.js 1644·1827)
MEASURE_JS = r"""()=>{
 const pv=document.querySelector('#a-live-preview');if(!pv)return {err:'no preview'};
 const pr=pv.getBoundingClientRect();
 const vis=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&Number(s.opacity)>0.05};
 const caps=[...pv.querySelectorAll('[data-edit-bind="caption"]')].filter(e=>vis(e)&&(e.innerText||'').trim());
 const field=document.querySelector('.layout-a [data-field-key="caption"]');
 const ta=field&&field.querySelector('[data-bind="caption"]');
 const g=window.sceneStyle&&window.sceneStyle.geometry?window.sceneStyle.geometry():{};
 const snap=window.sceneStyle&&window.sceneStyle.snapshot?window.sceneStyle.snapshot():null;
 const out={scene:g.sceneIndex,kind:g.kind,frame:snap&&snap.presetId,mode:snap&&snap.mode,spec:!!(snap&&snap.customFrame),
   fieldHidden:field?field.hidden:null,taValue:ta?ta.value:null,
   noteShown:!!(document.querySelector('.hook-caption-note')&&!document.querySelector('.hook-caption-note').hidden),caps:[]};
 for(const e of caps){const r=e.getBoundingClientRect(),s=getComputedStyle(e);
   // 글자 색은 자식 span 에 있을 수 있다 — 첫 글자 노드의 부모 색도 같이 본다
   // 강조 낱말 span 이 첫 글자일 수 있다(실측: 화자 대사 썰형) — 모든 글자 노드 부모의 색·글꼴을 모은다
   let inner=e;const w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);const cols=new Set(),fams=new Set();let t;while((t=w.nextNode())){if(!t.textContent.trim()||!t.parentElement)continue;const q=getComputedStyle(t.parentElement);cols.add(q.color);fams.add(q.fontFamily);inner=inner===e?t.parentElement:inner;}
   const si={color:[...cols].join(' / ')||getComputedStyle(e).color,fontFamily:[...fams].join(' / ')||getComputedStyle(e).fontFamily};
   out.caps.push({cls:e.className,text:(e.innerText||'').trim(),fontSize:s.fontSize,fontFamily:si.fontFamily,color:si.color,
     bg:s.backgroundColor,x:+((r.left-pr.left)/pr.width*100).toFixed(2),y:+((r.top-pr.top)/pr.height*100).toFixed(2),
     w:+(r.width/pr.width*100).toFixed(2),h:+(r.height/pr.height*100).toFixed(2),transform:s.transform});}
 // 자막박스(바탕 띠) 후보: caption 과 같이 쓰는 patch 들의 배경색·크기 묶음
 out.patches=[...pv.querySelectorAll('.precision-patch')].filter(vis).map(e=>{const r=e.getBoundingClientRect();return [e.dataset.editBind||'',getComputedStyle(e).backgroundColor,Math.round((r.top-pr.top)/pr.height*1000),Math.round(r.width/pr.width*1000),Math.round(r.height/pr.height*1000)].join('|')}).join(';');
 return out;}"""

# 컨트롤: (이름, 기대하는 변화 키, 동작 종류, 인자)
CONTROLS = [
    ("문구", "text", "fill", "점검자막 가나다 ABC"),
    ("크기＋", "fontSize", "click2", '.layout-a [data-field-key="caption"] [data-font-step="0.1"]'),
    ("위치↓", "pos", "click3", '.layout-a [data-field-key="caption"] [data-position-step="1"]'),
    ("자막 색", "color", "value", ('[data-caption-layout="color"]', "#ff2020")),
    ("자막박스 색", "pix", "value", ('[data-caption-layout="background"]', "#2050ff")),
    ("자막박스 너비", "pix", "value", ('[data-caption-layout="w"]', "35")),
    ("글꼴(폰트 탭)", "fontFamily", "font", None),
]


def http_json(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "Origin": url.split("/claude/")[0]} if body is not None else {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def pix_ratio(a: Path, b: Path) -> float:
    from PIL import Image, ImageChops
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if ia.size != ib.size:
        return 1.0
    diff = ImageChops.difference(ia, ib).convert("L").point(lambda v: 255 if v > 24 else 0)
    return sum(1 for v in diff.get_flattened_data() if v) / (ia.size[0] * ia.size[1])


def changed_keys(m0, m1):
    """두 측정의 자막 요소 차이 → 바뀐 항목 집합"""
    ks = set()
    c0, c1 = (m0.get("caps") or [{}])[0], (m1.get("caps") or [{}])[0]
    if c0.get("text") != c1.get("text"):
        ks.add("text")
    if c0.get("fontSize") != c1.get("fontSize") or c0.get("transform") != c1.get("transform") and "scale" in str(c1.get("transform")):
        ks.add("fontSize")
    if abs((c0.get("y") or 0) - (c1.get("y") or 0)) > 0.3 or abs((c0.get("x") or 0) - (c1.get("x") or 0)) > 0.3:
        ks.add("pos")
    if c0.get("color") != c1.get("color"):
        ks.add("color")
    if c0.get("fontFamily") != c1.get("fontFamily"):
        ks.add("fontFamily")
    if c0.get("bg") != c1.get("bg") or m0.get("patches") != m1.get("patches") or abs((c0.get("w") or 0) - (c1.get("w") or 0)) > 0.3:
        ks.add("box")
    return ks


def open_caption_row(fr, fl, res):
    """오른쪽 '문구/텍스트' 탭의 '자막' 줄을 펼친다(이미 열려 있으면 그대로 — 다시 누르면 접힌다)"""
    from playwright.sync_api import TimeoutError as PWTimeout
    is_open = fr.evaluate("""()=>{const f=document.querySelector('.layout-a [data-field-key="caption"]');if(!f)return null;const d=f.closest('details');return d?d.open:true}""")
    if is_open:
        return
    try:
        fl.locator("details > summary").filter(has_text="자막").first.click(timeout=3000)
    except PWTimeout:
        res["notes"].append("자막 줄 summary 못 찾음")


def audit_preset(pw, base, pid, name, out: Path, style_card: str = ""):
    from playwright.sync_api import TimeoutError as PWTimeout
    d = out / pid
    d.mkdir(parents=True, exist_ok=True)
    if not style_card:
        http_json(base + "api/select", {"preset": pid})
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 1600})
    pg = ctx.new_page()
    res = {"pid": pid, "name": name, "controls": {}, "notes": []}
    try:
        pg.goto(base, wait_until="networkidle")
        pg.locator("[data-step],.steps button,.steps a").filter(has_text="꾸미기").first.click()
        fr = None
        for _ in range(60):
            fr = next((f for f in pg.frames if "scene-style-ui-showcase" in f.url), None)
            if fr:
                try:
                    if fr.evaluate("()=>!!(window.sceneStyle&&document.querySelector('#a-live-preview'))"):
                        break
                except Exception:
                    pass
            pg.wait_for_timeout(250)
        pg.wait_for_timeout(2500)
        fl = pg.frame_locator('iframe[src*="scene-style-ui-showcase"]')
        prev = fl.locator("#a-live-preview")
        if style_card:   # 대조군: 편집기 왼쪽 '장면' 탭의 기본 틀 카드를 직접 고른다(칼카피 틀이 아닌 고정형)
            fl.get_by_text(style_card, exact=True).first.click()
            pg.wait_for_timeout(1500)
        m = lambda: fr.evaluate(MEASURE_JS)   # noqa: E731
        # ② 본문 장면으로
        cur = m()
        res["hook"] = {"fieldHidden": cur.get("fieldHidden"), "caps": len(cur.get("caps") or [])}
        for _ in range(4):
            if cur.get("scene", 0) >= 1 and cur.get("caps"):
                break
            fl.get_by_text("다음 ›").first.click()
            pg.wait_for_timeout(1500)
            cur = m()
        # 자막 줄 펼치기(문구/텍스트 탭)
        open_caption_row(fr, fl, res)
        pg.wait_for_timeout(800)
        # 자막박스 크기·색상 접힌 칸 열기(있으면)
        fr.evaluate("""()=>document.querySelectorAll('.layout-a [data-field-key="caption"] details').forEach(x=>x.open=true)""")
        pg.wait_for_timeout(300)
        cur = m()
        res.update(frame=cur.get("frame"), mode=cur.get("mode"), spec=cur.get("spec"), scene=cur.get("scene"), kind=cur.get("kind"),
                   fieldHidden=cur.get("fieldHidden"), noteShown=cur.get("noteShown"), caps=cur.get("caps"))
        pg.screenshot(path=str(d / "0_화면.png"))
        if cur.get("caps"):
            fl.locator('#a-live-preview [data-edit-bind="caption"]').first.screenshot(path=str(d / "0_자막요소.png"))
            res["selector_matches_text"] = (cur["caps"][0]["text"].replace("\n", "").replace(" ", "") ==
                                            (cur.get("taValue") or "").replace("\n", "").replace(" ", ""))
        if not cur.get("caps"):
            res["status"] = "자막 안 보임"
            for c in CONTROLS:
                res["controls"][c[0]] = "자막 안 보임"
            return res

        def shot(tag):
            p = d / f"{tag}.png"
            prev.screenshot(path=str(p))
            return p

        # ③ 무변경 대조
        p0, m0 = shot("무변경_전"), m()
        pg.wait_for_timeout(1500)
        p1, m1 = shot("무변경_후"), m()
        r = pix_ratio(p0, p1)
        ks = changed_keys(m0, m1)
        res["null"] = {"pix": round(r, 5), "keys": sorted(ks)}
        unstable = r >= PIX_MIN or bool(ks)

        for cname, expect, kind, arg in CONTROLS:
            safe = cname.replace("＋", "plus").replace("↓", "down").replace("(", "_").replace(")", "").replace(" ", "_")
            # 컨트롤 존재·표시 확인
            if kind in ("click2", "click3", "fill", "value"):
                sel = arg if kind in ("click2", "click3") else (arg[0] if kind == "value" else '.layout-a [data-field-key="caption"] [data-bind="caption"]')
                if kind == "value":
                    sel = '.layout-a [data-field-key="caption"] ' + sel
                st = fr.evaluate("""s=>{const e=document.querySelector(s);if(!e)return 'none';const f=e.closest('[data-field-key]');if(f&&f.hidden)return 'hidden';const r=e.getBoundingClientRect();return (r.width>0&&r.height>0)?'ok':'invisible'}""", sel)
                if st != "ok":
                    res["controls"][cname] = {"result": "컨트롤 없음", "why": {"none": "입력 없음", "hidden": "자막 칸 숨김", "invisible": "입력이 화면에 안 보임"}[st]}
                    continue
            pa, ma = shot(f"{safe}_전"), m()
            try:
                if kind == "fill":
                    fl.locator('.layout-a [data-field-key="caption"] [data-bind="caption"]').fill(arg)
                elif kind in ("click2", "click3"):
                    for _ in range(2 if kind == "click2" else 3):
                        fl.locator(arg).first.click()
                        pg.wait_for_timeout(250)
                elif kind == "value":
                    # 색 고르개·슬라이더는 운영체제 대화창이라 마우스로 못 연다 — 값을 넣고 input/change 를 쏜다(사용자가 고른 것과 같은 이벤트)
                    fr.evaluate("""([s,v])=>{const e=document.querySelector('.layout-a [data-field-key="caption"] '+s);e.focus();e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))}""", list(arg))
                elif kind == "font":
                    fl.locator(".font-tabs button, .tabs button, button").filter(has_text="폰트").first.click()
                    pg.wait_for_timeout(500)
                    fl.locator('[data-look-target="caption"]').first.click()
                    pg.wait_for_timeout(400)
                    fam0 = ma["caps"][0]["fontFamily"]
                    fams = fr.evaluate("()=>[...document.querySelectorAll('[data-font-one]:not([data-font-one=\"\"])')].map(b=>b.dataset.fontOne)")
                    pick = next((f for f in fams if f and f not in fam0), None)
                    if not pick:
                        res["controls"][cname] = {"result": "컨트롤 없음", "why": "폰트 버튼 없음"}
                        continue
                    fl.locator(f'[data-font-one="{pick}"]').first.click()
                    res["font_pick"] = pick
            except Exception as e:   # 클릭 실패 = 사용자가 못 누르는 컨트롤
                res["controls"][cname] = {"result": "컨트롤 없음", "why": f"조작 실패: {str(e)[:120]}"}
                continue
            pg.wait_for_timeout(1000)
            pb, mb = shot(f"{safe}_후"), m()
            r = pix_ratio(pa, pb)
            ks = changed_keys(ma, mb)
            want = {"text": "text", "fontSize": "fontSize", "pos": "pos", "color": "color", "fontFamily": "fontFamily", "pix": "box"}[expect]
            ok = (want in ks or (expect == "pix" and r >= PIX_MIN)) and r >= PIX_MIN
            c0, c1 = (ma.get("caps") or [{}])[0], (mb.get("caps") or [{}])[0]
            res["controls"][cname] = {"result": "바뀜" if ok else "안 바뀜", "pix": round(r, 5), "keys": sorted(ks),
                                      "before": {k: c0.get(k) for k in ("text", "fontSize", "fontFamily", "color", "x", "y", "w", "bg")},
                                      "after": {k: c1.get(k) for k in ("text", "fontSize", "fontFamily", "color", "x", "y", "w", "bg")},
                                      "shots": [str(pa), str(pb)]}
        res["status"] = "불안정(무변경에도 바뀜)" if unstable else "측정"
        return res
    finally:
        try:
            pg.screenshot(path=str(d / "9_끝.png"))
        except Exception:
            pass
        b.close()


def cell(v):
    if isinstance(v, str):
        return v
    r = v.get("result")
    return r if r != "컨트롤 없음" else f"없음({v.get('why', '')[:10]})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEF_BASE)
    ap.add_argument("--out", default=str(DEF_OUT))
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--positive", default="", help="대조군만 돌림: 편집기 왼쪽 기본 틀 카드 이름(예: '고정 스타일 01')")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    st = http_json(a.base + "api/state")
    orig = st.get("current")
    changed0 = json.dumps(st.get("changed"), sort_keys=True, ensure_ascii=False)
    presets = [(p["id"], p["name"]) for p in st.get("presets", [])]
    if a.positive:
        presets = [("positive", a.positive)]
    elif a.only:
        want = set(a.only.split(","))
        presets = [p for p in presets if p[0] in want]
    from playwright.sync_api import sync_playwright
    results = []
    try:
        with sync_playwright() as pw:
            for pid, name in presets:
                t = time.time()
                try:
                    r = audit_preset(pw, a.base, pid, name, out, style_card=a.positive)
                except Exception as e:
                    r = {"pid": pid, "name": name, "status": f"오류: {str(e)[:200]}", "controls": {}}
                r["sec"] = round(time.time() - t, 1)
                results.append(r)
                print(f"[{len(results)}/{len(presets)}] {name} ({pid}) {r.get('status')} · 무변경 {r.get('null')} · "
                      + " · ".join(f"{k}={cell(v)}" for k, v in r["controls"].items()), flush=True)
    finally:
        if orig:
            http_json(a.base + "api/select", {"preset": orig})
        st2 = http_json(a.base + "api/state")
        print(f"\n프리셋 되돌림: {orig} → 지금 {st2.get('current')} · changed {'그대로' if json.dumps(st2.get('changed'), sort_keys=True, ensure_ascii=False) == changed0 else '바뀜!'}")
    (Path(a.json) if a.json else out / "result.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    names = [c[0] for c in CONTROLS]
    print("\n| 프리셋 | 틀/모드 | 본문 자막 칸 | " + " | ".join(names) + " |")
    print("|" + "---|" * (3 + len(names)))
    bad = 0
    for r in results:
        cells = [cell(r["controls"].get(n, "-")) for n in names]
        bad += sum(1 for c in cells if not c.startswith("바뀜"))
        print(f"| {r['name']} | {r.get('frame')}/{r.get('mode')}{'/칼카피틀' if r.get('spec') else ''} | "
              f"{'숨김' if r.get('fieldHidden') else '보임'} | " + " | ".join(cells) + " |")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
