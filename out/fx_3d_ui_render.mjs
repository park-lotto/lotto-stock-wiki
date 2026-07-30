import puppeteer from 'puppeteer';
import fs from 'fs'; import path from 'path';
import http from 'http';

// file:// 는 ES 모듈 CORS로 막히므로 로컬 정적서버로 서빙한다
const MIME = {'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.png':'image/png','.json':'application/json'};
const server = http.createServer((req,res)=>{
  const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/,'') || 'scene.html';
  const f = path.resolve(rel);
  if(!f.startsWith(process.cwd()) || !fs.existsSync(f) || fs.statSync(f).isDirectory()){ res.writeHead(404); return res.end('nf'); }
  res.writeHead(200,{'Content-Type': MIME[path.extname(f)] || 'application/octet-stream'});
  fs.createReadStream(f).pipe(res);
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const PORT = server.address().port;
console.log('server http://127.0.0.1:'+PORT);

const dir = path.resolve('frames');
fs.rmSync(dir,{recursive:true,force:true}); fs.mkdirSync(dir,{recursive:true});

const b = await puppeteer.launch({headless:'new',
  args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader',
        '--enable-unsafe-swiftshader','--disable-lcd-text','--force-device-scale-factor=1']});
const p = await b.newPage();
p.on('console', m => { const t=m.text(); if(!t.includes('devtools')) console.log('[page]', t); });
p.on('pageerror', e => console.log('[pageerror]', e.message));
await p.setViewport({width:1920, height:1080, deviceScaleFactor:1});
await p.goto(`http://127.0.0.1:${PORT}/scene.html`, {waitUntil:'load'});

await p.waitForFunction('window.__ready===true', {timeout:30000});
await p.waitForFunction('window.__texReady===true', {timeout:30000});
const meta = await p.evaluate(()=>window.__meta);
console.log('meta', JSON.stringify(meta));

const canvas = await p.$('canvas');
for(let i=0;i<meta.frames;i++){
  const t = i/meta.FPS;
  await p.evaluate(tt=>window.__render(tt), t);
  await canvas.screenshot({path: path.join(dir, String(i).padStart(4,'0')+'.png')});
  if(i%30===0) console.log('frame', i, '/', meta.frames);
}
console.log('done', meta.frames);
await b.close();
server.close();
