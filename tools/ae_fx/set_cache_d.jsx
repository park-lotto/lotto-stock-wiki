// 에펙 디스크 캐시 위치를 D 드라이브로 옮긴다 (2026-10-04 사장님 "D드라이브에 저장해", 관제 112).
// 기본값 C:\Users\CH\AppData\Local\Temp (최대 23GB) 가 렌더 중 C 를 채웠다.
// 실행: py tools/ae_fx/run_jsx.py tools/ae_fx/set_cache_d.jsx D:\ae_fx_work\cache_done.txt 60
var SEC = "Disk Cache Controls", KEY = "Folder 7", TARGET = "D:\\ae_cache";
var L = [];
try {
  var T = PREFType.PREF_Type_MACHINE_SPECIFIC;
  var dir = new Folder(TARGET);
  if (!dir.exists) dir.create();
  L.push("전: " + (app.preferences.havePref(SEC, KEY, T) ? app.preferences.getPrefAsString(SEC, KEY, T) : "(없음)"));
  app.preferences.savePrefAsString(SEC, KEY, TARGET, T);
  app.preferences.saveToDisk();
  app.preferences.reload();
  L.push("후: " + app.preferences.getPrefAsString(SEC, KEY, T));
  L.push("최대 크기(GB): " + app.preferences.getPrefAsString(SEC, "Max Size 3", T));
} catch (e) {
  L.push("ERR " + e.toString() + " (line " + e.line + ")");
}
var f = new File("D:/ae_fx_work/cache_done.txt");
f.encoding = "UTF-8"; f.open("w"); f.write(L.join("\n")); f.close();
