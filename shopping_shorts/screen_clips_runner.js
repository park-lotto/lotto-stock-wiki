// 편집 화면 컷 계산(scene_play.js planClips)을 **그대로** 서버에서 돌린다 — 완성본·캡컷·청소본이 화면과 같은 컷을 쓰게.
// 서버 편성을 얹는 법은 scene_lab.html restoreServer 와 같다(목록=scene_override 조각 · 구절 맞춤 끔 · 손 컷 · 느리게 · 손 길이).
// 사용: node screen_clips_runner.js <scene_play.js> <data.json>  → stdout: [[{v,s,d,sd,fit}], ...] (칸 순서)
const fs = require('fs'), vm = require('vm');
const [,, jsPath, dataPath] = process.argv;
const noop = () => {}; const el = new Proxy(function(){}, {get: (t,k) => k === Symbol.toPrimitive ? () => '' : el, apply: () => el, set: () => true});
const ctx = {console, Math, JSON, Number, String, Array, Object, Set, Map, Date, parseFloat, parseInt, isFinite, Promise,
  setTimeout: noop, setInterval: noop, clearInterval: noop, clearTimeout: noop, requestAnimationFrame: noop, fetch: () => new Promise(noop),
  localStorage: {getItem: () => null, setItem: noop, removeItem: noop}, location: {search: '', href: ''}, navigator: {userAgent: 'node'},
  document: {getElementById: () => null, querySelector: () => null, querySelectorAll: () => [], addEventListener: noop, createElement: () => el, body: el, documentElement: el},
  addEventListener: noop, performance: {now: () => 0}};
ctx.window = ctx; ctx.self = ctx;
vm.createContext(ctx);
const src = fs.readFileSync(jsPath, 'utf8');
const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
const driver = `
DATA = __DATA__;
const _sl = b => { const ov = b && b.scene_override; if (!ov || !ov.length) return null; const o=[]; ov.forEach(s=>{const id=s&&s.seg_id; if(id&&!o.includes(id)) o.push(id)}); return o.length?o:null; };
lists = DATA.beats.map(b => _sl(b) || [b.primary && b.primary.seg_id].concat((b.alternates||[]).map(a=>a.seg_id)).filter(Boolean));
DATA.beats.forEach((b,i) => { if (b.phrase_sync === false) PHRASE_SYNC[i] = false;
  if (Array.isArray(b.manual_cuts)) CUTS[i] = b.manual_cuts.filter(c=>c&&c.seg_id&&c.dur>0).map(c=>c.lock?{seg_id:c.seg_id,dur:+c.dur,lock:1}:{seg_id:c.seg_id,dur:+c.dur});
  if (+b.slow > 1) SLOW[i] = +b.slow;
  for (const [sid,v] of Object.entries(b.fixed_lens||{})) FIXLEN[i+':'+sid] = v; });
__OUT__ = DATA.beats.map((b,i) => ({t: beatDur(i), c: planClips(lists[i] || [], beatDur(i), STRETCH[i], i).map(c => ({v:c.video_id, s:+(+c.start).toFixed(4), d:+(+c.dur).toFixed(4), sd: c.src_dur!=null ? +(+c.src_dur).toFixed(4) : null, fit: c.fit ? 1 : 0}))}));
`;
ctx.__DATA__ = data;
vm.runInContext(src + '\n;' + driver, ctx, {filename: 'scene_play.js'});
console.log(JSON.stringify(ctx.__OUT__));
