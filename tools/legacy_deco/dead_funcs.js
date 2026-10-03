// 사용: (acorn 필요) node tools/legacy_deco/dead_funcs.js shopping_shorts/static/produce.html <보호이름목록.txt> [--apply]  — 관제 058 C2(10-03): 43개·391줄 제거에 썼다
// produce.html 인라인 스크립트에서 '파일 어디서도 안 불리는' 최상위 함수 선언을 반복 제거(보호 목록 제외)
const fs=require('fs'),acorn=require('acorn');
const [,,file,protectFile,apply]=process.argv;
const protect=new Set(fs.readFileSync(protectFile,'utf8').split(/\s+/).filter(Boolean));
let src=fs.readFileSync(file,'utf8');const removed=[];
for(let round=0;round<10;round++){
  const blocks=[];const re=/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g;let m;
  while((m=re.exec(src))){const start=m.index+m[0].indexOf('>')+1;blocks.push({start,code:m[1]});}
  const fns=[];
  for(const b of blocks){let ast;try{ast=acorn.parse(b.code,{ecmaVersion:'latest',sourceType:'script',allowReturnOutsideFunction:true});}catch(e){console.error('파싱 실패',e.message);process.exit(2)}
    for(const n of ast.body)if(n.type==='FunctionDeclaration')fns.push({name:n.id.name,s:b.start+n.start,e:b.start+n.end});}
  const dead=fns.filter(f=>{if(protect.has(f.name))return false;const out=src.slice(0,f.s)+src.slice(f.e);return !new RegExp('(?<![\w$])'+f.name.replace(/\$/g,'\$')+'(?![\w$])').test(out);});
  // 같은 이름 두 번 정의 방지: 이름이 여러 번 정의되면 건드리지 않음
  const cnt={};fns.forEach(f=>cnt[f.name]=(cnt[f.name]||0)+1);
  const kill=dead.filter(f=>cnt[f.name]===1);
  if(!kill.length)break;
  kill.sort((a,b)=>b.s-a.s);
  for(const f of kill){let s=f.s;while(s>0&&/[ \t]/.test(src[s-1]))s--;let e=f.e;if(src[e]==='\n')e++;removed.push({name:f.name,lines:src.slice(s,e).split('\n').length-1});src=src.slice(0,s)+src.slice(e);}
}
console.log(JSON.stringify({count:removed.length,lines:removed.reduce((a,r)=>a+r.lines,0),names:removed.map(r=>r.name)}));
if(apply==='--apply')fs.writeFileSync(file,src);
