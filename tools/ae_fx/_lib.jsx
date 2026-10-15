// 에펙 견본 스크립트 공통 도구 (관제 112). 단독 실행하지 않는다 —
// 스크립트 첫 줄이 "// use-lib" 로 시작하면 run_jsx.py 가 이 파일을 앞에 붙여 보낸다.
// 속성은 전부 matchName·순번으로 잡는다 — 이 PC 에펙은 한글판이라 표시 이름이 다르다.
var OUT = "D:/ae_fx_work";
var FONT = "NotoSansKR-Black";
var OM_TEMPLATE = "H.264 - 렌더링 일치 설정 - 15Mbps";
var W = 1080, H = 1920, FPS = 30, DUR = 4;
var ONLY = null;          // <cfg> 파일의 only=A1,B2 로 일부만 다시 만든다. 없으면 전부
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


// ── 실행기 ───────────────────────────────────────────────
// builders = [[번호, 함수], ...]. o = {folder, aep, done, cfg, outDir}
// 컴포지션을 만들고 렌더 대기열에 올려 저장까지만 한다 — 실제 렌더는 render.py(aerender).
// (앱 안 renderQueue.render() 는 이 PC 에서 파일을 안 냈다)
function runBuilders(builders, o) {
  var cfg = new File(OUT + "/" + o.cfg);
  if (cfg.exists) {
    cfg.encoding = "UTF-8"; cfg.open("r"); var body = cfg.read(); cfg.close();
    var m = body.match(/only=([A-Za-z0-9,]+)/);
    if (m) ONLY = m[1].split(",");
  }
  function wanted(id) {
    if (!ONLY) return true;
    for (var k = 0; k < ONLY.length; k++) if (ONLY[k] == id) return true;
    return false;
  }
  app.beginSuppressDialogs();
  try {
    var i;
    for (i = app.project.numItems; i >= 1; i--) {          // 앞서 만든 것 치우기
      var it = app.project.item(i);
      if (it instanceof FolderItem && it.name.indexOf("FX_") == 0) it.remove();
    }
    while (app.project.renderQueue.numItems > 0) app.project.renderQueue.item(1).remove();
    FOLDER = app.project.items.addFolder(o.folder);
    FOOT = app.project.importFile(new ImportOptions(new File(OUT + "/bg.mp4")));
    FOOT.parentFolder = FOLDER;
    log("배경 " + FOOT.width + "x" + FOOT.height + " " + FOOT.duration.toFixed(2) + "초");
    var built = [];
    for (i = 0; i < builders.length; i++) {
      var id = builders[i][0];
      if (!wanted(id)) continue;
      try {
        var comp = builders[i][1]();
        built.push([id, comp]);
        log("OK   " + id + " " + comp.name + " 레이어 " + comp.numLayers);
      } catch (e) {
        log("FAIL " + id + " " + e.toString() + " (line " + e.line + ")");
      }
    }
    app.project.save(new File(OUT + "/" + o.aep + (ONLY ? "_part" : "") + ".aep"));
    for (i = 0; i < built.length; i++) {
      var rq = app.project.renderQueue.items.add(built[i][1]);
      rq.outputModule(1).applyTemplate(OM_TEMPLATE);
      rq.outputModule(1).file = new File(OUT + "/" + (o.outDir ? o.outDir + "/" : "") + built[i][0] + ".mp4");
    }
    log("대기열 " + built.length + "개");
    app.project.save();
  } catch (err) {
    log("ERR " + err.toString() + " (line " + err.line + ")");
  }
  app.endSuppressDialogs(false);
  flush(o.done);
}
