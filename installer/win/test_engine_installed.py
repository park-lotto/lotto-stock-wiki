"""설치본 엔진이 **설치 폴더 도구만으로** 도는가(관제 234 5판) — 저장소·이 PC 의 파이썬·node·yt-dlp 를 쓰지 않는다.

실행: py installer/win/test_engine_installed.py --install <설치 폴더> --pack <프리셋 꾸러미 zip> [--video <받기 시험 주소>]
검사(전부 설치본 python·node·chrome·ffmpeg·yt-dlp, PATH = 설치 도구만):
  1) 미리보기 목록(preview_request catalog) — 렌더러 글꼴 목록이 나오나
  2) 렌더(scene_style.render_layer_one) — 꾸러미를 엔진에 빌린 것처럼 풀고(.rented) 한 장면 PNG, 잉크가 있나 → 끝나면 지운다
  3) 받기(remake.download_url) — 인스타·틱톡 등 영상 한 편
  4) 받아쓰기(asr_local.transcribe) — 받은 영상 소리를 동봉 위스퍼 모델로
출력: JSON 한 줄 + rc(하나라도 실패면 1)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


def env_for(inst: Path, home: Path) -> dict:
    t = inst / "tools"
    path = os.pathsep.join([str(t / "ffmpeg"), str(t / "yt-dlp"), str(t / "node"), os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")])
    e = {k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "HOMEDRIVE", "HOMEPATH", "WINDIR", "COMSPEC")}
    e.update(PATH=path, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONNOUSERSITE="1",
             PUPPETEER_EXECUTABLE_PATH=str(t / "chrome-headless-shell" / "chrome-headless-shell.exe"),
             NODE_PATH=str(inst / "server" / "node_modules"), SHORTEM_WHISPER_DIR=str(inst / "models" / "whisper"),
             CALCOPY_CUSTOMER_MODE="1", CALCOPY_GEMINI_BACKEND="client", YTDLP_PROXY_SLOTS="0", INSTAGRAM_SCRAPER="playwright",
             HF_HUB_OFFLINE="1", CALCOPY_DATA_DIR=str(home / "창고"))
    return e


def py(inst: Path, env: dict, code: str, timeout=900) -> dict:
    r = subprocess.run([str(inst / "tools" / "python" / "python.exe"), "-I", "-c", "import sys;sys.path.insert(0,'.');" + code],
                       cwd=str(inst / "engine"), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    last = (r.stdout.strip().splitlines() or [""])[-1]
    try:
        return json.loads(last)
    except ValueError:
        return {"error": (r.stderr or r.stdout)[-600:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", required=True)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--preset", default="channel/sseolpulda/preset/A_흰바탕창/창아래_검정")
    ap.add_argument("--video", default="https://www.tiktok.com/@11street_official/video/7512363471871216903")
    a = ap.parse_args()
    inst = Path(a.install).resolve()
    home = inst / "_engine_test"
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True)
    env = env_for(inst, home)
    out = {}
    out["catalog"] = py(inst, env, "from tools.calcopy import preview_request as P;import json;c=P.catalog();print(json.dumps({'fonts':len(c['fonts']),'templates':len(c['templates']),'voices':len(c['voices'])}))")
    ch = inst / "engine" / "channel"
    try:                                                   # 빌린 것처럼 풀기(PC 의 preset_rent 와 같은 자리·표식)
        with zipfile.ZipFile(a.pack) as z:
            z.extractall(inst / "engine")
        (ch / ".rented").write_text("test", encoding="utf-8")
        out["render"] = py(inst, env, f"""
import json
from PIL import Image
import numpy as np
from shopping_shorts import calcopy_make as MK, scene_style
from shopping_shorts.calcopy_frame import schema, to_snapshot
from tools.calcopy.remake_video import title_text
from tools.calcopy import preview_request as PR
cfg=MK.merge_preset_pack({a.preset!r}, PR.default_pack())
spec=schema.validate(cfg['frame'])
tl=PR._sample_timeline(PR.SAMPLE_LINES)
snap=scene_style.validate_snapshot(to_snapshot.to_snapshot(cfg['frame']))
p=scene_style.render_layer_one(tl, snap, {str(home / 'layer')!r}, 0, {{'text': title_text(spec, {{'title': PR.SAMPLE_TITLE}})}})
im=np.asarray(Image.open(p).convert('RGBA'))
print(json.dumps({{'png': str(p), 'size': list(im.shape[:2]), 'ink': round(float((im[...,3]>0).mean()),3)}}))
""")
    finally:
        shutil.rmtree(ch, ignore_errors=True)
    out["download"] = py(inst, env, f"""
import json
from pathlib import Path
from tools.calcopy.engine import remake as R
p=R.download_url({a.video!r}, Path({str(home)!r}))
print(json.dumps({{'file': str(p) if p else None, 'bytes': p.stat().st_size if p else 0}}))
""")
    if out["download"].get("file"):
        out["asr"] = py(inst, env, f"""
import json
from tools.calcopy.engine import asr_local as A
r=A.transcribe({out['download']['file']!r})
print(json.dumps({{'phrases': len(r.get('segments') or []), 'text': ' '.join(str(s.get('text','')) for s in r.get('segments') or [])[:60], 'dur': r.get('dur')}}))   # -I 는 PYTHONIOENCODING 을 무시한다 — 글은  꼴로
""", timeout=1800)
    ok = (out["catalog"].get("fonts", 0) > 0 and out.get("render", {}).get("ink", 0) > 0.01
          and out["download"].get("bytes", 0) > 100000 and out.get("asr", {}).get("phrases", 0) > 0)
    out["ok"] = ok
    out["channel_left"] = ch.exists()
    print(json.dumps(out, ensure_ascii=False))
    return 0 if ok and not ch.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
