"""
카카오EP1 — 전체 씬 Whisper 배치 추출
출력: productions/kakao_ep1/_audio/{SCENE}_timestamps.json
검증: productions/kakao_ep1/_audio/VERIFY_REPORT.txt
"""
import sys, json, os, subprocess, time
sys.stdout.reconfigure(encoding='utf-8')

import whisper

BASE = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE, "_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

FPS = 30

SCENES = [
    ("S02", os.path.join(BASE, "S02_페인포인트", "s2 녹화본.mkv")),
    ("S03", os.path.join(BASE, "S03_철학",       "s3녹음.mp4")),
    ("S04", os.path.join(BASE, "S04_로드맵",     "s4 녹음.m4a")),
    ("S05", os.path.join(BASE, "S05_설치",       "s5 녹화+음성.mp4")),
    ("S06", os.path.join(BASE, "S06_MCP",        "s6녹음.mp4")),
    ("S07", os.path.join(BASE, "S07_연동",       "S7 녹화+음석.mp4")),
    ("S08", os.path.join(BASE, "S08_프롬프트",   "S8 녹화+음성.mp4")),
    ("S09", os.path.join(BASE, "S09_플러그인",   "s9 녹화+음성.mp4")),
    ("S10", os.path.join(BASE, "S10_스케줄",     "s10 녹화 음성.mp4")),
    ("S11", os.path.join(BASE, "S11_응용",       "s11 녹음 + 음성.mp4")),
]

def sec_to_frame(sec):
    return round(sec * FPS)

def extract_audio_wav(src, wav_path):
    """ffmpeg로 오디오만 추출 → WAV (Whisper 최적)"""
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-vn", "-ac", "1", "-ar", "16000",
        "-acodec", "pcm_s16le", wav_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패:\n{r.stderr[-500:]}")

def run_whisper(scene, src_path, model):
    wav_path = os.path.join(AUDIO_DIR, f"{scene}_temp.wav")
    out_json  = os.path.join(AUDIO_DIR, f"{scene}_timestamps.json")

    print(f"\n{'='*60}")
    print(f"[{scene}] 오디오 추출 중...")
    extract_audio_wav(src_path, wav_path)

    print(f"[{scene}] Whisper 분석 중...")
    t0 = time.time()
    result = model.transcribe(wav_path, language="ko", word_timestamps=False)
    elapsed = time.time() - t0

    segs = result["segments"]
    total_sec = segs[-1]["end"] if segs else 0
    total_frames = sec_to_frame(total_sec)

    segments_out = []
    for i, seg in enumerate(segs):
        sf = sec_to_frame(seg["start"])
        ef = sec_to_frame(seg["end"])
        segments_out.append({
            "index":       i + 1,
            "text":        seg["text"].strip(),
            "start_sec":   round(seg["start"], 3),
            "end_sec":     round(seg["end"], 3),
            "start_frame": sf,
            "end_frame":   ef,
        })

    out = {
        "scene":         scene,
        "source_file":   os.path.basename(src_path),
        "total_sec":     round(total_sec, 3),
        "total_frames":  total_frames,
        "fps":           FPS,
        "segments":      segments_out,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # temp WAV 삭제
    os.remove(wav_path)

    print(f"[{scene}] 완료 — {total_sec:.1f}초 / {total_frames}f / {len(segs)}세그 / {elapsed:.0f}s 소요")
    print(f"  → {out_json}")
    print(f"  첫 문장: {segments_out[0]['text'][:60] if segments_out else '(없음)'}")

    return {
        "scene":         scene,
        "total_sec":     round(total_sec, 3),
        "total_frames":  total_frames,
        "seg_count":     len(segs),
        "elapsed_s":     round(elapsed, 1),
        "first_text":    segments_out[0]["text"][:80] if segments_out else "",
        "last_text":     segments_out[-1]["text"][:80] if segments_out else "",
        "json_path":     out_json,
        "status":        "OK",
    }

def main():
    print("=" * 60)
    print("카카오EP1 Whisper 배치 — small 모델 (한국어)")
    print(f"대상 씬: {len(SCENES)}개")
    print("=" * 60)

    print("\n[모델 로딩] whisper small...")
    model = whisper.load_model("small")
    print("[모델 로딩] 완료\n")

    results = []
    failed  = []

    for scene, src in SCENES:
        if not os.path.exists(src):
            print(f"\n[{scene}] ⚠️  파일 없음: {src}")
            failed.append({"scene": scene, "error": f"파일 없음: {src}", "status": "SKIP"})
            continue
        try:
            r = run_whisper(scene, src, model)
            results.append(r)
        except Exception as e:
            print(f"\n[{scene}] ❌ 에러: {e}")
            failed.append({"scene": scene, "error": str(e), "status": "ERROR"})

    # 검증 리포트 작성
    report_path = os.path.join(AUDIO_DIR, "VERIFY_REPORT.txt")
    lines = []
    lines.append("카카오EP1 Whisper 배치 검증 리포트")
    lines.append("=" * 60)
    lines.append(f"완료: {len(results)}개 / 실패: {len(failed)}개")
    lines.append("")

    lines.append("[ 완료 씬 ]")
    for r in results:
        lines.append(f"  {r['scene']:5s} | {r['total_sec']:6.1f}초 | {r['total_frames']:5d}f | {r['seg_count']:3d}세그 | {r['elapsed_s']}s 소요")
        lines.append(f"         첫: {r['first_text']}")
        lines.append(f"         끝: {r['last_text']}")
        lines.append("")

    if failed:
        lines.append("[ 실패·스킵 ]")
        for f in failed:
            lines.append(f"  {f['scene']:5s} | {f['status']} | {f['error']}")

    report_txt = "\n".join(lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_txt)

    print("\n" + "=" * 60)
    print("전체 완료!")
    print(report_txt)
    print(f"\n검증 리포트: {report_path}")

if __name__ == "__main__":
    main()
