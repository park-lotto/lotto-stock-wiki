"""
sync_voiceover.py — 씬별 녹음 파일 → 대본 수정 + Remotion 프레임 계산

씬별 분리 녹음 처리:
    python scripts/sync_voiceover.py --scene          # 전체 씬 일괄 처리
    python scripts/sync_voiceover.py --scene s01      # 특정 씬만
    python scripts/sync_voiceover.py --merge          # 전체 합쳐서 총 길이 확인

파일 위치: out/voice/s01_훅.m4a, s02_공감.m4a, ...
결과: out/sync_result.md
"""

import sys, argparse, json, re
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
BASE  = Path(__file__).parent.parent
VOICE = BASE / "out" / "voice"
FPS   = 30

# ── 씬 목록 (파일명 접두사 기준) ─────────────────────────────────
SCENES = [
    {"id": "s01", "name": "씬1 훅",        "file": "s01_훅"},
    {"id": "s02", "name": "씬2 공감",      "file": "s02_공감"},
    {"id": "s03", "name": "씬3 선언",      "file": "s03_선언"},
    {"id": "s04a","name": "씬4-0 총괄",    "file": "s04_총괄"},
    {"id": "s04b","name": "씬4-1 수집",    "file": "s04_수집"},
    {"id": "s04c","name": "씬4-2 수급",    "file": "s04_수급"},
    {"id": "s04d","name": "씬4-3 탑픽",    "file": "s04_탑픽"},
    {"id": "s04e","name": "씬4-4 브리핑",  "file": "s04_브리핑"},
    {"id": "s04f","name": "씬4-5 배포",    "file": "s04_배포"},
    {"id": "s04g","name": "씬4-6 나머지",  "file": "s04_나머지"},
    {"id": "s05", "name": "씬5 클라이맥스","file": "s05_클라이맥스"},
    {"id": "s06", "name": "씬6 자각",      "file": "s06_자각"},
    {"id": "s07", "name": "씬7 여운",      "file": "s07_여운"},
    {"id": "s08", "name": "씬8 CTA",       "file": "s08_cta"},
]

EXTS = [".m4a", ".mp3", ".wav", ".aac", ".ogg"]


def find_audio(file_stem: str) -> Path | None:
    for ext in EXTS:
        p = VOICE / f"{file_stem}{ext}"
        if p.exists():
            return p
    return None


def get_duration(audio_path: Path) -> float:
    """오디오 길이(초) — ffprobe 또는 mutagen"""
    try:
        import subprocess
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(audio_path)],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(r.stdout)
        return float(data["format"]["duration"])
    except Exception:
        pass
    try:
        from mutagen import File as MFile
        f = MFile(str(audio_path))
        return f.info.length
    except Exception:
        pass
    # fallback: whisper로 길이 확인
    try:
        import whisper
        audio = whisper.load_audio(str(audio_path))
        return len(audio) / 16000
    except Exception:
        return 0.0


def transcribe_scene(audio_path: Path, model_name: str = "base") -> str:
    import whisper
    model = whisper.load_model(model_name)
    result = model.transcribe(str(audio_path), language="ko", verbose=False)
    return result.get("text", "").strip()


def process_all(model_name: str, scene_filter: str | None = None) -> list:
    results = []
    for sc in SCENES:
        if scene_filter and not sc["id"].startswith(scene_filter):
            continue
        audio = find_audio(sc["file"])
        if audio is None:
            results.append({**sc, "status": "없음", "sec": 0, "frames": 0, "text": ""})
            continue
        print(f"[처리] {sc['name']} ({audio.name})")
        sec    = get_duration(audio)
        frames = round(sec * FPS)
        print(f"       길이: {sec:.1f}초 = {frames}프레임")
        # 전사 (선택)
        text = ""
        try:
            text = transcribe_scene(audio, model_name)
            print(f"       대사: {text[:60]}...")
        except Exception as e:
            print(f"       전사 실패: {e}")
        results.append({
            **sc,
            "status": "완료",
            "file_path": str(audio),
            "sec": round(sec, 2),
            "frames": frames,
            "text": text,
        })
    return results


def write_report(results: list) -> str:
    total_sec    = sum(r.get("sec", 0) for r in results)
    total_frames = sum(r.get("frames", 0) for r in results)
    date_str     = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# 씬별 녹음 싱크 결과",
        "",
        f"> 처리일: {date_str}",
        f"> 총 길이: {total_sec:.1f}초 ({total_sec/60:.1f}분) / {total_frames}프레임",
        "",
        "---",
        "",
        "## 1. 씬별 길이 + Remotion 프레임",
        "",
        "| 씬 | 파일 | 길이 | 프레임 | 상태 |",
        "|----|------|------|--------|------|",
    ]

    for r in results:
        fname = Path(r.get("file_path", "")).name if r.get("file_path") else "—"
        sec   = f"{r['sec']:.1f}s" if r["sec"] else "—"
        fr    = str(r["frames"]) if r["frames"] else "—"
        st    = "✅" if r["status"] == "완료" else "⬜ 없음"
        lines.append(f"| {r['name']} | {fname} | {sec} | {fr} | {st} |")

    lines += [
        "",
        "---",
        "",
        "## 2. Root.tsx 반영 (durationInFrames)",
        "",
        "```tsx",
        "// 아래 값을 Root.tsx 각 Composition에 적용",
    ]
    for r in results:
        if r["frames"]:
            lines.append(f'// {r["name"]}: durationInFrames={{{r["frames"]}}}')
    lines.append("```")

    lines += [
        "",
        "---",
        "",
        "## 3. 실제 녹음 대사 (씬별)",
        "",
    ]
    for r in results:
        lines.append(f"### {r['name']}")
        lines.append("")
        if r["text"]:
            lines.append("```")
            lines.append(r["text"])
            lines.append("```")
        else:
            lines.append("_(녹음 파일 없음 또는 전사 실패)_")
        lines.append("")

    lines += [
        "---",
        "",
        "## 4. 대본 수정 사항",
        "",
        "원본 대본과 실제 녹음 대사 비교 후 수정:",
        "",
    ]
    for r in results:
        if r["text"]:
            lines.append(f"**{r['name']}**: _(수정 없음 / 아래에 변경 내용 기입)_")
            lines.append("")

    out = BASE / "out" / "sync_result.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene",  nargs="?", const="all", help="씬 처리 (s01/s02... 또는 all)")
    ap.add_argument("--model",  default="base", help="Whisper 모델 (base/small/medium)")
    ap.add_argument("--merge",  action="store_true", help="전체 길이 합산만")
    args = ap.parse_args()

    if args.merge:
        print("전체 씬 길이 합산:")
        total = 0
        for sc in SCENES:
            audio = find_audio(sc["file"])
            if audio:
                d = get_duration(audio)
                total += d
                print(f"  {sc['name']:18s} {d:.1f}s")
            else:
                print(f"  {sc['name']:18s} (없음)")
        print(f"\n총 {total:.1f}초 ({total/60:.1f}분)")
        return

    scene_filter = None if args.scene == "all" else args.scene
    results = process_all(args.model, scene_filter)
    out = write_report(results)

    print(f"\n결과 저장: {out}")

    import subprocess
    subprocess.Popen(["code", out], shell=True)


if __name__ == "__main__":
    main()
