"""무음 placeholder M4A 생성 — 녹음 전 Remotion 미리보기용"""
import sys, subprocess
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

VOICE_DIR = Path(__file__).parent.parent / "remotion-stock" / "public" / "voice"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

# 생성할 파일 목록 (파이프라인이 만든 씬들)
SCENES = [
    "yt_ai_s01_hook.m4a",
    "yt_ai_s02_empathy.m4a",
    "yt_ai_s03_declaration.m4a",
    "yt_ai_s04_demo.m4a",
    "yt_ai_s05_climax.m4a",
    "yt_ai_s06_awareness.m4a",
    "yt_ai_s07_tease.m4a",
    "yt_ai_s08_cta.m4a",
]

# ffmpeg으로 1초 무음 M4A 생성
ffmpeg_paths = [
    r"C:\Users\CH\Desktop\로또의 주식\remotion-stock\node_modules\@remotion\renderer\node_modules\ffmpeg-static\ffmpeg.exe",
    r"C:\Users\CH\Desktop\로또의 주식\remotion-stock\node_modules\ffmpeg-static\ffmpeg.exe",
    "ffmpeg",
]

ffmpeg = None
for p in ffmpeg_paths:
    if Path(p).exists() or p == "ffmpeg":
        ffmpeg = p
        break

created = 0
for fname in SCENES:
    fpath = VOICE_DIR / fname
    if fpath.exists() and fpath.stat().st_size > 1000:
        print(f"  이미 있음: {fname}")
        continue

    if ffmpeg:
        try:
            subprocess.run([
                ffmpeg, "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", "1",
                "-c:a", "aac",
                str(fpath)
            ], capture_output=True, timeout=10)
            if fpath.exists():
                print(f"  ✓ 생성: {fname}")
                created += 1
                continue
        except Exception:
            pass

    # ffmpeg 없으면 최소 유효 M4A 헤더로 생성
    fpath.write_bytes(
        bytes.fromhex("0000001c667479706d703432000000006d703432697369736f6d") +
        b"\x00" * 2048
    )
    print(f"  ✓ 더미 생성: {fname}")
    created += 1

print(f"\n완료: {created}개 생성 → {VOICE_DIR}")
