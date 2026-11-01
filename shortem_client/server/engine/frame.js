// 장면 규격(frame) 정규화 — 서버 bundle.frame(= 프리셋 frame.json 에서 sources·bench 원값만 뺀 것)을 그리기 값으로.
//   층 스키마는 shopping_shorts/calcopy_frame/schema.py 와 같다(kind bg·video·band·text·image, role title·caption·brand·label).
//   서버가 못 채운 "$per_video" 는 여기서 기본값으로 — 판단 주인은 normalizeFrame() 한 곳.
export const PER_VIDEO = '$per_video';
const isPV = v => v === PER_VIDEO;
const num = (v, d, lo = -1e5, hi = 1e5) => (typeof v === 'number' && Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : d);
const rgbOk = v => Array.isArray(v) && v.length === 3 && v.every(c => Number.isInteger(c) && c >= 0 && c <= 255);
const lum = c => (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255;

function textLayer(L, ctx) {
  const { W, H, bgRgb, video, fonts, title } = ctx;
  const role = ['title', 'caption', 'brand', 'label'].includes(L.role) ? L.role : 'label';
  const o = { kind: 'text', role };
  o.align = ['left', 'center', 'right'].includes(L.align) ? L.align : 'center';
  o.w = num(isPV(L.w) ? null : L.w, W - 80, 1, 2 * W);
  o.x = num(isPV(L.x) ? null : L.x, o.align === 'center' ? W / 2 : o.align === 'left' ? 40 : W - 40, -W, 2 * W);
  o.lines = Math.round(num(isPV(L.lines) ? null : L.lines, role === 'title' ? 2 : 1, 1, 4));
  const defSize = role === 'title' ? 96 : role === 'caption' ? 66 : 40;
  o.size = num(isPV(L.size) ? null : L.size, defSize, 4, 600);
  o.line_h = num(isPV(L.line_h) || L.line_h == null ? null : L.line_h, Math.round(o.size * 1.15), 4, 900);
  let y = isPV(L.y) ? null : L.y;
  if (y == null) {
    if (role === 'title') y = Math.max(40, (video ? video.y : H * 0.2) / 2 - (o.line_h * o.lines) / 2);
    else if (role === 'caption') y = video ? Math.min(H - o.line_h - 40, video.y + video.h + 30) : H * 0.72;
    else y = 30;
  }
  o.y = num(y, 0, -H, 2 * H);
  const font = isPV(L.font) ? null : L.font;
  o.font = font && fonts.has(font) ? font : (fonts.values().next().value || 'sans-serif');
  o.font_missing = !!font && !fonts.has(font);
  o.rgb = rgbOk(L.rgb) ? L.rgb : (lum(bgRgb) < 0.5 ? [255, 255, 255] : [0, 0, 0]);
  o.line_rgb = Array.isArray(L.line_rgb) && L.line_rgb.every(rgbOk) ? L.line_rgb.slice(0, 4) : null;
  o.line_scale = Array.isArray(L.line_scale) && L.line_scale.every(v => typeof v === 'number') ? L.line_scale.slice(0, 4).map(v => Math.min(3, Math.max(0.3, v))) : null;
  o.outline = L.outline && typeof L.outline === 'object' && !isPV(L.outline) && rgbOk(L.outline.rgb) ? { px: num(L.outline.px, 0, 0, 60), rgb: L.outline.rgb } : null;
  o.line_outline = Array.isArray(L.line_outline) ? L.line_outline.slice(0, 4).map(it => (Array.isArray(it) && it.length === 4 ? [num(it[0], 0, 0, 60), it[1] | 0, it[2] | 0, it[3] | 0] : (it && typeof it === 'object' && rgbOk(it.rgb) ? [num(it.px, 0, 0, 60), ...it.rgb] : null))) : null;
  o.shadow = L.shadow && typeof L.shadow === 'object' && !isPV(L.shadow) && rgbOk(L.shadow.rgb) ? { dx: num(L.shadow.dx, 0, -100, 100), dy: num(L.shadow.dy, 0, -100, 100), blur: num(L.shadow.blur, 0, 0, 200), rgb: L.shadow.rgb } : null;
  o.glow = L.glow && typeof L.glow === 'object' && !isPV(L.glow) && rgbOk(L.glow.rgb) ? { px: num(L.glow.px, 1, 1, 200), rgb: L.glow.rgb } : null;
  o.box = L.box && typeof L.box === 'object' && !isPV(L.box) && rgbOk(L.box.rgb) ? { rgb: L.box.rgb, pad: num(L.box.pad, 0, 0, 300), radius: num(L.box.radius, 0, 0, 500) } : null;
  o.italic = L.italic === true;
  o.letter_spacing = num(isPV(L.letter_spacing) ? null : L.letter_spacing, 0, -100, 200);
  o.word_spacing = num(isPV(L.word_spacing) ? null : L.word_spacing, 0, -100, 200);
  o.valign = L.valign === 'top' ? 'top' : 'center';
  const en = isPV(L.enter) ? null : L.enter;
  o.enter = en && typeof en === 'object' && typeof en.kind === 'string' ? { kind: en.kind, ms: num(en.ms, 300, 0, 5000) } : (typeof en === 'string' ? { kind: en, ms: 300 } : null);
  if (o.enter && o.enter.kind === 'none') o.enter = null;
  const em = isPV(L.emphasis) ? null : L.emphasis;
  o.emphasis = em && typeof em === 'object' && (em.words === 'auto' || Array.isArray(em.words)) ? { words: em.words === 'auto' ? 'auto' : em.words.filter(w => typeof w === 'string' && w.trim()).slice(0, 30), rgb: rgbOk(em.rgb) ? em.rgb : [255, 230, 0], style: ['color', 'grow', 'underline', 'highlight', 'circle', 'glow', 'box'].includes(em.style) ? em.style : 'color' } : null;
  if (role === 'title') o.text = title || '';
  else if (role === 'caption') o.text = null;
  else {
    let t = isPV(L.text) ? null : L.text;
    if ((t == null) && L.fill === 'title') t = String(title || '').replace(/\s+/g, ' ').trim();   // 서버가 비운 고정 글 자리 = 이 편 제목
    if (typeof t !== 'string' || !t.trim()) return null;   // 고정 문구를 모르면 그 층은 그리지 않는다
    o.text = t.slice(0, 80);
  }
  return o;
}

function layersOf(list, ctx) {
  const out = [];
  const bg = (list || []).find(l => l && l.kind === 'bg');
  ctx.bgRgb = bg && rgbOk(bg.rgb) ? bg.rgb : [20, 20, 20];
  const v = (list || []).find(l => l && l.kind === 'video');
  ctx.video = v ? { x: num(isPV(v.x) ? null : v.x, 0), y: num(isPV(v.y) ? null : v.y, 420), w: num(isPV(v.w) ? null : v.w, ctx.W, 1), h: num(isPV(v.h) ? null : v.h, 1010, 1), radius: num(v.radius, 0, 0, 500) } : null;
  for (const L of list || []) {
    if (!L || typeof L !== 'object') continue;
    if (L.kind === 'bg') out.push({ kind: 'bg', rgb: ctx.bgRgb });
    else if (L.kind === 'video') out.push({ kind: 'video', ...ctx.video });
    else if (L.kind === 'band') {
      if (!rgbOk(L.rgb) && !Array.isArray(L.grad_x)) continue;
      const b = { kind: 'band', x: num(L.x, 0), y: num(L.y, 0), w: num(L.w, ctx.W, 1), h: num(L.h, 10, 1), rgb: rgbOk(L.rgb) ? L.rgb : [0, 0, 0], radius: num(L.radius, 0, 0, 500) };
      if (Array.isArray(L.grad_x)) b.grad_x = L.grad_x.filter(s => Array.isArray(s) && s.length === 2 && rgbOk(s[1])).map(s => [num(s[0], 0, 0, 1), s[1]]);
      if (Array.isArray(L.fade) && L.fade.length === 2) b.fade = [num(L.fade[0], 0, 0, b.h), num(L.fade[1], 0, 0, b.h)];
      out.push(b);
    } else if (L.kind === 'image') {
      if (typeof L.src !== 'string' || !/^data:image\/(png|jpeg|svg\+xml|webp)[;,]/.test(L.src)) continue;   // 그림은 data: 만(네트워크·파일 경로 없음)
      out.push({ kind: 'image', src: L.src, x: num(L.x, 0), y: num(L.y, 0), w: num(L.w, 100, 1), h: num(L.h, 100, 1) });
    } else if (L.kind === 'text') {
      const t = textLayer(L, ctx);
      if (t) out.push(t);
    }
  }
  return out;
}

// frame(서버 축약본) → {W,H, frames:[{id, span:[a,b|null], layers}], tail_sec, fonts:[family…]}
//   opts: {title, firstSpanEnd(초), fonts:Set(받은 글꼴 family)} — 채널명 등 옵션 합치기는 서버 몫(이미 frame 에 들어 있다)
export function normalizeFrame(frame, opts = {}) {
  const f = frame && typeof frame === 'object' ? frame : {};
  const W = Array.isArray(f.canvas) && Number.isInteger(f.canvas[0]) ? f.canvas[0] : 1080;
  const H = Array.isArray(f.canvas) && Number.isInteger(f.canvas[1]) ? f.canvas[1] : 1920;
  const ctx = { W, H, fonts: opts.fonts || new Set(), title: opts.title || '' };
  let frames;
  if (Array.isArray(f.frames) && f.frames.length) {
    const cut = Number(opts.firstSpanEnd) || 1.5;
    frames = f.frames.slice(0, 4).map((fr, i, all) => {
      let span = Array.isArray(fr.span) && !isPV(fr.span) && fr.span.length === 2 && typeof fr.span[0] === 'number' ? [fr.span[0], typeof fr.span[1] === 'number' ? fr.span[1] : null] : null;
      if (!span) span = all.length === 1 ? [0, null] : i === 0 ? [0, cut] : [cut, i === all.length - 1 ? null : cut + 1e-3];
      return { id: String(fr.id || 'f' + i).slice(0, 20), span, layers: layersOf(fr.layers, ctx) };
    }).sort((a, b) => a.span[0] - b.span[0]);
  } else {
    frames = [{ id: 'main', span: [0, null], layers: layersOf(f.layers, ctx) }];
  }
  const off = f.template_off && typeof f.template_off === 'object' ? f.template_off : null;
  const tail = off && typeof off.tail_sec === 'number' && off.tail_sec > 0 ? Math.min(10, off.tail_sec) : 0;
  const families = new Set();
  frames.forEach(fr => fr.layers.forEach(l => { if (l.kind === 'text') families.add(l.font); }));
  return { W, H, frames, tail_sec: tail, fonts: [...families] };
}

export function framesAt(spec, t) {
  for (const fr of spec.frames) if (fr.span[0] <= t + 1e-6 && (fr.span[1] == null || t + 1e-6 < fr.span[1])) return fr;
  return spec.frames[spec.frames.length - 1];
}

export const videoRect = layers => layers.find(l => l.kind === 'video') || null;
export const captionLayer = layers => layers.find(l => l.kind === 'text' && l.role === 'caption') || null;
export const titleLayer = layers => layers.find(l => l.kind === 'text' && l.role === 'title') || null;

// 기본 틀(자가점검 시험 렌더용 — 프리셋 없이)
export const BASIC_FRAME = Object.freeze({
  canvas: [1080, 1920],
  layers: [
    { kind: 'bg', rgb: [18, 18, 22] },
    { kind: 'video', x: 0, y: 460, w: 1080, h: 1000, radius: 0 },
    { kind: 'text', role: 'title', x: 540, y: 180, w: 1000, align: 'center', lines: 2, font: PER_VIDEO, size: 92, line_h: 104, rgb: [255, 255, 255], line_rgb: [[255, 255, 255], [255, 222, 0]] },
    { kind: 'text', role: 'caption', x: 540, y: 1500, w: 1000, align: 'center', lines: 1, font: PER_VIDEO, size: 70, line_h: 82, rgb: [255, 255, 255], outline: { px: 4, rgb: [0, 0, 0] }, enter: { kind: 'pop', ms: 300 } },
  ],
  template_off: null,
});
