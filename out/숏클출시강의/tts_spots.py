"""필재 TTS 의심 발음 모음 — 지정 단어가 나오는 구간만 잘라 한 파일로 이어 붙인다(사장님 귀 확인용).

쓰기: py tts_spots.py <mp3·align 폴더> <출력.mp3> s00:숏클 s17:클로드가 ...
정렬: 서버가 조각(_sXX_NN.mp3.align.json)마다 글자 시각을 준다 → 앞 조각 길이를 더해 장면 안 시각으로 바꾼다.
"""
import glob, json, os, subprocess, sys

PAD = 0.9


def scene_chars(folder, scene):
    chars, off = [], 0.0
    for p in sorted(glob.glob(os.path.join(folder, "align", f"_{scene}_*.mp3.align.json"))):
        d = json.load(open(p, encoding="utf-8"))
        for c, s, e in zip(d["characters"], d["character_start_times_seconds"], d["character_end_times_seconds"]):
            chars.append((c, s + off, e + off))
        off += d["character_end_times_seconds"][-1]
    return chars


def find(chars, word):
    text = "".join(c for c, _, _ in chars)
    i = text.find(word)
    if i < 0:
        raise SystemExit(f"못 찾음: {word}")
    return chars[i][1], chars[i + len(word) - 1][2]


def main():
    folder, out, specs = sys.argv[1], sys.argv[2], sys.argv[3:]
    parts = []
    for k, spec in enumerate(specs):
        scene, word = spec.split(":", 1)
        s, e = find(scene_chars(folder, scene), word)
        clip = os.path.join(folder, f"_spot{k:02d}.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, s - PAD):.2f}", "-to", f"{e + PAD:.2f}",
                        "-i", os.path.join(folder, scene + ".mp3"), "-af", "apad=pad_dur=0.8", "-ar", "44100", "-ac", "1", clip], check=True)
        parts.append(clip)
        print(f"{k + 1}. {word} ({scene} {s:.1f}초)")
    lst = os.path.join(folder, "_spots.txt")
    open(lst, "w", encoding="utf-8").write("".join(f"file '{p.replace(os.sep, '/')}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:a", "libmp3lame", "-b:a", "160k", out], check=True)


main()
