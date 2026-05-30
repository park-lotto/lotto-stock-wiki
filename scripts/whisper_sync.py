"""
Whisper 싱크 도구
사용법: python whisper_sync.py <audio_file> [--scene GB01|GB02|GB03]

출력:
  - raw/yt/audio/{scene}_timestamps.json  ← 문장별 타임스탬프
  - 콘솔에 프레임 매핑 출력 (fps=30 기준)
"""
import sys, json, os, argparse
sys.stdout.reconfigure(encoding='utf-8')

import whisper

FPS = 30

def sec_to_frame(sec: float) -> int:
    return round(sec * FPS)

def run(audio_path: str, scene: str = None):
    print(f"[Whisper] 분석 중: {audio_path}")
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, language="ko", word_timestamps=True)

    total_sec = result["segments"][-1]["end"] if result["segments"] else 0
    total_frames = sec_to_frame(total_sec)

    print(f"\n{'='*60}")
    print(f"총 길이: {total_sec:.2f}초 = {total_frames}프레임")
    print(f"{'='*60}\n")

    segments = []
    for i, seg in enumerate(result["segments"]):
        start_f = sec_to_frame(seg["start"])
        end_f   = sec_to_frame(seg["end"])
        print(f"[{i+1:02d}] f{start_f:04d}~f{end_f:04d} | {seg['start']:.2f}s~{seg['end']:.2f}s")
        print(f"       {seg['text'].strip()}")
        segments.append({
            "index": i + 1,
            "text": seg["text"].strip(),
            "start_sec": round(seg["start"], 3),
            "end_sec":   round(seg["end"], 3),
            "start_frame": start_f,
            "end_frame":   end_f,
        })

    out = {
        "audio_file": os.path.basename(audio_path),
        "scene": scene,
        "total_sec": round(total_sec, 3),
        "total_frames": total_frames,
        "fps": FPS,
        "segments": segments,
    }

    os.makedirs("raw/yt/audio", exist_ok=True)
    name = scene or os.path.splitext(os.path.basename(audio_path))[0]
    out_path = f"raw/yt/audio/{name}_timestamps.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"저장 완료: {out_path}")
    print(f"Root.tsx durationInFrames: {total_frames}")
    print(f"{'='*60}")

    return out

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", help="오디오 파일 경로")
    parser.add_argument("--scene", default=None, help="씬 이름 (예: GB01)")
    args = parser.parse_args()
    run(args.audio, args.scene)
