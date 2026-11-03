# -*- coding: utf-8 -*-
"""품질 관문 자가시험(돈 없음): 완성본을 일부러 망가뜨려 관문이 잡는지 잰다. 고치기 전/후 같은 시험을 돌린다.
py -m tools.calcopy.gate_selftest <판> <doc> <work> <임시폴더>  → 망가뜨림별 새로 ×가 된 행. 안 잡힌 것 = 관문 구멍"""
import json, shutil, subprocess, sys
from pathlib import Path
from tools.calcopy.hybrid import quality_gate as Q
V = lambda f: ["-vf", f, "-c:a", "copy"]
M = {
 "화면 3초 멈춤": V("loop=loop=90:size=1:start=150,trim=end_frame=99999,setpts=N/30/TB"),
 "흰 번쩍임 3프레임": V("drawbox=c=white:t=fill:enable='between(n,200,202)'"),
 "검은 화면 2초": V("drawbox=c=black:t=fill:enable='between(t,5,7)'"),
 "큰 남의 글자 상시": V("drawbox=x=100:y=900:w=880:h=160:c=white:t=fill,drawbox=x=120:y=920:w=840:h=120:c=black:t=fill"),
 "해상도 720": V("scale=720:1280"),
 "소리 8dB 큼": ["-af", "volume=8dB", "-c:v", "copy"],
 "소리 3초 끊김": ["-af", "volume=0:enable='between(t,6,9)'", "-c:v", "copy"],
 "끝 5초 잘림": ["-t", "__CUT__", "-c", "copy"],
}
style, doc, work, tmp = sys.argv[1:5]
tmp = Path(tmp); w = tmp / "w"; d = tmp / "d"
if not w.exists():
    shutil.copytree(work, w); shutil.copytree(doc, d)
final = w / "render/final.mp4"; orig = tmp / "orig.mp4"
if not orig.exists(): shutil.copy(final, orig)
def run():
    r = Q.gate(style, d, w, eye_pack=False, fit=False, asr=False, log=lambda *_: None)
    return {f"{x['group']}/{x['what']}": x for x in r["rows"] if not x.get("ref")}
def clear():
    for f in (w / "render/gate_cache.json", w / "render/final.mp4.seal.json"):
        f.unlink(missing_ok=True)
base = run(); bad0 = {k for k, x in base.items() if x["ok"] is False}
print("기준 ×", len(bad0), sorted(bad0)[:12]); res = {}
for name, a in M.items():
    a = [str(Q.vdur(orig) - 5) if x == "__CUT__" else x for x in a]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(orig), *a, str(final)], check=True); clear()
    try:
        r = run(); new = [k for k, x in r.items() if x["ok"] is False and k not in bad0]
    except Exception as e:
        new = ["[관문 멈춤] " + repr(e)[:120]]
    res[name] = new; print(("잡힘 " if new else "★못잡음 ") + name, new[:5], flush=True)
shutil.copy(orig, final); (tmp / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf8")
print("못잡음", [k for k, v in res.items() if not v])
