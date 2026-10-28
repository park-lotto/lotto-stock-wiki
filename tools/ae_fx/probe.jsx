// 에펙 환경 조사 — 쓸 수 있는 효과(matchName)·내보내기 형식·한글 글꼴을 파일로 적는다.
// 실행: AfterFX.exe -r probe.jsx  (결과: 문서/ae-mcp-bridge/fx_probe.txt)
var L = [];
try {
  var c = app.project.items.addComp("probe", 1080, 1920, 1, 2, 30);
  var s = c.layers.addSolid([0, 0, 0], "s", 1080, 1920, 1);
  var names = ["ADBE Gaussian Blur 2", "ADBE Motion Blur", "ADBE Radial Blur", "CC Radial Fast Blur", "ADBE Glo2", "ADBE Noise", "ADBE Geometry2", "ADBE Channel Mixer", "ADBE Fractal Noise", "ADBE Displacement Map", "ADBE Tritone", "ADBE Tint", "ADBE HUE SATURATION", "ADBE CurvesCustom", "ADBE Brightness & Contrast 2", "ADBE Lumetri", "ADBE Turbulent Displace", "CC Light Sweep", "CC Light Rays", "ADBE Exposure2", "ADBE Ramp", "ADBE Fill", "ADBE Linear Wipe", "ADBE Camera Lens Blur", "CC Light Burst 2.5", "ADBE Wave Warp", "ADBE Posterize Time", "ADBE Echo", "CC Force Motion Blur", "ADBE Drop Shadow", "ADBE Roughen Edges", "ADBE Box Blur2", "ADBE Offset", "ADBE Optics Compensation"];
  for (var i = 0; i < names.length; i++) {
    L.push("fx|" + names[i] + "|" + s.property("ADBE Effect Parade").canAddProperty(names[i]));
  }
  var rq = app.project.renderQueue.items.add(c);
  var t = rq.outputModule(1).templates;
  for (var j = 0; j < t.length; j++) {
    if (t[j].indexOf("_HIDDEN") < 0) L.push("om|" + t[j]);
  }
  rq.remove();
  c.remove();
  var want = ["Pretendard", "Gmarket", "Black Han", "Jalnan", "Noto Sans KR", "Malgun", "Cafe24", "NanumSquare", "SUIT", "Paperlogy", "S-Core", "GongGothic"];
  if (app.fonts && app.fonts.allFonts) {
    var fam = app.fonts.allFonts;
    L.push("fontFamilies|" + fam.length);
    for (var a = 0; a < fam.length; a++) {
      for (var b = 0; b < fam[a].length; b++) {
        var fo = fam[a][b];
        var nm = fo.familyName + "";
        for (var w = 0; w < want.length; w++) {
          if (nm.toLowerCase().indexOf(want[w].toLowerCase()) >= 0) {
            L.push("font|" + fo.postScriptName + "|" + nm + "|" + fo.styleName);
            break;
          }
        }
      }
    }
  } else {
    L.push("font|app.fonts 없음");
  }
} catch (e) {
  L.push("ERR|" + e.toString() + "|line " + e.line);
}
var f = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/fx_probe.txt");
f.encoding = "UTF-8";
f.open("w");
f.write(L.join("\n"));
f.close();
