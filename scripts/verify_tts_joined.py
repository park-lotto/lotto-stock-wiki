"""서버 실측: 비트별 합성 vs 통짜 합성 — 이음매에서 실제로 목소리가 덜 튀는가.

측정: ①조각별 통합 라우드니스(EBU I) 편차 ②이음매 앞뒤 0.3초 RMS 점프
      ③이어붙인 결과물 mp3(귀로 확인용)
"""
import os, shutil, subprocess, sys, json
from pathlib import Path
sys.path.insert(0, "/tmp/sb")

BEATS = [
    {"beat_idx": 0, "role": "훅",       "narration": "주방에서 이거 하나만 바꿨는데요."},
    {"beat_idx": 1, "role": "페인포인트", "narration": "설거지가 매일 산더미처럼 쌓이잖아요."},
    {"beat_idx": 2, "role": "반전",      "narration": "그런데 이 비법 재료를 넣으면 달라져요."},
    {"beat_idx": 3, "role": "CTA",      "narration": "방법이 궁금하면 프로필 링크 확인해 보세요."},
]

def ebu_i(p):
    r = subprocess.run(["ffmpeg","-hide_banner","-nostats","-i",str(p),
                        "-af","ebur128=framelog=quiet","-f","null","-"],
                       capture_output=True, text=True)
    val = None
    for line in r.stderr.splitlines():
        if "I:" in line and "LUFS" in line:
            val = float(line.split("I:")[1].split("LUFS")[0].strip())
    return val

def rms_window(p, start, dur):
    r = subprocess.run(["ffmpeg","-hide_banner","-nostats","-ss",str(start),"-t",str(dur),
                        "-i",str(p),"-af","volumedetect","-f","null","-"],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0].strip())
    return None

def dur(p):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                        "-of","default=nw=1:nk=1",str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())

def run(mode, joined):
    os.environ["TTS_JOINED"] = "1" if joined else "0"
    import importlib
    from shopping_shorts import mix_pipeline, tts_joined
    importlib.reload(tts_joined)
    d = Path(f"/tmp/joined_verify/{mode}")
    shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    beats = json.loads(json.dumps(BEATS))
    mix_pipeline._synthesize_beats(beats, d, voice=None)
    paths = [b["tts_path"] for b in beats]
    ds = [dur(p) for p in paths]
    lufs = [ebu_i(p) for p in paths]
    # 이어붙이기
    lst = d/"list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in paths))
    cat = d/f"{mode}_이어붙임.mp3"
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0",
                    "-i",str(lst),"-c:a","libmp3lame","-q:a","2",str(cat)], check=True)
    # 이음매 앞뒤 0.3초 RMS 점프
    jumps, t = [], 0.0
    for i in range(len(ds)-1):
        t += ds[i]
        a = rms_window(cat, max(0,t-0.3), 0.3)
        b = rms_window(cat, t, 0.3)
        if a is not None and b is not None:
            jumps.append(round(abs(a-b),2))
    print(f"\n=== {mode} ===")
    print("조각 길이:", [round(x,2) for x in ds])
    print("조각 LUFS:", lufs, "→ 편차 %.2f dB" % (max(lufs)-min(lufs)) if all(l is not None for l in lufs) else "측정실패")
    print("이음매 RMS 점프(dB):", jumps, "→ 평균 %.2f" % (sum(jumps)/len(jumps)) if jumps else "")
    print("결과물:", cat)
    return cat

if __name__ == "__main__":
    a = run("비트별", False)
    b = run("통짜", True)
    print("\n두 파일을 들어보세요:", a, b)
