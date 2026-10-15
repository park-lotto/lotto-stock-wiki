# -*- coding: utf-8 -*-
"""10단계 SNS 예약 — 중복 물어보기·예약 목록·취소 버튼 점검(관제 114).

produce.html의 **실제 함수**(bufSchedule·bufLoadPosts·bufCancel)를 떼어 node로 돌린다.
서버 응답 모양은 shopping_shorts/tests/test_buffer_posts.py 가 지키는 것과 같다
(중복 판정 자체는 서버 buffer_posts.already_scheduled 한 곳 — 여기서 다시 계산하지 않는다).

    py tools/buffer_dup_ui_check.py        실패하면 rc=1
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, "shopping_shorts", "static", "produce.html"), encoding="utf-8").read()
NAMES = ["bufSchedule", "bufLoadPosts", "bufCancel"]


def fn(name):
    m = re.search(r"\n((?:async )?function " + name + r"\([^)]*\)\{)", SRC)
    assert m, name
    i = m.start(1)
    k = SRC.index("{", SRC.index(")", i))
    depth = 0
    while True:
        c = SRC[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return SRC[i:k + 1]
        k += 1


STATUS = re.search(r"\nvar BUF_STATUS_KO = \{.*?\};", SRC, re.S).group(0)

HARNESS = r"""
const els={};
function el(id){ return els[id] || (els[id]={id, value:'', textContent:'', innerHTML:'', disabled:false, style:{},
  _a:{}, getAttribute(k){return this._a[k]}, }); }
const document={ getElementById:el, querySelector:(q)=> q.indexOf('bufWhen')>=0 ? {value:'at'} : null };
el('bufAt').value='2026-10-04T07:30';
let MIX_JOB='job1';
const BUF={channels:[{id:'yt',service:'youtube',name:'내유튜브'},{id:'ig',service:'instagram',name:'내인스타'}],
           picked:{yt:true,ig:true}, source:'final'};
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'); }
let confirmAnswer=false; const asked=[]; const alerts=[];
function confirm(m){ asked.push(m); return confirmAnswer; }
function alert(m){ alerts.push(m); }
const calls=[]; let reply=null;
global.fetch=async(url,opt)=>{ const b=opt&&opt.body?JSON.parse(opt.body):null; calls.push({url,body:b});
  return {json:async()=>reply(url,b)}; };
%(code)s
const out={};
const DUP={ok:false,results:[
  {channel_id:'yt',ok:false,dup:true,error:'이미',existing:[{post_id:'p1'}]},
  {channel_id:'ig',ok:false,dup:true,error:'이미',existing:[{post_id:'p2'}]}]};
const POSTS={ok:true,posts:[
  {post_id:'p1',channel_id:'yt',due_at:'2026-10-03T22:30:00.000Z',status:'scheduled',link:'',cancellable:true},
  {post_id:'p2',channel_id:'ig',due_at:'2026-10-03T22:30:00.000Z',status:'sent',link:'https://insta/x',cancellable:false}]};
(async()=>{
  // ① 이미 예약된 영상을 또 누름 → 묻는다. '취소'면 force 요청이 나가지 않는다.
  reply=(u,b)=> u.indexOf('/schedule')>=0 ? DUP : POSTS;
  confirmAnswer=false; await bufSchedule();
  out.no_force_calls=calls.filter(c=>c.url.indexOf('/schedule')>=0).map(c=>c.body.force);
  out.no_asked=asked.length; out.no_status=el('bufStatus').innerHTML; out.no_btn=el('btnBufGo').disabled;
  // ② '확인'이면 중복 채널만 force로 다시 보낸다.
  calls.length=0; asked.length=0;
  reply=(u,b)=> u.indexOf('/schedule')<0 ? POSTS : (b.force
      ? {ok:true,results:b.channel_ids.map(i=>({channel_id:i,ok:true,post_id:'n'+i,due_at:'2026-10-03T22:30:00.000Z'}))}
      : {ok:true,results:[{channel_id:'yt',ok:true,post_id:'p9',due_at:''},DUP.results[1]]});
  confirmAnswer=true; await bufSchedule();
  out.yes_calls=calls.filter(c=>c.url.indexOf('/schedule')>=0).map(c=>[c.body.force,c.body.channel_ids]);
  out.yes_status=el('bufStatus').innerHTML;
  // ③ 예약 목록 — 취소 버튼은 cancellable 인 것에만.
  await bufLoadPosts(); out.list=el('bufPosts').innerHTML;
  // ④ 취소 버튼 → post_id 를 보내고 목록을 다시 읽는다.
  calls.length=0; reply=(u,b)=> u.indexOf('/cancel')>=0 ? {ok:true} : {ok:true,posts:[POSTS.posts[1]]};
  const btn={_a:{'data-post':'p1'},getAttribute(k){return this._a[k]},disabled:false,textContent:''};
  await bufCancel(btn);
  out.cancel_calls=calls.map(c=>[c.url.split('?')[0],c.body]); out.list_after=el('bufPosts').innerHTML;
  // ⑤ 취소 거절(이미 올라감) → 고객에게 사유를 보여준다.
  reply=(u,b)=> u.indexOf('/cancel')>=0 ? {ok:false,error:'이미 올라간 게시물'} : POSTS;
  await bufCancel(btn); out.alerts=alerts;
  console.log(JSON.stringify(out));
})();
"""


def main():
    code = STATUS + "\n" + "\n".join(fn(n) for n in NAMES)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(HARNESS % {"code": code})
        path = f.name
    try:
        r = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8")
    finally:
        os.unlink(path)
    if r.returncode != 0:
        print(r.stderr)
        return 1
    o = json.loads(r.stdout.strip().splitlines()[-1])
    checks = [
        ("중복이면 묻는다(1번)", o["no_asked"] == 1),
        ("'취소'면 force 요청이 없다", o["no_force_calls"] == [False]),
        ("'취소'면 다시 올리지 않았다고 보여준다", o["no_status"].count("다시 올리지 않았습니다") == 2),
        ("끝나면 버튼이 다시 켜진다", o["no_btn"] is False),
        ("'확인'이면 중복 채널만 force 로", o["yes_calls"] == [[False, ["yt", "ig"]], [True, ["ig"]]]),
        ("'확인' 뒤 두 채널 다 예약 완료 표시", o["yes_status"].count("예약 완료") == 2),
        ("예약 목록 2건", "<b>2</b>건" in o["list"]),
        ("취소 버튼은 예약됨 1건에만", o["list"].count("bufCancel(this)") == 1 and 'data-post="p1"' in o["list"]),
        ("올라간 글은 링크로", "올라간 글 보기" in o["list"] and "https://insta/x" in o["list"]),
        ("취소는 post_id 를 보낸다", o["cancel_calls"][0] == ["/api/buffer/cancel", {"post_id": "p1"}]),
        ("취소 뒤 목록을 다시 읽는다", o["cancel_calls"][1][0] == "/api/buffer/posts"
         and "bufCancel(this)" not in o["list_after"]),
        ("취소 거절 사유를 보여준다", o["alerts"] == ["이미 올라간 게시물"]),
    ]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("OK  " if ok else "FAIL"), n)
    if bad:
        print(json.dumps(o, ensure_ascii=False, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
