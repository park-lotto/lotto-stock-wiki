// 60칸 전수: '채널명 칸의 끝'으로 삼을 것이 데이터에 무엇이 있나 — 구분선 / 띠 끝 / 없음.
//   칸 구조로 옮기려면 모든 템플릿에 칸 경계가 하나씩 있어야 한다(2026-09-21 사장님 "다 구분선은 있어야 하는 거 아닌가").
const puppeteer=require('puppeteer');
(async()=>{const b=await puppeteer.launch({headless:true});const p=await b.newPage();
await p.goto(process.env.URL||'http://127.0.0.1:8771/out/scene-style-ui-showcase.html',{waitUntil:'networkidle0'});
const rows=await p.evaluate(()=>{
  const out=[],pct=(v,f)=>Math.round(v/f.height*1000)/10;
  const look=(name,kind,f)=>{
    if(!f)return;const ch=f.channel_box||(f.channel_boxes||[])[0];
    if(!ch){out.push({name,kind,종류:'채널명 없음'});return;}
    const titles=(f.lines||[]).filter(l=>l.bind!=='channel'&&l.bind!=='caption'),firstTitle=titles.length?Math.min(...titles.map(l=>l.y0)):f.height;
    const S=[...(f.surfaces||[]),...(f.boxes||[]),...(f.cleanup_regions||[]).filter(r=>r.role!=='source-footer').map(r=>({...r,x:r.x||0,width:r.width||f.width})),...(f.top_band?[{x:0,y:f.top_band.y0,width:f.width,height:f.top_band.y1-f.top_band.y0+1}]:[])],chMid=ch.y+ch.height/2,chBottom=ch.y+ch.height;
    const line=S.filter(s=>s.height<=2&&s.width>=f.width*.5&&s.y>chMid&&s.y<=firstTitle+2).sort((a,b)=>a.y-b.y)[0];
    const band=S.filter(s=>s.width>=f.width*.8&&s.y<=f.height*.02&&s.height>2&&s.y+s.height>chMid&&s.y+s.height<(f.video_from?.y||f.height)*.92&&s.y+s.height<=firstTitle+2).sort((a,b)=>a.height-b.height)[0];
    const bandEnd=band?band.y+band.height:null;
    out.push({name,kind,종류:line?'구분선':band?'띠 끝':'없음',경계:line?pct(line.y,f):band?pct(bandEnd,f):null,채널끝:pct(chBottom,f),첫제목:pct(firstTitle,f),
      겹침:(line?line.y:bandEnd)!=null&&(line?line.y:bandEnd)>firstTitle+1?'경계가 제목 시작보다 아래':''});
  };
  (window.PRECISION20||[]).forEach(p=>{look(p.name,'훅',p.hook);look(p.name,'본문',p.body);});
  (window.CONTINUOUS20||[]).forEach(p=>look(p.name,'고정',p.frame));
  return out;});
const count={};rows.forEach(r=>{const k=r.kind+' · '+r.종류;count[k]=(count[k]||0)+1;});
console.log('잰 칸',rows.length);Object.entries(count).sort().forEach(([k,v])=>console.log('  ',k.padEnd(16),v));
console.log('--- 구분선 있는 칸');rows.filter(r=>r.종류==='구분선').forEach(r=>console.log('  ',(r.name+' '+r.kind).padEnd(22),'경계',r.경계,'% / 채널명 끝',r.채널끝,'/ 첫 제목',r.첫제목,r.겹침));
console.log('--- 띠 끝만 있는 칸');rows.filter(r=>r.종류==='띠 끝').forEach(r=>console.log('  ',(r.name+' '+r.kind).padEnd(22),'경계',r.경계,'% / 채널명 끝',r.채널끝,'/ 첫 제목',r.첫제목,r.겹침));
console.log('--- 아무것도 없는 칸');console.log('  ',rows.filter(r=>r.종류==='없음').map(r=>r.name+' '+r.kind+'(채널끝 '+r.채널끝+'/제목 '+r.첫제목+')').join(' · '));
await b.close();})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1)});
