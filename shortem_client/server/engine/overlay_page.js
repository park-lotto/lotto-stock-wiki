// 브라우저 안에서 도는 그리기 코드(문자열로 페이지에 넣는다). 라이브 렌더러 out/precision20-ui.js 의
// renderSpec·specTexts·runCaptionEnter 와 같은 규칙으로 그린다:
//   글자 층 자리 = x·align 가로 기준, y = 첫 줄 칸 위 끝, 줄 칸 높이 = line_h, 칸 폭 넘으면 0.97 배씩 줄임(바닥 40%)
//   외곽선 = -webkit-text-stroke 2×px + paint-order stroke fill · 그림자·글로우(px/4·px/2·px 세 겹) · 상자 = 안쪽 span 배경
//   자막 등장 = CAPTION_MOTIONS(Web Animations, 멈춘 채 currentTime 으로 찍는다 — 아무 프레임이나 같은 그림)
export const PAGE_JS = String.raw`
(function(){
const D = window.__DATA__;            // {W,H,frames,scenes,title,motions,wordFx,fonts}
const stage = document.getElementById('stage');
const rgb = c => 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
const ALIAS = { typewriter: 'typing' };
const TITLE_FLASH = { ms: 520, easing: 'linear', frames: [{opacity:0},{opacity:1,offset:.12},{opacity:.25,offset:.26},{opacity:1,offset:.4},{opacity:.6,offset:.55},{opacity:1}] };
function motionOf(kind){ if(!kind) return null; if(kind==='flash') return TITLE_FLASH; const k = ALIAS[kind] || kind; return D.motions[k] || null; }
function frameById(id){ return D.frames.find(f => f.id === id) || D.frames[0]; }
function el(tag, cls, css){ const e = document.createElement(tag); if(cls) e.className = cls; if(css) Object.assign(e.style, css); return e; }
function outlineOf(l, n){ if (Array.isArray(l.line_outline)) { const o = l.line_outline[n]; return o ? { px: o[0], rgb: o.slice(1) } : null; } return l.outline; }

function drawBase(layers, off){
  if (off) return null;
  const v = layers.find(l => l.kind === 'video');
  for (const l of layers){
    if (l.kind === 'bg'){
      if (!v){ stage.append(el('div','', {position:'absolute',left:0,top:0,width:D.W+'px',height:D.H+'px',background:rgb(l.rgb)})); continue; }
      // 영상 창만 비우고 나머지를 바탕색으로 — 둥근 창이면 큰 그림자로 가장자리까지 칠한다
      const hole = el('div','', {position:'absolute',left:v.x+'px',top:v.y+'px',width:v.w+'px',height:v.h+'px',borderRadius:(v.radius||0)+'px',boxShadow:'0 0 0 '+(D.W+D.H)*2+'px '+rgb(l.rgb)});
      const clip = el('div','', {position:'absolute',left:0,top:0,width:D.W+'px',height:D.H+'px',overflow:'hidden'});
      clip.append(hole); stage.append(clip);
    } else if (l.kind === 'band'){
      const b = el('div','', {position:'absolute',left:l.x+'px',top:l.y+'px',width:l.w+'px',height:l.h+'px',background:rgb(l.rgb),borderRadius:(l.radius||0)+'px'});
      if (l.grad_x && l.grad_x.length > 1) b.style.background = 'linear-gradient(90deg,' + l.grad_x.map(s => rgb(s[1]) + ' ' + (s[0]*100).toFixed(2) + '%').join(',') + ')';
      if (l.fade && (l.fade[0] || l.fade[1])){ const m = 'linear-gradient(180deg,transparent 0,#000 '+(l.fade[0]/l.h*100)+'%,#000 '+(100-l.fade[1]/l.h*100)+'%,transparent 100%)'; b.style.webkitMaskImage = m; b.style.maskImage = m; }
      stage.append(b);
    } else if (l.kind === 'image'){
      const im = el('img','', {position:'absolute',left:l.x+'px',top:l.y+'px',width:l.w+'px',height:l.h+'px',objectFit:'contain'}); im.src = l.src; stage.append(im);
    }
  }
  return v;
}

// 글을 단위(span)로 — 강조 낱말(.wfx-w)·글자(.cap-c)·어절(.cap-w)
function fillInk(ink, text, opt){
  ink.textContent = '';
  const lines = String(text).split('\n');
  let wordNo = 0;
  lines.forEach((line, li) => {
    if (li) ink.append(document.createElement('br'));
    const words = line.split(/(\s+)/);
    for (const part of words){
      if (!part) continue;
      if (/^\s+$/.test(part)){ ink.append(document.createTextNode(part)); continue; }
      const w = el('span','wfx-w cap-w'); w.dataset.no = String(wordNo);
      if (opt.listEmph && opt.listEmph.test(part)) { w.classList.add('emph-list'); }
      if (opt.unit === 'char') { for (const ch of [...part]){ const c = el('span','cap-c'); c.textContent = ch; w.append(c); } }
      else w.textContent = part;
      ink.append(w); wordNo++;
    }
  });
  return wordNo;
}

function textItems(l, scene){
  if (l.role === 'title'){ const ts = String(D.title||'').split('\n'); const out = []; for (let n = 0; n < l.lines; n++) out.push({ text: (ts[n]||'').trim(), n, rows: 1 }); return out; }
  if (l.role === 'caption') return scene && scene.caption ? [{ text: scene.caption.trim(), n: 0, rows: l.lines }] : [];
  return [{ text: String(l.text||'').split('\n').join(' '), n: 0, rows: 1 }];
}

function drawText(l, scene, tLocal, tGlobal, metrics){
  const x0 = l.align === 'center' ? l.x - l.w/2 : l.align === 'left' ? l.x : l.x - l.w;
  let enterMs = 0;
  for (const it of textItems(l, scene)){
    if (!it.text) continue;
    const color = rgb(l.line_rgb && l.line_rgb[it.n] ? l.line_rgb[it.n] : l.rgb);
    const size0 = l.size * ((l.line_scale && l.line_scale[it.n]) || 1);
    const o = outlineOf(l, it.n);
    const shadows = [l.shadow ? l.shadow.dx+'px '+l.shadow.dy+'px '+l.shadow.blur+'px '+rgb(l.shadow.rgb) : '', ...(l.glow ? [.25,.5,1].map(k => '0 0 '+(l.glow.px*k)+'px '+rgb(l.glow.rgb)) : [])].filter(Boolean).join(',') || 'none';
    const e = el('div','precision-text spec-text', {left:x0+'px',width:l.w+'px',top:(l.y+it.n*l.line_h)+'px',height:(l.line_h*it.rows)+'px',
      fontFamily:'"'+l.font+'",sans-serif',fontWeight:'400',fontStyle:l.italic?'italic':'normal',fontSynthesis:l.italic?'style':'none',fontSize:size0+'px',
      letterSpacing:l.letter_spacing+'px',wordSpacing:(l.word_spacing||0)+'px',lineHeight:l.line_h+'px',color:color,textAlign:l.align,
      justifyContent:{left:'flex-start',center:'center',right:'flex-end'}[l.align],alignItems:l.valign==='top'?'flex-start':'center',whiteSpace:it.rows>1?'pre-line':'nowrap',wordBreak:'keep-all',
      webkitTextStroke:o&&o.px>0?(2*o.px)+'px '+rgb(o.rgb):'0px',paintOrder:'stroke fill',textShadow:shadows});
    e.dataset.role = l.role;
    // 글은 언제나 span 하나(ink) 안에 — 플렉스 칸의 직접 자식이면 낱말 사이 공백이 사라진다
    const ink = el('span','spec-ink', l.box ? {background:rgb(l.box.rgb),padding:'0 '+l.box.pad+'px',borderRadius:l.box.radius+'px',boxDecorationBreak:'clone',webkitBoxDecorationBreak:'clone'} : {});
    e.append(ink);
    const isCap = l.role === 'caption';
    const motion = isCap ? motionOf(l.enter && l.enter.kind) : (l.role === 'title' ? motionOf(l.enter && l.enter.kind) : null);
    const em = isCap ? l.emphasis : null;
    const listEmph = em && Array.isArray(em.words) && em.words.length ? new RegExp(em.words.slice().sort((a,b)=>b.length-a.length).map(w => w.replace(/[.*+?^$\{\}()|[\]\\]/g,'\\$&')).join('|')) : null;
    const nWords = fillInk(ink, it.text, { unit: motion && motion.unit, listEmph });
    if (em){
      e.style.setProperty('--wfx-color', rgb(em.rgb));
      e.classList.add('wfx-on', 'wfx-' + (em.style === 'grow' ? 'color' : em.style));
      if (em.words === 'auto' && scene && scene.words){
        // 지금 말하는 낱말 — 장면 시작 뒤 tLocal 에 켜진 마지막 낱말
        let now = 0; scene.words.forEach((w, k) => { if ((w.t0 - scene.t0) * 1000 <= tLocal + 1) now = k; });
        const w = ink.querySelector('.wfx-w[data-no="'+now+'"]'); if (w){ w.classList.add('now'); if (em.style==='grow') w.style.scale = '1.15'; }
        const def = D.wordFx[em.style]; const st = scene.words[now] ? (scene.words[now].t0 - scene.t0) * 1000 : 0;
        if (def && def.draw) e.style.setProperty('--wfx-p', String(Math.min(1, Math.max(0, (tLocal - st) / (def.draw * 1000)))));
      } else if (listEmph){
        ink.querySelectorAll('.emph-list').forEach(w => { w.classList.add('now'); if (em.style==='grow') w.style.scale = '1.15'; });
      }
    }
    stage.append(e);
    // 칸 폭(w) 넘으면 줄인다 — 잘리거나 칸 밖으로 나가지 않게(바닥 40%)
    const over = () => { if (it.rows > 1) return e.scrollHeight > e.clientHeight + 1; const r = document.createRange(); r.selectNodeContents(e); return Math.max(e.scrollWidth, r.getBoundingClientRect().width) > e.clientWidth + 1; };
    let size = size0; while (over() && size > size0 * .4){ size *= .97; e.style.fontSize = size + 'px'; }
    // 등장 효과 — 멈춘 애니메이션을 그 시각으로
    const t = l.role === 'title' ? tGlobal : tLocal;
    if (motion && (l.role === 'caption' || l.role === 'title')){
      const units = motion.unit === 'char' ? [...e.querySelectorAll('.cap-c')] : motion.unit === 'word' ? [...e.querySelectorAll('.cap-w')] : [ink];
      const T = e.getBoundingClientRect(), cx = T.left + T.width/2, cy = T.top + T.height/2, ms = motion.ms || 300;
      const step = units.length > 1 ? Math.min(motion.stagger || 0, (motion.spread != null ? motion.spread : Infinity) / (units.length - 1)) : 0, mid = (units.length - 1)/2;
      units.forEach((u, k) => {
        if (u !== e && getComputedStyle(u).display === 'inline') u.style.display = 'inline-block';
        if (motion.origin === true){ const r = u.getBoundingClientRect(); u.style.transformOrigin = (cx - r.left) + 'px ' + (cy - r.top) + 'px'; }
        else if (typeof motion.origin === 'string') u.style.transformOrigin = motion.origin;
        const frames = motion.spreadX ? motion.frames.map(f => { const g = Object.assign({}, f); const sk = g.spreadK || 0; delete g.spreadK; g.translate = ((k - mid) * motion.spreadX * sk).toFixed(3) + 'em 0'; return g; }) : motion.frames;
        const a = u.animate(frames, { duration: ms, delay: k * step, easing: motion.easing || 'cubic-bezier(.2,.8,.3,1)', fill: 'both' });
        a.pause(); a.currentTime = Math.max(0, t);
      });
      const total = Math.ceil((units.length - 1) * step + ms);
      if (isCap) enterMs = Math.max(enterMs, total); else metrics.titleEnterMs = Math.max(metrics.titleEnterMs || 0, total);
    }
    if (isCap){
      const r = e.getBoundingClientRect(), rr = document.createRange(); rr.selectNodeContents(e); const ir = rr.getBoundingClientRect();
      metrics.caption = { text: it.text, fit: Math.round(size/size0*100), inside: ir.left >= -1 && ir.right <= D.W + 1 && ir.top >= -1 && ir.bottom <= D.H + 1, box: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], words: nWords };
    }
    if (l.role === 'title') { metrics.titleFit = Math.min(metrics.titleFit || 100, Math.round(size/size0*100)); }
  }
  return enterMs;
}

// 장면 i 를 장면 시작 뒤 tLocal(ms) 시점으로 그린다. 반환 = 재기(등장 길이·자막 자리)
window.R = {
  show(i, tLocal){
    stage.textContent = '';
    const scene = D.scenes[i];
    const metrics = { off: !!scene.off };
    if (scene.off) return metrics;   // 틀 끈 장면(꼬리): 아무것도 안 그린다 — 영상이 전체 화면
    const fr = frameById(scene.frame);
    drawBase(fr.layers, false);
    const tGlobal = scene.t0 * 1000 + tLocal;
    let enter = 0;
    for (const l of fr.layers) if (l.kind === 'text') enter = Math.max(enter, drawText(l, scene, tLocal, tGlobal, metrics));
    metrics.enterMs = enter;
    return metrics;
  },
  async fontsReady(){
    const res = {};
    for (const f of D.fonts){ try { const got = await document.fonts.load('40px "' + f + '"', '가A1'); res[f] = got.length > 0; } catch(e){ res[f] = false; } }
    await document.fonts.ready; return res;
  },
};
})();
`;

export const PAGE_CSS = `
html,body{margin:0;padding:0;background:transparent}
#stage{position:relative;width:var(--W);height:var(--H);overflow:hidden}
.precision-text{position:absolute;z-index:2;display:flex;align-items:center;overflow:visible;line-height:1;white-space:nowrap;text-rendering:geometricPrecision;-webkit-font-smoothing:antialiased;font-synthesis:none}
.precision-text.wfx-on{isolation:isolate}
.precision-text .wfx-w{position:relative;display:inline-block;transform-origin:50% 60%}
.precision-text .wfx-w.now{z-index:1}
.precision-text.wfx-underline .wfx-w.now::after{content:'';position:absolute;left:-.04em;bottom:-.1em;height:.13em;width:calc((100% + .08em)*var(--wfx-p,1));background:var(--wfx-color);border-radius:.07em}
.precision-text.wfx-highlight .wfx-w.now::before{content:'';position:absolute;z-index:-1;left:-.1em;top:.36em;bottom:-.04em;width:calc((100% + .2em)*var(--wfx-p,1));background:color-mix(in srgb,var(--wfx-color) 72%,transparent);border-radius:.1em;transform:skewX(-10deg)}
.precision-text.wfx-circle .wfx-w.now::after{content:'';position:absolute;left:-.26em;right:-.26em;top:-.2em;bottom:-.2em;border:.075em solid var(--wfx-color);border-radius:50%;transform:rotate(-4deg);-webkit-mask:conic-gradient(from -100deg,#000 calc(var(--wfx-p,1)*360deg),transparent 0);mask:conic-gradient(from -100deg,#000 calc(var(--wfx-p,1)*360deg),transparent 0)}
.precision-text.wfx-glow .wfx-w.now{color:#FFFFFF!important;text-shadow:0 0 .08em #fff,0 0 .18em var(--wfx-color),0 0 .4em var(--wfx-color),0 0 .7em var(--wfx-color)!important}
.precision-text.wfx-box .wfx-w.now::before{content:'';position:absolute;z-index:-1;left:-.16em;right:-.16em;top:-.02em;bottom:-.02em;border-radius:.24em;background:var(--wfx-color)}
.precision-text.wfx-color .wfx-w.now{color:var(--wfx-color)!important}
.cap-c{display:inline-block}
`;
