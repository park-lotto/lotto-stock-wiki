# -*- coding: utf-8 -*-
"""즐겨찾기 분석 신호등 점검(관제 48) — collection.html의 **실제 loadAnalysis/analyzeCodes**를 node로 돌린다.

가짜 서버는 라이브의 두 제약을 그대로 흉내 낸다:
  ① 앞단 Apache: 요청줄이 8190바이트를 넘으면 414(HTML 본문 → .json() 실패)
  ② 앱: analysis_status·analyze 모두 앞 100개만 처리
재료: 조율가님(207) 즐겨찾기 353개 실제 코드와 서버 판정(tools/analysis_status_fixture_207.json, 2026-09-30).
통과 기준: 화면 '분석완료' 수 == 서버 done 수, 414 0건, analyze가 고른 개수 전부를 서버에 넘김.

    py tools/analysis_status_check.py             # 지금 파일
    py tools/analysis_status_check.py <html경로>   # 다른 판(옛 코드로 실패하는지 확인용)
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "shopping_shorts", "static", "collection.html")
FIX = json.load(open(os.path.join(ROOT, "tools", "analysis_status_fixture_207.json"), encoding="utf-8"))
SRC = open(HTML, encoding="utf-8").read()


def grab(pat):
    m = re.search(pat, SRC, flags=re.S)
    return m.group(0) if m else ""


def fn(name):
    m = re.search(r"\n((?:async )?function " + name + r"\([^)]*\)\{)", SRC)
    if not m:
        return ""
    i = m.start(1)
    k = SRC.index("{", i)
    depth = 0
    while True:
        c = SRC[k]
        depth += c == "{"
        depth -= c == "}"
        if c == "}" and depth == 0:
            return SRC[i:k + 1]
        k += 1


CODE = "\n".join([grab(r"const ANALYSIS_BATCH=\d+;"), fn("_chunks"), fn("loadAnalysis"), fn("analyzeCodes")])
JS = """
let ANALYSIS={}; let _pollTimer=null; let SELECTED=new Set();
const FIX=%(fix)s;
let ITEMS=FIX.codes.slice().reverse().map(sc=>({shortcode:sc}));
function render(){} function alert(m){ globalThis.ALERTS.push(m); }
globalThis.ALERTS=[]; const stat={r414:0, statusCalls:0, analyzed:[]};
function setTimeout(){ return 0; } function clearTimeout(){}
global.fetch=async(url,opt)=>{
  const line=((opt&&opt.method)||'GET')+' '+url+' HTTP/1.1';
  if(line.length>8190){ stat.r414++; return {json:async()=>{ throw new SyntaxError('Unexpected token <'); }}; }
  if(url.startsWith('/api/basket/analysis_status')){
    stat.statusCalls++;
    const q=decodeURIComponent(url.split('shortcodes=')[1]||'');
    const codes=q.split(',').filter(Boolean).slice(0,100);
    const items={}; codes.forEach(c=>{ items[c]={state:FIX.state[c]||'idle',reason:''}; });
    return {json:async()=>({ok:true,items})};
  }
  if(url==='/api/basket/analyze'){
    const codes=JSON.parse(opt.body).shortcodes.slice(0,100); stat.analyzed.push(...codes);
    const items={}; codes.forEach(c=>items[c]='queued');
    return {json:async()=>({ok:true,items,note:''})};
  }
  throw new Error('unknown '+url);
};
%(code)s
(async()=>{
  await loadAnalysis();
  const shown=Object.values(ANALYSIS).filter(v=>v.state==='done').length;
  const pick=ITEMS.slice(0,250).map(i=>i.shortcode);
  await analyzeCodes(pick);
  console.log(JSON.stringify({shown_done:shown, r414:stat.r414, statusCalls:stat.statusCalls,
    analyzed:new Set(stat.analyzed).size, picked:pick.length}));
})().catch(e=>console.log(JSON.stringify({error:String(e)})));
"""


def main():
    js = JS % {"fix": json.dumps(FIX, ensure_ascii=False), "code": CODE}
    f = os.path.join(tempfile.gettempdir(), "analysis_status_check.js")
    open(f, "w", encoding="utf-8").write(js)
    r = subprocess.run(["node", f], capture_output=True, text=True, encoding="utf-8",
                       stdin=subprocess.DEVNULL, timeout=60)
    out = json.loads((r.stdout.strip().splitlines() or ["{}"])[-1])
    want = sum(1 for v in FIX["state"].values() if v == "done")
    checks = [
        ("화면 분석완료 = 서버 done(%d)" % want, out.get("shown_done") == want),
        ("414 0건", out.get("r414") == 0),
        ("analyze 고른 %d개 전부 전달" % out.get("picked", 0), out.get("analyzed") == out.get("picked")),
    ]
    print(json.dumps(out, ensure_ascii=False))
    for name, ok in checks:
        print(("OK  " if ok else "FAIL"), name)
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
