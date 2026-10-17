# -*- coding: utf-8 -*-
"""(MuskLab 등) 편 소리 구성 선별 — 뒤에 id 를 주면 그 편만.
MuskLab 상위 편 소리 구성 선별 — 뜯기와 같은 받아쓰기 지시문(analyze.ASR_PROMPT)·무료 키(gemini_free.ask)로
오디오만 받아써서 '한국어 나레 + 원음(외국어 말·source 말·현장음)'인 편(현장썰)을 고른다.

    PYTHONUTF8=1 py channel/스타일분석/현장썰/재는법/screen_musklab.py C:/숏템_칼카피/musklab
결과: <base>/screen/<id>.json + 표 출력. 판정: ko narration 구절 ≥1 이고 (비한국어 구절 ≥1 또는 kind=source 구절 ≥1) → 현장썰,
ko narration 만 → 나레썰. 현장음(ambient)만 있는 편은 '현장음만'으로 따로 적는다(귀 확인 필요).
"""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.environ["BRAINBULB_VERTEX"] = "0"
from tools.calcopy.engine import gemini_free
from tools.calcopy.engine.analyze import ASR_PROMPT

MODEL = "gemini-2.5-flash"   # 뜯기 고정 모델(3.5-flash)·대체(lite-latest)가 2026-10-17(태평양) 42키 전부 한도 — 무료 2.5-flash 로. 답에 _model 남김
base = Path(sys.argv[1]); out = base / "screen"; out.mkdir(exist_ok=True)
only = set(sys.argv[2:])
for mp4 in sorted((base / "mp4").glob("*.mp4")):
    if only and mp4.stem not in only:
        continue
    f = out / f"{mp4.stem}.json"
    if not f.exists():
        mp3 = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", "-f", "mp3", "-"], capture_output=True).stdout
        d, err = gemini_free.ask([(mp3, "audio/mp3")], ASR_PROMPT, "screen", models=(MODEL,))
        f.write_text(json.dumps({"err": err, "d": d}, ensure_ascii=False), encoding="utf-8")
    r = json.loads(f.read_text(encoding="utf-8"))
    seg = ((r.get("d") or {}).get("segments") or [])
    ko_n = [s for s in seg if s.get("lang") == "ko" and s.get("kind") == "narration"]
    src = [s for s in seg if s.get("lang") != "ko" or s.get("kind") == "source"]
    amb = (r.get("d") or {}).get("ambient") or ""
    style = "현장썰" if ko_n and src else ("현장음만(귀확인)" if ko_n and amb else ("나레썰" if ko_n else "기타"))
    print(mp4.stem, style, len(ko_n), len(src), amb[:30], "|", " / ".join(f"{s.get('lang')}:{s.get('kind')}:{s.get('text','')[:25]}" for s in src[:4]), r.get("err") or "", flush=True)
