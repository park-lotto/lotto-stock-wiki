// 에펙 기본 글자 프리셋(Presets/Text)을 한글 자막에 하나씩 걸어 견본 컴포지션을 만든다 (관제 112).
// 실행: py tools/ae_fx/run_jsx.py tools/ae_fx/build_presets.jsx D:\ae_fx_work\presets_done.txt 900
// 결과: D:/ae_fx_work/fx_presets.aep (렌더 대기열 포함) + presets_manifest.txt(번호·폴더·이름·건 뒤 글꼴/크기/색)
// presets_cfg.txt 에 limit=6 을 적으면 폴더마다 앞 6개만(시험용).
var OUT = "D:/ae_fx_work";
var PRESETS = "D:/Adobe/Adobe After Effects 2026/Support Files/Presets/Text";
var FONT = "NotoSansKR-Black";
var OM_TEMPLATE = "H.264 - 렌더링 일치 설정 - 5Mbps";
var W = 1080, H = 1920, FPS = 30, DUR = 3.5, START = 0.3;
var BG_IN = [0, 52, 62, 70, 4, 56, 66];   // 원본 자막이 안 보이는 구간
var LIMIT = 0;
var LOG = [], MAN = [];

(function () {
  var f = new File(OUT + "/presets_cfg.txt");
  if (!f.exists) return;
  f.encoding = "UTF-8"; f.open("r"); var body = f.read(); f.close();
  var m = body.match(/limit=(\d+)/);
  if (m) LIMIT = parseInt(m[1], 10);
})();

function saveLines(name, lines) {
  var f = new File(OUT + "/" + name);
  f.encoding = "UTF-8"; f.open("w"); f.write(lines.join("\n")); f.close();
}
function pad(n) { var s = "" + n; while (s.length < 3) s = "0" + s; return s; }
function rgb(c) { return Math.round(c[0] * 255) + "," + Math.round(c[1] * 255) + "," + Math.round(c[2] * 255); }

app.beginSuppressDialogs();
try {
  var i, j;
  for (i = app.project.numItems; i >= 1; i--) {
    var it = app.project.item(i);
    if (it instanceof FolderItem && (it.name == "FX_PRESETS" || it.name == "FX_SAMPLES")) it.remove();
  }
  while (app.project.renderQueue.numItems > 0) app.project.renderQueue.item(1).remove();
  var folder = app.project.items.addFolder("FX_PRESETS");
  var foot = app.project.importFile(new ImportOptions(new File(OUT + "/bg.mp4")));
  foot.parentFolder = folder;

  var dirs = new Folder(PRESETS).getFiles(function (f) { return f instanceof Folder; });
  dirs.sort(function (a, b) { return a.name < b.name ? -1 : 1; });
  var n = 0, ok = 0;
  for (i = 0; i < dirs.length; i++) {
    var files = dirs[i].getFiles("*.ffx");
    files.sort(function (a, b) { return decodeURI(a.name) < decodeURI(b.name) ? -1 : 1; });
    var dirName = decodeURI(dirs[i].name);
    var multi = dirName == "Multi-Line";
    for (j = 0; j < files.length; j++) {
      if (LIMIT && j >= LIMIT) break;
      n++;
      var id = "P" + pad(n), pname = decodeURI(files[j].name).replace(/\.ffx$/i, "");
      try {
        var c = app.project.items.addComp(id, W, H, 1, DUR, FPS);
        c.parentFolder = folder;
        var b = c.layers.add(foot);
        b.property("ADBE Transform Group").property("ADBE Scale").setValue([150, 150]);
        b.startTime = -BG_IN[n % BG_IN.length];
        if (b.hasAudio) b.audioEnabled = false;
        var isNum = dirName == "Number Counters";
        var t = c.layers.addText(isNum ? "0" : (multi ? "겉은 바삭\r속은 촉촉\r버터쿠키" : "겉은 바삭 속은 촉촉"));
        var dp = t.property("ADBE Text Properties").property("ADBE Text Document");
        var d = dp.value;
        d.resetCharStyle();
        d.font = FONT; d.fontSize = 100; d.tracking = -20;
        d.applyFill = true; d.fillColor = [1, 1, 1];
        d.applyStroke = true; d.strokeColor = [0, 0, 0]; d.strokeWidth = 11; d.strokeOverFill = false;
        d.justification = ParagraphJustification.CENTER_JUSTIFY;
        dp.setValue(d);
        t.property("ADBE Transform Group").property("ADBE Position").setValue([540, multi ? 1180 : 1300]);
        c.time = START;                  // 프리셋은 현재 시각부터 키를 건다
        c.openInViewer();
        t.selected = true;
        t.applyPreset(files[j]);
        var after = t.property("ADBE Text Properties").property("ADBE Text Document").valueAtTime(DUR - 0.1, false);
        var na = t.property("ADBE Text Properties").property("ADBE Text Animators").numProperties;
        var ne = t.property("ADBE Effect Parade").numProperties;
        MAN.push([id, dirName, pname, after.font, Math.round(after.fontSize), after.applyFill ? rgb(after.fillColor) : "-", na, ne, t.threeDPerChar ? "3D" : "2D"].join("\t"));
        var rq = app.project.renderQueue.items.add(c);
        rq.outputModule(1).applyTemplate(OM_TEMPLATE);
        rq.outputModule(1).file = new File(OUT + "/presets/" + id + ".mp4");
        ok++;
      } catch (e) {
        LOG.push("FAIL " + id + " " + dirName + "/" + pname + " :: " + e.toString());
        MAN.push([id, dirName, pname, "FAIL", "", "", "", "", ""].join("\t"));
      }
    }
  }
  LOG.push("프리셋 " + n + "개 중 " + ok + "개 컴포지션 생성");
  app.project.save(new File(OUT + "/fx_presets.aep"));
} catch (err) {
  LOG.push("ERR " + err.toString() + " (line " + err.line + ")");
}
app.endSuppressDialogs(false);
saveLines("presets_manifest.txt", MAN);
saveLines("presets_done.txt", LOG);
