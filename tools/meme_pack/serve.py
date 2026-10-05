"""감정짤 밈팩 — 후보를 감정 카테고리로 나눠 보고, 지우고, 옮기는 로컬 뷰어.

    py tools/meme_pack/serve.py <작업폴더> [--port 8765] [--no-open]

지우기·이동은 <작업폴더>/state.json 에 바로 저장된다(브라우저를 닫아도 남는다).
  state.json = { "<영상 id>": {"emotion": "<옮긴 카테고리>", "deleted": true|false} }
지우기는 휴지통으로 보내는 것이다 — 영상 파일은 안 지운다(되살리기 가능).
카테고리 목록의 주인은 search.py:EMOTIONS 하나다(여기서 다시 적지 않는다).
"""
import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from search import EMOTIONS  # noqa: E402

WORK = ""
LOCK = threading.Lock()
MIME = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".png": "image/png"}


def _load(name, default):
    p = os.path.join(WORK, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save_state(state):
    p = os.path.join(WORK, "state.json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def items():
    """후보 전체 + 현재 카테고리·휴지통 여부."""
    cands, log, state = _load("candidates.json", {}), _load("fetch_log.json", {}), _load("state.json", {})
    out = []
    for emo, rows in cands.items():
        for r in rows:
            info = log.get(r["id"], {})
            if not info.get("ok"):
                continue
            st = state.get(r["id"], {})
            out.append({"id": r["id"], "title": r.get("title") or "", "views": r.get("views") or 0,
                        "duration": info["duration"], "w": info["w"], "h": info["h"],
                        "source": f'https://www.youtube.com/watch?v={r["id"]}',
                        "origin": emo, "emotion": st.get("emotion") or emo, "deleted": bool(st.get("deleted"))})
    # 이미 잘라 온 짤 묶음(extra_*.json — 예: AGT 심사위원 리액션). 파일이 있고 감정이 목록에 있는 것만 싣는다
    seen = {it["id"] for it in out}
    for name in sorted(os.listdir(WORK)):
        if not (name.startswith("extra_") and name.endswith(".json")):
            continue
        for r in _load(name, []):
            cid = r.get("id")
            if (not cid or cid in seen or r.get("emotion") not in EMOTIONS
                    or not os.path.isfile(os.path.join(WORK, "raw", f"{cid}.mp4"))):
                continue
            seen.add(cid)
            st = state.get(cid, {})
            out.append({"id": cid, "title": r.get("title") or "", "views": r.get("views") or 0,
                        "duration": r.get("duration") or 0, "w": r.get("w") or 0, "h": r.get("h") or 0,
                        "source": r.get("source") or "", "origin": r["emotion"],
                        "emotion": st.get("emotion") or r["emotion"], "deleted": bool(st.get("deleted"))})
    # 국내/해외·실사/애니: 사장님이 고친 값(state.json)이 자동 판정(tags.json)을 이긴다
    tags = _load("tags.json", {})
    for it in out:
        st, tg = state.get(it["id"], {}), tags.get(it["id"], {})
        it["region"] = st.get("region") or tg.get("region") or ""
        it["kind"] = st.get("kind") or tg.get("kind") or ""
    hl = _load("highlights.json", {})
    for it in out:
        h = hl.get(it["id"])
        ok = h and os.path.isfile(os.path.join(WORK, "library", "clips", it["id"] + ".mp4"))
        it["hl"] = {"start": h["start"], "dur": h["dur"], "usable": h.get("usable", True),
                    "what": h.get("what", "")} if ok else None
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 콘솔 조용히
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, rel):
        path = os.path.normpath(os.path.join(WORK, rel))
        if not path.startswith(os.path.normpath(WORK)) or not os.path.isfile(path):
            return self._json({"error": "없는 파일"}, 404)
        size = os.path.getsize(path)
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):  # 영상 탐색용
            a, _, b = rng[6:].partition("-")
            start = int(a) if a else 0
            end = min(int(b), size - 1) if b else size - 1
            code = 206
        self.send_response(code)
        self.send_header("Content-Type", MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream"))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 16, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                return  # 브라우저가 재생을 끊은 것 — 정상

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/items":
            import classify  # 구분 목록의 주인
            self._json({"categories": list(EMOTIONS), "regions": list(classify.REGIONS),
                        "kinds": list(classify.KINDS), "items": items()})
        elif path.startswith(("/raw/", "/sheets/", "/library/")):
            self._file(path.lstrip("/"))
        else:
            self._json({"error": "없는 주소"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self._json({"error": "요청 형식 오류"}, 400)
        ids = [i for i in (req.get("ids") or []) if isinstance(i, str)]
        known = {it["id"] for it in items()}
        if not ids or any(i not in known for i in ids):
            return self._json({"error": "모르는 영상 id"}, 400)
        with LOCK:
            state = _load("state.json", {})
            if path == "/api/nudge":
                # 하이라이트 구간의 주인은 build_pack — 여기는 부르기만 한다
                import build_pack
                dur = {it["id"]: it["duration"] for it in items()}[ids[0]]
                try:
                    h = build_pack.nudge(WORK, ids[0], float(req.get("delta") or 0), dur)
                except Exception as e:
                    return self._json({"error": str(e)}, 400)
                return self._json({"ok": True, "start": h["start"], "dur": h["dur"]})
            if path == "/api/tag":
                import classify
                region, kind = req.get("region"), req.get("kind")
                if (region and region not in classify.REGIONS) or (kind and kind not in classify.KINDS) or not (region or kind):
                    return self._json({"error": "없는 구분"}, 400)
                for i in ids:
                    if region:
                        state.setdefault(i, {})["region"] = region
                    if kind:
                        state.setdefault(i, {})["kind"] = kind
                _save_state(state)
                return self._json({"ok": True, "count": len(ids)})
            if path == "/api/move":
                emo = req.get("emotion")
                if emo not in EMOTIONS:
                    return self._json({"error": "없는 카테고리"}, 400)
                for i in ids:
                    state.setdefault(i, {})["emotion"] = emo
            elif path == "/api/delete":
                for i in ids:
                    state.setdefault(i, {})["deleted"] = True
            elif path == "/api/restore":
                for i in ids:
                    state.setdefault(i, {})["deleted"] = False
            else:
                return self._json({"error": "없는 주소"}, 404)
            _save_state(state)
        self._json({"ok": True, "count": len(ids)})


PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>감정짤 밈팩 고르기</title>
<style>
body{margin:0;background:#111;color:#eee;font-family:'Malgun Gothic',sans-serif}
header{position:sticky;top:0;background:#000;padding:10px 16px;z-index:5;border-bottom:1px solid #333}
h1{font-size:17px;margin:0 0 8px}
#tabs button{background:#222;color:#ddd;border:1px solid #444;border-radius:16px;padding:5px 12px;margin:0 6px 6px 0;font-size:14px;cursor:pointer}
#tabs button.on{background:#ffd84a;color:#000;border-color:#ffd84a;font-weight:bold}
#tabs button.trash{border-color:#a44}
#tabs button.trash.on{background:#e55;color:#fff;border-color:#e55}
#filters{margin:0 0 8px;font-size:13px;color:#aaa}
#filters button{background:#1b1b1b;color:#ccc;border:1px solid #444;border-radius:6px;padding:3px 10px;margin-right:4px;font-size:13px;cursor:pointer}
#filters button.on{background:#7ab8ff;color:#000;border-color:#7ab8ff;font-weight:bold}
#filters span{margin:0 6px 0 14px} #filters span:first-child{margin-left:0}
.tg{display:inline-block;border-radius:4px;padding:0 6px;margin-right:4px;font-size:11px;font-weight:bold;cursor:pointer;border:1px solid #555;color:#ddd;background:#2a2a2a}
.tg.r국내{background:#2d4f8a;border-color:#2d4f8a;color:#fff} .tg.k애니{background:#7a3d8a;border-color:#7a3d8a;color:#fff}
#bar{display:flex;gap:8px;align-items:center;font-size:13px;color:#aaa;flex-wrap:wrap}
#bar select,#bar button,figure select,figure button{background:#2a2a2a;color:#eee;border:1px solid #555;border-radius:6px;padding:4px 8px;font-size:13px;cursor:pointer}
.act button.del,#bar button.del{border-color:#a44!important;color:#f99!important}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;padding:14px 16px}
figure{margin:0;background:#1c1c1c;border-radius:8px;overflow:hidden;border:2px solid transparent;position:relative}
figure.sel{border-color:#ffd84a}
figure input{position:absolute;top:6px;left:6px;width:20px;height:20px;z-index:2;cursor:pointer}
video{width:100%;height:250px;object-fit:contain;background:#000;display:block;cursor:pointer}
figcaption{font-size:12px;padding:6px 8px 2px;color:#bbb;line-height:1.4;min-height:50px}
figcaption b{color:#fff} figcaption a{color:#7ab8ff}
.act{display:flex;gap:6px;padding:4px 8px 8px} .act select{flex:1;min-width:0}
.cut{color:#7dff9a;font-weight:bold} .warn{color:#ffb14a;font-weight:bold}
.nd button{flex:1;font-size:12px!important;padding:3px 4px!important}
#big{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;align-items:center;justify-content:center;z-index:9}
#big video{width:auto;height:92vh;max-width:96vw}
#msg{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:#ffd84a;color:#000;padding:8px 16px;border-radius:8px;font-weight:bold;display:none;z-index:10}
#empty{padding:40px;color:#888;text-align:center}
</style></head><body>
<header><h1>감정짤 밈팩 고르기 <small id="total" style="color:#999;font-weight:normal"></small></h1>
<div id="tabs"></div>
<div id="filters"></div>
<div id="bar"><span id="selcount">선택 0개</span>
<button id="selall">이 화면 전체 선택</button><button id="selnone">선택 해제</button>
<select id="bulkmove"></select><button id="bulkdel" class="del">선택한 것 지우기</button>
<span>· 영상에 마우스 올리면 재생, 클릭하면 크게(소리)</span></div></header>
<div class="grid" id="grid"></div><div id="empty" style="display:none">이 카테고리는 비어 있습니다</div>
<div id="big"><video controls></video></div><div id="msg"></div>
<script>
const TRASH='휴지통'; let cats=[], regions=[], kinds=[], all=[], cur=null, sel=new Set(), fR='', fK='';
const $=id=>document.getElementById(id);
function say(t){const m=$('msg');m.textContent=t;m.style.display='block';clearTimeout(say.t);say.t=setTimeout(()=>m.style.display='none',1600);}
async function load(){const r=await fetch('/api/items');const j=await r.json();cats=j.categories;regions=j.regions;kinds=j.kinds;all=j.items;if(cur===null)cur=cats[0];draw();}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();if(!r.ok||!j.ok){alert('저장 실패: '+(j.error||r.status));return false;}return true;}
function src(it){return it.hl?`/library/clips/${it.id}.mp4?s=${it.hl.start}`:`/raw/${it.id}.mp4`;}
function passF(it){return (!fR||it.region===fR)&&(!fK||it.kind===fK);}
function inCat(it,c){return passF(it)&&(c===TRASH?it.deleted:(!it.deleted&&it.emotion===c));}
function drawFilters(){const f=$('filters');f.innerHTML='';
  const grp=(label,vals,get,set)=>{const s=document.createElement('span');s.textContent=label;f.appendChild(s);
    ['',...vals].forEach(v=>{const b=document.createElement('button');const live=all.filter(i=>!i.deleted);
      const n=v?live.filter(i=>(label==='지역'?i.region:i.kind)===v).length:live.length;
      b.textContent=(v||'전체')+' '+n;b.dataset.f=label+':'+v;if(get()===v)b.classList.add('on');
      b.onclick=()=>{set(v);sel.clear();draw();};f.appendChild(b);});};
  grp('지역',regions,()=>fR,v=>fR=v);grp('종류',kinds,()=>fK,v=>fK=v);
  const un=all.filter(i=>!i.deleted&&(!i.region||!i.kind)).length;if(un){const s=document.createElement('span');s.textContent='· 구분 전 '+un+'개';f.appendChild(s);}}
function draw(){
  drawFilters();const tabs=$('tabs');tabs.innerHTML='';
  [...cats,TRASH].forEach(c=>{const b=document.createElement('button');const n=all.filter(it=>inCat(it,c)).length;
    b.textContent=c.replace('_','·')+' '+n;b.dataset.cat=c;if(c===TRASH)b.classList.add('trash');if(c===cur)b.classList.add('on');
    b.onclick=()=>{cur=c;sel.clear();draw();window.scrollTo(0,0);};tabs.appendChild(b);});
  $('total').textContent='남은 것 '+all.filter(i=>!i.deleted).length+'개 / 전체 '+all.length+'개';
  const opts=c0=>'<option value="">이동…</option>'+cats.filter(c=>c!==c0).map(c=>`<option value="${c}">→ ${c.replace('_','·')}</option>`).join('');
  $('bulkmove').innerHTML=opts(cur).replace('이동…','선택한 것 이동…');
  $('bulkdel').textContent=cur===TRASH?'선택한 것 되살리기':'선택한 것 지우기';
  const list=all.filter(it=>inCat(it,cur)), g=$('grid');g.innerHTML='';
  $('empty').style.display=list.length?'none':'block';
  list.forEach(it=>{const f=document.createElement('figure');f.dataset.id=it.id;if(sel.has(it.id))f.classList.add('sel');
    const esc=s=>s.replace(/[&<>"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
    f.innerHTML=`<input type="checkbox" ${sel.has(it.id)?'checked':''}>
      <video src="${src(it)}" poster="${it.hl?`/library/thumbs/${it.id}.jpg?s=${it.hl.start}`:`/sheets/thumbs/${it.id}.jpg`}" preload="none" muted loop playsinline></video>
      <figcaption><span class="tg r${it.region}" data-t="region" title="누르면 국내↔해외">${it.region||"지역?"}</span><span class="tg k${it.kind}" data-t="kind" title="누르면 실사↔애니">${it.kind||"종류?"}</span><br><b>${esc(it.title)}</b><br>${it.hl?`<span class="cut">✂ ${it.hl.dur.toFixed(1)}초</span> (원본 ${Math.round(it.duration)}초 중 ${it.hl.start.toFixed(1)}초부터)${it.hl.usable?"":` <span class="warn">리액션 불분명</span>`}`:`<span class="warn">아직 안 자름</span> · 원본 ${Math.round(it.duration)}초`} · ${it.w}×${it.h} · <a href="${esc(it.source)}" target="_blank">출처</a></figcaption>
      ${it.hl?`<div class="act nd"><button data-d="-0.5">◀ 0.5초 앞</button><button data-d="0.5">0.5초 뒤 ▶</button><button class="full">전체 보기</button></div>`:""}
      <div class="act"><select class="mv">${cur===TRASH?'<option value="">(휴지통)</option>':opts(it.emotion)}</select>
      <button class="${cur===TRASH?'rs':'del'}">${cur===TRASH?'되살리기':'지우기'}</button></div>`;
    f.querySelectorAll('.tg').forEach(t=>t.onclick=async()=>{const key=t.dataset.t,vals=key==='region'?regions:kinds;
      const next=vals[(vals.indexOf(it[key])+1)%vals.length];
      if(await post('/api/tag',{ids:[it.id],[key]:next})){it[key]=next;say(next+' 로 바꿈');draw();}});
    const v=f.querySelector('video');
    f.querySelectorAll('.nd button[data-d]').forEach(b=>b.onclick=async()=>{b.disabled=true;
      const r=await fetch('/api/nudge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids:[it.id],delta:parseFloat(b.dataset.d)})});
      const j=await r.json();if(!r.ok||!j.ok){alert('다시 자르기 실패: '+(j.error||r.status));b.disabled=false;return;}
      it.hl.start=j.start;say('다시 잘랐습니다: '+j.start.toFixed(1)+'초부터');draw();});
    const fb=f.querySelector('.full');if(fb)fb.onclick=()=>{const b=$('big'),bv=b.querySelector('video');bv.src='/raw/'+it.id+'.mp4';b.style.display='flex';bv.muted=false;bv.play();};
    v.onmouseenter=()=>v.play().catch(()=>{});v.onmouseleave=()=>v.pause();
    v.onclick=()=>{const b=$('big'),bv=b.querySelector('video');bv.src=v.src;b.style.display='flex';bv.muted=false;bv.play();};
    f.querySelector('input').onchange=e=>{e.target.checked?sel.add(it.id):sel.delete(it.id);f.classList.toggle('sel',e.target.checked);upd();};
    f.querySelector('.mv').onchange=async e=>{const to=e.target.value;if(!to)return;if(await post('/api/move',{ids:[it.id],emotion:to})){it.emotion=to;sel.delete(it.id);say('→ '+to.replace('_','·')+' 로 이동');draw();}};
    f.querySelector('.act:not(.nd) button').onclick=async()=>{const back=cur===TRASH;if(await post(back?'/api/restore':'/api/delete',{ids:[it.id]})){it.deleted=!back;sel.delete(it.id);say(back?'되살림':'휴지통으로');draw();}};
    g.appendChild(f);});
  upd();
}
function upd(){$('selcount').textContent='선택 '+sel.size+'개';}
$('selall').onclick=()=>{all.filter(it=>inCat(it,cur)).forEach(it=>sel.add(it.id));draw();};
$('selnone').onclick=()=>{sel.clear();draw();};
$('bulkmove').onchange=async e=>{const to=e.target.value;if(!to)return;if(!sel.size){say('먼저 체크하세요');e.target.value='';return;}
  const ids=[...sel];if(await post('/api/move',{ids,emotion:to})){all.forEach(it=>{if(sel.has(it.id)){it.emotion=to;}});say(ids.length+'개 → '+to.replace('_','·'));sel.clear();draw();}};
$('bulkdel').onclick=async()=>{if(!sel.size){say('먼저 체크하세요');return;}const back=cur===TRASH,ids=[...sel];
  if(await post(back?'/api/restore':'/api/delete',{ids})){all.forEach(it=>{if(sel.has(it.id))it.deleted=!back;});say(ids.length+'개 '+(back?'되살림':'휴지통으로'));sel.clear();draw();}};
$('big').onclick=e=>{if(e.target.id==='big'){e.currentTarget.querySelector('video').pause();e.currentTarget.style.display='none';}};
load();
</script></body></html>"""


def main():
    global WORK
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    WORK = os.path.abspath(a.work)
    url = f"http://127.0.0.1:{a.port}/"
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    except OSError:
        # 이미 켜져 있다(바로가기를 두 번 누른 경우) — 새로 띄우지 말고 켜져 있는 화면을 연다
        print(f"이미 켜져 있습니다: {url}")
        if not a.no_open:
            webbrowser.open(url)
        return
    print(f"감정짤 뷰어: {url}  (이 창을 닫으면 꺼집니다)")
    if not a.no_open:
        webbrowser.open(url)
    srv.serve_forever()


if __name__ == "__main__":
    main()
