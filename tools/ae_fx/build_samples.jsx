// 에펙 고급효과 견본 — 6개 카테고리 × 3개 = 18개 컴포지션을 만들고 mp4 로 뽑는다 (관제 112, 로컬 시제품).
// 실행: py tools/ae_fx/run_jsx.py tools/ae_fx/build_samples.jsx D:\ae_fx_work\build_done.txt 1800
// 속성은 전부 matchName·순번으로 잡는다 — 이 PC 에펙은 한글판이라 표시 이름이 다르다.
var OUT = "D:/ae_fx_work";
var FONT = "NotoSansKR-Black";
var OM_TEMPLATE = "H.264 - 렌더링 일치 설정 - 15Mbps";
var W = 1080, H = 1920, FPS = 30, DUR = 4;
var ONLY = null;          // build_cfg.txt 의 only=A1,B2 로 일부만 다시 만든다. 없으면 전부
var QUEUE = true;         // 렌더 대기열에 올린다 — 실제 렌더는 aerender (앱 안 render() 는 이 PC 에서 파일을 안 냈다)
(function () {
  var f = new File(OUT + "/build_cfg.txt");
  if (!f.exists) return;
  f.encoding = "UTF-8"; f.open("r"); var body = f.read(); f.close();
  var m = body.match(/only=([A-Za-z0-9,]+)/);
  if (m) ONLY = m[1].split(",");
})();
var LOG = [];
var FOOT = null, FOLDER = null;

function log(s) { LOG.push(s); }
function flush(name) {
  var f = new File(OUT + "/" + name);
  f.encoding = "UTF-8"; f.open("w"); f.write(LOG.join("\n")); f.close();
}

// ── 공통 도구 ─────────────────────────────────────────────
function T(layer) { return layer.property("ADBE Transform Group"); }
function pos(layer) { return T(layer).property("ADBE Position"); }
function scl(layer) { return T(layer).property("ADBE Scale"); }
function opa(layer) { return T(layer).property("ADBE Opacity"); }
function rot(layer) { return T(layer).property("ADBE Rotate Z"); }

function K(prop, arr, infl, hold) {      // arr = [[시각, 값], ...]
  for (var i = 0; i < arr.length; i++) prop.setValueAtTime(arr[i][0], arr[i][1]);
  if (hold) {
    for (var h = 1; h <= prop.numKeys; h++) prop.setInterpolationTypeAtKey(h, KeyframeInterpolationType.HOLD);
    return;
  }
  if (infl === 0) return;                // 0 = 직선
  var n = 1, t = prop.propertyValueType;
  if (t == PropertyValueType.TwoD) n = 2; else if (t == PropertyValueType.ThreeD) n = 3;
  var e = [];
  for (var d = 0; d < n; d++) e.push(new KeyframeEase(0, infl || 75));
  for (var k = 1; k <= prop.numKeys; k++) prop.setTemporalEaseAtKey(k, e, e);
}

function mk(id, label, dur) {
  var c = app.project.items.addComp(id + "_" + label, W, H, 1, dur || DUR, FPS);
  c.parentFolder = FOLDER;
  c.bgColor = [0, 0, 0];
  return c;
}

function bg(comp, inSec, s) {            // 배경 영상(720×1280)을 1080×1920 에 꽉 채운다
  var l = comp.layers.add(FOOT);
  scl(l).setValue([s || 150, s || 150]);
  l.startTime = -inSec;
  if (l.hasAudio) l.audioEnabled = false;
  return l;
}

function txt(comp, s, size, p, col, left) {
  var l = comp.layers.addText(s);
  var dp = l.property("ADBE Text Properties").property("ADBE Text Document");
  var d = dp.value;
  d.resetCharStyle();
  d.font = FONT; d.fontSize = size; d.tracking = -20;
  d.applyFill = true; d.fillColor = col || [1, 1, 1];
  d.applyStroke = true; d.strokeColor = [0, 0, 0]; d.strokeWidth = Math.round(size * 0.11); d.strokeOverFill = false;
  d.justification = left ? ParagraphJustification.LEFT_JUSTIFY : ParagraphJustification.CENTER_JUSTIFY;
  dp.setValue(d);
  pos(l).setValue(p);
  return l;
}

function fx(layer, mn) {                 // 효과 추가 — 다음 효과를 더하면 이 참조는 죽는다. 바로 값을 넣어라
  var par = layer.property("ADBE Effect Parade");
  if (!par.canAddProperty(mn)) { log("  ! 효과 없음: " + mn); return null; }
  return par.addProperty(mn);
}
function fxAt(layer, i) { return layer.property("ADBE Effect Parade").property(i); }

function shadow(layer) {
  var e = fx(layer, "ADBE Drop Shadow");
  if (!e) return;
  e.property(2).setValue(140); e.property(4).setValue(10); e.property(5).setValue(28);
}

function anims(layer) { return layer.property("ADBE Text Properties").property("ADBE Text Animators"); }
function animator(layer, list) {         // list = [[matchName, 값], ...] → 애니메이터 순번
  anims(layer).addProperty("ADBE Text Animator");
  var idx = anims(layer).numProperties;
  for (var i = 0; i < list.length; i++) {
    anims(layer).property(idx).property("ADBE Text Animator Properties").addProperty(list[i][0]).setValue(list[i][1]);
  }
  return idx;
}
function charAnchorCenter(layer) {       // 글자마다 제 가운데에서 커지게
  try {
    layer.property("ADBE Text Properties").property("ADBE Text More Options").property("ADBE Text Anchor Point Align").setValue([0, -45]);
  } catch (e) { log("  ! 글자 기준점: " + e.toString()); }
}

function row(comp, words, y, size, gap) { // 단어마다 레이어 하나 — 가운데 정렬한 한 줄
  var ls = [], rs = [], tot = 0, i;
  for (i = 0; i < words.length; i++) {
    var l = txt(comp, words[i], size, [0, y], [1, 1, 1], true);
    var r = l.sourceRectAtTime(0, false);
    ls.push(l); rs.push(r); tot += r.width;
  }
  tot += gap * (words.length - 1);
  var x = W / 2 - tot / 2, xs = [];
  for (i = 0; i < words.length; i++) {
    pos(ls[i]).setValue([x - rs[i].left, y]);
    xs.push(x);
    x += rs[i].width + gap;
  }
  return { layers: ls, rects: rs, xs: xs };
}
function wordIn(layer, t0) {             // 단어 등장: 살짝 올라오며 나타남
  var p = pos(layer).value;
  K(opa(layer), [[t0, 0], [t0 + 0.18, 100]], 60);
  K(pos(layer), [[t0, [p[0], p[1] + 40]], [t0 + 0.22, [p[0], p[1]]]], 80);
}

function shapeLayer(comp, name) { var l = comp.layers.addShape(); l.name = name; return l; }
function grp(layer) {                    // 새 그룹 → 그룹 순번
  layer.property("ADBE Root Vectors Group").addProperty("ADBE Vector Group");
  return layer.property("ADBE Root Vectors Group").numProperties;
}
function vg(layer, gi) { return layer.property("ADBE Root Vectors Group").property(gi).property("ADBE Vectors Group"); }
function strokeOf(layer, gi, col, w) {
  var s = vg(layer, gi).addProperty("ADBE Vector Graphic - Stroke");
  s.property("ADBE Vector Stroke Color").setValue(col);
  s.property("ADBE Vector Stroke Width").setValue(w);
  s.property("ADBE Vector Stroke Line Cap").setValue(2);
  s.property("ADBE Vector Stroke Line Join").setValue(2);
}
function fillOf(layer, gi, col) {
  vg(layer, gi).addProperty("ADBE Vector Graphic - Fill").property("ADBE Vector Fill Color").setValue(col);
}
function pathOf(layer, gi, verts, ins, outs, closed) {
  var sh = new Shape();
  sh.vertices = verts;
  if (ins) sh.inTangents = ins;
  if (outs) sh.outTangents = outs;
  sh.closed = !!closed;
  vg(layer, gi).addProperty("ADBE Vector Shape - Group").property("ADBE Vector Shape").setValue(sh);
}
function trimOf(layer, gi) { vg(layer, gi).addProperty("ADBE Vector Filter - Trim"); }
function trimEnd(layer, gi) { return vg(layer, gi).property("ADBE Vector Filter - Trim").property("ADBE Vector Trim End"); }
function trimStart(layer, gi) { return vg(layer, gi).property("ADBE Vector Filter - Trim").property("ADBE Vector Trim Start"); }

function vignette(comp, strength) {
  var l = shapeLayer(comp, "vignette");
  var g = grp(l);
  vg(l, g).addProperty("ADBE Vector Shape - Ellipse").property("ADBE Vector Ellipse Size").setValue([2150, 3050]);
  strokeOf(l, g, [0, 0, 0], 760);
  pos(l).setValue([W / 2, H / 2]);
  var e = fx(l, "ADBE Gaussian Blur 2");
  if (e) e.property(1).setValue(300);
  opa(l).setValue(strength || 45);
  return l;
}

// ── A. 자막 등장 (글자 단위) ───────────────────────────────
function A1() {
  var c = mk("A1", "글자 블러 올라오기");
  bg(c, 2);
  var t = txt(c, "겉은 바삭 속은 촉촉", 104, [540, 1300]);
  shadow(t);
  var a = animator(t, [["ADBE Text Position 3D", [0, 90, 0]], ["ADBE Text Opacity", 0], ["ADBE Text Blur", [34, 34]]]);
  anims(t).property(a).property("ADBE Text Selectors").addProperty("ADBE Text Selector");
  var sel = anims(t).property(a).property("ADBE Text Selectors").property(1);
  sel.property("ADBE Text Range Advanced").property("ADBE Text Range Shape").setValue(2);   // 2 = 점점 올라감
  sel.property("ADBE Text Range Advanced").property("ADBE Text Levels Max Ease").setValue(60);
  K(anims(t).property(a).property("ADBE Text Selectors").property(1).property("ADBE Text Percent Offset"), [[0.3, -100], [1.5, 100]], 0);
  return c;
}
function A2() {
  var c = mk("A2", "글자 팝 튕김");
  bg(c, 12);
  var t = txt(c, "이게 진짜 버터쿠키", 108, [540, 1300], [1, 0.9, 0.1]);
  shadow(t);
  charAnchorCenter(t);
  var a = animator(t, [["ADBE Text Scale 3D", [0, 0, 100]]]);
  anims(t).property(a).property("ADBE Text Selectors").addProperty("ADBE Text Expressible Selector");
  anims(t).property(a).property("ADBE Text Selectors").property(1).property("ADBE Text Expressible Amount").expression =
    "var t = time - 0.3 - (textIndex - 1) * 0.06;\n" +
    "var s = t < 0 ? 0 : 1 - Math.exp(-9 * t) * Math.cos(2 * Math.PI * 2.2 * t);\n" +
    "var a = (1 - s) * 100; [a, a, a]";
  return c;
}
function A3() {
  var c = mk("A3", "자간 모이며 등장");
  bg(c, 22);
  var t = txt(c, "한 입 먹으면 끝", 112, [540, 1300]);
  shadow(t);
  var a = animator(t, [["ADBE Text Tracking Amount", 0]]);
  K(anims(t).property(a).property("ADBE Text Animator Properties").property("ADBE Text Tracking Amount"), [[0.3, 90], [1.3, 0]], 85);
  K(opa(t), [[0.3, 0], [0.9, 100]], 60);
  var e = fx(t, "ADBE Gaussian Blur 2");
  if (e) K(e.property(1), [[0.3, 40], [1.0, 0]], 70);
  return c;
}

// ── B. 단어 강조 ──────────────────────────────────────────
function B1() {
  var c = mk("B1", "형광펜 긋기");
  var b = bg(c, 33);
  var r = row(c, ["입안에서", "사르르", "녹아요"], 1300, 92, 26);
  for (var i = 0; i < 3; i++) wordIn(r.layers[i], 0.3 + i * 0.12);
  var w = r.rects[1].width + 36, h = r.rects[1].height;
  var m = shapeLayer(c, "marker");
  var g = grp(m);
  var rc = vg(m, g).addProperty("ADBE Vector Shape - Rect");
  rc.property("ADBE Vector Rect Size").setValue([w, h * 0.62]);
  vg(m, g).property("ADBE Vector Shape - Rect").property("ADBE Vector Rect Position").setValue([w / 2, 0]);
  fillOf(m, g, [1, 0.25, 0.45]);
  pos(m).setValue([r.xs[1] - 18, 1300 + r.rects[1].top + h * 0.66]);
  rot(m).setValue(-1.5);
  K(scl(m), [[1.0, [0, 100]], [1.3, [100, 100]]], 80);
  m.moveBefore(b);                       // 글자 아래, 영상 위
  return c;
}
function B2() {
  var c = mk("B2", "단어 번쩍 글로우");
  bg(c, 43);
  var r = row(c, ["버터", "향이", "미쳤어요"], 1300, 92, 26);
  for (var i = 0; i < 3; i++) wordIn(r.layers[i], 0.3 + i * 0.12);
  var l = r.layers[2], rc = r.rects[2], p = pos(l).value;
  var ax = rc.left + rc.width / 2, ay = rc.top + rc.height / 2;
  T(l).property("ADBE Anchor Point").setValue([ax, ay]);
  // 등장 키가 이미 걸려 있어 위치를 통째로 옮긴다(기준점을 가운데로 옮긴 만큼)
  var pp = pos(l);
  for (var k = 1; k <= pp.numKeys; k++) { var v = pp.keyValue(k); pp.setValueAtKey(k, [v[0] + ax, v[1] + ay]); }
  K(scl(l), [[1.2, [100, 100]], [1.32, [128, 128]], [1.55, [112, 112]]], 70);
  var a = animator(l, [["ADBE Text Fill Color", [1, 1, 1]]]);
  K(anims(l).property(a).property("ADBE Text Animator Properties").property("ADBE Text Fill Color"), [[1.2, [1, 1, 1]], [1.32, [1, 0.92, 0.1]]], 0);
  var e = fx(l, "ADBE Glo2");
  if (e) {
    e.property(2).setValue(55); e.property(3).setValue(70);
    K(e.property(4), [[1.2, 0], [1.32, 2.4], [1.8, 0.9]], 60);
  }
  return c;
}
function B3() {
  var c = mk("B3", "밑줄 그려지기");
  bg(c, 52);
  var r = row(c, ["딱", "한 가지만", "기억하세요"], 1300, 88, 26);
  for (var i = 0; i < 3; i++) wordIn(r.layers[i], 0.3 + i * 0.12);
  var w = r.rects[1].width;
  var u = shapeLayer(c, "underline");
  var g = grp(u);
  pathOf(u, g, [[0, 0], [w, -4]], [[0, 0], [-w / 3, 12]], [[w / 3, 12], [0, 0]], false);
  trimOf(u, g);
  strokeOf(u, g, [1, 0.9, 0.1], 16);
  pos(u).setValue([r.xs[1], 1300 + 34]);
  K(trimEnd(u, g), [[1.0, 0], [1.3, 100]], 80);
  shadow(u);
  return c;
}

// ── C. 화면 전환 ──────────────────────────────────────────
function C1() {
  var c = mk("C1", "휩 팬 (휙 넘김)");
  c.motionBlur = true; c.shutterAngle = 360;
  var a = bg(c, 0), b = bg(c, 62);
  a.outPoint = 2.3; b.inPoint = 1.7;
  a.motionBlur = true; b.motionBlur = true;
  K(pos(a), [[1.8, [540, 960]], [2.2, [-540, 960]]], 88);
  K(pos(b), [[1.8, [1620, 960]], [2.2, [540, 960]]], 88);
  return c;
}
function C2() {
  var c = mk("C2", "줌 블러 전환");
  var a = bg(c, 22), b = bg(c, 70);
  a.outPoint = 2.0; b.inPoint = 2.0;
  K(scl(a), [[1.72, [150, 150]], [2.0, [320, 320]]], 0);
  scl(a).setTemporalEaseAtKey(1, [new KeyframeEase(0, 90), new KeyframeEase(0, 90), new KeyframeEase(0, 90)], [new KeyframeEase(0, 90), new KeyframeEase(0, 90), new KeyframeEase(0, 90)]);
  var ea = fx(a, "CC Radial Fast Blur");
  if (ea) K(ea.property(2), [[1.72, 0], [2.0, 88]], 0);
  K(scl(b), [[2.0, [320, 320]], [2.32, [150, 150]]], 0);
  scl(b).setTemporalEaseAtKey(2, [new KeyframeEase(0, 90), new KeyframeEase(0, 90), new KeyframeEase(0, 90)], [new KeyframeEase(0, 90), new KeyframeEase(0, 90), new KeyframeEase(0, 90)]);
  var eb = fx(b, "CC Radial Fast Blur");
  if (eb) K(eb.property(2), [[2.0, 88], [2.32, 0]], 0);
  var f = c.layers.addSolid([1, 1, 1], "flash", W, H, 1);
  f.blendingMode = BlendingMode.ADD;
  K(opa(f), [[1.9, 0], [2.0, 55], [2.2, 0]], 0);
  return c;
}
function C3() {
  var src = mk("C3src", "글리치 원본");
  var sa = bg(src, 33), sb = bg(src, 12);
  sa.outPoint = 2.0; sb.inPoint = 2.0;
  var c = mk("C3", "글리치 전환");
  var gate = "var g = (time > 1.82 && time < 2.22) ? 1 : 0;\n";
  var take = [[3, 4], [2, 4], [2, 3]];   // 빨강만 / 초록만 / 파랑만 — 끄는 채널 순번(2=빨강 3=초록 4=파랑)
  var seeds = [11, 0, 37];
  for (var i = 2; i >= 0; i--) {
    var l = c.layers.add(src);
    var e = fx(l, "ADBE Shift Channels");
    if (e) { e.property(take[i][0]).setValue(10); fxAt(l, 1).property(take[i][1]).setValue(10); }   // 10 = 완전히 끔
    scl(l).setValue([110, 110]);
    if (i < 2) l.blendingMode = BlendingMode.ADD;
    if (seeds[i]) {
      pos(l).expression = gate + "seedRandom(Math.floor(time * 30) + " + seeds[i] + ", true);\nvalue + [g * random(-46, 46), g * random(-10, 10)]";
    }
  }
  var adj = c.layers.addSolid([1, 1, 1], "glitch", W, H, 1);
  adj.adjustmentLayer = true;
  var w = fx(adj, "ADBE Wave Warp");
  if (w) {
    w.property(1).setValue(2);           // 네모 물결 = 가로로 찢어지는 줄
    w.property(3).setValue(260); w.property(4).setValue(0); w.property(5).setValue(6);
    w.property(6).setValue(2);           // 가장자리 고정 — 화면 옆이 검게 뜯기지 않게
    w.property(2).expression = gate + "seedRandom(Math.floor(time * 30), true);\ng * random(10, 70)";
  }
  return c;
}

// ── D. 빛·질감 ────────────────────────────────────────────
function leak(comp, col, from, to, peak, size) {
  // 도형에 흐림 효과를 걸면 도형 테두리 상자에서 네모로 잘렸다(실측) → 큰 단색판에 타원 마스크 + 마스크 번짐으로 만든다
  var SW = 2600, SH = 3400, cx = SW / 2, cy = SH / 2, rx = size[0] / 2, ry = size[1] / 2, k = 0.5523;
  var l = comp.layers.addSolid(col, "leak", SW, SH, 1);
  var sh = new Shape();
  sh.vertices = [[cx, cy - ry], [cx + rx, cy], [cx, cy + ry], [cx - rx, cy]];
  sh.inTangents = [[-rx * k, 0], [0, -ry * k], [rx * k, 0], [0, ry * k]];
  sh.outTangents = [[rx * k, 0], [0, ry * k], [-rx * k, 0], [0, -ry * k]];
  sh.closed = true;
  var m = l.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
  m.property("ADBE Mask Shape").setValue(sh);
  l.property("ADBE Mask Parade").property(1).property("ADBE Mask Feather").setValue([420, 420]);
  l.blendingMode = BlendingMode.SCREEN;
  K(pos(l), [[0, from], [4, to]], 0);
  K(opa(l), [[0.2, 0], [1.4, peak], [2.6, peak], [3.8, 0]], 60);
  return l;
}
function D1() {
  var c = mk("D1", "빛 번짐 (라이트 릭)");
  bg(c, 62);
  leak(c, [1, 0.42, 0.08], [-150, 350], [1150, 900], 62, [900, 1400]);
  leak(c, [1, 0.2, 0.45], [1200, 1500], [250, 1150], 34, [700, 1000]);
  return c;
}
function wipeIn(comp, graded) {          // 왼쪽 원본 → 오른쪽으로 효과가 번져 온다(전/후가 한 화면에 보인다)
  var l = comp.layers.add(graded);
  var e = fx(l, "ADBE Linear Wipe");
  if (e) { e.property(2).setValue(-90); e.property(3).setValue(4); K(e.property(1), [[0.8, 100], [2.2, 0]], 70); }
  return l;
}
function D2() {
  var g = mk("D2src", "영화 색감 원본");
  var b = bg(g, 43);
  var e1 = fx(b, "ADBE Brightness & Contrast 2");
  if (e1) { e1.property(1).setValue(-14); fxAt(b, 1).property(2).setValue(20); }
  var e3 = fx(b, "ADBE Noise");
  if (e3) { e3.property(1).setValue(9); fxAt(b, 2).property(2).setValue(0); }
  var warm = g.layers.addSolid([1, 0.55, 0.2], "warm", W, H, 1);
  warm.blendingMode = BlendingMode.SOFT_LIGHT; opa(warm).setValue(22);
  vignette(g, 50);
  var c = mk("D2", "영화 색감 (대비·그레인·비네트)");
  bg(c, 43);
  wipeIn(c, g);
  return c;
}
function D3() {
  var g = mk("D3src", "블룸 원본");
  bg(g, 70);
  var soft = bg(g, 70);
  var e = fx(soft, "ADBE Gaussian Blur 2");
  if (e) e.property(1).setValue(70);
  var e2 = fx(soft, "ADBE Brightness & Contrast 2");
  if (e2) { e2.property(1).setValue(10); fxAt(soft, 2).property(2).setValue(40); }
  soft.blendingMode = BlendingMode.SCREEN; opa(soft).setValue(62);
  var c = mk("D3", "블룸 (뽀얀 빛)");
  bg(c, 70);
  wipeIn(c, g);
  return c;
}

// ── E. 장식·도형 ──────────────────────────────────────────
function scribble(layer) {               // 손으로 그린 듯 흔들리는 선
  var e = fx(layer, "ADBE Turbulent Displace");
  if (!e) return;
  e.property(2).setValue(16); e.property(3).setValue(46);
  e.property(6).expression = "Math.floor(time * 8) * 47";
}
function E1() {
  var c = mk("E1", "손그림 동그라미");
  bg(c, 0);
  for (var i = 0; i < 2; i++) {
    var l = shapeLayer(c, "circle" + i);
    var g = grp(l);
    vg(l, g).addProperty("ADBE Vector Shape - Ellipse").property("ADBE Vector Ellipse Size").setValue([560 + i * 34, 330 + i * 26]);
    trimOf(l, g);
    strokeOf(l, g, [1, 0.9, 0.1], 15);
    pos(l).setValue([540, 760]);
    rot(l).setValue(-9 + i * 5);
    K(trimEnd(l, g), [[0.5 + i * 0.28, 0], [0.9 + i * 0.28, 100]], 78);
    scribble(l);
    shadow(l);
  }
  return c;
}
function E2() {
  var c = mk("E2", "화살표 그려지기");
  bg(c, 52);
  var l = shapeLayer(c, "arrow");
  var tip = [150, 120];
  var g1 = grp(l);
  pathOf(l, g1, [[-260, -230], tip], [[0, 0], [-100, -150]], [[210, -40], [0, 0]], false);
  trimOf(l, g1);
  strokeOf(l, g1, [1, 1, 1], 20);
  var g2 = grp(l);
  pathOf(l, g2, [[tip[0] - 98, tip[1] - 48], tip, [tip[0] - 8, tip[1] - 108]], null, null, false);
  trimOf(l, g2);
  strokeOf(l, g2, [1, 1, 1], 20);
  pos(l).setValue([520, 760]);
  K(trimEnd(l, g1), [[0.5, 0], [1.0, 100]], 80);
  K(trimEnd(l, g2), [[1.0, 0], [1.15, 100]], 60);
  scribble(l);
  shadow(l);
  return c;
}
function burst(comp, p, t0, col) {
  var l = shapeLayer(comp, "burst");
  var g = grp(l);
  pathOf(l, g, [[0, -70], [0, -190]], null, null, false);
  trimOf(l, g);
  strokeOf(l, g, col, 15);
  var rp = vg(l, g).addProperty("ADBE Vector Filter - Repeater");
  rp.property("ADBE Vector Repeater Copies").setValue(10);
  vg(l, g).property("ADBE Vector Filter - Repeater").property("ADBE Vector Repeater Transform").property("ADBE Vector Repeater Rotation").setValue(36);
  pos(l).setValue(p);
  K(trimEnd(l, g), [[t0, 0], [t0 + 0.16, 100]], 75);
  K(trimStart(l, g), [[t0 + 0.08, 0], [t0 + 0.34, 100]], 75);
  return l;
}
function sparkle(comp, p, t0, size) {
  var l = shapeLayer(comp, "sparkle");
  var g = grp(l);
  var st = vg(l, g).addProperty("ADBE Vector Shape - Star");
  st.property("ADBE Vector Star Points").setValue(4);
  vg(l, g).property("ADBE Vector Shape - Star").property("ADBE Vector Star Outer Radius").setValue(size);
  vg(l, g).property("ADBE Vector Shape - Star").property("ADBE Vector Star Inner Radius").setValue(size * 0.2);
  fillOf(l, g, [1, 1, 1]);
  pos(l).setValue(p);
  K(scl(l), [[t0, [0, 0]], [t0 + 0.14, [125, 125]], [t0 + 0.3, [90, 90]], [t0 + 0.75, [0, 0]]], 65);
  K(rot(l), [[t0, -30], [t0 + 0.75, 60]], 0);
  var e = fx(l, "ADBE Glo2");
  if (e) { e.property(2).setValue(40); fxAt(l, 1).property(3).setValue(45); fxAt(l, 1).property(4).setValue(1.6); }
  return l;
}
function E3() {
  var c = mk("E3", "터지는 선·반짝이");
  bg(c, 33);
  burst(c, [540, 800], 0.5, [1, 0.9, 0.1]);
  sparkle(c, [300, 520], 0.75, 82);
  sparkle(c, [820, 660], 0.95, 58);
  sparkle(c, [700, 1120], 1.15, 70);
  burst(c, [330, 1250], 2.1, [1, 1, 1]);
  sparkle(c, [860, 420], 2.3, 76);
  sparkle(c, [220, 900], 2.5, 54);
  return c;
}

// ── F. 카메라 움직임 ──────────────────────────────────────
function F1() {
  var c = mk("F1", "펀치 줌 (뚝 끊는 확대)");
  c.motionBlur = true; c.shutterAngle = 270;
  var b = bg(c, 43);
  b.motionBlur = true;
  var e3 = [new KeyframeEase(0, 85), new KeyframeEase(0, 85), new KeyframeEase(0, 85)];
  var s = scl(b);
  s.setValueAtTime(0, [150, 150]); s.setValueAtTime(1.0, [150, 150]); s.setValueAtTime(1.12, [205, 205]);
  s.setValueAtTime(2.5, [205, 205]); s.setValueAtTime(2.5 + 1 / 30, [150, 150]);
  s.setValueAtTime(3.0, [150, 150]); s.setValueAtTime(3.12, [225, 225]);
  s.setTemporalEaseAtKey(3, e3, e3); s.setTemporalEaseAtKey(7, e3, e3);
  s.setInterpolationTypeAtKey(4, KeyframeInterpolationType.HOLD);
  var t = txt(c, "이거 하나면 끝", 104, [540, 1340]);
  shadow(t);
  return c;
}
function F2() {
  var c = mk("F2", "쾅 흔들림");
  c.motionBlur = true; c.shutterAngle = 220;
  var b = bg(c, 22, 166);
  b.motionBlur = true;
  pos(b).expression =
    "var hits = [1.0, 2.4], o = [0, 0];\n" +
    "for (var i = 0; i < hits.length; i++) {\n" +
    "  var t = time - hits[i];\n" +
    "  if (t >= 0 && t < 0.6) { var d = Math.exp(-t * 8); o = [Math.sin(t * 95) * 46 * d, Math.cos(t * 78) * 34 * d]; }\n" +
    "}\n" +
    "value + o";
  K(scl(b), [[0.97, [166, 166]], [1.03, [178, 178]], [1.3, [166, 166]], [2.37, [166, 166]], [2.43, [178, 178]], [2.7, [166, 166]]], 60);
  return c;
}
function F3() {
  var c = mk("F3", "천천히 밀고 들어가기");
  var b = bg(c, 12);
  K(scl(b), [[0, [150, 150]], [4, [180, 180]]], 0);
  K(rot(b), [[0, -0.6], [4, 1.2]], 0);
  vignette(c, 40);
  return c;
}

// ── 2차: 사장님 참고 영상(프로에펙러 텍스트 효과 모음집 1·2편) 에서 숏폼 자막에 쓸 만한 것 ──
function restyle(layer, fn) {
  var dp = layer.property("ADBE Text Properties").property("ADBE Text Document");
  var d = dp.value; fn(d); dp.setValue(d);
}
function centerAnchor(layer) {           // 키를 걸기 전에 부른다 — 글자 한가운데를 기준점으로
  var r = layer.sourceRectAtTime(0, false), p = pos(layer).value;
  var ax = r.left + r.width / 2, ay = r.top + r.height / 2;
  T(layer).property("ADBE Anchor Point").setValue([ax, ay]);
  pos(layer).setValue([p[0] + ax, p[1] + ay]);
  return r;
}
function exprSel(layer, a, expr) {
  anims(layer).property(a).property("ADBE Text Selectors").addProperty("ADBE Text Expressible Selector");
  var n = anims(layer).property(a).property("ADBE Text Selectors").numProperties;
  anims(layer).property(a).property("ADBE Text Selectors").property(n).property("ADBE Text Expressible Amount").expression = expr;
}
function dim(comp, amount) {
  var s = comp.layers.addSolid([0, 0, 0], "dim", W, H, 1);
  opa(s).setValue(amount);
  return s;
}

function A4() {                          // 참고 2편 #1 — 선 뒤에서 올라오는 글자
  var c = mk("A4", "선 뒤에서 올라오기");
  bg(c, 62);
  var t = txt(c, "아주 쉬운 레시피", 104, [540, 1290]);
  var r = t.sourceRectAtTime(0, false);
  K(pos(t), [[0.55, [540, 1290 + 150]], [1.0, [540, 1290]]], 85);
  var m = c.layers.addSolid([1, 1, 1], "matte", W, H, 1);
  pos(m).setValue([540, 1312 - H / 2]);
  t.setTrackMatte(m, TrackMatteType.ALPHA);
  var ln = shapeLayer(c, "line");
  var g = grp(ln);
  pathOf(ln, g, [[0, 0], [r.width + 40, 0]], null, null, false);
  trimOf(ln, g);
  strokeOf(ln, g, [1, 1, 1], 8);
  pos(ln).setValue([540 - (r.width + 40) / 2, 1322]);
  K(trimEnd(ln, g), [[0.3, 0], [0.7, 100]], 80);
  shadow(ln);
  return c;
}
function A5() {                          // 참고 1편 #6 — 쾅 박히고 화면이 흔들림
  var c = mk("A5", "쾅 박히기");
  c.motionBlur = true; c.shutterAngle = 200;
  var b = bg(c, 33, 164);
  pos(b).expression =
    "var t = time - 1.13;\n" +
    "if (t >= 0 && t < 0.6) { var d = Math.exp(-t * 9); value + [Math.sin(t * 95) * 40 * d, Math.cos(t * 78) * 30 * d]; } else value";
  var t = txt(c, "대박 레시피", 150, [540, 1250], [1, 0.9, 0.1]);
  shadow(t);
  centerAnchor(t);
  t.motionBlur = true;
  t.inPoint = 1.0;
  var s = scl(t);
  s.setValueAtTime(1.0, [650, 650]); s.setValueAtTime(1.13, [100, 100]);
  var e3 = [new KeyframeEase(0, 80), new KeyframeEase(0, 80), new KeyframeEase(0, 80)], lin = [new KeyframeEase(0, 1), new KeyframeEase(0, 1), new KeyframeEase(0, 1)];
  s.setTemporalEaseAtKey(1, e3, e3); s.setTemporalEaseAtKey(2, lin, lin);
  var f = c.layers.addSolid([1, 1, 1], "flash", W, H, 1);
  f.blendingMode = BlendingMode.ADD;
  K(opa(f), [[1.1, 0], [1.14, 22], [1.34, 0]], 0);
  return c;
}
function jamoSteps(str) {                // 한글을 자모 순서로 쳐 나가는 중간 글자들
  var CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ", out = [], done = "";
  for (var i = 0; i < str.length; i++) {
    var ch = str.charAt(i), code = str.charCodeAt(i);
    if (code >= 0xAC00 && code <= 0xD7A3) {
      var idx = code - 0xAC00, cho = Math.floor(idx / 588), jung = Math.floor((idx % 588) / 28), jong = idx % 28;
      out.push(done + CHO.charAt(cho));
      out.push(done + String.fromCharCode(0xAC00 + cho * 588 + jung * 28));
      if (jong) out.push(done + ch);
    } else {
      out.push(done + ch);
    }
    done += ch;
  }
  return out;
}
function A6() {                          // 참고 1편 #1 — 한글 타이핑
  var c = mk("A6", "한글 타이핑");
  bg(c, 12);
  var full = "오늘은 버터쿠키";
  var t = txt(c, full, 104, [0, 1300], [1, 1, 1], true);
  shadow(t);
  var r = t.sourceRectAtTime(0, false);
  pos(t).setValue([540 - r.width / 2 - r.left, 1300]);
  var steps = jamoSteps(full), quoted = [];
  for (var i = 0; i < steps.length; i++) quoted.push('"' + steps[i] + '"');
  t.property("ADBE Text Properties").property("ADBE Text Document").expression =
    "var s = [" + quoted.join(",") + "];\n" +
    "var i = Math.floor((time - 0.3) * 13);\n" +
    "var body = i < 0 ? '' : s[Math.min(i, s.length - 1)];\n" +
    "var typing = i < s.length;\n" +
    "body + ((typing || Math.floor(time * 3) % 2 == 0) ? '|' : '')";
  return c;
}
function A7() {                          // 참고 1편 #2 — 꿀렁이는 젤리 글자
  var c = mk("A7", "젤리 꿀렁");
  bg(c, 43);
  var t = txt(c, "말랑말랑 쫀득", 116, [540, 1300], [1, 0.42, 0.66]);
  shadow(t);
  var tExpr = "var t = time - 0.3 - (textIndex - 1) * 0.07;\n";
  var a1 = animator(t, [["ADBE Text Opacity", 0]]);
  exprSel(t, a1, tExpr + "t < 0 ? 100 : 0");
  var a2 = animator(t, [["ADBE Text Scale 3D", [150, 50, 100]]]);
  exprSel(t, a2, tExpr + "var a = t < 0 ? 0 : 100 * Math.exp(-4.5 * t) * Math.cos(2 * Math.PI * 3 * t); [a, a, a]");
  var a3 = animator(t, [["ADBE Text Position 3D", [0, -70, 0]]]);
  exprSel(t, a3, tExpr + "var a = t < 0 ? 0 : 100 * Math.exp(-5 * t) * Math.abs(Math.sin(2 * Math.PI * 3 * t)); [a, a, a]");
  return c;
}

function B4() {                          // 참고 1편 #18 — 상자가 덮고 글자색이 뒤집힘
  var c = mk("B4", "강조 상자 덮기");
  var b = bg(c, 52);
  var r = row(c, ["진짜", "강조하고", "싶을 때"], 1300, 90, 28);
  for (var i = 0; i < 3; i++) wordIn(r.layers[i], 0.3 + i * 0.12);
  var rc = r.rects[1], w = rc.width + 44, h = rc.height + 44;
  var m = shapeLayer(c, "box");
  var g = grp(m);
  var q = vg(m, g).addProperty("ADBE Vector Shape - Rect");
  q.property("ADBE Vector Rect Size").setValue([w, h]);
  vg(m, g).property("ADBE Vector Shape - Rect").property("ADBE Vector Rect Position").setValue([w / 2, 0]);
  vg(m, g).property("ADBE Vector Shape - Rect").property("ADBE Vector Rect Roundness").setValue(16);
  fillOf(m, g, [0.47, 0.27, 0.95]);
  pos(m).setValue([r.xs[1] - 22, 1300 + rc.top + rc.height / 2]);
  K(scl(m), [[1.0, [0, 100]], [1.22, [100, 100]]], 82);
  m.moveBefore(b);
  restyle(r.layers[1], function (d) { d.applyStroke = false; });
  return c;
}
function B5() {                          // 참고 1편 #9 — 펜으로 동그라미·별표
  var c = mk("B5", "펜 동그라미·별표");
  bg(c, 0);
  var r = row(c, ["이건", "꼭", "사세요"], 1300, 96, 28);
  for (var i = 0; i < 3; i++) wordIn(r.layers[i], 0.3 + i * 0.12);
  var rc = r.rects[2], cx = r.xs[2] + rc.width / 2, cy = 1300 + rc.top + rc.height / 2;
  var ring = shapeLayer(c, "ring");
  var g = grp(ring);
  vg(ring, g).addProperty("ADBE Vector Shape - Ellipse").property("ADBE Vector Ellipse Size").setValue([rc.width + 90, rc.height + 80]);
  trimOf(ring, g);
  strokeOf(ring, g, [1, 0.16, 0.2], 11);
  pos(ring).setValue([cx, cy]); rot(ring).setValue(-6);
  K(trimEnd(ring, g), [[1.0, 0], [1.35, 100]], 78);
  scribble(ring);
  var star = shapeLayer(c, "star");
  var g2 = grp(star), pts = [], R = 62;
  for (var k = 0; k < 6; k++) {          // 한붓그리기 별: 꼭짓점을 두 칸씩 건너뛴다
    var ang = (-90 + k * 144) * Math.PI / 180;
    pts.push([Math.cos(ang) * R, Math.sin(ang) * R]);
  }
  pathOf(star, g2, pts, null, null, false);
  trimOf(star, g2);
  strokeOf(star, g2, [1, 0.16, 0.2], 9);
  pos(star).setValue([r.xs[0] - 50, 1300 + r.rects[0].top - 60]); rot(star).setValue(-12);
  K(trimEnd(star, g2), [[1.45, 0], [1.85, 100]], 60);
  scribble(star);
  return c;
}
function B6() {                          // 참고 2편 #10 — 덜덜 떨리는 글자
  var c = mk("B6", "덜덜 떨림");
  bg(c, 22);
  var r = row(c, ["너무", "맛있어서", "덜덜"], 1300, 96, 28);
  for (var i = 0; i < 3; i++) wordIn(r.layers[i], 0.3 + i * 0.12);
  var l = r.layers[2];
  restyle(l, function (d) { d.fillColor = [1, 0.3, 0.3]; });
  var a = animator(l, [["ADBE Text Position 3D", [7, 9, 0]], ["ADBE Text Rotation", 7]]);
  try {
    anims(l).property(a).property("ADBE Text Selectors").addProperty("ADBE Text Wiggly Selector");
    anims(l).property(a).property("ADBE Text Selectors").property(1).property("ADBE Text Temporal Freq").setValue(14);
  } catch (e) { log("  ! 흔들 선택기: " + e.toString()); }
  return c;
}

function G1() {                          // 참고 1편 #3 — 네온사인
  var c = mk("G1", "네온사인");
  bg(c, 62);
  dim(c, 62);
  var flick = "seedRandom(Math.floor(time * 18), true);\ntime < 0.3 ? 0 : (time < 1.2 ? (random() > 0.45 ? 100 : 12) : 100)";
  var cols = [[1, 0.2, 0.75], [1, 0.85, 0.95]], widths = [9, 3];
  for (var i = 0; i < 2; i++) {
    var t = txt(c, "오늘만 특가", 150, [540, 1250]);
    (function (col, w) {
      restyle(t, function (d) { d.applyFill = false; d.applyStroke = true; d.strokeColor = col; d.strokeWidth = w; d.strokeOverFill = true; });
    })(cols[i], widths[i]);
    opa(t).expression = flick;
    if (i == 0) {
      var e = fx(t, "ADBE Glo2");
      if (e) { e.property(2).setValue(20); fxAt(t, 1).property(3).setValue(36); fxAt(t, 1).property(4).setValue(1.2); }
      var e2 = fx(t, "ADBE Glo2");
      if (e2) { e2.property(2).setValue(20); fxAt(t, 2).property(3).setValue(150); fxAt(t, 2).property(4).setValue(0.8); }
    }
  }
  return c;
}
function G2() {                          // 참고 2편 #19 — 물결치는 무지개 글자
  var c = mk("G2", "물결 무지개");
  bg(c, 70);
  var t = txt(c, "달콤 고소 바삭 촉촉", 100, [540, 1300], [0.2, 0.9, 1]);
  shadow(t);
  var a1 = animator(t, [["ADBE Text Position 3D", [0, -44, 0]]]);
  exprSel(t, a1, "var a = 100 * Math.sin(time * 7 - textIndex * 0.75); [a, a, a]");
  var a2 = animator(t, [["ADBE Text Fill Hue", 300]]);
  exprSel(t, a2, "var a = ((textIndex / textTotal) * 100 + time * 40) % 100; [a, a, a]");
  K(opa(t), [[0.3, 0], [0.6, 100]], 60);
  return c;
}
function G3() {                          // 참고 1편 #14 — 지지직 글리치 글자
  var src = mk("G3src", "글리치 글자 원본");
  var gate = "var g = ((time > 0.3 && time < 0.75) || (time > 2.2 && time < 2.45)) ? 1 : 0;\n";
  var cols = [[1, 0, 0], [0, 1, 0], [0, 0, 1]], seeds = [11, 0, 37];
  for (var i = 0; i < 3; i++) {
    var t = txt(src, "품절 임박", 160, [540, 1250]);
    (function (col) { restyle(t, function (d) { d.applyStroke = false; d.fillColor = col; }); })(cols[i]);
    if (i > 0) t.blendingMode = BlendingMode.ADD;
    if (seeds[i]) pos(t).expression = gate + "seedRandom(Math.floor(time * 30) + " + seeds[i] + ", true);\nvalue + [g * random(-34, 34), g * random(-8, 8)]";
  }
  var c = mk("G3", "글리치 글자");
  bg(c, 33);
  dim(c, 35);
  var l = c.layers.add(src);
  l.inPoint = 0.3;
  var w = fx(l, "ADBE Wave Warp");
  if (w) {
    w.property(1).setValue(2); w.property(3).setValue(90); w.property(4).setValue(0); w.property(5).setValue(8);
    w.property(2).expression = gate + "seedRandom(Math.floor(time * 30), true);\ng * random(8, 60)";
  }
  shadow(l);
  return c;
}
function G4() {                          // 참고 1편 #8 — 슬롯머신처럼 도는 숫자(가격)
  var c = mk("G4", "가격 숫자 롤링");
  bg(c, 52);
  var r = row(c, ["39,900", "원"], 1280, 170, 10);
  for (var i = 0; i < 2; i++) {
    (function (l) { restyle(l, function (d) { d.fillColor = [1, 0.9, 0.1]; }); })(r.layers[i]);
    shadow(r.layers[i]);
    K(opa(r.layers[i]), [[0.3, 0], [0.45, 100]], 0);
  }
  var l = r.layers[0];
  var a = animator(l, [["ADBE Text Character Offset", 0]]);
  K(anims(l).property(a).property("ADBE Text Animator Properties").property("ADBE Text Character Offset"), [[0.3, 47], [1.6, 0]], 0);
  var cp = anims(l).property(a).property("ADBE Text Animator Properties").property("ADBE Text Character Offset");
  cp.setTemporalEaseAtKey(2, [new KeyframeEase(0, 85)], [new KeyframeEase(0, 85)]);
  var e = fx(l, "ADBE Motion Blur");
  if (e) { e.property(1).setValue(0); K(fxAt(l, 2).property(2), [[0.3, 46], [1.5, 0]], 60); }
  return c;
}
function G5() {                          // 참고 2편 #16 — 두께가 있는 글자가 튀어나옴
  var c = mk("G5", "입체 글자 튀어나오기");
  bg(c, 0);
  var N = 14;
  var expr = "var t = time - 0.3 - (textIndex - 1) * 0.07;\n" +
    "var s = t < 0 ? 0 : 1 - Math.exp(-8 * t) * Math.cos(2 * Math.PI * 2 * t);\n" +
    "var a = (1 - s) * 100; [a, a, a]";
  for (var i = N; i >= 0; i--) {
    var col = i == 0 ? [1, 0.84, 0.06] : [0.86 - i * 0.012, 0.47 - i * 0.012, 0.02];
    var t = txt(c, "득템 찬스!", 156, [540 + i * 2.4, 1250 + i * 2.4], col);
    restyle(t, function (d) { d.applyStroke = false; });
    rot(t).setValue(-5);
    charAnchorCenter(t);
    var a = animator(t, [["ADBE Text Scale 3D", [0, 0, 100]]]);
    exprSel(t, a, expr);
    if (i == N) shadow(t);
  }
  return c;
}

// ── 실행 ─────────────────────────────────────────────────
var BUILDERS = [["A1", A1], ["A2", A2], ["A3", A3], ["B1", B1], ["B2", B2], ["B3", B3], ["C1", C1], ["C2", C2], ["C3", C3],
                ["D1", D1], ["D2", D2], ["D3", D3], ["E1", E1], ["E2", E2], ["E3", E3], ["F1", F1], ["F2", F2], ["F3", F3],
                ["A4", A4], ["A5", A5], ["A6", A6], ["A7", A7], ["B4", B4], ["B5", B5], ["B6", B6],
                ["G1", G1], ["G2", G2], ["G3", G3], ["G4", G4], ["G5", G5]];

function wanted(id) {
  if (!ONLY) return true;
  for (var i = 0; i < ONLY.length; i++) if (ONLY[i] == id) return true;
  return false;
}

app.beginSuppressDialogs();
try {
  var i;
  for (i = app.project.numItems; i >= 1; i--) {          // 앞서 만든 것 치우기
    var it = app.project.item(i);
    if (it instanceof FolderItem && it.name == "FX_SAMPLES") it.remove();
  }
  while (app.project.renderQueue.numItems > 0) app.project.renderQueue.item(1).remove();
  FOLDER = app.project.items.addFolder("FX_SAMPLES");
  FOOT = app.project.importFile(new ImportOptions(new File(OUT + "/bg.mp4")));
  FOOT.parentFolder = FOLDER;
  log("배경 " + FOOT.width + "x" + FOOT.height + " " + FOOT.duration.toFixed(2) + "초");
  var built = [];
  for (i = 0; i < BUILDERS.length; i++) {
    var id = BUILDERS[i][0];
    if (!wanted(id)) continue;
    try {
      var comp = BUILDERS[i][1]();
      built.push([id, comp]);
      log("OK   " + id + " " + comp.name + " 레이어 " + comp.numLayers);
    } catch (e) {
      log("FAIL " + id + " " + e.toString() + " (line " + e.line + ")");
    }
  }
  app.project.save(new File(OUT + "/" + (ONLY ? "fx_part.aep" : "fx_samples.aep")));
  if (QUEUE) {
    for (i = 0; i < built.length; i++) {
      var rq = app.project.renderQueue.items.add(built[i][1]);
      rq.outputModule(1).applyTemplate(OM_TEMPLATE);
      rq.outputModule(1).file = new File(OUT + "/" + built[i][0] + ".mp4");
    }
    log("대기열 " + built.length + "개");
  }
  app.project.save();
} catch (err) {
  log("ERR " + err.toString() + " (line " + err.line + ")");
}
app.endSuppressDialogs(false);
flush("build_done.txt");
