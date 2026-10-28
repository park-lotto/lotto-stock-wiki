// 인포크 번호 제안 점검(2026-09-23): 제품 못 잡은 영상에서 '연결하기→저장' 뒤에도
// '내 마지막 번호+1'이 번호칸에 남는지. 사용: node tools/check_inpock_suggest.js shopping_shorts/static/produce.html
// 기대: open 후 suggestNo = 2 / 번호칸 value = "2" (고치기 전 코드는 0 / "")
const fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const a=src.indexOf('let COUPANG={'), b=src.indexOf('// ── 쿠팡 연결 끝 ── COUPANG-END');
const code=src.slice(a,b);
const els={};
const mk=id=>els[id]||(els[id]={id,innerHTML:'',textContent:'',value:''});
globalThis.document={getElementById:id=>mk(id),createElement:()=>({})};
globalThis.esc=s=>String(s==null?'':s);globalThis.toast=()=>{};globalThis.stepName=()=>'8단계';
globalThis.ErrorHelp={text:()=>'net'};globalThis.MIX_JOB='job1';globalThis.COUPANG_UI='쿠팡';
mk('cpUrl').value='https://www.coupang.com/vp/products/1';mk('cpName').value='모형케이크';
mk('cpPartner').value='https://link.coupang.com/a/x';
const dm={listing_name:'모형케이크',dm_title:'t',dm_button:'b',dm_desc:'d',number:''};
globalThis.fetch=async()=>({ok:true,json:async()=>({ok:true,product:{url:'u',name:'모형케이크',partner_url:'https://link.coupang.com/a/x',inpock_number:''},dm_set:dm,suggest_number:2})});
(0,eval)(code+';globalThis.__c={renderCoupangSlot,coupangOpen,coupangSave,coupangDmSet,get C(){return COUPANG}}');
(async()=>{
  const c=globalThis.__c;
  c.renderCoupangSlot({affiliate_target:'',product:null,suggest_number:2});
  c.coupangOpen();
  console.log('open 후 suggestNo =',c.C.suggestNo);
  await c.coupangSave({});
  const h=c.coupangDmSet();
  console.log('번호칸 value =',JSON.stringify((h.match(/id="inpockNum" value="([^"]*)"/)||[])[1]));
})();
