# -*- coding: utf-8 -*-
"""얜샷템 나레 TTS = 일레븐랩스 미나 — 서버(숏템 서비스)에서 서비스 코드 그대로 합성해 파일만 받아 온다 (관제 097, 2026-10-17).

    PYTHONUTF8=1 py tools/calcopy/mina_tts.py "<대사>" <out.mp3> [--tone expressive|stable|natural|whisper]

왜 서버에서: 로컬 .env 의 ELEVENLABS_API_KEY 는 '키 ID'라 400(api_key_id_used_as_api_key) — 서비스는 서버 환경
(/etc/shopping-shorts.env)으로 잘 돈다(10-17 실측: 서버에서 shopping_shorts.tts.synthesize_tts → 4.88초 진짜 음성, 받아쓰기 일치).
키를 PC로 옮기지 않는다 — 서버에서 합성하고 mp3 만 가져온다.
성우 값의 주인 = shopping_shorts/assets/voice_presets.json(kr-mina-<tone>). 속도는 1.0 통째 합성 뒤 atempo 로(서비스 규칙, 미나 1.35) — 이 도구는 1.0 원음만 준다.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = "C:/Users/CH/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
HOST = "ubuntu@3.35.251.172"
REPO = "/home/ubuntu/lotto-stock-wiki"

REMOTE = r'''
import json, sys
from shopping_shorts import tts
a = json.loads(sys.stdin.read())
tts.synthesize_tts(a["text"], a["out"], voice_id=a["voice_id"], voice_settings=a["settings"], model_id=a["model_id"])
print("OK", a["out"])
'''


def preset(tone: str) -> dict:
    d = json.loads((ROOT / "shopping_shorts/assets/voice_presets.json").read_text(encoding="utf-8"))
    rows = d if isinstance(d, list) else next(iter(d.values()))
    p = next(x for x in rows if x.get("preset_id") == f"kr-mina-{tone}")
    return {"voice_id": p["base_voice_id"], "model_id": p["model_id"], "settings": p["voice_settings"]}


def synth(text: str, out: str, tone: str = "expressive") -> str:
    p = preset(tone)
    remote_out = f"/tmp/calcopy_mina_{abs(hash((text, tone))) % 10**10}.mp3"
    arg = json.dumps({"text": text, "out": remote_out, **p}, ensure_ascii=False)
    cmd = (f"cd {REPO} && set -a && . <(sudo cat /etc/shopping-shorts.env) && set +a && "
           f"timeout 180 python3 -c {shlex.quote(REMOTE)}")
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=20", "-i", KEY, HOST, cmd], input=arg,
                       capture_output=True, text=True, encoding="utf-8")
    if "OK" not in r.stdout:
        raise RuntimeError(f"서버 미나 합성 실패: {r.stdout[-400:]} {r.stderr[-400:]}")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["scp", "-q", "-i", KEY, f"{HOST}:{remote_out}", out], check=True)
    subprocess.run(["ssh", "-i", KEY, HOST, f"rm -f {remote_out}"], capture_output=True)
    if Path(out).stat().st_size < 5000:
        raise RuntimeError(f"받은 파일이 너무 작다(무음 mock 의심): {out}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("out")
    ap.add_argument("--tone", default="expressive", choices=["expressive", "stable", "natural", "whisper"])
    a = ap.parse_args()
    print(synth(a.text, a.out, a.tone))
    return 0


if __name__ == "__main__":
    sys.exit(main())
