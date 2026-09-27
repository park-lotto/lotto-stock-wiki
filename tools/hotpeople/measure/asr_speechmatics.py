# -*- coding: utf-8 -*-
r"""스피치매틱스 배치 전사 — 나레/말 유무·단어 시각·발화 속도. (사장님 2026-09-28: 위스퍼 말고 스피치매틱스)
키: ~/.volcano/keys/speechmatics (볼케이노 실행기와 같은 자리, 값만 한 줄) 또는 환경변수 SPEECHMATICS_KEY.
표본 폴더에서: <프로젝트>\.venv\Scripts\python.exe ..\measure\asr_speechmatics.py [파일…] → asr/<id>.json + 콘솔
결과: words(단어·시작·끝), text, 말한 시간(단어 구간 합), 글자/초(공백 제외 글자 ÷ 말한 시간), 첫 발화 시각.
"""
import os, sys, json, glob, subprocess, pathlib

KEY = os.environ.get("SPEECHMATICS_KEY") or pathlib.Path.home().joinpath(".volcano", "keys", "speechmatics").read_text(encoding="utf-8").strip()
from speechmatics.models import ConnectionSettings
from speechmatics.batch_client import BatchClient

os.makedirs("asr", exist_ok=True)
files = sys.argv[1:] or sorted(glob.glob("*.mp4"))
settings = ConnectionSettings(url="https://asr.api.speechmatics.com/v2", auth_token=KEY)
conf = {"type": "transcription", "transcription_config": {"language": "ko", "operating_point": "enhanced", "diarization": "none"}}
with BatchClient(settings) as client:
    for f in files:
        vid = os.path.basename(f)[:11]
        outp = f"asr/{vid}.json"
        if os.path.exists(outp):
            r = json.load(open(outp, encoding="utf-8"))
        else:
            wav = f"asr/{vid}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-ac", "1", "-ar", "16000", wav], check=True)
            job = client.submit_job(audio=wav, transcription_config=conf)
            r = client.wait_for_completion(job, transcription_format="json-v2")
            json.dump(r, open(outp, "w", encoding="utf-8"), ensure_ascii=False)
            os.remove(wav)
        words = [(x["alternatives"][0]["content"], x["start_time"], x["end_time"]) for x in r.get("results", []) if x.get("type") == "word"]
        spoken = sum(e - s for _, s, e in words)
        chars = sum(len(w) for w, _, _ in words)
        text = " ".join(w for w, _, _ in words)
        print(f"{vid} 단어 {len(words)} 말한시간 {spoken:.1f}s 글자/초 {chars / spoken if spoken else 0:.1f} 첫발화 {words[0][1] if words else None}s | {text[:80]}")
